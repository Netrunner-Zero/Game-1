// Neon Haven – Garage (Showroom zum Ansehen, Tunen und Testen der Fahrzeuge).
// Die offene Spielwelt kommt später; hier werden nur die Autos geprüft.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { VehicleLibrary } from '../src/vehicles/VehicleLibrary.js';
import { Settings, QUALITY } from '../src/vehicles/settings.js';
import { createEnvironment } from '../src/vehicles/environment.js';
import { FINISHES, defaultTuning } from '../src/vehicles/Vehicle.js';

const ROSTER = [
  { id: 'vektra_gt', name: 'Vektra GT', color: '#c8102e' },
  { id: 'brawler_77', name: 'Brawler 77', color: '#f5a300' },
  { id: 'ion_spectre', name: 'Ion Spectre', color: '#e9edf3' },
  { id: 'rhino_x', name: 'Rhino X', color: '#5b6b4e' },
  { id: 'pulse', name: 'Pulse', color: '#1f6fff' },
  { id: 'aurelion_s', name: 'Aurelion S', color: '#1b2a3a' },
];
const PAINTS = ['#c8102e', '#f5a300', '#e9edf3', '#0c0d10', '#1f6fff', '#3d4a3e', '#6a1fd1', '#1b2a3a',
  '#ffcf00', '#ff5a1f', '#18c29c', '#9aa3ad', '#7a0f1c', '#f0e7d8', '#0a3d2e', '#ff2bd6'];
const RIM_COLORS = ['#a3a9b2', '#1d1f23', '#d9dde3', '#c9a45c', '#2f3238', '#7b8088', '#b31b1b', '#00a9c4'];
const CALIPERS = ['#c8102e', '#f0b400', '#1f6fff', '#1d1f23', '#e9edf3', '#18c29c', '#ff5a1f', '#b0b4bb'];
const NEON = ['#00e5ff', '#ff2bd6', '#b6ff00', '#ff8a00', '#7a5cff', '#ff1f3d', '#ffffff', '#00ff9c'];
const AMBIENT = ['#ff3040', '#00e5ff', '#ff2bd6', '#ffb26b', '#7a5cff', '#b6ff00', '#ffffff', '#3a7bff'];
const TUNE_KEY = 'neonHaven.tuning.v1';

// ----------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const settings = new Settings();
let Q = QUALITY[settings.resolvedQuality()];

const canvas = $('view');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: Q.antialias, powerPreference: 'high-performance' });
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.info.autoReset = false;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 400);
camera.position.set(5.6, 1.9, 6.2);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.target.set(0, 0.55, 0);
controls.minDistance = 2.6;
controls.maxDistance = 16;
controls.maxPolarAngle = THREE.MathUtils.degToRad(87);
controls.enablePan = false;

const composer = new EffectComposer(renderer);
const renderPass = new RenderPass(scene, camera);
const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.25, 0.4, 1.0);
composer.addPass(renderPass);
composer.addPass(bloom);
composer.addPass(new OutputPass());

const lib = new VehicleLibrary('../models/', renderer);
let car = null;
let night = false;
let camMode = 'orbit';
let turntable = true;
const envCache = {};
const look = { yaw: 0, pitch: -0.08 };

// ----------------------------------------------------------------------
// Bühne: Drehteller, Boden, Licht
const stage = new THREE.Group();
scene.add(stage);
const floorMat = new THREE.MeshStandardMaterial({ color: 0x0c0d11, roughness: 0.42, metalness: 0.25 });
const floor = new THREE.Mesh(new THREE.CircleGeometry(40, 64), floorMat);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.045;
floor.receiveShadow = true;
stage.add(floor);
const deckMat = new THREE.MeshStandardMaterial({ color: 0x15171d, roughness: 0.32, metalness: 0.4 });
const deck = new THREE.Mesh(new THREE.CylinderGeometry(3.9, 4.0, 0.08, 96), deckMat);
deck.position.y = -0.04;
deck.receiveShadow = true;
stage.add(deck);
const ringMat = new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0x00e5ff, emissiveIntensity: 1.6 });
const ring = new THREE.Mesh(new THREE.TorusGeometry(3.95, 0.012, 8, 160), ringMat);
ring.rotation.x = Math.PI / 2;
ring.position.y = 0.0;
stage.add(ring);
const grid = new THREE.GridHelper(80, 80, 0x1a2230, 0x10141c);
grid.position.y = -0.044;
grid.material.transparent = true;
grid.material.opacity = 0.35;
stage.add(grid);

