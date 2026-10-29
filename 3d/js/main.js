// Highway Dodge 3D – Spielablauf, Kamera, Darstellung und Bedienoberfläche
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { KMH, LANE_X, PLAYER_BOUNDS, clamp, lerp, smoothstep, rand } from './config.js';
import { createRadialTexture, createSmokeTexture } from './textures.js';
import { Sky } from './sky.js';
import { World } from './world.js';
import { SPECS, createVehicleMaterials, TrafficRenderer, PlayerCar } from './vehicles.js';
import { Traffic, idm } from './traffic.js';
import { Glows, Particles, WindStreaks } from './effects.js';
import { GameAudio } from './audio.js';
import { Input } from './input.js';

const $ = id => document.getElementById(id);
const approach = (a, b, d) => (a < b ? Math.min(a + d, b) : Math.max(a - d, b));
const isTouch = matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window;
const isMobile = isTouch || /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);

// ---------------------------------------------------------------- Einstellungen und Highscore
const SETTINGS_KEY = 'hd3d-settings';
const BEST_KEY = 'hd3d-best';
const settings = { sound: 'on', quality: 'auto', control: 'touch' };
try {
  Object.assign(settings, JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}'));
} catch { /* kein Speicher verfügbar */ }
const saveSettings = () => {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch { /* privater Modus */ }
};
let best = 0;
try {
  best = parseInt(localStorage.getItem(BEST_KEY), 10) || 0;
} catch { /* kein Speicher verfügbar */ }

// ---------------------------------------------------------------- Renderer und Szene
const canvas = $('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(65, 1, 0.3, 1300);

const sky = new Sky(renderer, scene);
const world = new World(scene, renderer);
const shadowTex = createRadialTexture();
const mats = createVehicleMaterials();
const CAPACITY = { sedan: 16, hatch: 14, suv: 12, coupe: 8, van: 10, truck: 10, bus: 6 };
const trafficRenderer = new TrafficRenderer(scene, mats, CAPACITY, shadowTex);
const dims = {};
for (const k of Object.keys(CAPACITY)) dims[k] = { L: SPECS[k].L, W: SPECS[k].W };
const traffic = new Traffic(dims, CAPACITY);
const player = new PlayerCar(scene, mats, shadowTex);
const glows = new Glows(scene);
const smoke = new Particles(scene, 260, 'smoke', createSmokeTexture());
const sparks = new Particles(scene, 220, 'spark');
const wind = new WindStreaks(scene);
const audio = new GameAudio();

// Nachbearbeitung (Bloom) nur in der höchsten Grafikstufe
let composer = null, bloom = null;
function ensureComposer() {
  if (composer) return;
  const rt = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
  composer = new EffectComposer(renderer, rt);
  composer.addPass(new RenderPass(scene, camera));
  bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.3, 0.55, 1.2);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
}

// ---------------------------------------------------------------- Spielzustand
const MAX_V = 300 * KMH;
const P = {
  s: 1000, x: LANE_X[2], v: 118 * KMH, vx: 0, lane: 2, lc: null,
  L: SPECS.coupe.L - 0.1, W: SPECS.coupe.W - 0.06,
  yaw: 0, roll: 0, pitch: 0, accel: 0, steer: 0, braking: false, spin: 0, lat: 0,
};
const game = {
  state: 'loading', time: 0, clock: 0, score: 0, dist: 0, near: 0, combo: 0, comboT: 0,
  top: 0, crashT: 0, shake: 0, scrape: 0, camBlend: 0, hudT: 0, hintT: 0,
};
// Grundtempo steigt von 120 km/h langsam Richtung 260 km/h
const baseSpeed = t => (120 + 140 * (1 - Math.exp(-t / 110))) * KMH;

