// Neon Haven – Open World (Phase 1: Fahrphysik, Steuerung, Kameras, Testgelände).

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { VehicleLibrary } from '../src/vehicles/VehicleLibrary.js';
import { defaultTuning } from '../src/vehicles/Vehicle.js';
import { Settings, QUALITY } from '../src/vehicles/settings.js';
import { CarPhysics } from '../src/physics/CarPhysics.js';
import { Collisions, carShape } from '../src/physics/collision.js';
import { World } from '../src/world/World.js';
import { Input } from '../src/game/input.js';
import { CameraRig, CAMERAS } from '../src/game/cameras.js';
import { Hud } from '../src/game/hud.js';
import { SkySystem } from '../src/game/sky.js';
import { CarAudio } from '../src/game/audio.js';

const $ = (id) => document.getElementById(id);
const TUNE_KEY = 'neonHaven.tuning.v1';
const CAR_ORDER = ['vektra_gt', 'brawler_77', 'ion_spectre', 'rhino_x', 'pulse', 'aurelion_s'];

// ----------------------------------------------------------------------------- Grundgerüst
const settings = new Settings();
let Q = QUALITY[settings.resolvedQuality()];
const canvas = $('view');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: Q.antialias, powerPreference: 'high-performance' });
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.info.autoReset = false;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 3500);
const sky = new SkySystem(renderer, scene);
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.25, 0.45, 0.9);
composer.addPass(bloom);
composer.addPass(new OutputPass());

const lib = new VehicleLibrary('../models/', renderer);
const input = new Input({ steerMode: settings.get('touchSteer'), sensitivity: settings.get('steerSens') });
const rig = new CameraRig(camera);
rig.setMode(settings.get('camera'));
const hud = new Hud($('hud'));
const audio = new CarAudio();
audio.setVolume(settings.get('volume'));

let world = null;
let collisions = null;
let car = null;           // Vehicle (Grafik)
let phys = null;          // CarPhysics
let colEntry = null;
let started = false;
let paused = false;
let hours = settings.get('timeOfDay');
let lightsOn = false;
let lightsManual = false;
let carLoading = false;

// ----------------------------------------------------------------------------- Größe, Qualität, Look
function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  const pr = Math.min(window.devicePixelRatio || 1, Q.pixelRatio);
  renderer.setPixelRatio(pr);
  renderer.setSize(w, h, false);
  composer.setPixelRatio(pr);
  composer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);

function applyQuality() {
  Q = QUALITY[settings.resolvedQuality()];
  renderer.shadowMap.enabled = Q.shadows;
  sky.sun.castShadow = Q.shadows;
  if (Q.shadows) {
    sky.sun.shadow.mapSize.set(Q.shadowSize, Q.shadowSize);
    if (sky.sun.shadow.map) { sky.sun.shadow.map.dispose(); sky.sun.shadow.map = null; }
    sky.setShadowRange(Q.shadowSize >= 2048 ? 48 : 34);
  }
  resize();
  if (car) car.setQuality(Q);
  scene.traverse((o) => { if (o.material && !Array.isArray(o.material)) o.material.needsUpdate = true; });
}

function applyLook() {
  const n = sky.nightK;
  renderer.toneMappingExposure = settings.get('exposure') * (1 + 0.75 * n);
  bloom.threshold = 0.95 - 0.35 * n;
  bloom.strength = 0.18 + 0.45 * n;
  bloom.radius = 0.5;
}

function setTime(h, force = false) {
  hours = ((h % 24) + 24) % 24;
  sky.setTime(hours, force);
  if (world) world.setNight(sky.nightK);
  if (car) {
    car.setNight(sky.nightK > 0.5);
    if (!lightsManual) setLights(sky.nightK > 0.35, false);
  }
  applyLook();
}

function setLights(on, manual = true) {
  lightsOn = on;
  if (manual) lightsManual = true;
  if (car) car.setLights(on);
  $('bLights').classList.toggle('on', on);
}

// ----------------------------------------------------------------------------- Tuning aus der Garage
function savedTuning(id) {
  try { return (JSON.parse(localStorage.getItem(TUNE_KEY) || '{}') || {})[id] || null; } catch (e) { return null; }
}

