// Wetter: Regen (Tropfen-Striche um die Kamera, im Shader animiert), nasse Straßen, Bewölkung.
//
//   weather.set('rain')                  // 'clear' | 'cloudy' | 'rain' | 'storm'
//   weather.update(dt, camera, world, sky, audio)
// Die Nässe der Straße folgt dem Regen langsam (nass werden ~20 s, trocknen ~2 min).

import * as THREE from 'three';

export const WEATHERS = {
  clear: { label: 'Klar', cloud: 0.0, rain: 0.0 },
  cloudy: { label: 'Bewölkt', cloud: 0.75, rain: 0.0 },
  rain: { label: 'Regen', cloud: 0.9, rain: 0.55 },
  storm: { label: 'Starkregen', cloud: 1.0, rain: 1.0 },
};

const VERT = /* glsl */`
attribute vec3 aOff;
attribute float aSeg;
uniform float uTime, uFall, uExpo;
uniform vec3 uCam, uBox, uWind, uCamVel;
varying float vA;
void main() {
  vec3 vel = vec3(uWind.x, -uFall, uWind.z);
  vec3 p = aOff + vel * uTime;
  p = mod(p - uCam + uBox * 0.5, uBox) + uCam - uBox * 0.5;
  // Strich: Ende zeigt entgegen der Bewegung relativ zur Kamera (Bewegungsunschärfe)
  p -= (vel - uCamVel) * (aSeg * uExpo);
  vA = 1.0 - aSeg * 0.85;
  // nahe Tropfen ausblenden (sonst große Striche direkt vor der Linse)
  float d = length(p - uCam);
  vA *= smoothstep(0.6, 2.5, d) * (1.0 - smoothstep(uBox.x * 0.38, uBox.x * 0.5, d));
  gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
}`;

const FRAG = /* glsl */`
uniform vec3 uColor;
uniform float uOpacity;
varying float vA;
void main() {
  gl_FragColor = vec4(uColor, uOpacity * vA);
}`;

export class Weather {
  constructor(scene, opts = {}) {
    this.scene = scene;
    this.kind = 'clear';
    this.target = WEATHERS.clear;
    this.cloud = 0;
    this.rain = 0;
    this.wet = 0;
    this.time = 0;
    this._lastCam = new THREE.Vector3();
    this._camVel = new THREE.Vector3();
    const n = opts.drops || 6000;
    const box = new THREE.Vector3(44, 26, 44);
    const pos = new Float32Array(n * 2 * 3);
    const off = new Float32Array(n * 2 * 3);
    const seg = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      const x = Math.random() * box.x, y = Math.random() * box.y, z = Math.random() * box.z;
      for (let k = 0; k < 2; k++) {
        off.set([x, y, z], (i * 2 + k) * 3);
        seg[i * 2 + k] = k;
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('aOff', new THREE.BufferAttribute(off, 3));
    g.setAttribute('aSeg', new THREE.BufferAttribute(seg, 1));
    this.uniforms = {
      uTime: { value: 0 }, uFall: { value: 9.5 }, uExpo: { value: 0.045 }, uCam: { value: new THREE.Vector3() },
      uBox: { value: box }, uWind: { value: new THREE.Vector3(1.2, 0, 0.6) }, uCamVel: { value: new THREE.Vector3() },
      uColor: { value: new THREE.Color(0.55, 0.6, 0.68) }, uOpacity: { value: 0 },
    };
    this.material = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms: this.uniforms,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    this.lines = new THREE.LineSegments(g, this.material);
    this.lines.frustumCulled = false;
    this.lines.visible = false;
    this.lines.renderOrder = 5;
    scene.add(this.lines);
  }

  set(kind) {
    if (!WEATHERS[kind]) kind = 'clear';
    this.kind = kind;
    this.target = WEATHERS[kind];
  }

  /** Sofort auf das Zielwetter springen (z. B. beim Laden). */
  snap() {
    this.cloud = this.target.cloud;
    this.rain = this.target.rain;
    this.wet = this.target.rain > 0 ? Math.min(1, 0.4 + this.target.rain) : 0;
  }

  update(dt, camera, world, sky, audio) {
    this.time += dt;
    const T = this.target;
    // weich überblenden (Wolken ~15 s, Regen ~8 s)
    this.cloud += (T.cloud - this.cloud) * Math.min(1, dt / 15);
    this.rain += (T.rain - this.rain) * Math.min(1, dt / 8);
    // Straße: nass werden schnell, trocknen langsam
    const wetTarget = this.rain > 0.05 ? Math.min(1, 0.45 + this.rain) : 0;
    this.wet += (wetTarget - this.wet) * Math.min(1, dt / (wetTarget > this.wet ? 20 : 120));
    if (world) world.setWetness(this.wet);
    if (sky) sky.setWeather(this.cloud, this.rain);
    if (audio && audio.setRain) { audio.setRain(this.rain); audio.wet = this.wet; }
    // Tropfen
    const u = this.uniforms;
    const on = this.rain > 0.01;
    this.lines.visible = on;
    if (!on) return;
    const cam = camera.position;
    if (dt > 0) {
      this._camVel.subVectors(cam, this._lastCam).divideScalar(dt);
      if (this._camVel.length() > 120) this._camVel.set(0, 0, 0);       // Kamerasprung
    }
    this._lastCam.copy(cam);
    u.uCamVel.value.lerp(this._camVel, Math.min(1, dt * 10));
    u.uTime.value = this.time;
    u.uCam.value.copy(cam);
    u.uFall.value = 8.5 + this.rain * 3;
    u.uOpacity.value = 0.12 + this.rain * 0.22;
    const nightDim = sky ? 1 - 0.55 * sky.nightK : 1;
    u.uColor.value.setRGB(0.55 * nightDim, 0.6 * nightDim, 0.68 * nightDim);
    // weniger Tropfen bei Nieselregen: Teil der Striche ausblenden über die Zeichenanzahl
    const total = this.lines.geometry.attributes.aSeg.count;
    this.lines.geometry.setDrawRange(0, Math.floor(total * Math.min(1, 0.25 + this.rain * 0.75) / 2) * 2);
  }
}