const hemi = new THREE.HemisphereLight(0xdfe7ff, 0x14161a, 0.35);
scene.add(hemi);
const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(4.5, 8, 3.5);
key.castShadow = true;
key.shadow.camera.left = -4; key.shadow.camera.right = 4;
key.shadow.camera.top = 4; key.shadow.camera.bottom = -4;
key.shadow.camera.near = 1; key.shadow.camera.far = 20;
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.02;
key.shadow.radius = 4;
scene.add(key);
const nightLights = new THREE.Group();
for (const [c, x, z] of [[0xff2bd6, -5, -4], [0x00e5ff, 5, -3], [0x7a5cff, 0, 6]]) {
  const l = new THREE.PointLight(c, 18, 14, 2);
  l.position.set(x, 2.6, z);
  nightLights.add(l);
}
nightLights.visible = false;
scene.add(nightLights);

// ----------------------------------------------------------------------
function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  const pr = Math.min(window.devicePixelRatio || 1, Q.pixelRatio);
  renderer.setPixelRatio(pr);
  renderer.setSize(w, h, false);
  composer.setPixelRatio(pr);
  composer.setSize(w, h);
  camera.aspect = w / h;
  camera.fov = camMode === 'orbit' ? (w < h ? 55 : 40) : 72;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);

function envFor(mode) {
  if (!envCache[mode]) envCache[mode] = createEnvironment(renderer, mode);
  return envCache[mode];
}

function applyQuality() {
  Q = QUALITY[settings.resolvedQuality()];
  renderer.shadowMap.enabled = Q.shadows;
  key.castShadow = Q.shadows;
  if (Q.shadows) {
    key.shadow.mapSize.set(Q.shadowSize, Q.shadowSize);
    if (key.shadow.map) { key.shadow.map.dispose(); key.shadow.map = null; }
  }
  resize();
  if (car) car.setQuality(Q);
  scene.traverse((o) => { if (o.material) o.material.needsUpdate = true; });
}

function applyLook() {
  const exp = settings.get('exposure');
  renderer.toneMappingExposure = (night ? 0.92 : 1.0) * exp;
  bloom.threshold = night ? 0.85 : 1.0;
  bloom.strength = night ? 0.42 : 0.22;
  bloom.radius = 0.45;
}

function setNight(on) {
  night = on;
  scene.environment = envFor(on ? 'night' : 'day');
  scene.background = new THREE.Color(on ? 0x030409 : 0x0b0d12);
  scene.fog = new THREE.Fog(on ? 0x030409 : 0x0b0d12, 18, 60);
  hemi.intensity = on ? 0.06 : 0.35;
  key.intensity = on ? 0.35 : 2.2;
  key.color.set(on ? 0x8fa8ff : 0xffffff);
  nightLights.visible = on;
  ringMat.emissive.set(on ? 0xff2bd6 : 0x00e5ff);
  $('btnNight').textContent = on ? '☀' : '☾';
  if (car) {
    car.setNight(on);
    car.setLights(on);
    $('btnLights').classList.toggle('active', on);
  }
  applyLook();
}

// ----------------------------------------------------------------------
// Tuning speichern / laden
function loadTunings() {
  try { return JSON.parse(localStorage.getItem(TUNE_KEY) || '{}') || {}; } catch (e) { return {}; }
}
function saveTuning() {
  if (!car) return;
  const all = loadTunings();
  all[car.meta.id] = car.tuning;
  try { localStorage.setItem(TUNE_KEY, JSON.stringify(all)); } catch (e) { /* egal */ }
}