// ----------------------------------------------------------------------------- Auto laden / wechseln
async function spawnCar(id, at, onProgress) {
  if (carLoading) return;
  carLoading = true;
  try {
    const meta = lib.byId[id] || lib.cars[0];
    const v = await lib.create(meta.id, onProgress);
    const keep = phys && !at ? { x: phys.pos.x, z: phys.pos.z, yaw: phys.yaw } : null;
    if (car) car.dispose();
    if (colEntry) collisions.remove(colEntry);
    car = v;
    scene.add(car.object);
    car.setQuality(Q);
    car.applyTuning({ ...defaultTuning(meta), ...(savedTuning(meta.id) || {}) });
    car.setInteriorLight(settings.get('interiorLight'));
    car.setDisplayBrightness(settings.get('displayBrightness'));
    car.createHeadLamps();
    car.createCabinLight();
    car.forcedLod = settings.get('lodMode') === 'auto' ? null : Number(settings.get('lodMode'));
    car.setNight(sky.nightK > 0.5);
    car.setLights(lightsOn);
    phys = new CarPhysics(meta, { assists: settings.get('assists') });
    phys.applyTuning(car.tuning);
    const p = at || keep || world.spawns[0];
    phys.place(p.x, p.z, p.yaw || 0, world.groundHeight(p.x, p.z));
    colEntry = collisions.add(phys, carShape(meta, phys.zcg));
    audio.setCar(meta, car.tuning);
    hud.setAccent(meta.defaultAccent || '#00e5ff');
    document.documentElement.style.setProperty('--accent', meta.defaultAccent || '#00e5ff');
    rig.snap();
    car.syncPhysics(phys, {});
    try { localStorage.setItem('neonHaven.lastCar', meta.id); } catch (e) { /* egal */ }
    hud.toast(meta.name + ' · ' + Math.round((car.tuning && meta.tuning && meta.tuning.engine && meta.tuning.engine[car.tuning.engine || 0]
      ? meta.tuning.engine[car.tuning.engine || 0].powerKw : meta.stats.powerKw) * 1.36) + ' PS', 2.2);
  } finally {
    carLoading = false;
  }
}

function resetCar(toSpawn = false) {
  if (!phys) return;
  let p;
  if (toSpawn) p = world.spawns[0];
  else p = { x: phys.pos.x, z: phys.pos.z, yaw: phys.yaw };
  phys.place(p.x, p.z, p.yaw, world.groundHeight(p.x, p.z));
  // aus Hindernissen herausschieben
  for (let i = 0; i < 4; i++) collisions.step(null);
  phys.vel.x = phys.vel.z = 0; phys.yawRate = 0;
  rig.snap();
  hud.toast(toSpawn ? 'Zurück zum Start' : 'Auto zurückgesetzt');
}

// ----------------------------------------------------------------------------- Eingaben / Aktionen
let lastPress = 0;
input.addEventListener('action', (e) => {
  const a = e.detail;
  if (a === 'pause') { togglePause(); return; }
  if (!started || paused) return;
  switch (a) {
    case 'camera': nextCamera(); break;
    case 'lights': setLights(!lightsOn); hud.toast(lightsOn ? 'Licht an' : 'Licht aus'); break;
    case 'indicatorLeft': if (car) car.state.indicator = car.state.indicator === -1 ? 0 : -1; break;
    case 'indicatorRight': if (car) car.state.indicator = car.state.indicator === 1 ? 0 : 1; break;
    case 'hazard': if (car) car.state.indicator = car.state.indicator === 2 ? 0 : 2; break;
    case 'horn': audio.horn && audio.horn(); break;
    case 'reset': {
      const now = performance.now();
      resetCar(now - lastPress < 600);     // zweimal schnell = zurück zum Start
      lastPress = now;
      break;
    }
    default: break;
  }
});
input.addEventListener('source', (e) => {
  if (e.detail === 'touch') showTouch(true);
  if (e.detail === 'gamepad' && started) hud.toast('Controller verbunden');
});

function nextCamera() {
  const label = rig.next();
  settings.set('camera', rig.mode);
  hud.toast('Kamera: ' + label);
}

$('bCam').onclick = () => { if (started) nextCamera(); };
$('bLights').onclick = () => { if (started) { setLights(!lightsOn); hud.toast(lightsOn ? 'Licht an' : 'Licht aus'); } };
$('bReset').onclick = () => { if (started) resetCar(false); };
$('bMenu').onclick = () => togglePause();

// Touch-Bedienung
input.bindTouch({ steerZone: $('steerZone'), knob: $('knob'), left: $('tLeft'), right: $('tRight'),
  gas: $('tGas'), brake: $('tBrake'), hand: $('tHand') });