// ---------------------------------------------------------------- Oberfläche
const ui = {
  hud: $('hud'), score: $('hudScore'), best: $('hudBest'), speed: $('hudSpeed'),
  popup: $('popup'), hint: $('hint'), pedals: $('pedals'),
  menu: $('menu'), pause: $('pause'), over: $('over'), loading: $('loading'),
  menuBest: $('menuBest'), overScore: $('overScore'), overRecord: $('overRecord'),
  statDist: $('statDist'), statTop: $('statTop'), statNear: $('statNear'),
  soundBtn: $('soundBtn'), tiltNote: $('tiltNote'),
};
const show = (el, on) => el.classList.toggle('hidden', !on);

const input = new Input({ surface: canvas, gasBtn: $('gasBtn'), brakeBtn: $('brakeBtn'), onPause: () => togglePause() });

// ---------------------------------------------------------------- Grafikstufen
const PR_CAP = [1, 1.5, 2];
const quality = { level: 1, scale: 1, bloom: false };

function levelFromSetting() {
  if (settings.quality === 'low') return 0;
  if (settings.quality === 'medium') return 1;
  if (settings.quality === 'high') return 2;
  // Automatik: Handy startet mittel, PC hoch – die Bildratenmessung regelt danach herunter
  return isMobile ? 1 : 2;
}

function applyQuality(level) {
  const shadowType = level === 2 ? THREE.PCFSoftShadowMap : THREE.PCFShadowMap;
  const recompile = renderer.shadowMap.enabled !== (level >= 1) || renderer.shadowMap.type !== shadowType;
  quality.level = level;
  quality.bloom = level === 2;
  if (quality.bloom) ensureComposer();
  renderer.shadowMap.enabled = level >= 1;
  renderer.shadowMap.type = shadowType;
  sky.setQuality(level);
  world.setQuality(level);
  mats.paint.clearcoat = level === 2 ? 1 : 0;
  player.setClearcoat(level >= 1);
  if (recompile) {
    scene.traverse(o => {
      if (!o.material) return;
      for (const m of Array.isArray(o.material) ? o.material : [o.material]) m.needsUpdate = true;
    });
  }
  perf.hold = 3;
  resize();
}

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  const pr = Math.min(window.devicePixelRatio || 1, PR_CAP[quality.level]) * quality.scale;
  renderer.setPixelRatio(pr);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  if (composer) {
    composer.setPixelRatio(pr);
    composer.setSize(w, h);
  }
  if (game.state === 'paused') render();
}
window.addEventListener('resize', resize);

// Automatik: erst die Auflösung senken, dann die Grafikstufe
const perf = { t: 0, n: 0, hold: 3 };
function perfSample(raw) {
  if (settings.quality !== 'auto' || raw > 0.25) return;
  if (game.state !== 'playing' && game.state !== 'menu') return;
  if (perf.hold > 0) {
    perf.hold -= raw;
    return;
  }
  perf.t += raw;
  perf.n++;
  if (perf.t < 2.5) return;
  const fps = perf.n / perf.t;
  perf.t = perf.n = 0;
  if (fps < 45) {
    if (quality.scale > 0.75) {
      quality.scale -= 0.1;
      resize();
      perf.hold = 1;
    } else if (quality.level > 0) {
      quality.scale = 1;
      applyQuality(quality.level - 1);
    }
  } else if (fps > 57 && quality.scale < 1) {
    quality.scale = Math.min(1, quality.scale + 0.05);
    resize();
  }
}

// ---------------------------------------------------------------- Kamera
const cam = { x: P.x, orbit: 0.6 };
const camPos = new THREE.Vector3(), camLook = new THREE.Vector3();