// ----------------------------------------------------------------------
async function loadCar(id) {
  const meta = lib.byId[id];
  if (!meta) return;
  $('loading').classList.remove('hidden');
  $('loadText').textContent = meta.name + ' wird geladen …';
  $('loadBar').style.width = '0%';
  let next;
  try {
    next = await lib.create(id, (f) => { $('loadBar').style.width = Math.round(f * 100) + '%'; });
  } catch (e) {
    $('loadText').textContent = 'Fehler beim Laden: ' + e.message;
    return;
  }
  if (car) car.dispose();
  car = next;
  scene.add(car.object);
  car.setQuality(Q);
  const saved = loadTunings()[id];
  car.applyTuning({ ...defaultTuning(meta), ...(saved || {}) });
  car.setInteriorLight(settings.get('interiorLight'));
  car.setDisplayBrightness(settings.get('displayBrightness'));
  car.createHeadLamps();
  car.createCabinLight();
  car.forcedLod = settings.get('lodMode') === 'auto' ? null : Number(settings.get('lodMode'));
  car.setNight(night);
  car.setLights(night || $('btnLights').classList.contains('active'));
  car.state.indicator = 0;
  $('loading').classList.add('hidden');
  document.querySelectorAll('.car').forEach((b) => b.classList.toggle('active', b.dataset.id === id));
  $('carTitle').textContent = meta.name;
  $('carClass').textContent = (meta.class || '') + ' · ' + meta.description;
  document.documentElement.style.setProperty('--accent', meta.defaultAccent || '#00e5ff');
  try { localStorage.setItem('neonHaven.lastCar', id); } catch (e) { /* egal */ }
  buildTab(currentTab);
  updateStats();
}

function updateStats() {
  if (!car) return;
  const m = car.meta, t = car.tuning;
  const eng = (m.tuning && m.tuning.engine && m.tuning.engine[t.engine]) || null;
  const kw = eng ? eng.powerKw : m.stats.powerKw;
  const cage = (m.tuning && m.tuning.cage && m.tuning.cage[t.cage]) || {};
  const mass = m.stats.massKg + (cage.massKg || 0);
  const ps = Math.round(kw * 1.35962);
  // Schätzung 0–100 km/h aus Leistungsgewicht und Antrieb (an echten Autos abgeglichen)
  const trac = m.stats.drive === 'AWD' ? 0.9 : m.stats.drive === 'RWD' ? 1.0 : 1.12;
  const t100 = Math.max(1.8, 1.444 * Math.pow(mass / kw, 0.7) * trac);
  $('stats').innerHTML =
    `<span>Leistung<b>${kw} kW · ${ps} PS</b></span><span>Gewicht<b>${mass} kg</b></span>` +
    `<span>0–100<b>≈ ${t100.toFixed(1)} s</b></span><span>Vmax<b>${m.stats.topSpeedKmh} km/h</b></span>` +
    `<span>Antrieb<b>${m.stats.drive}</b></span><span>Fahrwerk<b>${m.stats.suspension}</b></span>`;
}

// ----------------------------------------------------------------------
// Tuning-Oberfläche
let currentTab = 'paint';

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function group(label, value) {
  const g = el('div', 'group');
  g.appendChild(el('div', 'label', `<span>${label}</span><span>${value || ''}</span>`));
  return g;
}

function options(parent, list, current, onPick) {
  const box = el('div', 'opts');
  list.forEach(([val, label]) => {
    const b = el('button', 'opt' + (val === current ? ' active' : ''), label);
    b.onclick = () => {
      box.querySelectorAll('.opt').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      onPick(val);
    };
    box.appendChild(b);
  });
  parent.appendChild(box);
}