function showTouch(on) {
  $('touch').classList.toggle('hidden', !on);
  applySteerMode();
}
function applySteerMode() {
  const m = settings.get('touchSteer');
  input.steerMode = m;
  $('steerBtns').classList.toggle('hidden', m !== 'buttons');
  $('steerZone').classList.toggle('hidden', m !== 'swipe');
  $('steerHint').textContent = m === 'swipe' ? '← links wischen zum Lenken →' : m === 'tilt' ? 'Handy kippen zum Lenken' : '';
  if (m === 'tilt') input.enableTilt().then((ok) => { if (!ok) hud.toast('Neigungssensor nicht verfügbar'); });
}
if (matchMedia('(pointer: coarse)').matches) showTouch(true);

// Umschauen: Maus/Finger auf dem Bild ziehen
let look = null;
canvas.addEventListener('pointerdown', (e) => { look = { id: e.pointerId, x: e.clientX, y: e.clientY }; });
window.addEventListener('pointermove', (e) => {
  if (!look || e.pointerId !== look.id) return;
  input.addLook(e.clientX - look.x, e.clientY - look.y);
  look.x = e.clientX; look.y = e.clientY;
});
window.addEventListener('pointerup', (e) => { if (look && e.pointerId === look.id) look = null; });

// Auslösen von Vibration/Wackeln/Geräusch bei Aufprall
function onImpact(entry, s) {
  if (!entry || entry !== colEntry) return;
  if (s < 1.2) return;
  rig.addShake(Math.min(0.9, s / 16));
  input.rumble(Math.min(1, s / 12), Math.min(1, s / 8), 90 + Math.min(300, s * 20));
  audio.impact(Math.min(1, s / 18));
}
function onPropHit(k) {
  audio.impact(0.12 + k * 0.2);
  input.rumble(0.1 + k * 0.3, 0.3, 60);
}

// ----------------------------------------------------------------------------- Pause / Menü
function togglePause(force) {
  if (!started) return;
  const dlg = $('menu');
  const open = force !== undefined ? force : !dlg.open;
  if (open && !dlg.open) {
    paused = true; input.enabled = false; audio.suspend();
    buildMenu(currentTab);
    dlg.showModal();
  }
  if (!open && dlg.open) dlg.close();
}
$('menu').addEventListener('close', () => { paused = false; input.enabled = true; audio.resume(); clock.getDelta(); });
$('menu').addEventListener('cancel', (e) => { e.preventDefault(); togglePause(false); });
$('bClose').onclick = () => togglePause(false);

let currentTab = 'drive';
document.querySelectorAll('#tabs .tab').forEach((b) => (b.onclick = () => buildMenu(b.dataset.tab)));

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}
function row(parent, label, value) {
  const r = el('label', 'row');
  r.appendChild(el('span', '', `<span>${label}</span><b>${value || ''}</b>`));
  parent.appendChild(r);
  return r;
}
function opts(parent, list, current, onPick) {
  const box = el('div', 'opts');
  for (const [val, label] of list) {
    const b = el('button', 'opt' + (val === current ? ' active' : ''), label);
    b.type = 'button';
    b.onclick = () => { box.querySelectorAll('.opt').forEach((x) => x.classList.remove('active')); b.classList.add('active'); onPick(val); };
    box.appendChild(b);
  }
  parent.appendChild(box);
  return box;
}
function range(parent, min, max, step, value, onInput) {
  const i = el('input');
  i.type = 'range'; i.min = min; i.max = max; i.step = step; i.value = value;
  i.oninput = () => onInput(Number(i.value));
  parent.appendChild(i);
  return i;
}
function check(parent, label, value, onChange) {
  const r = el('label', 'row check');
  const i = el('input'); i.type = 'checkbox'; i.checked = value;
  i.onchange = () => onChange(i.checked);
  r.appendChild(i); r.appendChild(el('span', '', label));
  parent.appendChild(r);
}
const fmtTime = (h) => `${String(Math.floor(h)).padStart(2, '0')}:${String(Math.floor((h % 1) * 60)).padStart(2, '0')}`;