function updateCamera(dt) {
  const t = clamp((camera.aspect - 0.55) / (1.6 - 0.55), 0, 1); // 0 = Hochformat, 1 = Querformat
  const sp = clamp((P.v - 30) / 45, 0, 1);
  // Verfolgerkamera: im Hochformat höher und weiter hinten, damit man mehr Straße sieht
  cam.x = lerp(cam.x, P.x * 0.8, 1 - Math.exp(-dt * 4));
  camPos.set(cam.x, lerp(5.4, 2.6, t) + sp * 0.15, lerp(10.2, 6.6, t) + sp);
  camLook.set(P.x * 0.9, lerp(0.2, 0.9, t), -lerp(24, 11, t));
  let fov = lerp(72, 56, t) + sp * 9;

  // Menü: Kamera kreist um das Auto
  const b = game.camBlend * game.camBlend * (3 - 2 * game.camBlend);
  if (b < 1) {
    cam.orbit += dt * 0.14;
    const r = lerp(11.5, 8.5, t);
    const ox = P.x + Math.sin(cam.orbit) * r, oz = Math.cos(cam.orbit) * r;
    camPos.set(lerp(ox, camPos.x, b), lerp(lerp(3.6, 2.1, t), camPos.y, b), lerp(oz, camPos.z, b));
    camLook.set(lerp(P.x, camLook.x, b), lerp(lerp(-1.2, 0.5, t), camLook.y, b), lerp(0, camLook.z, b));
    fov = lerp(lerp(58, 48, t), fov, b);
  }
  camera.position.copy(camPos);
  const shake = game.shake + smoothstep(58, 83, P.v) * 0.025 * b;
  if (shake > 0) {
    camera.position.x += (Math.random() - 0.5) * shake;
    camera.position.y += (Math.random() - 0.5) * shake;
  }
  camera.lookAt(camLook);
  camera.rotateZ(-P.steer * 0.015 * b);
  if (Math.abs(camera.fov - fov) > 0.01) {
    camera.fov = fov;
    camera.updateProjectionMatrix();
  }
}

// ---------------------------------------------------------------- Fahrphysik Spieler
function updatePlayer(dt) {
  const base = baseSpeed(game.time);
  let target = base;
  if (input.gas) target = Math.min(MAX_V, base + 60 * KMH);
  if (input.brake) target = 55 * KMH;
  const dv = target - P.v;
  let a = dv > 0
    ? Math.min(dv * 2, (input.gas ? 8 : 5) * Math.max(0.2, 1 - P.v / 95))
    : Math.max(dv * 2.5, input.brake ? -11 : -4);
  if (game.scrape) a -= 6;
  P.v = Math.max(0, P.v + a * dt);
  P.accel = lerp(P.accel, a, 1 - Math.exp(-dt * 6));
  P.braking = input.brake;

  // Querbewegung: bei höherem Tempo schnellere Spurwechsel
  const maxLat = 4.2 + Math.min(P.v, 70) * 0.06;
  const prevVx = P.vx;
  P.vx += (input.steer * maxLat - P.vx) * Math.min(1, dt * 7);
  P.x += P.vx * dt;
  game.scrape = 0;
  if (P.x < PLAYER_BOUNDS.min || P.x > PLAYER_BOUNDS.max) {
    const side = P.x < PLAYER_BOUNDS.min ? -1 : 1;
    P.x = clamp(P.x, PLAYER_BOUNDS.min, PLAYER_BOUNDS.max);
    if (P.vx * side > 0) P.vx = -side * 0.8; // von Leitplanke/Schutzwand abprallen
    game.scrape = side;
  }
  const latAcc = (P.vx - prevVx) / Math.max(dt, 1e-3);
  P.yaw = -Math.atan2(P.vx, Math.max(P.v, 5));
  P.roll = lerp(P.roll, clamp(latAcc * 0.004, -0.05, 0.05), 1 - Math.exp(-dt * 8));
  P.pitch = lerp(P.pitch, clamp(P.accel * 0.004, -0.035, 0.025), 1 - Math.exp(-dt * 6));
  P.steer = input.steer;
  P.s += P.v * dt;
}