function swatches(parent, colors, current, onPick, allowNone) {
  const box = el('div', 'swatches');
  const all = allowNone ? [null, ...colors] : colors;
  all.forEach((c) => {
    const b = el('button', 'sw' + ((c || null) === (current || null) ? ' active' : ''));
    b.style.background = c || 'repeating-linear-gradient(45deg,#333 0 4px,#555 4px 8px)';
    b.title = c || 'wie Lack';
    b.onclick = () => {
      box.querySelectorAll('.sw').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      onPick(c);
    };
    box.appendChild(b);
  });
  const pick = el('label', 'sw pick');
  pick.title = 'Eigene Farbe';
  const inp = document.createElement('input');
  inp.type = 'color';
  inp.value = current || '#ffffff';
  inp.oninput = () => {
    box.querySelectorAll('.sw').forEach((x) => x.classList.remove('active'));
    pick.classList.add('active');
    onPick(inp.value);
  };
  pick.appendChild(inp);
  box.appendChild(pick);
  parent.appendChild(box);
}

function slider(parent, min, max, step, value, onInput) {
  const i = document.createElement('input');
  i.type = 'range'; i.min = min; i.max = max; i.step = step; i.value = value;
  i.oninput = () => onInput(Number(i.value));
  parent.appendChild(i);
  return i;
}

function tune(patch) {
  if (!car) return;
  car.applyTuning(patch);
  saveTuning();
  updateStats();
}

function buildTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  const body = $('tabBody');
  body.innerHTML = '';
  if (!car) return;
  const m = car.meta, t = car.tuning;
  if (tab === 'paint') {
    let g = group('Lackfarbe');
    swatches(g, PAINTS, t.paint, (c) => tune({ paint: c }));
    body.appendChild(g);
    g = group('Lackart');
    options(g, Object.entries(FINISHES).map(([k, f]) => [k, f.label]), t.finish, (v) => tune({ finish: v }));
    body.appendChild(g);
    g = group('Dach / Zweifarbig');
    swatches(g, ['#0c0d10', '#e9edf3', '#9aa3ad', '#c8102e', '#1b2a3a', '#c9a45c', '#1f6fff'], t.roofColor,
      (c) => tune({ roofColor: c }), true);
    body.appendChild(g);
    g = group('Folierung');
    options(g, [[0, 'Ohne'], ...(m.liveries || []).map((l, i) => [i + 1, l])], t.livery, (v) => tune({ livery: v }));
    swatches(g, ['#f2f2f2', '#0c0d10', '#ffcf00', '#00e5ff', '#ff2bd6', '#c8102e', '#18c29c', '#ff5a1f'], t.liveryColor,
      (c) => tune({ liveryColor: c }));
    body.appendChild(g);
  } else if (tab === 'wheels') {
    let g = group('Felgen');
    options(g, (m.rims || []).map((r, i) => [i + 1, r]), t.rim, (v) => tune({ rim: v }));
    body.appendChild(g);
    g = group('Felgenfarbe');
    swatches(g, RIM_COLORS, t.rimColor, (c) => tune({ rimColor: c }));
    body.appendChild(g);
    g = group('Bremssättel');
    swatches(g, CALIPERS, t.caliper, (c) => tune({ caliper: c }));
    body.appendChild(g);
    const max = m.maxLoweringCm || 4;
    g = group('Tieferlegung', `<b id="vLow">${t.lowering} cm</b>`);
    slider(g, 0, max, 0.5, t.lowering, (v) => { $('vLow').textContent = v + ' cm'; tune({ lowering: v }); });
    body.appendChild(g);
  } else if (tab === 'aero') {
    let g = group('Spoiler');
    options(g, [[0, 'Ohne'], ...(m.spoilers || []).map((l, i) => [i + 1, l])], t.spoiler, (v) => tune({ spoiler: v }));
    body.appendChild(g);
    g = group('Scheibentönung', `<b id="vTint">${Math.round(t.tint * 100)} %</b>`);
    slider(g, 0, 1, 0.01, t.tint, (v) => { $('vTint').textContent = Math.round(v * 100) + ' %'; tune({ tint: v }); });
    body.appendChild(g);
    g = group('Neon / Unterboden');
    options(g, [[false, 'Aus'], [true, 'An']], t.neon, (v) => tune({ neon: v }));
    swatches(g, NEON, t.neonColor, (c) => tune({ neonColor: c }));
    body.appendChild(g);
  } else if (tab === 'engine') {
    const T = m.tuning || {};
    let g = group('Motorisierung');
    options(g, (T.engine || [{ name: 'Serie', powerKw: m.stats.powerKw }]).map((e, i) =>
      [i, `${e.name} · ${Math.round(e.powerKw * 1.36)} PS`]), t.engine, (v) => tune({ engine: v }));
    body.appendChild(g);
    g = group('Auspuffanlage');
    options(g, (T.exhaust || [{ name: 'Serie' }]).map((e, i) => [i + 1, e.name]), t.exhaust, (v) => tune({ exhaust: v }));
    body.appendChild(g);
    g = group('Überrollkäfig');
    options(g, (T.cage || [{ name: 'Kein Käfig' }, { name: 'Halbkäfig' }, { name: 'Vollkäfig' }]).map((e, i) => [i, e.name]),
      t.cage, (v) => tune({ cage: v }));
    body.appendChild(g);
    body.appendChild(el('p', 'hint', 'Motor-Stufen sind am Auto sichtbar (z. B. unter der Heckscheibe, Hutzen, Turbos). ' +
      'Die Fahrwerte nutzt später die offene Spielwelt.'));
  } else if (tab === 'interior') {
    let g = group('Ambiente-Farbe');
    swatches(g, AMBIENT, t.ambient, (c) => tune({ ambient: c }), true);
    body.appendChild(g);
    g = group('Innenraumbeleuchtung', `<b id="vIl2">${Math.round(settings.get('interiorLight') * 100)} %</b>`);
    slider(g, 0, 100, 1, Math.round(settings.get('interiorLight') * 100), (v) => {
      $('vIl2').textContent = v + ' %';
      settings.set('interiorLight', v / 100);
    });
    body.appendChild(g);
    g = group('Displays & Instrumente', `<b id="vDb2">${Math.round(settings.get('displayBrightness') * 100)} %</b>`);
    slider(g, 0, 100, 1, Math.round(settings.get('displayBrightness') * 100), (v) => {
      $('vDb2').textContent = v + ' %';
      settings.set('displayBrightness', v / 100);
    });
    body.appendChild(g);
    g = group('Ansicht');
    options(g, [['orbit', 'Außen'], ['cockpit', 'Cockpit'], ['hood', 'Motorhaube']], camMode, (v) => setCamMode(v));
    body.appendChild(g);
  }
}