function buildMenu(tab) {
  currentTab = tab;
  document.querySelectorAll('#tabs .tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  const body = $('menuBody');
  body.innerHTML = '';
  if (tab === 'drive') {
    let r = row(body, 'Fahrhilfen');
    opts(r, [['full', 'Voll (ABS, ASR, ESP)'], ['sport', 'Sport'], ['off', 'Aus']], settings.get('assists'), (v) => settings.set('assists', v));
    body.appendChild(el('p', 'hint', 'Voll: ideal für Touch und Einsteiger. Sport: mehr Rutschen erlaubt. Aus: nur ABS-frei, ' +
      'Driften mit Gas und Handbremse – wie echt.'));
    r = row(body, 'Kamera');
    opts(r, CAMERAS.map((c) => [c.id, c.label]), rig.mode, (v) => { rig.setMode(v); settings.set('camera', v); });
    r = row(body, 'Touch-Lenkung');
    opts(r, [['swipe', 'Wischen'], ['tilt', 'Neigen'], ['buttons', 'Tasten']], settings.get('touchSteer'), (v) => settings.set('touchSteer', v));
    r = row(body, 'Lenkempfindlichkeit', `<span id="vSens">${Math.round(settings.get('steerSens') * 100)} %</span>`);
    range(r, 50, 150, 5, Math.round(settings.get('steerSens') * 100), (v) => { $('vSens').textContent = v + ' %'; settings.set('steerSens', v / 100); });
    r = row(body, 'Ort');
    opts(r, world.spawns.map((s, i) => [i, s.name]), -1, (i) => { resetAt(world.spawns[i]); togglePause(false); });
  } else if (tab === 'car') {
    const box = el('div', 'cars');
    for (const id of CAR_ORDER) {
      const m = lib.byId[id];
      if (!m) continue;
      const b = el('button', 'car' + (car && car.meta.id === id ? ' active' : ''), `<b>${m.name}</b><span>${m.class || ''} · ${m.stats.drive}</span>`);
      b.type = 'button';
      b.style.borderLeft = `3px solid ${m.defaultAccent}`;
      b.onclick = async () => {
        box.querySelectorAll('.car').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        await spawnCar(id, null);
        togglePause(false);
      };
      box.appendChild(b);
    }
    body.appendChild(box);
    body.appendChild(el('p', 'hint', 'Lack, Felgen, Motor, Auspuff und Käfig stellst du in der Garage ein – das Tuning gilt dann auch hier ' +
      '(mehr Leistung, Käfig = mehr Gewicht, Tieferlegung = tieferer Schwerpunkt).'));
    const a = el('a', 'opt primary', 'Garage öffnen');
    a.href = '../garage/index.html';
    body.appendChild(a);
    if (car) {
      const m = car.meta, t = car.tuning;
      const eng = m.tuning && m.tuning.engine && m.tuning.engine[t.engine || 0];
      body.appendChild(el('p', 'hint', `Aktuell: ${m.name} · ${eng ? eng.name : 'Serie'} · ${Math.round(phys.powerW / 1000 * 1.36)} PS · ` +
        `${Math.round(phys.mass)} kg · ${m.stats.drive}`));
    }
  } else if (tab === 'world') {
    let r = row(body, 'Tageszeit', `<span id="vTime">${fmtTime(hours)}</span>`);
    range(r, 0, 23.99, 0.05, hours, (v) => { $('vTime').textContent = fmtTime(v); setTime(v); settings.set('timeOfDay', v); });
    check(body, 'Zeit läuft weiter (ein Tag = 24 Minuten)', settings.get('timeFlow'), (v) => settings.set('timeFlow', v));
    body.appendChild(el('p', 'hint', 'Nachts gehen Straßenlaternen, Fenster und Neon an; die Scheinwerfer schalten sich in der Dämmerung ' +
      'automatisch ein (Taste L / Controller X schaltet von Hand). Regen und die Stadt folgen in den nächsten Schritten.'));
    const b = el('button', 'opt', 'Pylonen wieder aufstellen');
    b.type = 'button';
    b.onclick = () => { if (world.props) world.props.resetAll(); };
    body.appendChild(b);
  } else if (tab === 'gfx') {
    let r = row(body, 'Lautstärke', `<span id="vVol">${Math.round(settings.get('volume') * 100)} %</span>`);
    range(r, 0, 100, 1, Math.round(settings.get('volume') * 100), (v) => { $('vVol').textContent = v + ' %'; settings.set('volume', v / 100); });
    r = row(body, 'Grafikqualität');
    opts(r, [['auto', 'Automatisch'], ['low', 'Niedrig'], ['medium', 'Mittel'], ['high', 'Hoch']], settings.get('quality'), (v) => settings.set('quality', v));
    r = row(body, 'Belichtung', `<span id="vExp">${settings.get('exposure').toFixed(2)}</span>`);
    range(r, 50, 160, 1, Math.round(settings.get('exposure') * 100), (v) => { $('vExp').textContent = (v / 100).toFixed(2); settings.set('exposure', v / 100); });
    r = row(body, 'Innenraumbeleuchtung', `<span id="vIl">${Math.round(settings.get('interiorLight') * 100)} %</span>`);
    range(r, 0, 100, 1, Math.round(settings.get('interiorLight') * 100), (v) => { $('vIl').textContent = v + ' %'; settings.set('interiorLight', v / 100); });
    r = row(body, 'Displays & Instrumente', `<span id="vDb">${Math.round(settings.get('displayBrightness') * 100)} %</span>`);
    range(r, 0, 100, 1, Math.round(settings.get('displayBrightness') * 100), (v) => { $('vDb').textContent = v + ' %'; settings.set('displayBrightness', v / 100); });
    check(body, 'Leuchteffekt (Bloom)', settings.get('bloom'), (v) => settings.set('bloom', v));
    check(body, 'Leistungsanzeige (FPS)', settings.get('showFps'), (v) => settings.set('showFps', v));
  } else if (tab === 'help') {
    body.innerHTML = `<table>
      <tr><td>Gas / Bremse</td><td>W, S · Pfeiltasten · RT, LT · Touch rechts</td></tr>
      <tr><td>Rückwärts</td><td>im Stand Bremse halten, dann Bremse = rückwärts fahren</td></tr>
      <tr><td>Lenken</td><td>A, D · linker Stick · Touch links wischen / kippen / Tasten</td></tr>
      <tr><td>Handbremse</td><td>Leertaste · A · Touch HANDBREMSE</td></tr>
      <tr><td>Kamera</td><td>C · Y · Kamera-Knopf oben (Verfolger, weit, Haube, Stoßstange, Cockpit)</td></tr>
      <tr><td>Umschauen</td><td>Maus/Finger ziehen · rechter Stick · nach hinten: B (Taste und Controller)</td></tr>
      <tr><td>Licht, Blinker</td><td>L · X · Q/E · LB/RB · Warnblinker X-Taste bzw. Steuerkreuz unten</td></tr>
      <tr><td>Zurücksetzen</td><td>R · Ansicht-Taste · zweimal schnell = zurück zum Start</td></tr>
      <tr><td>Menü</td><td>Esc, P · Menü-Taste</td></tr></table>
      <p class="hint">Fahrphysik: echtes Reifenmodell (Schlupf, Schräglauf), Gewichtsverlagerung über die Federung,
      Getriebe, Differenzial. Mit „Fahrhilfen: Voll“ regeln ABS, ASR und ESP – die Lampen unten leuchten, wenn sie eingreifen.</p>`;
  }
}

function resetAt(p) {
  phys.place(p.x, p.z, p.yaw || 0, world.groundHeight(p.x, p.z));
  rig.snap();
}

settings.addEventListener('change', (e) => {
  const { key, value } = e.detail;
  if (key === 'quality') applyQuality();
  if (key === 'exposure') applyLook();
  if (key === 'assists' && phys) phys.setAssists(value);
  if (key === 'touchSteer') applySteerMode();
  if (key === 'steerSens') input.sensitivity = value;
  if (key === 'volume') audio.setVolume(value);
  if (key === 'interiorLight' && car) car.setInteriorLight(value);
  if (key === 'displayBrightness' && car) car.setDisplayBrightness(value);
  if (key === 'showFps') $('perf').classList.toggle('hidden', !value);
  if (key === 'lodMode' && car) car.forcedLod = value === 'auto' ? null : Number(value);
});

// ----------------------------------------------------------------------------- Hauptschleife
const clock = new THREE.Clock();
let fpsAcc = 0, fpsFrames = 0;
let zoneShown = '';
let timeSaveT = 0;
const STEP = 1 / 120;

function frame() {
  requestAnimationFrame(frame);
  renderer.info.reset();
  const dt = Math.min(0.05, clock.getDelta());
  const t = clock.elapsedTime;
  if (!world || !car || !phys) { renderer.render(scene, camera); return; }
  const inp = input.update(dt, phys.speedKmh);
  if (started && !paused) {
    // Physik und Kollisionen in kleinen Schritten (kein Durchtunneln bei Tempo 300)
    const n = Math.max(1, Math.ceil(dt / STEP));
    const h = dt / n;
    for (let i = 0; i < n; i++) {
      phys.step(h, inp, world);
      collisions.step(onImpact);
    }
    world.update(dt, [colEntry], phys.pos, onPropHit);
    if (settings.get('timeFlow')) {
      setTime(hours + dt / 60);            // 24 Minuten je Tag
      timeSaveT += dt;
      if (timeSaveT > 5) { timeSaveT = 0; settings.set('timeOfDay', hours); }
    }
  }
  car.syncPhysics(phys, started && !paused ? inp : {});
  car.update(dt, t);
  car.updateLOD(camera, Q.lodDistances, rig.attached);
  rig.update(dt, car, phys, started && !paused ? inp : { lookX: 0, lookY: 0, lookBack: false }, camera.aspect);
  sky.follow(phys.pos);
  hud.update(dt, phys);
  audio.update(dt, phys, started && !paused ? inp : {});
  const zone = world.zoneAt(phys.pos.x, phys.pos.z) || world.meta.name;
  if (zone !== zoneShown) { zoneShown = zone; $('zone').textContent = zone === world.meta.name ? zone : world.meta.name + ' · ' + zone; }

  if (settings.get('bloom') && Q.bloom) composer.render(dt);
  else renderer.render(scene, camera);

  fpsAcc += dt; fpsFrames++;
  if (fpsAcc > 0.5) {
    if (settings.get('showFps')) {
      const info = renderer.info.render;
      $('perf').textContent = `${(fpsFrames / fpsAcc).toFixed(0)} FPS  ${settings.resolvedQuality()}\n` +
        `${Math.round(info.triangles / 1000)} k Dreiecke  ${info.calls} Draw Calls\n` +
        `LOD ${car.lodLevel}  ${phys.speedKmh.toFixed(0)} km/h  ${(phys.accLat / 9.81).toFixed(2)} g quer`;
    }
    fpsAcc = 0; fpsFrames = 0;
  }
}

// ----------------------------------------------------------------------------- Start
async function boot() {
  applyQuality();
  setTime(hours, true);
  $('perf').classList.toggle('hidden', !settings.get('showFps'));
  const bar = $('loadBar'), info = $('loadInfo');
  const prog = (a, b) => (f) => { bar.style.width = Math.round((a + (b - a) * f) * 100) + '%'; };
  try {
    info.textContent = 'Fahrzeuge …';
    await lib.init();
    info.textContent = 'Testgelände wird geladen …';
    world = await World.load('../world/', 'testgelaende', renderer, prog(0, 0.4));
    scene.add(world.object);
    sky.setFog(world.meta.env && world.meta.env.fogNear || 250, world.meta.env && world.meta.env.fogFar || 1700);
    collisions = new Collisions(world.statics);
    rig.world = world.statics;
    let id = null;
    try { id = localStorage.getItem('neonHaven.lastCar'); } catch (e) { /* egal */ }
    if (!id || !lib.byId[id]) id = CAR_ORDER[0];
    info.textContent = (lib.byId[id] ? lib.byId[id].name : 'Auto') + ' wird geladen …';
    await spawnCar(id, world.spawns[0], prog(0.4, 1));
    setTime(hours, true);
    if (sky.nightK > 0.35) setLights(true, false);
  } catch (e) {
    console.error(e);
    info.textContent = 'Fehler beim Laden: ' + e.message + ' – bitte über einen Webserver öffnen (siehe README).';
    return;
  }
  bar.style.width = '100%';
  info.textContent = 'Bereit.';
  const go = $('bGo');
  go.disabled = false;
  go.focus();
  const begin = async () => {
    if (started) return;
    started = true;
    $('start').classList.add('hidden');
    await audio.start();
    audio.setVolume(settings.get('volume'));
    clock.getDelta();
    hud.toast('Kamera: ' + rig.label, 1.4);
  };
  go.onclick = begin;
  window.addEventListener('keydown', (e) => { if (!started && !go.disabled && (e.code === 'Enter' || e.code === 'Space')) begin(); });
  // Controller: A startet
  const padWait = () => {
    if (started) return;
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (const p of pads) if (p && p.buttons[0] && p.buttons[0].pressed) { begin(); return; }
    requestAnimationFrame(padWait);
  };
  padWait();
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) { audio.suspend(); if (started && !paused) togglePause(true); }
});

// Zugriff für die Browser-Konsole und den Rauchtest (tests/smoke)
window.neonHaven = {
  settings, input, rig, sky, hud, audio,
  get world() { return world; }, get car() { return car; }, get phys() { return phys; },
  get started() { return started; }, get paused() { return paused; }, get hours() { return hours; },
  spawnCar, resetCar, setTime,
};

requestAnimationFrame(frame);
boot();