// Im Menü fährt das Auto von selbst (gleiche Logik wie der Verkehr)
function autopilot(dt) {
  const lead = traffic.leader(P, null);
  P.v = Math.max(0, P.v + idm(P.v, 118 * KMH, lead.gap, P.v - lead.v) * dt);
  if (!P.lc && lead.gap < 50 && lead.v < 112 * KMH) {
    for (const l of [P.lane - 1, P.lane + 1]) {
      if (l >= 0 && l <= 3 && traffic.laneSafe(P, l, null)) {
        P.lc = { from: P.lane, to: l };
        break;
      }
    }
  }
  const tx = LANE_X[P.lc ? P.lc.to : P.lane];
  P.vx += (clamp((tx - P.x) * 1.6, -3.2, 3.2) - P.vx) * Math.min(1, dt * 4);
  P.x += P.vx * dt;
  if (P.lc && Math.abs(tx - P.x) < 0.05) {
    P.lane = P.lc.to;
    P.lc = null;
  }
  P.yaw = -Math.atan2(P.vx, Math.max(P.v, 5));
  P.steer = clamp(P.vx / 3, -1, 1) * 0.5;
  P.roll = lerp(P.roll, -P.steer * 0.02, 1 - Math.exp(-dt * 4));
  P.pitch = lerp(P.pitch, 0, 1 - Math.exp(-dt * 4));
  P.braking = lead.gap < 25;
  P.s += P.v * dt;
}

// ---------------------------------------------------------------- Spielablauf
function updatePlaying(dt) {
  game.time += dt;
  const s0 = P.s;
  updatePlayer(dt);
  game.dist += P.s - s0;
  game.top = Math.max(game.top, P.v);
  traffic.update(dt, P, { active: true, difficulty: Math.min(1, game.time / 180) });
  const ev = traffic.events;
  for (const w of ev.whoosh) audio.whoosh(w.pan, w.vol, w.heavy);
  for (const gap of ev.near) nearMiss(gap);
  if (ev.crash) {
    crash(ev.crash);
    return;
  }
  game.score += (P.v * dt) / 5;
  if (game.comboT > 0 && (game.comboT -= dt) <= 0) game.combo = 0;

  // Schleifen an Leitplanke/Schutzwand
  audio.setScrape(game.scrape ? 1 : 0);
  if (game.scrape) {
    game.shake = Math.max(game.shake, 0.1);
    const x = P.x + game.scrape * P.W * 0.5;
    for (let i = 0; i < 3; i++) {
      sparks.spawn(x, rand(0.25, 0.6), rand(-2, 1.5), -game.scrape * rand(0.5, 2), rand(1, 3), rand(2, 9),
        rand(0.25, 0.5), 0.1, 0.04, 1, rand(0.55, 0.8), 0.25, 1);
    }
  }
  // Reifenqualm bei Vollbremsung
  if (P.braking && P.v > 15 && Math.random() < dt * 25) {
    const g = lerp(0.75, 0.2, sky.night);
    for (const sx of [-0.8, 0.8]) smoke.spawn(P.x + sx, 0.25, 1.3, rand(-0.3, 0.3), rand(0.2, 0.6), rand(0, 2), rand(0.8, 1.4), 0.5, 2.2, g, g, g, 0.25);
  }
}

function nearMiss(gap) {
  game.combo = game.comboT > 0 ? Math.min(game.combo + 1, 5) : 1;
  game.comboT = 4;
  const pts = Math.round((60 + (1.1 - gap) * 120) / 10) * 10 * game.combo;
  game.score += pts;
  game.near++;
  ui.popup.innerHTML = `KNAPP! +${pts}${game.combo > 1 ? ` <span>×${game.combo}</span>` : ''}`;
  ui.popup.classList.remove('show');
  void ui.popup.offsetWidth; // Animation neu starten
  ui.popup.classList.add('show');
  audio.nearMiss(game.combo);
}

function crash(v) {
  game.state = 'crash';
  game.crashT = 0;
  traffic.hit(v, P);
  const side = Math.sign(P.x - v.x) || (Math.random() < 0.5 ? -1 : 1);
  P.spin = -side * rand(1.2, 2.2);
  P.lat = side * rand(2, 4);
  P.v *= v.s > P.s ? 0.45 : 0.8;
  game.shake = 0.6;
  audio.crash();
  audio.setScrape(0);
  const cx = (P.x + v.x) / 2;
  const cz = clamp(v.z + (v.z < 0 ? v.L / 2 : -v.L / 2), -P.L / 2, P.L / 2);
  for (let i = 0; i < 70; i++) {
    sparks.spawn(cx, rand(0.3, 1), cz, rand(-6, 6), rand(1, 6), rand(-4, 8), rand(0.3, 0.8), 0.12, 0.05, 1, rand(0.5, 0.8), 0.2, 1);
  }
  const g = lerp(0.7, 0.15, sky.night);
  for (let i = 0; i < 22; i++) {
    smoke.spawn(cx + rand(-1, 1), rand(0.3, 1.2), cz + rand(-1.5, 1.5), rand(-1.5, 1.5), rand(0.5, 2), rand(-1, 1),
      rand(1.5, 3), 1.2, 4.5, g, g, g, 0.55);
  }
  if (navigator.vibrate) navigator.vibrate(200);
}