document.querySelectorAll('.tab').forEach((b) => (b.onclick = () => buildTab(b.dataset.tab)));
function toggleTuning(force) {
  const t = $('tuning');
  const collapse = force !== undefined ? force : !t.classList.contains('collapsed');
  t.classList.toggle('collapsed', collapse);
  document.body.classList.toggle('tuning-open', !collapse);
  $('btnTuneToggle').textContent = collapse ? '▴' : '▾';
}
$('btnTuneToggle').onclick = (e) => { e.stopPropagation(); toggleTuning(); };
document.querySelector('.tuning .panel-head').addEventListener('click', () => {
  if ($('tuning').classList.contains('collapsed')) toggleTuning(false);
});
if (window.innerWidth <= 820) {
  $('tuning').classList.add('collapsed');
  $('btnTuneToggle').textContent = '▴';
} else {
  document.body.classList.add('tuning-open');
}

// ----------------------------------------------------------------------
// Kamera
function setCamMode(mode) {
  camMode = mode;
  controls.enabled = mode === 'orbit';
  $('btnCam').textContent = mode === 'orbit' ? 'Außen' : mode === 'cockpit' ? 'Cockpit' : 'Haube';
  look.yaw = 0;
  look.pitch = mode === 'cockpit' ? -0.1 : -0.04;
  camera.near = mode === 'orbit' ? 0.05 : 0.01;
  resize();
}
$('btnCam').onclick = () => setCamMode(camMode === 'orbit' ? 'cockpit' : camMode === 'cockpit' ? 'hood' : 'orbit');

