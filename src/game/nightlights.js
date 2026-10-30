// Nachtbeleuchtung der Straßen.
//
//  * Lichtkegel auf dem Boden unter ALLEN Laternen: ein InstancedMesh aus weichen, additiven Flecken
//    (1 Draw Call) – so leuchten die Straßen bis zum Horizont, ohne echte Lichtquellen.
//  * Echte Lichter (SpotLights) nur an den nächsten Laternen um das Auto: beleuchten Autos, Wände,
//    Pylonen. Die Anzahl ist fest je Qualitätsstufe (sonst müsste three.js Shader neu übersetzen).
//  * Bei Nässe werden die Flecken heller und länglich (Spiegelung auf nasser Fahrbahn).

import * as THREE from 'three';

const GLOW_VERT = /* glsl */`
varying vec2 vUv;
varying float vFade;
void main() {
  vUv = uv;
  vec4 mv = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
  vFade = 1.0 - smoothstep(220.0, 520.0, -mv.z);      // weit weg im Dunst ausblenden
  gl_Position = projectionMatrix * mv;
}`;
const GLOW_FRAG = /* glsl */`
uniform vec3 uColor;
uniform float uStrength;
varying vec2 vUv;
varying float vFade;
void main() {
  vec2 d = vUv - 0.5;
  float r = length(d) * 2.0;
  float a = pow(max(0.0, 1.0 - r), 2.2);
  gl_FragColor = vec4(uColor * a * uStrength * vFade, 1.0);
}`;

export class StreetLights {
  constructor(scene, heads, groundHeight, count = 6) {
    this.scene = scene;
    this.heads = heads || [];
    this.group = new THREE.Group();
    this.group.name = 'StreetLights';
    scene.add(this.group);
    this.lights = [];
    for (let i = 0; i < count; i++) {
      const l = new THREE.SpotLight(0xffd2a0, 0, 30, 1.0, 0.7, 1.6);
      l.castShadow = false;
      l.visible = true;                      // Anzahl der Lichter bleibt immer gleich (keine Shader-Neuübersetzung)
      this.group.add(l);
      this.group.add(l.target);
      this.lights.push({ l, head: -1 });
    }
    this.night = 0;
    this.wet = 0;
    this._t = 0;
    this.glow = null;
    if (this.heads.length) {
      const geo = new THREE.PlaneGeometry(1, 1);
      geo.rotateX(-Math.PI / 2);
      this.glowMat = new THREE.ShaderMaterial({
        vertexShader: GLOW_VERT, fragmentShader: GLOW_FRAG, transparent: true, depthWrite: false,
        blending: THREE.AdditiveBlending, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
        uniforms: { uColor: { value: new THREE.Color(1.0, 0.68, 0.38) }, uStrength: { value: 0 } },
      });
      const im = new THREE.InstancedMesh(geo, this.glowMat, this.heads.length);
      im.frustumCulled = false;
      im.renderOrder = 1;
      const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3(13, 1, 13);
      this.heads.forEach((h, i) => {
        p.set(h.x, groundHeight(h.x, h.z) + 0.03, h.z);
        m.compose(p, q, s);
        im.setMatrixAt(i, m);
      });
      im.instanceMatrix.needsUpdate = true;
      im.visible = false;
      this.glow = im;
      this.group.add(im);
    }
  }

  dispose() {
    this.scene.remove(this.group);
    if (this.glow) { this.glow.geometry.dispose(); this.glowMat.dispose(); }
  }

  update(dt, pos, fwd, night, wet) {
    this.night = night;
    const on = night > 0.3;
    if (this.glow) {
      this.glow.visible = on;
      this.glowMat.uniforms.uStrength.value = Math.max(0, (night - 0.3) / 0.7) * (0.45 + 0.55 * wet);
    }
    const k = Math.max(0, (night - 0.3) / 0.7);
    // alle 0,25 s die nächsten Laternen (etwas voraus) neu zuordnen
    this._t -= dt;
    if (this._t <= 0 && this.heads.length && this.lights.length) {
      this._t = 0.25;
      const ax = pos.x + fwd.x * 12, az = pos.z + fwd.z * 12;
      const best = [];
      for (let i = 0; i < this.heads.length; i++) {
        const h = this.heads[i];
        const d = (h.x - ax) * (h.x - ax) + (h.z - az) * (h.z - az);
        if (d > 70 * 70) continue;
        best.push([d, i]);
      }
      best.sort((a, b) => a[0] - b[0]);
      const want = best.slice(0, this.lights.length).map((b) => b[1]);
      // bestehende Zuordnungen behalten (kein Flackern), freie Lichter neu vergeben
      const keep = new Set();
      for (const L of this.lights) if (want.includes(L.head)) keep.add(L.head); else L.head = -1;
      const free = want.filter((h) => !keep.has(h));
      for (const L of this.lights) {
        if (L.head >= 0 || !free.length) continue;
        L.head = free.shift();
        const h = this.heads[L.head];
        L.l.position.set(h.x, h.y - 0.15, h.z);
        L.l.target.position.set(h.x, h.y - 9, h.z);
        L.l.target.updateMatrixWorld();
      }
    }
    for (const L of this.lights) L.l.intensity = L.head >= 0 ? 55 * k : 0;
  }
}
