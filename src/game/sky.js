// Himmel, Sonne/Mond, Licht und Spiegelungen nach Tageszeit.
//
// Eine Himmelskuppel (eigener Shader: Farbverlauf, Dunst am Horizont, Sonnenscheibe mit Glühen)
// liefert gleichzeitig die Umgebungstextur (PMREM) für Lack, Glas und Chrom – die Autos spiegeln
// also den echten Himmel. Dazu Sonne als gerichtetes Licht mit Schatten, der dem Spieler folgt.
// setTime(Stunden 0..24) stellt alles passend ein (Nacht: Mondlicht, dunkelblau, Stadtlichter).

import * as THREE from 'three';

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const lerpC = (a, b, t) => a.clone().lerp(b, t);

// Farben (linear) für Tag, goldene Stunde, Dämmerung und Nacht
const PAL = {
  day: { zenith: new THREE.Color(0.10, 0.24, 0.62), horizon: new THREE.Color(0.55, 0.66, 0.80), ground: new THREE.Color(0.12, 0.115, 0.11),
    sun: new THREE.Color(1.0, 0.95, 0.86), sunI: 3.4, hemiSky: new THREE.Color(0.55, 0.66, 0.85), hemiGround: new THREE.Color(0.22, 0.2, 0.18), hemiI: 0.35 },
  gold: { zenith: new THREE.Color(0.12, 0.2, 0.45), horizon: new THREE.Color(0.95, 0.58, 0.32), ground: new THREE.Color(0.1, 0.08, 0.07),
    sun: new THREE.Color(1.0, 0.62, 0.32), sunI: 2.4, hemiSky: new THREE.Color(0.5, 0.48, 0.6), hemiGround: new THREE.Color(0.2, 0.15, 0.12), hemiI: 0.3 },
  dusk: { zenith: new THREE.Color(0.035, 0.05, 0.14), horizon: new THREE.Color(0.42, 0.18, 0.28), ground: new THREE.Color(0.03, 0.025, 0.03),
    sun: new THREE.Color(0.9, 0.4, 0.3), sunI: 0.5, hemiSky: new THREE.Color(0.25, 0.2, 0.35), hemiGround: new THREE.Color(0.06, 0.05, 0.06), hemiI: 0.22 },
  night: { zenith: new THREE.Color(0.004, 0.006, 0.018), horizon: new THREE.Color(0.03, 0.03, 0.07), ground: new THREE.Color(0.01, 0.01, 0.014),
    sun: new THREE.Color(0.55, 0.65, 1.0), sunI: 0.22, hemiSky: new THREE.Color(0.12, 0.13, 0.25), hemiGround: new THREE.Color(0.03, 0.03, 0.04), hemiI: 0.18 },
};

const VERT = /* glsl */`
varying vec3 vDir;
void main() {
  vDir = position;
  vec4 p = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * p;
  gl_Position.z = gl_Position.w * 0.99999;   // immer ganz hinten
}`;