// Umschauen im Cockpit (Maus/Touch ziehen)
let drag = null;
canvas.addEventListener('pointerdown', (e) => { if (camMode !== 'orbit') drag = { x: e.clientX, y: e.clientY }; });
window.addEventListener('pointerup', () => { drag = null; });
window.addEventListener('pointermove', (e) => {
  if (!drag) return;
  look.yaw = THREE.MathUtils.clamp(look.yaw - (e.clientX - drag.x) * 0.005, -1.9, 1.9);
  look.pitch = THREE.MathUtils.clamp(look.pitch - (e.clientY - drag.y) * 0.004, -0.7, 0.5);
  drag = { x: e.clientX, y: e.clientY };
});

const tmpV = new THREE.Vector3();
const tmpQ = new THREE.Quaternion();
function updateCamera() {
  if (!car || camMode === 'orbit') return;
  const h = camMode === 'cockpit' ? 'Cam_Cockpit' : 'Cam_Hood';
  if (!car.helperWorld(h, tmpV)) return;
  camera.position.copy(tmpV);
  car.object.getWorldQuaternion(tmpQ);
  const e = new THREE.Euler(look.pitch, Math.PI + look.yaw, 0, 'YXZ');   // Kamera blickt entlang +Z des Autos
  camera.quaternion.copy(tmpQ).multiply(new THREE.Quaternion().setFromEuler(e));
}

// ----------------------------------------------------------------------
// Demo-Steuerung
const demo = { throttle: 0, steer: 0, brake: false };
$('inSteer').oninput = (e) => { demo.steer = Number(e.target.value); };
$('inThrottle').oninput = (e) => { demo.throttle = Number(e.target.value); };
const brakeOn = (on) => { demo.brake = on; $('btnBrake').classList.toggle('active', on); };
$('btnBrake').addEventListener('pointerdown', () => brakeOn(true));
$('btnBrake').addEventListener('pointerup', () => brakeOn(false));
$('btnBrake').addEventListener('pointerleave', () => brakeOn(false));
$('btnLights').onclick = () => {
  const on = !$('btnLights').classList.contains('active');
  $('btnLights').classList.toggle('active', on);
  if (car) car.setLights(on);
};
$('btnIndL').onclick = () => { if (car) car.state.indicator = car.state.indicator === -1 ? 0 : -1; };
$('btnIndR').onclick = () => { if (car) car.state.indicator = car.state.indicator === 1 ? 0 : 1; };
$('btnSpin').onclick = () => { turntable = !turntable; $('btnSpin').classList.toggle('active', turntable); };
$('btnNight').onclick = () => setNight(!night);

function simulate(dt) {
  if (!car) return;
  const s = car.state;
  const p = car.meta.physics || {};
  const idle = p.idleRpm || 900, red = p.redlineRpm || 7000;
  s.steer += (demo.steer - s.steer) * Math.min(1, dt * 6);
  s.throttle += (demo.throttle - s.throttle) * Math.min(1, dt * 8);
  // Rollenprüfstand: Gas beschleunigt, Bremse/Luftwiderstand verzögern
  const vmax = 120;
  const acc = s.throttle * 28 - (demo.brake ? 60 : 0) - s.speedKmh * 0.12;
  s.speedKmh = THREE.MathUtils.clamp(s.speedKmh + acc * dt, 0, vmax);
  const gears = [0, 18, 34, 52, 72, 96, 125];
  let gear = 1;
  while (gear < gears.length && s.speedKmh > gears[gear]) gear++;
  s.gear = s.speedKmh < 0.5 && s.throttle < 0.05 ? (demo.brake ? 'P' : 'N') : String(gear);
  const lo = gears[gear - 1] || 0, hi = gears[gear] || vmax;
  const f = THREE.MathUtils.clamp((s.speedKmh - lo) / Math.max(1, hi - lo), 0, 1);
  const target = s.speedKmh < 0.5 ? idle + (red - idle) * s.throttle * 0.9 : idle + (red - idle) * (0.25 + 0.7 * f);
  s.rpm += (target - s.rpm) * Math.min(1, dt * 7);
  car.setBrake(demo.brake ? 1 : 0);
}