function updateCrashed(dt) {
  P.v = Math.max(0, P.v - 12 * dt);
  P.yaw += P.spin * dt;
  P.spin *= Math.max(0, 1 - 1.6 * dt);
  P.x = clamp(P.x + P.lat * dt, PLAYER_BOUNDS.min, PLAYER_BOUNDS.max);
  P.lat *= Math.max(0, 1 - 2.5 * dt);
  P.roll *= 0.95;
  P.pitch *= 0.95;
  P.steer *= 0.9;
  P.braking = true;
  P.s += P.v * dt;
  traffic.update(dt, P, { active: false, difficulty: Math.min(1, game.time / 180) });
  // Rauch aus dem Motorraum
  if (Math.random() < dt * 12) {
    const g = lerp(0.6, 0.12, sky.night);
    smoke.spawn(P.x - 1.6 * Math.sin(P.yaw), 0.9, -1.6 * Math.cos(P.yaw), rand(-0.3, 0.3), rand(1, 2), rand(-0.3, 0.3),
      rand(2, 3.5), 0.8, 3.5, g, g, g, 0.45);
  }
  game.crashT += dt;
  if (game.state === 'crash' && game.crashT > 1.4) gameOver();
}

function resetDrive() {
  Object.assign(P, { x: LANE_X[2], lane: 2, lc: null, v: 118 * KMH, vx: 0, yaw: 0, roll: 0, pitch: 0, accel: 0, steer: 0, spin: 0, lat: 0, braking: false });
  cam.x = P.x;
  smoke.clear();
  sparks.clear();
}

function startGame() {
  audio.init();
  audio.setEnabled(settings.sound === 'on');
  audio.resume();
  input.mode = settings.control === 'tilt' && isTouch ? 'tilt' : 'touch';
  input.reset();
  input.calibrate();
  // Vom Menü aus fährt man direkt los; nach einem Crash wird die Straße neu aufgebaut
  if (game.state !== 'menu') {
    resetDrive();
    traffic.populate(P);
  }
  Object.assign(game, { time: 0, score: 0, dist: 0, near: 0, combo: 0, comboT: 0, top: 0, crashT: 0, shake: 0, scrape: 0 });
  sky.reset();
  game.state = 'playing';
  show(ui.menu, false);
  show(ui.over, false);
  show(ui.pause, false);
  show(ui.hud, true);
  show(ui.pedals, isTouch);
  ui.hint.textContent = !isTouch
    ? '← → lenken · ↑ Gas · ↓ Bremse · P Pause'
    : input.mode === 'tilt' ? 'Handy neigen zum Lenken · Gas und Bremse unten' : 'Links/rechts halten zum Lenken';
  ui.hint.classList.add('show');
  game.hintT = 4;
}

function gameOver() {
  game.state = 'over';
  const score = Math.floor(game.score);
  const record = score > best;
  if (record) {
    best = score;
    try {
      localStorage.setItem(BEST_KEY, String(best));
    } catch { /* privater Modus */ }
  }
  ui.overScore.textContent = score;
  ui.overRecord.textContent = record ? 'Neuer Highscore!' : `Highscore: ${best}`;
  ui.overRecord.classList.toggle('record', record);
  ui.statDist.textContent = `${(game.dist / 1000).toFixed(1).replace('.', ',')} km`;
  ui.statTop.textContent = `${Math.round(game.top * 3.6)} km/h`;
  ui.statNear.textContent = game.near;
  show(ui.hud, false);
  show(ui.over, true);
}

