// Prozedurale Texturen – alles wird zur Laufzeit auf Canvas gezeichnet, keine Bilddateien.
import * as THREE from 'three';
import { ROAD, LANE_X, ONCOMING_X } from './config.js';

// Reproduzierbarer Zufall (mulberry32), damit die Texturen immer gleich aussehen
function rng(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

// Kachelbares Value-Noise auf einem Gitter mit gw × gh Zellen
function valueNoise(random, gw, gh) {
  const grid = new Float32Array(gw * gh);
  for (let i = 0; i < grid.length; i++) grid[i] = random();
  return (x, y) => {
    const xi = Math.floor(x), yi = Math.floor(y);
    const fx = x - xi, fy = y - yi;
    const x0 = ((xi % gw) + gw) % gw, y0 = ((yi % gh) + gh) % gh;
    const x1 = (x0 + 1) % gw, y1 = (y0 + 1) % gh;
    const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
    const a = grid[y0 * gw + x0], b = grid[y0 * gw + x1];
    const c = grid[y1 * gw + x0], d = grid[y1 * gw + x1];
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
  };
}

const to255 = v => (v < 0 ? 0 : v > 255 ? 255 : v);

// Asphalt mit Fahrbahnmarkierungen. Breite = ganze Straße, Länge = 18 m (6 m Strich, 12 m Lücke)
export function createRoadTexture(anisotropy) {
  const W = 1024, H = 512;
  const span = ROAD.right - ROAD.left;
  const c = makeCanvas(W, H), g = c.getContext('2d');
  const X = x => ((x - ROAD.left) / span) * W;
  const ZP = H / 18;
  const random = rng(7);

  g.fillStyle = '#55575a';
  g.fillRect(0, 0, W, H);
  // Bankett an den Außenkanten
  g.fillStyle = '#5f6548';
  g.fillRect(0, 0, X(-27.0), H);
  g.fillRect(X(9.8), 0, W - X(9.8), H);
  // Standstreifen mit leicht anderem Belag
  g.fillStyle = 'rgba(255,255,255,0.035)';
  g.fillRect(X(7.2), 0, X(9.8) - X(7.2), H);
  g.fillRect(X(-27.0), 0, X(-24.4) - X(-27.0), H);
  // Dunklere Rollspuren in jeder Fahrspur
  for (const lx of [...LANE_X, ...ONCOMING_X]) {
    for (const off of [-0.85, 0.85]) {
      const a = X(lx + off - 0.45), b = X(lx + off + 0.45);
      const grd = g.createLinearGradient(a, 0, b, 0);
      grd.addColorStop(0, 'rgba(22,22,25,0)');
      grd.addColorStop(0.5, 'rgba(22,22,25,0.24)');
      grd.addColorStop(1, 'rgba(22,22,25,0)');
      g.fillStyle = grd;
      g.fillRect(a, 0, b - a, H);
    }
  }
  // Ausgebesserte Stellen
  for (let i = 0; i < 7; i++) {
    g.fillStyle = `rgba(32,32,35,${0.12 + random() * 0.14})`;
    const x = ROAD.left + 1 + random() * (span - 2);
    g.fillRect(X(x), random() * H, ((0.8 + random() * 2.2) * W) / span, (0.6 + random() * 1.6) * ZP);
  }
  // Markierungen: durchgezogene Randlinien, gestrichelte Leitlinien
  g.fillStyle = '#eeece4';
  const line = (x, w, z0, z1) =>
    g.fillRect(X(x - w / 2), z0 * ZP, Math.max(2, X(x + w / 2) - X(x - w / 2)), (z1 - z0) * ZP);
  for (const x of [-7.2, 7.2, -10.0, -24.4]) line(x, 0.3, 0, 18);
  for (const x of [-3.6, 0, 3.6, -13.6, -17.2, -20.8]) line(x, 0.15, 0, 6);

  // Körnung und großflächige Helligkeitsunterschiede
  const img = g.getImageData(0, 0, W, H), d = img.data;
  const coarse = valueNoise(random, 32, 16);
  const mid = valueNoise(random, 128, 64);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      const f = 1 + (coarse(x / 32, y / 32) - 0.5) * 0.16 + (mid(x / 8, y / 8) - 0.5) * 0.1 + (random() - 0.5) * 0.13;
      d[i] = to255(d[i] * f);
      d[i + 1] = to255(d[i + 1] * f);
      d[i + 2] = to255(d[i + 2] * f);
    }
  }
  g.putImageData(img, 0, 0);

  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.ClampToEdgeWrapping;
  t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = anisotropy;
  return t;
}

// Feine Asphaltstruktur als Normal-Map (kachelbar, 2,5 m × 2,5 m)
export function createAsphaltNormal(anisotropy) {
  const N = 256;
  const random = rng(11);
  const n1 = valueNoise(random, 64, 64);
  const h = new Float32Array(N * N);
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) h[y * N + x] = random() * 0.65 + n1(x / 4, y / 4) * 0.35;
  }
  const c = makeCanvas(N, N), g = c.getContext('2d');
  const img = g.createImageData(N, N), d = img.data;
  const s = 2.4;
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const l = h[y * N + ((x - 1 + N) % N)], r = h[y * N + ((x + 1) % N)];
      const u = h[((y - 1 + N) % N) * N + x], dn = h[((y + 1) % N) * N + x];
      let nx = (l - r) * s, ny = (u - dn) * s, nz = 1;
      const len = Math.hypot(nx, ny, nz);
      nx /= len; ny /= len; nz /= len;
      const i = (y * N + x) * 4;
      d[i] = (nx * 0.5 + 0.5) * 255;
      d[i + 1] = (ny * 0.5 + 0.5) * 255;
      d[i + 2] = (nz * 0.5 + 0.5) * 255;
      d[i + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = anisotropy;
  return t;
}