// ----------------------------------------------------------------------
// Einstellungen
function bindSettings() {
  const sI = $('sInterior'), sD = $('sDisplay'), sE = $('sExposure');
  const show = () => {
    $('vInterior').textContent = Math.round(settings.get('interiorLight') * 100) + ' %';
    $('vDisplay').textContent = Math.round(settings.get('displayBrightness') * 100) + ' %';
    $('vExposure').textContent = settings.get('exposure').toFixed(2);
  };
  sI.value = Math.round(settings.get('interiorLight') * 100);
  sD.value = Math.round(settings.get('displayBrightness') * 100);
  sE.value = Math.round(settings.get('exposure') * 100);
  $('sQuality').value = settings.get('quality');
  $('sLod').value = settings.get('lodMode');
  $('sBloom').checked = settings.get('bloom');
  $('sFps').checked = settings.get('showFps');
  show();
  sI.oninput = () => { settings.set('interiorLight', Number(sI.value) / 100); show(); };
  sD.oninput = () => { settings.set('displayBrightness', Number(sD.value) / 100); show(); };
  sE.oninput = () => { settings.set('exposure', Number(sE.value) / 100); show(); };
  $('sQuality').onchange = (e) => settings.set('quality', e.target.value);
  $('sLod').onchange = (e) => settings.set('lodMode', e.target.value);
  $('sBloom').onchange = (e) => settings.set('bloom', e.target.checked);
  $('sFps').onchange = (e) => settings.set('showFps', e.target.checked);
  $('btnReset').onclick = () => { settings.reset(); bindSettings(); };
  $('btnSettings').onclick = () => $('settings').showModal();
  $('btnPerfTest').onclick = () => perfTest();
}
settings.addEventListener('change', (e) => {
  const { key, value } = e.detail;
  if (key === 'interiorLight' && car) car.setInteriorLight(value);
  if (key === 'displayBrightness' && car) car.setDisplayBrightness(value);
  if (key === 'quality') applyQuality();
  if (key === 'exposure') applyLook();
  if (key === 'lodMode' && car) car.forcedLod = value === 'auto' ? null : Number(value);
  if (key === 'showFps') $('perf').classList.toggle('hidden', !value);
  if (car) car.settingsView = { interiorLight: settings.get('interiorLight'), displayBrightness: settings.get('displayBrightness') };
});

// ----------------------------------------------------------------------
// Leistungstest: 12 Autos in verschiedenen Entfernungen, Kamerafahrt, FPS messen
let perfRun = null;
async function perfTest() {
  if (!car || perfRun) return;
  $('perfResult').textContent = 'Leistungstest läuft (8 s) …';
  $('settings').close();
  const extra = [];
  const spots = [[-5, 4], [5, 4], [-6, -6], [6, -6], [-9, 12], [9, 12], [0, 18], [-14, 22], [14, 22], [0, 32], [-20, 40]];
  for (const [x, z] of spots) {
    const c = await lib.create(car.meta.id);
    c.setQuality(Q);
    c.applyTuning(car.tuning);
    c.setInteriorLight(settings.get('interiorLight'));
    c.setDisplayBrightness(settings.get('displayBrightness'));
    c.object.position.set(x, 0, z);
    c.object.rotation.y = Math.random() * Math.PI * 2;
    scene.add(c.object);
    extra.push(c);
  }
  const wasMode = camMode, wasDist = controls.maxDistance;
  setCamMode('orbit');
  controls.maxDistance = 60;
  perfRun = { t0: performance.now(), frames: 0, worst: 0, extra, last: performance.now(), wasMode, wasDist };
}
function perfTick(now) {
  if (!perfRun) return;
  const r = perfRun;
  const dt = now - r.last;
  r.last = now;
  r.frames++;
  if (r.frames > 10) r.worst = Math.max(r.worst, dt);
  const t = (now - r.t0) / 1000;
  camera.position.set(Math.sin(t * 0.5) * 16, 4 + Math.sin(t) * 1.5, Math.cos(t * 0.5) * 16 + 8);
  controls.target.set(0, 0.6, 8);
  if (t > 8) {
    const fps = (r.frames / t);
    const tris = renderer.info.render.triangles;
    for (const c of r.extra) c.dispose();
    controls.maxDistance = r.wasDist;
    controls.target.set(0, 0.55, 0);
    camera.position.set(5.6, 1.9, 6.2);
    setCamMode(r.wasMode);
    perfRun = null;
    const msg = `Ergebnis: Ø ${fps.toFixed(0)} FPS, langsamstes Bild ${(r.worst).toFixed(0)} ms, ` +
      `12 Autos, ${Math.round(tris / 1000)} k Dreiecke im Bild (Qualität ${settings.resolvedQuality()}).`;
    $('perfResult').textContent = msg;
    $('settings').showModal();
  }
}