function toMenu() {
  game.state = 'menu';
  resetDrive();
  traffic.populate(P, 60);
  sky.reset();
  audio.update(0, 0, false);
  audio.setScrape(0);
  show(ui.pause, false);
  show(ui.over, false);
  show(ui.hud, false);
  show(ui.menu, true);
  ui.menuBest.textContent = best > 0 ? `Highscore: ${best}` : '';
}

function pauseGame() {
  if (game.state !== 'playing') return;
  game.state = 'paused';
  input.reset();
  audio.suspend();
  show(ui.pause, true);
}

function resumeGame() {
  if (game.state !== 'paused') return;
  game.state = 'playing';
  show(ui.pause, false);
  audio.resume();
  input.calibrate();
  last = performance.now();
}

function togglePause() {
  if (game.state === 'playing') pauseGame();
  else if (game.state === 'paused') resumeGame();
}

// Automatisch pausieren, wenn Tab oder App in den Hintergrund gehen
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    pauseGame();
    audio.suspend();
  }
});
window.addEventListener('pagehide', pauseGame);
window.addEventListener('blur', pauseGame);

// ---------------------------------------------------------------- Darstellung pro Frame
function updateScene(dt, shift) {
  game.clock += dt;
  updateCamera(dt);
  sky.update(dt, camera, game.state !== 'menu');
  world.update(P.s, sky.night);
  player.update(dt, { x: P.x, yaw: P.yaw, roll: P.roll, pitch: P.pitch, steer: P.steer, v: P.v, braking: P.braking, night: sky.night });

  trafficRenderer.begin();
  glows.begin();
  for (const v of traffic.list) trafficRenderer.add(v, glows, sky.night, game.clock);
  for (const o of traffic.oncoming) trafficRenderer.add(o, glows, sky.night, game.clock);
  trafficRenderer.end();
  if (sky.night > 0.02) {
    const k = sky.night * 1.1;
    world.forEachLampHead((x, y, z) => glows.push(x, y, z, k, k * 0.88, k * 0.7, 3.4));
  }
  player.pushGlows(glows, sky.night, P.braking);
  const scale = renderer.domElement.height / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
  const fog = scene.fog.density;
  glows.end(scale, fog);
  smoke.update(dt, shift, scale, fog);
  sparks.update(dt, shift, scale, fog);
  wind.update(dt, game.state === 'playing' ? P.v : 0, camera, 1 - sky.night * 0.6);
}

function render() {
  if (quality.bloom) {
    bloom.strength = lerp(0.2, 0.7, sky.night);
    bloom.threshold = lerp(1.25, 0.75, sky.night);
    composer.render();
  } else {
    renderer.render(scene, camera);
  }
}

function updateHud(dt) {
  if (game.hintT > 0 && (game.hintT -= dt) <= 0) ui.hint.classList.remove('show');
  if ((game.hudT -= dt) > 0) return;
  game.hudT = 0.1;
  const score = Math.floor(game.score);
  ui.score.textContent = score;
  ui.best.textContent = `HI ${Math.max(best, score)}`;
  ui.speed.textContent = Math.round(P.v * 3.6);
}

let last = performance.now();
function frame(now) {
  requestAnimationFrame(frame);
  const raw = Math.max(0, (now - last) / 1000);
  last = now;
  if (game.state === 'paused' || game.state === 'loading') return;
  const dt = Math.min(raw, 0.05);
  perfSample(raw);
  input.update(dt);
  const s0 = P.s;
  if (game.state === 'playing') updatePlaying(dt);
  else if (game.state === 'menu') {
    autopilot(dt);
    traffic.update(dt, P, { active: false, difficulty: 0.15 });
  } else updateCrashed(dt);
  game.shake = Math.max(0, game.shake - dt * 1.2);
  game.camBlend = approach(game.camBlend, game.state === 'menu' ? 0 : 1, dt / 1.2);
  updateScene(dt, P.s - s0);
  const throttle = input.gas ? 1 : input.brake ? 0.05 : 0.45;
  audio.update(P.v * 3.6, throttle, game.state === 'playing');
  updateHud(dt);
  render();
}

