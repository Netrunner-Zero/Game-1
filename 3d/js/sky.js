// Himmel, Licht, Nebel und Tag-Nacht-Wechsel
import * as THREE from 'three';
import { smoothstep } from './config.js';

const SKY_VERT = /* glsl */ `
varying vec3 vWorldPos;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}`;

const SKY_FRAG = /* glsl */ `
uniform vec3 uZenith;
uniform vec3 uHorizon;
uniform vec3 uSunDir;
uniform vec3 uSunColor;
uniform float uSunVis;
uniform vec3 uMoonDir;
uniform float uMoonVis;
uniform float uStars;
uniform vec3 uCloudLit;
uniform vec3 uCloudDark;
uniform vec3 uMountain;
uniform vec3 uMountainFar;
uniform float uTime;
varying vec3 vWorldPos;

float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}
float hash13(vec3 p3) {
  p3 = fract(p3 * 0.1031);
  p3 += dot(p3, p3.zyx + 31.32);
  return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
             mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * vnoise(p); p = p * 2.07 + vec2(13.1, 7.7); a *= 0.5; }
  return v;
}

void main() {
  vec3 d = normalize(vWorldPos - cameraPosition);
  float h = d.y;
  float hp = max(h, 0.0);
  vec3 col = mix(uHorizon, uZenith, pow(hp, 0.55));

  // Sonne: Halo, Leuchten am Horizont und Sonnenscheibe
  float sd = max(dot(d, uSunDir), 0.0);
  float band = exp(-abs(h) * 7.0);
  col += uSunColor * (pow(sd, 5.0) * (0.08 + 0.4 * band) + pow(sd, 90.0) * 0.7) * uSunVis;
  col += uSunColor * smoothstep(0.99955, 0.99975, sd) * 28.0 * uSunVis * step(-0.01, h);

  // Sterne und Mond
  if (uStars > 0.001) {
    vec3 sp = d * 180.0;
    vec3 id = floor(sp);
    float r = hash13(id);
    float s = step(0.993, r) * smoothstep(0.34, 0.0, length(fract(sp) - 0.5));
    float tw = 0.65 + 0.35 * sin(uTime * 2.3 + r * 60.0);
    col += vec3(0.9, 0.95, 1.0) * s * tw * uStars * smoothstep(0.03, 0.25, h) * 1.6;
  }
  float md = max(dot(d, uMoonDir), 0.0);
  col += vec3(0.85, 0.9, 1.0) * (smoothstep(0.99935, 0.99955, md) * 3.0 + pow(md, 260.0) * 0.3) * uMoonVis;

  #ifdef CLOUDS
  if (h > 0.0) {
    vec2 uv = d.xz / (h + 0.12) * 1.5 + vec2(uTime * 0.006, uTime * 0.002);
    float n = fbm(uv);
    float cov = smoothstep(0.5, 0.78, n) * smoothstep(0.015, 0.2, h);
    vec3 cc = mix(uCloudDark, uCloudLit, clamp(smoothstep(0.45, 0.9, n) * 0.55 + pow(sd, 3.0) * 0.6, 0.0, 1.0));
    col = mix(col, cc, cov * 0.88);
  }
  #endif

  // Bergsilhouetten am Horizont (zwei Schichten mit Dunst)
  if (h < 0.08) {
    float az = atan(d.x, -d.z);
    vec2 cp = vec2(cos(az), sin(az));
    float mFar = 0.012 + 0.048 * fbm(cp * 2.0 + vec2(3.1, 1.7));
    float mNear = 0.004 + 0.03 * fbm(cp * 5.0 + vec2(8.3, 2.9));
    vec3 farCol = mix(uMountainFar, uHorizon, smoothstep(mFar, -0.01, h) * 0.6);
    col = mix(col, farCol, 1.0 - smoothstep(mFar - 0.0015, mFar, h));
    vec3 nearCol = mix(uMountain, uHorizon, smoothstep(mNear, -0.01, h) * 0.5);
    col = mix(col, nearCol, 1.0 - smoothstep(mNear - 0.0015, mNear, h));
    col = mix(col, uHorizon, 1.0 - smoothstep(-0.012, -0.002, h));
  }

  gl_FragColor = vec4(col, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

// Stützpunkte nach Sonnenhöhe (Grad). Farben als sRGB-Hex.
const KEYS = [
  { e: -20, zenith: 0x02050d, horizon: 0x0e1729, sun: 0x000000, sunI: 0, hemiSky: 0x33467a, hemiGround: 0x101217, hemiI: 1.15, density: 0.003, exposure: 1.05, envI: 0.9, cloudLit: 0x1a2232, cloudDark: 0x0a0e16, mtn: 0x060a11, mtnFar: 0x0b1222, stars: 1 },
  { e: -7, zenith: 0x0b1838, horizon: 0x3a4268, sun: 0xff7040, sunI: 0, hemiSky: 0x4b5583, hemiGround: 0x1b1d24, hemiI: 1.0, density: 0.0029, exposure: 1.0, envI: 0.9, cloudLit: 0x4a4466, cloudDark: 0x1d2033, mtn: 0x141a2a, mtnFar: 0x262c48, stars: 0.35 },
  { e: -1.5, zenith: 0x1d3366, horizon: 0xd06a45, sun: 0xff5a20, sunI: 0.25, hemiSky: 0x8282a8, hemiGround: 0x3a3027, hemiI: 0.85, density: 0.0027, exposure: 0.95, envI: 1, cloudLit: 0xff9a6a, cloudDark: 0x4c3c55, mtn: 0x3a3346, mtnFar: 0x7a5560, stars: 0 },
  { e: 4, zenith: 0x2a529c, horizon: 0xf0a36a, sun: 0xff9246, sunI: 1.7, hemiSky: 0xa9b8d8, hemiGround: 0x4e4a33, hemiI: 0.85, density: 0.0026, exposure: 0.9, envI: 1, cloudLit: 0xffd2a0, cloudDark: 0x7a7488, mtn: 0x5a6070, mtnFar: 0xb08a80, stars: 0 },
  { e: 14, zenith: 0x2b5fae, horizon: 0xd6d8d6, sun: 0xffd6a0, sunI: 2.6, hemiSky: 0xb6cbe8, hemiGround: 0x56603a, hemiI: 0.95, density: 0.0025, exposure: 0.85, envI: 1, cloudLit: 0xfff4e6, cloudDark: 0x8a92a3, mtn: 0x66788a, mtnFar: 0x9fb0c0, stars: 0 },
  { e: 48, zenith: 0x1f5bbd, horizon: 0xb4cde6, sun: 0xfff4e4, sunI: 3.0, hemiSky: 0xbcd4f0, hemiGround: 0x5b6640, hemiI: 1.0, density: 0.0024, exposure: 0.82, envI: 1, cloudLit: 0xffffff, cloudDark: 0x9aa3b2, mtn: 0x6f8296, mtnFar: 0xa3b6c8, stars: 0 },
];
const COLOR_KEYS = ['zenith', 'horizon', 'sun', 'hemiSky', 'hemiGround', 'cloudLit', 'cloudDark', 'mtn', 'mtnFar'];
const NUM_KEYS = ['sunI', 'hemiI', 'density', 'exposure', 'envI', 'stars'];
for (const k of KEYS) for (const c of COLOR_KEYS) k[c] = new THREE.Color(k[c]);

const MAX_ELEV = 48;             // höchster Sonnenstand
const START_ANGLE = Math.PI - Math.asin(32 / MAX_ELEV); // Nachmittag, Sonne sinkt
const DAY_SPEED = 0.0104;        // rad/s → nach gut einer Minute Sonnenuntergang
const SUN_AZ = new THREE.Vector2(-0.72, -0.69).normalize(); // vorne links
const MOON_DIR = new THREE.Vector3(0.45, 0.5, -0.74).normalize();
const MOON_COLOR = new THREE.Color(0x9db4ff);

export class Sky {
  constructor(renderer, scene) {
    this.renderer = renderer;
    this.scene = scene;
    this.cur = {};
    for (const c of COLOR_KEYS) this.cur[c] = new THREE.Color();

    this.uniforms = {
      uZenith: { value: new THREE.Color() },
      uHorizon: { value: new THREE.Color() },
      uSunDir: { value: new THREE.Vector3(0, 1, 0) },
      uSunColor: { value: new THREE.Color() },
      uSunVis: { value: 1 },
      uMoonDir: { value: MOON_DIR },
      uMoonVis: { value: 0 },
      uStars: { value: 0 },
      uCloudLit: { value: new THREE.Color() },
      uCloudDark: { value: new THREE.Color() },
      uMountain: { value: new THREE.Color() },
      uMountainFar: { value: new THREE.Color() },
      uTime: { value: 0 },
    };
    this.material = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: SKY_VERT,
      fragmentShader: SKY_FRAG,
      side: THREE.BackSide,
      depthWrite: false,
      depthTest: false,
      fog: false,
      defines: { CLOUDS: 1 },
    });
    const geo = new THREE.SphereGeometry(1, 48, 24);
    this.dome = new THREE.Mesh(geo, this.material);
    this.dome.scale.setScalar(950);
    this.dome.renderOrder = -100;
    this.dome.frustumCulled = false;
    scene.add(this.dome);

    // Sonne (nachts Mond) mit Schatten, dazu Himmelslicht
    this.light = new THREE.DirectionalLight(0xffffff, 3);
    this.light.castShadow = true;
    this.light.shadow.bias = -0.0004;
    this.light.shadow.normalBias = 0.035;
    this.light.target.position.set(0, 0, -22);
    scene.add(this.light, this.light.target);
    this.hemi = new THREE.HemisphereLight(0xffffff, 0x444444, 1);
    scene.add(this.hemi);
    scene.fog = new THREE.FogExp2(0xffffff, 0.0026);

    // Bereich, in dem Schatten berechnet werden (um den Spieler herum)
    this.region = [];
    for (const x of [-13, 13]) for (const y of [0, 8]) for (const z of [-58, 14]) this.region.push(new THREE.Vector3(x, y, z));
    this.tmpCam = new THREE.OrthographicCamera();
    this.tmpV = new THREE.Vector3();
    this.lightDir = new THREE.Vector3();

    // Umgebungs-Map für Reflexionen (Lack, Glas, Chrom)
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.envScene = new THREE.Scene();
    // Für die Reflexionen reicht der Himmel ohne Wolken (spart Rechenzeit beim Neuberechnen)
    const envMat = this.material.clone();
    envMat.uniforms = this.uniforms;
    delete envMat.defines.CLOUDS;
    const envDome = new THREE.Mesh(geo, envMat);
    envDome.scale.setScalar(50);
    this.envGround = new THREE.Mesh(
      new THREE.CircleGeometry(60, 24).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ color: 0x333333 })
    );
    this.envGround.position.y = -1.5;
    this.envScene.add(envDome, this.envGround);
    this.envRT = null;
    this.lastEnvElev = 999;
    this.envStep = 3;

    this.time = 0;
    this.reset();
  }

  reset() {
    this.angle = START_ANGLE;
    this.apply();
  }

  setQuality(level) {
    const clouds = level >= 1;
    if (clouds !== ('CLOUDS' in this.material.defines)) {
      if (clouds) this.material.defines.CLOUDS = 1;
      else delete this.material.defines.CLOUDS;
      this.material.needsUpdate = true;
      this.lastEnvElev = 999;
    }
    this.envStep = level === 0 ? 7 : 3;
    this.light.shadow.mapSize.setScalar(level === 2 ? 2048 : 1024);
    if (this.light.shadow.map) {
      this.light.shadow.map.dispose();
      this.light.shadow.map = null;
    }
  }

  // advance = false: Zeit steht (Menü)
  update(dt, camera, advance) {
    this.time += dt;
    if (advance) {
      const e = this.elevation;
      const speed = e < -8 ? 2.6 : e < 4 ? 0.85 : 1;
      this.angle += dt * DAY_SPEED * speed;
    }
    this.apply();
    this.dome.position.copy(camera.position);
    if (Math.abs(this.elevation - this.lastEnvElev) > this.envStep) this.updateEnvironment();
  }

  apply() {
    const e = MAX_ELEV * Math.sin(this.angle);
    this.elevation = e;

    // Zwischen den Stützpunkten interpolieren
    let i = 0;
    while (i < KEYS.length - 2 && e > KEYS[i + 1].e) i++;
    const a = KEYS[i], b = KEYS[i + 1];
    const t = Math.min(1, Math.max(0, (e - a.e) / (b.e - a.e)));
    const cur = this.cur;
    for (const c of COLOR_KEYS) cur[c].copy(a[c]).lerp(b[c], t);
    for (const n of NUM_KEYS) cur[n] = a[n] + (b[n] - a[n]) * t;

    const u = this.uniforms;
    const er = THREE.MathUtils.degToRad(e);
    u.uSunDir.value.set(SUN_AZ.x * Math.cos(er), Math.sin(er), SUN_AZ.y * Math.cos(er)).normalize();
    u.uZenith.value.copy(cur.zenith);
    u.uHorizon.value.copy(cur.horizon);
    u.uSunColor.value.copy(cur.sun);
    u.uSunVis.value = smoothstep(-6, -1, e);
    u.uMoonVis.value = smoothstep(-2, -10, e);
    u.uStars.value = cur.stars;
    u.uCloudLit.value.copy(cur.cloudLit);
    u.uCloudDark.value.copy(cur.cloudDark);
    u.uMountain.value.copy(cur.mtn);
    u.uMountainFar.value.copy(cur.mtnFar);
    u.uTime.value = this.time;

    // Gerichtetes Licht: tagsüber Sonne, nachts Mond
    const sunI = cur.sunI * smoothstep(-2.5, 1.5, e);
    const moonI = 0.45 * smoothstep(-3, -12, e);
    if (sunI >= moonI) {
      this.lightDir.copy(u.uSunDir.value);
      this.light.color.copy(cur.sun);
      this.light.intensity = sunI;
    } else {
      this.lightDir.copy(MOON_DIR);
      this.light.color.copy(MOON_COLOR);
      this.light.intensity = moonI;
    }
    this.light.position.copy(this.light.target.position).addScaledVector(this.lightDir, 150);
    this.fitShadowCamera();

    this.hemi.color.copy(cur.hemiSky);
    this.hemi.groundColor.copy(cur.hemiGround);
    this.hemi.intensity = cur.hemiI;
    this.scene.fog.color.copy(cur.horizon);
    this.scene.fog.density = cur.density;
    this.scene.environmentIntensity = cur.envI;
    this.renderer.toneMappingExposure = cur.exposure;
    this.night = smoothstep(3, -7, e); // 0 = Tag, 1 = Nacht (Laternen an)
  }

  // Schattenkamera eng um den sichtbaren Bereich legen → scharfe Schatten
  fitShadowCamera() {
    const cam = this.light.shadow.camera;
    const tc = this.tmpCam;
    tc.position.copy(this.light.position);
    tc.lookAt(this.light.target.position);
    tc.updateMatrixWorld();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity;
    for (const p of this.region) {
      const v = this.tmpV.copy(p).applyMatrix4(tc.matrixWorldInverse);
      if (v.x < minX) minX = v.x;
      if (v.x > maxX) maxX = v.x;
      if (v.y < minY) minY = v.y;
      if (v.y > maxY) maxY = v.y;
      if (v.z < minZ) minZ = v.z;
    }
    cam.left = minX - 1;
    cam.right = maxX + 1;
    cam.bottom = minY - 1;
    cam.top = maxY + 1;
    cam.near = 1;
    cam.far = -minZ + 15;
    cam.updateProjectionMatrix();
  }

  updateEnvironment() {
    this.lastEnvElev = this.elevation;
    this.envGround.material.color.copy(this.cur.hemiGround).multiplyScalar(0.55);
    const old = this.envRT;
    this.envRT = this.pmrem.fromScene(this.envScene, 0, 0.1, 100);
    this.scene.environment = this.envRT.texture;
    if (old) old.dispose();
  }
}