// Wiese (kachelbar, 7 m × 7 m)
export function createGrassTexture(anisotropy) {
  const N = 256;
  const random = rng(23);
  const big = valueNoise(random, 4, 4);
  const mid = valueNoise(random, 16, 16);
  const fine = valueNoise(random, 64, 64);
  const c = makeCanvas(N, N), g = c.getContext('2d');
  const img = g.createImageData(N, N), d = img.data;
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const b = big(x / 64, y / 64), m = mid(x / 16, y / 16), f = fine(x / 4, y / 4);
      const v = 0.55 + b * 0.25 + m * 0.25 + f * 0.15 + (random() - 0.5) * 0.18;
      const dry = Math.max(0, m - 0.62) * 1.6; // gelbliche, trockene Stellen
      const i = (y * N + x) * 4;
      d[i] = to255((62 + dry * 70) * v);
      d[i + 1] = to255((98 + dry * 30) * v);
      d[i + 2] = to255((40 + dry * 10) * v);
      d[i + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = anisotropy;
  return t;
}

// Beton der Mittelschutzwand: u = Höhe (0–0,9 m), v = Länge mit Fuge alle 6 m
export function createConcreteTexture() {
  const W = 64, H = 256;
  const random = rng(31);
  const n = valueNoise(random, 8, 32);
  const c = makeCanvas(W, H), g = c.getContext('2d');
  const img = g.createImageData(W, H), d = img.data;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      let v = 0.86 + (n(x / 8, y / 8) - 0.5) * 0.18 + (random() - 0.5) * 0.08;
      v *= 0.78 + 0.22 * Math.min(1, x / 18); // Schmutz unten
      if (y < 3) v *= 0.55;                   // Fuge
      const i = (y * W + x) * 4;
      d[i] = to255(178 * v);
      d[i + 1] = to255(176 * v);
      d[i + 2] = to255(168 * v);
      d[i + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

// Weicher runder Verlauf (Kontaktschatten, Lichtkegel der Laternen)
export function createRadialTexture() {
  const N = 128;
  const c = makeCanvas(N, N), g = c.getContext('2d');
  const grd = g.createRadialGradient(N / 2, N / 2, 0, N / 2, N / 2, N / 2);
  grd.addColorStop(0, 'rgba(255,255,255,1)');
  grd.addColorStop(0.45, 'rgba(255,255,255,0.75)');
  grd.addColorStop(0.75, 'rgba(255,255,255,0.25)');
  grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, N, N);
  return new THREE.CanvasTexture(c);
}

// Rauch-Partikel
export function createSmokeTexture() {
  const N = 64;
  const random = rng(5);
  const c = makeCanvas(N, N), g = c.getContext('2d');
  for (let i = 0; i < 9; i++) {
    const x = N / 2 + (random() - 0.5) * N * 0.35, y = N / 2 + (random() - 0.5) * N * 0.35;
    const r = N * (0.18 + random() * 0.2);
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    grd.addColorStop(0, 'rgba(255,255,255,0.35)');
    grd.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, N, N);
  }
  return new THREE.CanvasTexture(c);
}

// Blaues Autobahnschild (Schilderbrücke)
export function drawSign(texture, { arrow, top, bottom, tag }) {
  const c = texture.image, g = c.getContext('2d');
  const W = c.width, H = c.height;
  g.fillStyle = '#1d4f91';
  g.fillRect(0, 0, W, H);
  g.strokeStyle = '#ffffff';
  g.lineWidth = 6;
  g.strokeRect(9, 9, W - 18, H - 18);
  g.fillStyle = '#ffffff';
  g.textBaseline = 'middle';
  g.font = 'bold 60px "Segoe UI", Roboto, Arial, sans-serif';
  g.fillText(top, 120, H * 0.33);
  g.fillText(bottom, 120, H * 0.7);
  // Pfeil
  g.save();
  g.translate(62, H / 2);
  if (arrow === 'right') g.rotate(Math.PI / 4);
  g.beginPath();
  g.moveTo(0, -48); g.lineTo(28, -12); g.lineTo(10, -12); g.lineTo(10, 46);
  g.lineTo(-10, 46); g.lineTo(-10, -12); g.lineTo(-28, -12);
  g.closePath();
  g.fill();
  g.restore();
  if (tag) {
    // Autobahnnummer bzw. Ausfahrt-Kennung
    g.font = 'bold 38px "Segoe UI", Roboto, Arial, sans-serif';
    const w = g.measureText(tag).width + 26;
    g.fillStyle = '#ffffff';
    g.fillRect(W - w - 22, 22, w, 52);
    g.fillStyle = '#1d4f91';
    g.fillText(tag, W - w - 9, 49);
  }
  texture.needsUpdate = true;
}

export function createSignTexture(anisotropy) {
  const t = new THREE.CanvasTexture(makeCanvas(512, 200));
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = anisotropy;
  return t;
}