const FRAG = /* glsl */`
uniform vec3 uZenith, uHorizon, uGround, uSunColor, uSunDir, uMoonDir;
uniform float uSunDisc, uNight, uCityGlow;
uniform vec3 uCityColor;
varying vec3 vDir;
float hash(vec3 p) { return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
void main() {
  vec3 d = normalize(vDir);
  float h = d.y;
  vec3 col = mix(uHorizon, uZenith, pow(clamp(h, 0.0, 1.0), 0.42));
  // Lichtglocke der Stadt am Horizont (nachts)
  col += uCityColor * uCityGlow * exp(-max(h, 0.0) * 9.0);
  col = mix(col, uGround, smoothstep(0.0, -0.06, h));
  float s = max(dot(d, uSunDir), 0.0);
  col += uSunColor * (pow(s, 1400.0) * 60.0 * uSunDisc + pow(s, 14.0) * 0.30 + pow(s, 3.0) * 0.10) * step(-0.02, h);
  // Mond und Sterne
  float m = max(dot(d, uMoonDir), 0.0);
  col += vec3(0.8, 0.85, 1.0) * pow(m, 2600.0) * 8.0 * uNight;
  vec3 g = floor(d * 420.0);
  float st = step(0.9965, hash(g)) * smoothstep(0.05, 0.4, h);
  col += vec3(0.9, 0.95, 1.0) * st * uNight * 0.9 * hash(g + 1.7);
  gl_FragColor = vec4(col, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export class SkySystem {
  constructor(renderer, scene) {
    this.renderer = renderer;
    this.scene = scene;
    this.uniforms = {
      uZenith: { value: new THREE.Color() }, uHorizon: { value: new THREE.Color() }, uGround: { value: new THREE.Color() },
      uSunColor: { value: new THREE.Color() }, uSunDir: { value: new THREE.Vector3(0, 1, 0) },
      uMoonDir: { value: new THREE.Vector3(0, 1, 0) }, uSunDisc: { value: 1 }, uNight: { value: 0 },
      uCityGlow: { value: 0 }, uCityColor: { value: new THREE.Color(0.35, 0.12, 0.3) },
    };
    this.material = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms: this.uniforms,
      side: THREE.BackSide, depthWrite: false, fog: false });
    this.dome = new THREE.Mesh(new THREE.SphereGeometry(4000, 48, 24), this.material);
    this.dome.frustumCulled = false;
    this.dome.renderOrder = -10;
    scene.add(this.dome);

    this.sun = new THREE.DirectionalLight(0xffffff, 3);
    this.sun.castShadow = true;
    this.sun.shadow.bias = -0.0003;
    this.sun.shadow.normalBias = 0.03;
    this.sun.shadow.camera.near = 1;
    this.sun.shadow.camera.far = 220;
    this.setShadowRange(36);
    scene.add(this.sun);
    scene.add(this.sun.target);
    this.hemi = new THREE.HemisphereLight(0xffffff, 0x222222, 0.3);
    scene.add(this.hemi);
    scene.fog = new THREE.Fog(0x8899aa, 250, 1700);

    // Umgebung für Spiegelungen: eigene kleine Szene mit derselben Kuppel + dunklem Boden
    this.envScene = new THREE.Scene();
    this.envDome = new THREE.Mesh(new THREE.SphereGeometry(50, 32, 16), this.material);
    this.envScene.add(this.envDome);
    this.envGroundMat = new THREE.MeshBasicMaterial({ color: 0x111111 });
    const g = new THREE.Mesh(new THREE.CircleGeometry(48, 32), this.envGroundMat);
    g.rotation.x = -Math.PI / 2;
    g.position.y = -1.6;
    this.envScene.add(g);
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.envRT = null;
    this.hours = -1;
    this.envHours = -99;
    this.nightK = 0;
    this.fogNear = 250;
    this.fogFar = 1700;
  }

  setShadowRange(r) {
    const c = this.sun.shadow.camera;
    c.left = -r; c.right = r; c.top = r; c.bottom = -r;
    c.updateProjectionMatrix();
    this.shadowRange = r;
  }

  setFog(near, far) {
    this.fogNear = near; this.fogFar = far;
    this.scene.fog.near = near * (1 + 0.6 * this.nightK);
    this.scene.fog.far = far * (1 + 0.9 * this.nightK);
  }

  /** Tageszeit in Stunden (0..24). */
  setTime(hours, force = false) {
    hours = ((hours % 24) + 24) % 24;
    if (!force && Math.abs(hours - this.hours) < 1e-4) return;
    this.hours = hours;
    // Sonnenbahn: Aufgang 6:00, Untergang 20:00, Höchststand 13:00 (~60°)
    const dayT = (hours - 6) / 14;
    const el = dayT >= 0 && dayT <= 1 ? Math.sin(Math.PI * dayT) * 1.05 : -Math.sin(Math.PI * Math.min(1, Math.abs(dayT < 0 ? (hours + 4) / 10 : (hours - 20) / 10))) * 0.6;
    // Karte: +Z = Norden (dort liegt die Stadt), Osten = −X. Sonne: Osten -> Süden (−Z) -> Westen (+X)
    const phi = Math.PI * Math.min(1.2, Math.max(-0.2, dayT));
    const sunDir = new THREE.Vector3(-Math.cos(phi) * Math.cos(el), Math.sin(el), -Math.sin(phi) * Math.cos(el) - 0.25).normalize();
    const moonDir = new THREE.Vector3(-0.42, 0.62, -0.66).normalize();
    const elDeg = el * 180 / Math.PI;
    // Mischung der Paletten nach Sonnenhöhe
    const P = PAL;
    let A, B, t;
    if (elDeg > 14) { A = P.gold; B = P.day; t = smooth(14, 30, elDeg); }
    else if (elDeg > 2) { A = P.dusk; B = P.gold; t = smooth(2, 14, elDeg); }
    else if (elDeg > -8) { A = P.night; B = P.dusk; t = smooth(-8, 2, elDeg); }
    else { A = P.night; B = P.night; t = 1; }
    const u = this.uniforms;
    u.uZenith.value.copy(lerpC(A.zenith, B.zenith, t));
    u.uHorizon.value.copy(lerpC(A.horizon, B.horizon, t));
    u.uGround.value.copy(lerpC(A.ground, B.ground, t));
    const night = 1 - smooth(-7, 4, elDeg);
    this.nightK = night;
    u.uSunColor.value.copy(lerpC(A.sun, B.sun, t)).multiplyScalar(1 - night);
    u.uSunDir.value.copy(sunDir);
    u.uMoonDir.value.copy(moonDir);
    u.uSunDisc.value = smooth(-2, 3, elDeg);
    u.uNight.value = night;
    u.uCityGlow.value = night * 0.9;
    // Licht: über dem Horizont die Sonne, sonst der Mond
    const lightDir = elDeg > -3 ? sunDir : moonDir;
    this.lightDir = lightDir.clone();
    this.sun.color.copy(night > 0.7 ? P.night.sun : lerpC(A.sun, B.sun, t));
    this.sun.intensity = night > 0.7 ? P.night.sunI : THREE.MathUtils.lerp(A.sunI, B.sunI, t) * smooth(-3, 4, elDeg) + P.night.sunI * night;
    this.hemi.color.copy(lerpC(A.hemiSky, B.hemiSky, t));
    this.hemi.groundColor.copy(lerpC(A.hemiGround, B.hemiGround, t));
    this.hemi.intensity = THREE.MathUtils.lerp(A.hemiI, B.hemiI, t);
    // Nebel in Horizontfarbe (nachts mit etwas Stadtglühen)
    this.scene.fog.color.copy(u.uHorizon.value).lerp(u.uCityColor.value, night * 0.25);
    // nachts klarere Sicht (sonst verschwinden die Lichter der Stadt im Dunst)
    this.scene.fog.near = this.fogNear * (1 + 0.6 * night);
    this.scene.fog.far = this.fogFar * (1 + 0.9 * night);
    this.envGroundMat.color.copy(u.uGround.value).multiplyScalar(0.8);
    if (force || Math.abs(hours - this.envHours) > 0.2) this.updateEnv();
  }

  updateEnv() {
    this.envHours = this.hours;
    const old = this.envRT;
    this.envRT = this.pmrem.fromScene(this.envScene, 0, 0.1, 200);
    this.scene.environment = this.envRT.texture;
    if (old) old.dispose();
  }

  /** Schatten-Ausschnitt mit dem Spieler mitführen (in Texel-Schritten, damit nichts flimmert). */
  follow(pos) {
    const d = this.lightDir || new THREE.Vector3(0.4, 0.8, 0.3);
    const size = this.shadowRange * 2;
    const texel = size / (this.sun.shadow.mapSize.x || 1024);
    const x = Math.round(pos.x / texel) * texel, z = Math.round(pos.z / texel) * texel;
    this.sun.target.position.set(x, 0, z);
    this.sun.position.set(x + d.x * 120, Math.max(8, d.y * 120), z + d.z * 120);
    this.sun.target.updateMatrixWorld();
    this.dome.position.set(pos.x, 0, pos.z);
  }
}
