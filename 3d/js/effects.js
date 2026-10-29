// Effekte: Leuchtpunkte (Lichthöfe), Rauch, Funken und Fahrtwind
import * as THREE from 'three';
import { rand, smoothstep } from './config.js';

const POINT_VERT = /* glsl */ `
attribute vec4 pColor;
attribute float pSize;
uniform float uScale;
uniform float uFog;
varying vec4 vColor;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float dist = -mv.z;
  gl_PointSize = clamp(pSize * uScale / max(dist, 0.5), 0.0, 400.0);
  float f = 1.0 - exp(-uFog * uFog * dist * dist);
  vColor = vec4(pColor.rgb, pColor.a * (1.0 - f));
  gl_Position = projectionMatrix * mv;
}`;

// Lichthof: heller Kern, weicher Rand
const GLOW_FRAG = /* glsl */ `
varying vec4 vColor;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  float a = exp(-d * d * 4.5) * (1.0 - d) + exp(-d * d * 60.0) * 1.2;
  gl_FragColor = vec4(vColor.rgb * vColor.a * a, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

const SMOKE_FRAG = /* glsl */ `
uniform sampler2D uMap;
varying vec4 vColor;
void main() {
  float a = texture2D(uMap, gl_PointCoord).a;
  gl_FragColor = vec4(vColor.rgb, vColor.a * a);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

const SPARK_FRAG = /* glsl */ `
varying vec4 vColor;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  if (d > 1.0) discard;
  gl_FragColor = vec4(vColor.rgb * vColor.a * (1.0 - d * d), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

class PointBuffer {
  constructor(scene, max, fragmentShader, opts) {
    this.max = max;
    this.pos = new Float32Array(max * 3);
    this.col = new Float32Array(max * 4);
    this.size = new Float32Array(max);
    const g = new THREE.BufferGeometry();
    this.attrs = [
      new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage),
      new THREE.BufferAttribute(this.col, 4).setUsage(THREE.DynamicDrawUsage),
      new THREE.BufferAttribute(this.size, 1).setUsage(THREE.DynamicDrawUsage),
    ];
    g.setAttribute('position', this.attrs[0]);
    g.setAttribute('pColor', this.attrs[1]);
    g.setAttribute('pSize', this.attrs[2]);
    this.uniforms = { uScale: { value: 800 }, uFog: { value: 0.0026 }, ...(opts.uniforms || {}) };
    this.material = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: POINT_VERT,
      fragmentShader,
      transparent: true,
      depthWrite: false,
      blending: opts.blending,
    });
    this.points = new THREE.Points(g, this.material);
    this.points.frustumCulled = false;
    this.points.renderOrder = opts.renderOrder || 5;
    scene.add(this.points);
  }

  upload(n, scale, fog) {
    this.points.geometry.setDrawRange(0, n);
    for (const a of this.attrs) a.needsUpdate = true;
    this.uniforms.uScale.value = scale;
    this.uniforms.uFog.value = fog;
  }
}

// Lichthöfe um Rücklichter, Scheinwerfer, Blinker und Laternen (jeden Frame neu befüllt)
export class Glows extends PointBuffer {
  constructor(scene) {
    super(scene, 640, GLOW_FRAG, { blending: THREE.AdditiveBlending, renderOrder: 6 });
    this.n = 0;
  }

  begin() {
    this.n = 0;
  }

  push(x, y, z, r, g, b, size) {
    if (this.n >= this.max) return;
    const i = this.n++;
    this.pos[i * 3] = x;
    this.pos[i * 3 + 1] = y;
    this.pos[i * 3 + 2] = z;
    this.col[i * 4] = r;
    this.col[i * 4 + 1] = g;
    this.col[i * 4 + 2] = b;
    this.col[i * 4 + 3] = 1;
    this.size[i] = size;
  }

  end(scale, fog) {
    this.upload(this.n, scale, fog);
  }
}

// Partikel mit Lebensdauer (Rauch, Funken). Die Welt bewegt sich am Spieler vorbei,
// deshalb werden Partikel jeden Frame um die gefahrene Strecke nach hinten geschoben.
export class Particles extends PointBuffer {
  constructor(scene, max, kind, texture) {
    const additive = kind === 'spark';
    super(scene, max, additive ? SPARK_FRAG : SMOKE_FRAG, {
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      uniforms: additive ? {} : { uMap: { value: texture } },
      renderOrder: additive ? 7 : 4,
    });
    this.vel = new Float32Array(max * 3);
    this.age = new Float32Array(max).fill(1);
    this.life = new Float32Array(max).fill(1);
    this.s0 = new Float32Array(max);
    this.s1 = new Float32Array(max);
    this.a0 = new Float32Array(max);
    this.drag = kind === 'spark' ? 0.6 : 1.6;
    this.gravity = kind === 'spark' ? -9 : 0.6;
    this.cursor = 0;
    this.active = 0;
  }

  spawn(x, y, z, vx, vy, vz, life, s0, s1, r, g, b, a) {
    const i = this.cursor;
    this.cursor = (this.cursor + 1) % this.max;
    this.pos[i * 3] = x;
    this.pos[i * 3 + 1] = y;
    this.pos[i * 3 + 2] = z;
    this.vel[i * 3] = vx;
    this.vel[i * 3 + 1] = vy;
    this.vel[i * 3 + 2] = vz;
    this.col[i * 4] = r;
    this.col[i * 4 + 1] = g;
    this.col[i * 4 + 2] = b;
    this.a0[i] = a;
    this.age[i] = 0;
    this.life[i] = life;
    this.s0[i] = s0;
    this.s1[i] = s1;
    this.active = this.max;
  }

  update(dt, shift, scale, fog) {
    if (!this.active) return;
    let alive = 0;
    const damp = Math.max(0, 1 - this.drag * dt);
    for (let i = 0; i < this.max; i++) {
      if (this.age[i] >= this.life[i]) {
        this.size[i] = 0;
        continue;
      }
      alive++;
      this.age[i] += dt;
      const t = Math.min(1, this.age[i] / this.life[i]);
      this.vel[i * 3] *= damp;
      this.vel[i * 3 + 1] = this.vel[i * 3 + 1] * damp + this.gravity * dt;
      this.vel[i * 3 + 2] *= damp;
      this.pos[i * 3] += this.vel[i * 3] * dt;
      this.pos[i * 3 + 1] = Math.max(0.05, this.pos[i * 3 + 1] + this.vel[i * 3 + 1] * dt);
      this.pos[i * 3 + 2] += this.vel[i * 3 + 2] * dt + shift;
      this.size[i] = this.s0[i] + (this.s1[i] - this.s0[i]) * t;
      this.col[i * 4 + 3] = this.a0[i] * (1 - t) * Math.min(1, t * 8 + 0.3);
    }
    if (!alive) this.active = 0;
    this.upload(this.max, scale, fog);
  }

  clear() {
    this.age.fill(1);
    this.size.fill(0);
    this.upload(this.max, this.uniforms.uScale.value, this.uniforms.uFog.value);
  }
}

// Fahrtwind: feine Linien, die bei hohem Tempo an der Kamera vorbeiziehen
export class WindStreaks {
  constructor(scene, n = 40) {
    this.items = [];
    for (let i = 0; i < n; i++) this.items.push({ x: 0, y: 0, z: 1e9 });
    this.pos = new Float32Array(n * 6);
    const g = new THREE.BufferGeometry();
    this.attr = new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage);
    g.setAttribute('position', this.attr);
    this.mat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false, fog: false });
    this.lines = new THREE.LineSegments(g, this.mat);
    this.lines.frustumCulled = false;
    scene.add(this.lines);
  }

  update(dt, v, cam, brightness) {
    const k = smoothstep(42, 78, v);
    this.mat.opacity = 0.22 * k * brightness;
    this.lines.visible = k > 0.01;
    if (!this.lines.visible) return;
    const len = v * 0.06, cz = cam.position.z, cx = cam.position.x;
    for (let i = 0; i < this.items.length; i++) {
      const it = this.items[i];
      it.z += v * 1.3 * dt;
      if (it.z > cz + 1 || it.z < cz - 120) {
        it.z = cz - rand(15, 90);
        it.x = cx + rand(2.2, 9) * (Math.random() < 0.5 ? -1 : 1);
        it.y = rand(0.4, 7);
      }
      const o = i * 6;
      this.pos[o] = it.x;
      this.pos[o + 1] = it.y;
      this.pos[o + 2] = it.z;
      this.pos[o + 3] = it.x;
      this.pos[o + 4] = it.y;
      this.pos[o + 5] = it.z - len;
    }
    this.attr.needsUpdate = true;
  }
}