// ---------------------------------------------------------------- Menü und Einstellungen
function bindSetting(name, onChange) {
  const buttons = document.querySelectorAll(`[data-setting="${name}"] button`);
  const sync = () => buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.value === settings[name])));
  buttons.forEach(b => b.addEventListener('click', async () => {
    if ((await onChange(b.dataset.value)) === false) return;
    settings[name] = b.dataset.value;
    saveSettings();
    sync();
  }));
  sync();
}

function soundIcon() {
  ui.soundBtn.classList.toggle('muted', settings.sound !== 'on');
  ui.soundBtn.setAttribute('aria-label', settings.sound === 'on' ? 'Ton ausschalten' : 'Ton einschalten');
}

function setupUi() {
  $('startBtn').addEventListener('click', startGame);
  $('againBtn').addEventListener('click', startGame);
  $('resumeBtn').addEventListener('click', resumeGame);
  $('restartBtn').addEventListener('click', () => {
    game.state = 'over';
    startGame();
  });
  $('menuBtn').addEventListener('click', toMenu);
  $('overMenuBtn').addEventListener('click', toMenu);
  $('pauseBtn').addEventListener('click', togglePause);
  ui.soundBtn.addEventListener('click', () => {
    settings.sound = settings.sound === 'on' ? 'off' : 'on';
    saveSettings();
    audio.setEnabled(settings.sound === 'on');
    soundIcon();
    document.querySelectorAll('[data-setting="sound"] button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.value === settings.sound)));
  });

  bindSetting('sound', v => {
    audio.setEnabled(v === 'on');
    settings.sound = v;
    soundIcon();
  });
  bindSetting('quality', v => {
    settings.quality = v;
    quality.scale = 1;
    applyQuality(levelFromSetting());
  });
  bindSetting('control', async v => {
    show(ui.tiltNote, false);
    if (v !== 'tilt') return true;
    const ok = await input.requestTilt();
    if (!ok) {
      ui.tiltNote.textContent = 'Der Neigungssensor ist nicht verfügbar oder wurde nicht erlaubt. Es bleibt bei Tippen.';
      show(ui.tiltNote, true);
      return false;
    }
    return true;
  });
  if (!isTouch) {
    show($('controlRow'), false);
    settings.control = 'touch';
  }
  $('controlsHelp').textContent = isTouch
    ? 'Links/rechts halten zum Lenken (oder Handy neigen) · Gas und Bremse unten · Das Auto fährt von selbst.'
    : 'Pfeiltasten ← → lenken · ↑ Gas · ↓ Bremse · P oder Esc: Pause';
  ui.menuBest.textContent = best > 0 ? `Highscore: ${best}` : '';
  soundIcon();
}

// ---------------------------------------------------------------- Start
function init() {
  setupUi();
  quality.level = levelFromSetting();
  applyQuality(quality.level);
  world.reset(P.s);
  traffic.populate(P, 60);
  sky.reset();
  updateCamera(1 / 60);
  sky.update(0, camera, false);
  world.update(P.s, sky.night);
  renderer.compile(scene, camera);
  game.state = 'menu';
  show(ui.loading, false);
  show(ui.menu, true);
  window.__hd3dReady = true;
  last = performance.now();
  requestAnimationFrame(frame);
}

canvas.addEventListener('webglcontextlost', e => {
  e.preventDefault();
  game.state = 'paused';
  window.__hd3dFail?.('Die Grafikkarte hat das Spiel unterbrochen. Bitte lade die Seite neu.');
});

// Für Tests: ?debug blendet Hilfsfunktionen ein (z. B. Tageszeit setzen)
if (new URLSearchParams(location.search).has('debug')) {
  window.hd3d = {
    game, P, sky, traffic, renderer, quality, applyQuality,
    setElevation: e => {
      sky.angle = Math.PI - Math.asin(clamp(e / 48, -1, 1));
      sky.apply();
      sky.updateEnvironment();
    },
  };
}

init();