// ----------------------------------------------------------------------
// Hauptschleife
const clock = new THREE.Clock();
let fpsAcc = 0, fpsFrames = 0, fpsShown = 0;
function frame() {
  renderer.info.reset();
  const dt = Math.min(0.05, clock.getDelta());
  const t = clock.elapsedTime;
  simulate(dt);
  if (car) {
    if (turntable && camMode === 'orbit' && !perfRun) car.object.rotation.y += dt * 0.12;
    car.update(dt, t);
    const lod = car.updateLOD(camera, Q.lodDistances, camMode !== 'orbit');
    if (perfRun) for (const c of perfRun.extra) { c.update(dt, t); c.updateLOD(camera, Q.lodDistances); }
    car._lodShown = lod;
  }
  if (camMode === 'orbit' && !perfRun) controls.update();
  updateCamera();
  perfTick(performance.now());
  const useBloom = settings.get('bloom') && Q.bloom;
  if (useBloom) composer.render(dt);
  else renderer.render(scene, camera);
  // Leistungsanzeige
  fpsAcc += dt; fpsFrames++;
  if (fpsAcc > 0.5) {
    fpsShown = fpsFrames / fpsAcc;
    fpsAcc = 0; fpsFrames = 0;
    if (settings.get('showFps')) {
      const info = renderer.info.render;
      $('perf').textContent = `${fpsShown.toFixed(0)} FPS  ${settings.resolvedQuality()}\n` +
        `${Math.round(info.triangles / 1000)} k Dreiecke  ${info.calls} Draw Calls\n` +
        `LOD ${car ? car._lodShown : '-'}  ${(renderer.getPixelRatio()).toFixed(2)}x`;
    }
  }
  requestAnimationFrame(frame);
}

// ----------------------------------------------------------------------
async function main() {
  applyQuality();
  setNight(false);
  bindSettings();
  $('perf').classList.toggle('hidden', !settings.get('showFps'));
  try {
    await lib.init();
  } catch (e) {
    $('loadText').textContent = 'cars.json konnte nicht geladen werden. Bitte über einen Webserver öffnen.';
    return;
  }
  const list = $('carList');
  for (const r of ROSTER) {
    const meta = lib.byId[r.id];
    const b = el('button', 'car' + (meta ? '' : ' soon'),
      `<b>${r.name}</b><span>${meta ? (meta.class || '') : 'kommt bald'}</span>`);
    b.dataset.id = r.id;
    b.style.setProperty('--c', meta ? meta.defaultAccent : '#555');
    if (meta) b.onclick = () => loadCar(r.id);
    list.appendChild(b);
  }
  let first = null;
  try { first = localStorage.getItem('neonHaven.lastCar'); } catch (e) { /* egal */ }
  if (!first || !lib.byId[first]) first = lib.cars[0] && lib.cars[0].id;
  requestAnimationFrame(frame);
  if (first) await loadCar(first);
}
main();
