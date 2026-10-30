// Darstellung des Verkehrs: je Auto-Typ zwei InstancedMeshes (nah/fern), weiche Bodenschatten
// und nachts Lichtkegel der Scheinwerfer auf der Straße (je 1 Draw Call für alle Autos).

import * as THREE from 'three';
import { makeProxyMaterial, makeProxyMesh } from './proxies.js';

const BLOB_FRAG = /* glsl */`
varying vec2 vUv;
uniform float uDark;
void main() {
  vec2 d = (vUv - 0.5) * 2.0;
  float r = length(d * vec2(1.0, 1.0));
  float a = (1.0 - smoothstep(0.55, 1.0, r)) * uDark;
  gl_FragColor = vec4(0.0, 0.0, 0.0, a);
}`;
const POOL_FRAG = /* glsl */`
varying vec2 vUv;
uniform float uStrength;
void main() {
  vec2 d = vec2((vUv.x - 0.5) * 2.0, 1.0 - vUv.y);      // y: 0 = am Auto, 1 = vorne
  float a = (1.0 - smoothstep(0.2, 1.0, abs(d.x))) * smoothstep(0.0, 0.25, d.y) * (1.0 - smoothstep(0.55, 1.0, d.y));
  gl_FragColor = vec4(vec3(1.0, 0.92, 0.78) * a * uStrength, 1.0);
}`;
const QUAD_VERT = /* glsl */`
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
}`;

export class TrafficView {
  constructor(scene, geos, capacity = 40) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'Traffic';
    scene.add(this.group);
    this.mat = makeProxyMaterial();
    this.meshes = {};
    for (const [id, lods] of Object.entries(geos)) {
      this.meshes[id] = lods.map((g) => {
        const im = makeProxyMesh(g, this.mat, capacity);
        this.group.add(im);
        return im;
      });
    }
    const plane = new THREE.PlaneGeometry(1, 1);
    plane.rotateX(-Math.PI / 2);
    this.blobMat = new THREE.ShaderMaterial({ vertexShader: QUAD_VERT, fragmentShader: BLOB_FRAG, transparent: true, depthWrite: false,
      polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3, uniforms: { uDark: { value: 0.55 } } });
    this.blobs = new THREE.InstancedMesh(plane, this.blobMat, capacity);
    this.blobs.frustumCulled = false;
    this.blobs.count = 0;
    this.group.add(this.blobs);
    const plane2 = new THREE.PlaneGeometry(1, 1);
    plane2.rotateX(-Math.PI / 2);
    this.poolMat = new THREE.ShaderMaterial({ vertexShader: QUAD_VERT, fragmentShader: POOL_FRAG, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
      uniforms: { uStrength: { value: 0 } } });
    this.pools = new THREE.InstancedMesh(plane2, this.poolMat, capacity);
    this.pools.frustumCulled = false;
    this.pools.count = 0;
    this.group.add(this.pools);
    this.capacity = capacity;
    this._m = new THREE.Matrix4();
    this._q = new THREE.Quaternion();
    this._p = new THREE.Vector3();
    this._s = new THREE.Vector3(1, 1, 1);
    this._Y = new THREE.Vector3(0, 1, 0);
  }

  dispose() {
    this.scene.remove(this.group);
    for (const lods of Object.values(this.meshes)) for (const im of lods) im.geometry.dispose();
    this.mat.dispose(); this.blobMat.dispose(); this.poolMat.dispose();
  }

  update(traffic, camera, night, groundHeight, time) {
    for (const lods of Object.values(this.meshes)) for (const im of lods) im.count = 0;
    let nb = 0, np = 0;
    const cx = camera.position.x, cz = camera.position.z;
    const m = this._m, q = this._q, p = this._p, s = this._s;
    this.mat.userData.uniforms.uNight.value = night;
    this.poolMat.uniforms.uStrength.value = Math.max(0, (night - 0.35) / 0.65) * 0.7;
    for (const c of traffic.cars) {
      const lods = this.meshes[c.id];
      if (!lods) continue;
      const d = Math.hypot(c.x - cx, c.z - cz);
      const im = lods[d < 45 ? 0 : 1];
      if (im.count >= this.capacity) continue;
      const i = im.count++;
      const gy = groundHeight(c.x, c.z);
      p.set(c.x, gy, c.z);
      q.setFromAxisAngle(this._Y, c.yaw);
      s.set(1, 1, 1);
      m.compose(p, q, s);
      im.setMatrixAt(i, m);
      const pa = im.geometry.attributes.aPaint, st = im.geometry.attributes.aState;
      pa.setXYZ(i, c.paint[0], c.paint[1], c.paint[2]);
      const L = traffic.lights(c, time);
      st.setXYZ(i, L[0], L[1], L[2]);
      if (d < 120 && nb < this.capacity) {
        p.set(c.x + Math.sin(c.yaw) * ((c.front - c.back) / 2), gy + 0.015, c.z + Math.cos(c.yaw) * ((c.front - c.back) / 2));
        s.set(c.halfW * 2.3, 1, (c.front + c.back) * 1.08);
        m.compose(p, q, s);
        this.blobs.setMatrixAt(nb++, m);
      }
      if (night > 0.35 && c.state === 'drive' && d < 160 && np < this.capacity) {
        p.set(c.x + Math.sin(c.yaw) * (c.front + 5.5), gy + 0.02, c.z + Math.cos(c.yaw) * (c.front + 5.5));
        s.set(4.2, 1, 11);
        m.compose(p, q, s);
        this.pools.setMatrixAt(np++, m);
      }
    }
    for (const lods of Object.values(this.meshes)) {
      for (const im of lods) {
        if (!im.count) continue;
        im.instanceMatrix.needsUpdate = true;
        im.geometry.attributes.aPaint.needsUpdate = true;
        im.geometry.attributes.aState.needsUpdate = true;
      }
    }
    this.blobs.count = nb;
    this.blobs.instanceMatrix.needsUpdate = true;
    this.pools.count = np;
    this.pools.instanceMatrix.needsUpdate = true;
  }
}
