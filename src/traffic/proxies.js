// Verkehrs-Autos als InstancedMesh: vereinfachte Modelle aus models/traffic.bin (tools/car-generator/traffic_proxies.py).
//
// Je Auto-Typ zwei Stufen (nah/fern), je Stufe ein InstancedMesh – alle teilen ein Material, das im Shader
// je Instanz Lackfarbe, Bremslicht und Blinker setzt und nachts Front- und Rücklichter leuchten lässt.

import * as THREE from 'three';

export async function loadProxyData(baseUrl) {
  const base = baseUrl.endsWith('/') ? baseUrl : baseUrl + '/';
  const [idx, bin] = await Promise.all([
    fetch(base + 'traffic.json', { cache: 'no-cache' }).then((r) => { if (!r.ok) throw new Error('traffic.json fehlt'); return r.json(); }),
    fetch(base + 'traffic.bin', { cache: 'no-cache' }).then((r) => { if (!r.ok) throw new Error('traffic.bin fehlt'); return r.arrayBuffer(); }),
  ]);
  const geos = {};
  for (const car of idx.cars) {
    geos[car.id] = car.lods.map((l) => {
      const g = new THREE.BufferGeometry();
      const n = l.vertices;
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(bin, l.position, n * 3), 3));
      const nq = new Int8Array(bin, l.normal, n * 3);
      g.setAttribute('normal', new THREE.BufferAttribute(nq, 3, true));
      // Farben liegen als sRGB vor, three.js rechnet Punktfarben linear
      const cs = new Uint8Array(bin, l.color, n * 3);
      const cl = new Float32Array(n * 3);
      for (let i = 0; i < n * 3; i++) cl[i] = Math.pow(cs[i] / 255, 2.2);
      g.setAttribute('color', new THREE.BufferAttribute(cl, 3));
      const fl = new Uint8Array(bin, l.flags, n);
      g.setAttribute('aFlags', new THREE.BufferAttribute(new Float32Array(fl), 1));
      const idxArr = l.index32 ? new Uint32Array(bin, l.index, l.triangles * 3) : new Uint16Array(bin, l.index, l.triangles * 3);
      g.setIndex(new THREE.BufferAttribute(idxArr, 1));
      g.computeBoundingSphere();
      return g;
    });
  }
  return geos;
}

/** Gemeinsames Material: Lack je Instanz, Licht-Merkmale, Nacht. */
export function makeProxyMaterial() {
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.6, metalness: 0.1 });
  const uniforms = { uNight: { value: 0 } };
  mat.userData.uniforms = uniforms;
  mat.onBeforeCompile = (sh) => {
    sh.uniforms.uNight = uniforms.uNight;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', `#include <common>
attribute float aFlags;
attribute vec3 aPaint;
attribute vec3 aState;
varying float vFlags;
varying vec3 vPaint;
varying vec3 vState;
varying float vSide;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>
vFlags = aFlags; vPaint = aPaint; vState = aState; vSide = position.x;`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>
uniform float uNight;
varying float vFlags;
varying vec3 vPaint;
varying vec3 vState;
varying float vSide;`)
      .replace('#include <color_fragment>', `#include <color_fragment>
int pfl = int(vFlags + 0.5);
if ((pfl & 1) != 0) diffuseColor.rgb = vPaint;`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
roughnessFactor = (pfl & 8) != 0 ? 0.06 : (pfl & 1) != 0 ? 0.3 : (pfl & 16) != 0 ? 0.25 : 0.7;`)
      .replace('#include <metalnessmap_fragment>', `#include <metalnessmap_fragment>
metalnessFactor = (pfl & 16) != 0 ? 0.95 : (pfl & 1) != 0 ? 0.4 : 0.05;`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
int plt = (pfl >> 1) & 3;
if (plt == 1) totalEmissiveRadiance += vec3(1.0, 0.95, 0.86) * (0.25 + uNight * 3.0);
else if (plt == 2) totalEmissiveRadiance += vec3(1.0, 0.04, 0.02) * (0.15 + uNight * 1.3 + vState.x * 4.5);
else if (plt == 3) totalEmissiveRadiance += vec3(1.0, 0.42, 0.0) * 4.5 * (vSide > 0.0 ? vState.y : vState.z);`);
  };
  return mat;
}

/** InstancedMesh für einen Auto-Typ und eine Stufe, mit Instanz-Attributen für Lack und Zustand. */
export function makeProxyMesh(geo, mat, capacity) {
  const g = geo.clone();
  g.setAttribute('aPaint', new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3), 3));
  g.setAttribute('aState', new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3), 3));
  const im = new THREE.InstancedMesh(g, mat, capacity);
  im.count = 0;
  im.frustumCulled = false;
  im.castShadow = false;
  im.receiveShadow = true;
  im.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  return im;
}
