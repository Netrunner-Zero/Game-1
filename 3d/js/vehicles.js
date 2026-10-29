// Fahrzeugmodelle aus einfachen Formen: Seitenprofil extrudieren, Kanten abrunden,
// Scheiben, Leuchten und Räder als eigene Teile. Alles nach Material gruppiert,
// damit der Verkehr per Instancing mit wenigen Draw-Calls gezeichnet werden kann.
import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

const V3 = THREE.Vector3;
export const PARTS = ['paint', 'body2', 'glass', 'trim', 'chrome', 'lights'];

// Leuchtfarben (HDR, Werte > 1 erzeugen Bloom)
const LIGHT = {
  tail: [3.6, 0.1, 0.06],
  head: [4.5, 4.4, 4.0],
  plate: [0.8, 0.8, 0.78],
  eu: [0.06, 0.14, 0.6],
  reflRed: [0.55, 0.03, 0.02],
  marker: [2.2, 0.9, 0.0],
};

// ---------------------------------------------------------------- Geometrie-Helfer
function box(w, h, d, x, y, z) {
  const g = new THREE.BoxGeometry(w, h, d);
  g.translate(x, y, z);
  return g;
}

function colorize(g, c) {
  const n = g.attributes.position.count, a = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    a[i * 3] = c[0];
    a[i * 3 + 1] = c[1];
    a[i * 3 + 2] = c[2];
  }
  g.setAttribute('color', new THREE.BufferAttribute(a, 3));
  return g;
}

// Für mergeGeometries: alle Teile nicht-indiziert, nur position/normal(/color)
function finalize(g) {
  const out = g.index ? g.toNonIndexed() : g;
  for (const name of Object.keys(out.attributes)) {
    if (name !== 'position' && name !== 'normal' && name !== 'color') out.deleteAttribute(name);
  }
  if (!out.attributes.normal) out.computeVertexNormals();
  return out;
}

const mirrorX = x => (Math.abs(x) < 1e-6 ? [0] : [-x, x]);
const clamp01 = v => (v < 0 ? 0 : v > 1 ? 1 : v);

// Ecken eines Polygons abrunden. Punkte: [u, y, radius]
function roundPolygon(pts, seg = 4) {
  const out = [], n = pts.length;
  for (let i = 0; i < n; i++) {
    const p = pts[i], a = pts[(i + n - 1) % n], b = pts[(i + 1) % n];
    const r = p[2] || 0;
    if (r <= 0) {
      out.push([p[0], p[1]]);
      continue;
    }
    let ux = a[0] - p[0], uy = a[1] - p[1], vx = b[0] - p[0], vy = b[1] - p[1];
    const lu = Math.hypot(ux, uy), lv = Math.hypot(vx, vy);
    ux /= lu; uy /= lu; vx /= lv; vy /= lv;
    const ang = Math.acos(Math.max(-1, Math.min(1, ux * vx + uy * vy)));
    if (ang < 0.01 || ang > Math.PI - 0.01) {
      out.push([p[0], p[1]]);
      continue;
    }
    const tanHalf = Math.tan(ang / 2);
    const t = Math.min(r / tanHalf, 0.45 * lu, 0.45 * lv);
    const rr = t * tanHalf;
    let bx = ux + vx, by = uy + vy;
    const bl = Math.hypot(bx, by);
    bx /= bl; by /= bl;
    const dist = rr / Math.sin(ang / 2);
    const cx = p[0] + bx * dist, cy = p[1] + by * dist;
    const a1 = Math.atan2(p[1] + uy * t - cy, p[0] + ux * t - cx);
    let da = Math.atan2(p[1] + vy * t - cy, p[0] + vx * t - cx) - a1;
    while (da > Math.PI) da -= 2 * Math.PI;
    while (da < -Math.PI) da += 2 * Math.PI;
    for (let k = 0; k <= seg; k++) {
      const aa = a1 + (da * k) / seg;
      out.push([cx + Math.cos(aa) * rr, cy + Math.sin(aa) * rr]);
    }
  }
  return out;
}

// Seitenprofil der Karosserie inkl. Radausschnitten
function bodyOutline(spec) {
  const pts = spec.body.map(p => [p[0], p[1], p[2] ?? 0.08]);
  const R = spec.wheelR, ra = R + 0.07;
  const axles = [...spec.axles].sort((a, b) => b - a);
  for (const ax of axles) {
    const phi = Math.asin(Math.min(0.9, Math.max(0, (R - spec.floorY) / ra)));
    const seg = 12;
    for (let k = 0; k <= seg; k++) {
      const a = -phi + ((Math.PI + 2 * phi) * k) / seg;
      pts.push([ax + Math.cos(a) * ra, R + Math.sin(a) * ra, 0]);
    }
  }
  return roundPolygon(pts);
}

// u-Position der Hinter- (min) bzw. Vorderkante (max) des Profils auf Höhe y
function profileU(poly, y, side) {
  let best = side === 'rear' ? Infinity : -Infinity;
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i], b = poly[(i + 1) % poly.length];
    if ((a[1] - y) * (b[1] - y) > 0 || a[1] === b[1]) continue;
    const u = a[0] + ((b[0] - a[0]) * (y - a[1])) / (b[1] - a[1]);
    if (side === 'rear' ? u < best : u > best) best = u;
  }
  return best;
}

// Profil über die Breite extrudieren, Kanten abrunden, weich schattieren.
// Ergebnis in Fahrzeugkoordinaten: x = quer, y = hoch, z = L/2 - u (Front bei -z)
function extrudeProfile(outline, width, bevel, L, taper) {
  const shape = new THREE.Shape(outline.map(p => new THREE.Vector2(p[0], p[1])));
  const depth = Math.max(0.02, width - 2 * bevel);
  let g = new THREE.ExtrudeGeometry(shape, {
    depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelOffset: -bevel,
    bevelSegments: 3, curveSegments: 4, steps: 1,
  });
  g.rotateY(Math.PI / 2);
  g.translate(-depth / 2, 0, L / 2);
  g.deleteAttribute('normal');
  g.deleteAttribute('uv');
  g = mergeVertices(g, 1e-4);
  if (taper) {
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) p.setX(i, p.getX(i) * taperScale(p.getY(i), taper));
  }
  g.computeVertexNormals();
  return g;
}

function taperScale(y, t) {
  return 1 - t.k * clamp01((y - t.y0) / (t.y1 - t.y0));
}

// Konvexes Polygon um d nach innen versetzen
function insetPoly(pts, d) {
  const n = pts.length;
  let area = 0;
  for (let i = 0; i < n; i++) {
    const a = pts[i], b = pts[(i + 1) % n];
    area += a[0] * b[1] - b[0] * a[1];
  }
  const sgn = area > 0 ? 1 : -1;
  const lines = [];
  for (let i = 0; i < n; i++) {
    const a = pts[i], b = pts[(i + 1) % n];
    let dx = b[0] - a[0], dy = b[1] - a[1];
    const l = Math.hypot(dx, dy);
    dx /= l; dy /= l;
    lines.push([a[0] - dy * sgn * d, a[1] + dx * sgn * d, dx, dy]);
  }
  const out = [];
  for (let i = 0; i < n; i++) {
    const A = lines[(i + n - 1) % n], B = lines[i];
    const den = A[2] * B[3] - A[3] * B[2];
    if (Math.abs(den) < 1e-9) {
      out.push([B[0], B[1]]);
      continue;
    }
    const t = ((B[0] - A[0]) * B[3] - (B[1] - A[1]) * B[2]) / den;
    out.push([A[0] + A[2] * t, A[1] + A[3] * t]);
  }
  return out;
}

// Polygon an der Halbebene a*u + b*y + c >= 0 abschneiden
function clipPoly(pts, a, b, c) {
  const out = [];
  for (let i = 0; i < pts.length; i++) {
    const P = pts[i], Q = pts[(i + 1) % pts.length];
    const fp = a * P[0] + b * P[1] + c, fq = a * Q[0] + b * Q[1] + c;
    if (fp >= 0) out.push(P);
    if ((fp >= 0) !== (fq >= 0)) {
      const t = fp / (fp - fq);
      out.push([P[0] + (Q[0] - P[0]) * t, P[1] + (Q[1] - P[1]) * t]);
    }
  }
  return out;
}

// Konvexes 3D-Polygon als Dreiecksfächer, Vorderseite zeigt in Richtung hint
function polyGeom(verts, hint) {
  let nx = 0, ny = 0, nz = 0;
  for (let i = 0; i < verts.length; i++) {
    const a = verts[i], b = verts[(i + 1) % verts.length];
    nx += (a.y - b.y) * (a.z + b.z);
    ny += (a.z - b.z) * (a.x + b.x);
    nz += (a.x - b.x) * (a.y + b.y);
  }
  if (nx * hint.x + ny * hint.y + nz * hint.z < 0) verts = verts.slice().reverse();
  const pos = [];
  for (let i = 1; i < verts.length - 1; i++) {
    for (const v of [verts[0], verts[i], verts[i + 1]]) pos.push(v.x, v.y, v.z);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  return g;
}

// Scheibe auf einer schrägen Fläche zwischen den Profilpunkten a und b (Front-/Heckscheibe)
function wallGlass(L, a, b, insA, insB, halfW, centroid) {
  const du = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(du, dy);
  const tu = du / len, ty = dy / len;
  let nu = -ty, ny = tu;
  const mu = (a[0] + b[0]) / 2 - centroid[0], my = (a[1] + b[1]) / 2 - centroid[1];
  if (nu * mu + ny * my < 0) {
    nu = -nu;
    ny = -ny;
  }
  const off = 0.012;
  const u0 = a[0] + tu * insA + nu * off, y0 = a[1] + ty * insA + ny * off;
  const u1 = b[0] - tu * insB + nu * off, y1 = b[1] - ty * insB + ny * off;
  const w0 = halfW(y0), w1 = halfW(y1);
  const z0 = L / 2 - u0, z1 = L / 2 - u1;
  return polyGeom([new V3(-w0, y0, z0), new V3(w0, y0, z0), new V3(w1, y1, z1), new V3(-w1, y1, z1)], new V3(0, ny, -nu));
}

// Seitenscheibe: Polygon im Profil, auf die Seitenfläche gelegt
function sideGlass(L, poly, halfW, s) {
  return polyGeom(poly.map(([u, y]) => new V3(s * halfW(y), y, L / 2 - u)), new V3(s, 0, 0));
}

function addWheel(P, R, WW, x, z) {
  const tire = new THREE.CylinderGeometry(R, R, WW, 18, 1);
  tire.rotateZ(Math.PI / 2);
  tire.translate(x, R, z);
  P.trim.push(tire);
  const rim = new THREE.CylinderGeometry(R * 0.62, R * 0.62, WW + 0.014, 14, 1);
  rim.rotateZ(Math.PI / 2);
  rim.translate(x, R, z);
  P.chrome.push(rim);
}

// ---------------------------------------------------------------- Pkw, Transporter, Bus
function buildStandard(P, G, spec) {
  const { L, W, wheelR: R, wheelW: WW, floorY } = spec;
  const zOf = u => L / 2 - u;
  const outline = bodyOutline(spec);
  P.paint.push(extrudeProfile(outline, W, spec.bevel ?? 0.07, L));
  const rearZ = y => zOf(profileU(outline, y, 'rear'));
  const frontZ = y => zOf(profileU(outline, y, 'front'));

  // Fahrgastzelle mit Scheiben
  if (spec.cabin) {
    const [rb, rt, ft, fb] = spec.cabin;
    const ext = (from, to, d) => {
      const dx = to[0] - from[0], dy = to[1] - from[1], l = Math.hypot(dx, dy);
      return [to[0] + (dx / l) * d, to[1] + (dy / l) * d];
    };
    const rbe = ext(rt, rb, 0.14), fbe = ext(ft, fb, 0.14);
    const r = spec.cabinR ?? 0.14;
    const poly = roundPolygon([[rbe[0], rbe[1], 0], [rt[0], rt[1], r], [ft[0], ft[1], r], [fbe[0], fbe[1], 0]]);
    const wc = W - 2 * spec.cabinInset;
    const taper = { y0: Math.min(rb[1], fb[1]), y1: Math.max(rt[1], ft[1]), k: spec.taper ?? 0.12 };
    P.paint.push(extrudeProfile(poly, wc, 0.05, L, taper));
    const halfW = y => (wc / 2) * taperScale(y, taper);
    const centroid = [(rb[0] + rt[0] + ft[0] + fb[0]) / 4, (rb[1] + rt[1] + ft[1] + fb[1]) / 4];
    P.glass.push(wallGlass(L, fb, ft, 0.05, 0.1, y => halfW(y) - 0.09, centroid));
    P.glass.push(wallGlass(L, rb, rt, 0.05, 0.1, y => halfW(y) - 0.09, centroid));
    let side = insetPoly([rb, rt, ft, fb], 0.075);
    side = clipPoly(side, 0, 1, -(Math.max(rb[1], fb[1]) + 0.05));
    const windows = spec.bPillar
      ? [clipPoly(side, -1, 0, spec.bPillar - 0.05), clipPoly(side, 1, 0, -(spec.bPillar + 0.05))]
      : [side];
    for (const w of windows) {
      if (w.length < 3) continue;
      for (const s of [-1, 1]) P.glass.push(sideGlass(L, w, y => halfW(y) + 0.006, s));
    }
    // Außenspiegel
    const mu = fb[0] - 0.22, my = fb[1] + 0.1, hw = wc / 2;
    for (const s of [-1, 1]) {
      P.paint.push(box(0.2, 0.12, 0.1, s * (hw + 0.14), my, zOf(mu)));
      P.trim.push(box(0.12, 0.04, 0.06, s * (hw + 0.05), my - 0.03, zOf(mu)));
    }
  }

  // Scheiben direkt auf der Karosserie (Transporter, Bus)
  if (spec.glass) {
    const gl = spec.glass;
    const centroid = [L / 2, spec.H / 2];
    for (const [a, b, insA, insB, inset] of gl.walls || []) P.glass.push(wallGlass(L, a, b, insA, insB, () => W / 2 - inset, centroid));
    for (const poly of gl.sides || []) for (const s of [-1, 1]) P.glass.push(sideGlass(L, poly, () => W / 2 + 0.006, s));
    for (const poly of gl.right || []) P.glass.push(sideGlass(L, poly, () => W / 2 + 0.006, 1));
    for (const r of gl.rear || []) {
      for (const x of mirrorX(r.x)) {
        const z = rearZ((r.y0 + r.y1) / 2) + 0.012;
        P.glass.push(polyGeom([
          new V3(x - r.w / 2, r.y0, z), new V3(x + r.w / 2, r.y0, z),
          new V3(x + r.w / 2, r.y1, z), new V3(x - r.w / 2, r.y1, z),
        ], new V3(0, 0, 1)));
      }
    }
  }

  // Leuchten und Leuchtpunkte für die Glow-Effekte
  for (const t of spec.tail) {
    for (const x of mirrorX(t.x)) {
      const z = rearZ(t.y);
      P.tail.push(colorize(box(t.w, t.h, 0.06, x, t.y, z - 0.015), LIGHT.tail));
      if (!t.noGlow) G.tail.push([x, t.y, z + 0.3]);
    }
  }
  for (const h of spec.head) {
    for (const x of mirrorX(h.x)) {
      const z = frontZ(h.y);
      P.lights.push(colorize(box(h.w, h.h, 0.06, x, h.y, z + 0.015), LIGHT.head));
      G.head.push([x, h.y, z - 0.3]);
    }
  }
  const ty = spec.tail[0].y, hy = spec.head[0].y, ix = W / 2 - 0.1;
  G.indL.push([-ix, ty, rearZ(ty) + 0.25], [-ix, hy, frontZ(hy) - 0.25]);
  G.indR.push([ix, ty, rearZ(ty) + 0.25], [ix, hy, frontZ(hy) - 0.25]);

  // Kennzeichen, Stoßfänger, Kühlergrill
  const pz = rearZ(spec.plateY);
  P.lights.push(colorize(box(0.52, 0.12, 0.02, 0, spec.plateY, pz + 0.008), LIGHT.plate));
  P.lights.push(colorize(box(0.05, 0.12, 0.024, -0.235, spec.plateY, pz + 0.009), LIGHT.eu));
  P.lights.push(colorize(box(0.52, 0.12, 0.02, 0, spec.plateFrontY, frontZ(spec.plateFrontY) - 0.008), LIGHT.plate));
  const by = floorY + 0.12;
  P.trim.push(box(W - 0.16, 0.15, 0.08, 0, by, rearZ(by) - 0.012));
  P.trim.push(box(W - 0.16, 0.15, 0.08, 0, by, frontZ(by) + 0.012));
  if (spec.grille) P.trim.push(box(spec.grille.w, spec.grille.h, 0.05, 0, spec.grille.y, frontZ(spec.grille.y) + 0.006));

  // Radkästen (verhindern Durchblick), Unterboden, Räder
  for (const ax of spec.axles) {
    const ra = R + 0.07, lo = R - 0.1, hi = R + ra;
    P.trim.push(box(W - 2 * (WW + 0.08), hi - lo, ra * 1.9, 0, (lo + hi) / 2, zOf(ax)));
    if (!spec.noWheels) for (const s of [-1, 1]) addWheel(P, R, WW, s * (W / 2 - WW / 2 - 0.03), zOf(ax));
  }
  P.trim.push(box(W - 0.3, 0.08, L - 0.5, 0, floorY + 0.03, 0));

  if (spec.extras) spec.extras(P, G, { spec, zOf, rearZ, frontZ });
}

// ---------------------------------------------------------------- Lkw mit Auflieger
function buildTruck(P, G, spec) {
  const { L, W } = spec;
  const zOf = u => L / 2 - u;
  // Auflieger
  const trailer = roundPolygon([[0, 1.18, 0.06], [0, 4.0, 0.08], [13.6, 4.0, 0.08], [13.6, 1.18, 0.06]]);
  P.body2.push(extrudeProfile(trailer, W, 0.05, L));
  P.trim.push(box(W - 0.5, 0.25, 13.0, 0, 1.05, zOf(6.8)));
  for (const ax of [1.3, 2.6, 3.9]) for (const s of [-1, 1]) addWheel(P, 0.5, 0.48, s * (W / 2 - 0.3), zOf(ax));
  P.trim.push(box(W - 1.2, 0.55, 3.9, 0, 0.82, zOf(2.6)));
  for (const s of [-1, 1]) {
    P.trim.push(box(0.5, 0.45, 0.03, s * (W / 2 - 0.3), 0.55, zOf(0.6)));
    P.chrome.push(box(0.04, 0.08, 7.0, s * (W / 2 - 0.1), 0.62, zOf(8.2)));
    P.chrome.push(box(0.04, 0.08, 7.0, s * (W / 2 - 0.1), 0.9, zOf(8.2)));
  }
  // Heck: Unterfahrschutz, Leuchtenträger, Türen, Konturmarkierung
  const rz = zOf(0);
  P.trim.push(box(W - 0.25, 0.14, 0.12, 0, 0.5, rz - 0.08));
  for (const s of [-1, 1]) P.trim.push(box(0.1, 0.55, 0.1, s * 0.8, 0.8, rz - 0.15));
  P.trim.push(box(W - 0.1, 0.24, 0.1, 0, 0.98, rz - 0.06));
  for (const s of [-1, 1]) {
    P.tail.push(colorize(box(0.34, 0.13, 0.04, s * 0.92, 0.98, rz), LIGHT.tail));
    P.lights.push(colorize(box(0.1, 0.13, 0.04, s * 0.66, 0.98, rz), LIGHT.marker));
    G.tail.push([s * 0.92, 0.98, rz + 0.3]);
  }
  P.lights.push(colorize(box(0.52, 0.12, 0.02, 0, 0.98, rz + 0.012), LIGHT.plate));
  P.trim.push(box(0.025, 2.7, 0.012, 0, 2.6, rz + 0.008));
  for (const x of [-0.95, -0.35, 0.35, 0.95]) P.chrome.push(box(0.035, 2.6, 0.04, x, 2.6, rz + 0.02));
  P.lights.push(colorize(box(W - 0.12, 0.06, 0.012, 0, 3.92, rz + 0.006), LIGHT.reflRed));
  for (const s of [-1, 1]) P.lights.push(colorize(box(0.06, 2.6, 0.012, s * (W / 2 - 0.06), 2.6, rz + 0.006), LIGHT.reflRed));
  for (let u = 1.0; u < 13.0; u += 2.4) {
    for (const s of [-1, 1]) P.lights.push(colorize(box(0.03, 0.06, 0.1, s * (W / 2 - 0.15), 1.05, zOf(u)), LIGHT.marker));
  }
  // Zugmaschine
  P.trim.push(box(1.0, 0.45, 4.6, 0, 0.8, zOf(14.0)));
  for (const s of [-1, 1]) {
    addWheel(P, 0.5, 0.48, s * (W / 2 - 0.3), zOf(12.9));
    addWheel(P, 0.5, 0.32, s * (W / 2 - 0.2), zOf(15.75));
    P.trim.push(box(0.55, 0.06, 1.25, s * (W / 2 - 0.3), 1.08, zOf(12.9)));
  }
  const cab = roundPolygon([[13.95, 1.0, 0.05], [13.95, 3.55, 0.12], [14.2, 3.85, 0.2], [16.05, 3.85, 0.3],
    [16.45, 3.25, 0.12], [16.5, 2.2, 0.1], [16.5, 1.0, 0.05]]);
  P.paint.push(extrudeProfile(cab, W - 0.04, 0.09, L));
  const fz = zOf(16.5);
  P.trim.push(box(W - 0.06, 0.55, 0.22, 0, 0.78, fz - 0.06));
  P.trim.push(box(1.5, 0.7, 0.03, 0, 1.55, fz - 0.005));
  P.glass.push(wallGlass(L, [16.5, 2.2], [16.45, 3.25], 0.06, 0.1, () => W / 2 - 0.16, [15.2, 2.4]));
  for (const s of [-1, 1]) {
    P.glass.push(sideGlass(L, [[15.3, 2.3], [15.3, 3.28], [16.12, 3.28], [16.3, 2.3]], () => (W - 0.04) / 2 + 0.006, s));
    P.lights.push(colorize(box(0.42, 0.14, 0.04, s * 0.85, 0.85, fz - 0.17), LIGHT.head));
    G.head.push([s * 0.85, 0.85, fz - 0.45]);
    P.trim.push(box(0.08, 0.5, 0.18, s * (W / 2 + 0.2), 2.75, zOf(16.2)));
    P.trim.push(box(0.25, 0.04, 0.04, s * (W / 2 + 0.08), 3.0, zOf(16.2)));
  }
  P.lights.push(colorize(box(0.52, 0.12, 0.02, 0, 0.62, fz - 0.18), LIGHT.plate));
  G.indL.push([-(W / 2 - 0.05), 0.98, rz + 0.25], [-(W / 2 - 0.05), 0.85, fz - 0.4]);
  G.indR.push([W / 2 - 0.05, 0.98, rz + 0.25], [W / 2 - 0.05, 0.85, fz - 0.4]);
}

// ---------------------------------------------------------------- Zusatzteile
function coupeExtras(P, G, { spec, zOf, rearZ }) {
  const W = spec.W;
  P.paint.push(box(W - 0.42, 0.035, 0.24, 0, 0.99, zOf(0.2)));       // Heckflügel
  for (const s of [-1, 1]) {
    P.trim.push(box(0.05, 0.08, 0.08, s * 0.55, 0.945, zOf(0.22)));
    const pipe = new THREE.CylinderGeometry(0.048, 0.048, 0.18, 12);  // Endrohre
    pipe.rotateX(Math.PI / 2);
    pipe.translate(s * 0.52, 0.26, rearZ(0.26) - 0.02);
    P.chrome.push(pipe);
    P.trim.push(box(0.05, 0.08, 1.75, s * (W / 2 - 0.02), 0.2, zOf(2.33))); // Seitenschweller
  }
  P.trim.push(box(1.25, 0.1, 0.22, 0, 0.21, rearZ(0.21) - 0.06));      // Diffusor
}

function suvExtras(P, G, { spec, zOf }) {
  const hw = ((spec.W - 2 * spec.cabinInset) / 2) * (1 - spec.taper) - 0.12;
  for (const s of [-1, 1]) {
    P.chrome.push(box(0.04, 0.04, 2.3, s * hw, 1.83, zOf(1.75)));
    for (const u of [0.75, 2.7]) P.trim.push(box(0.05, 0.06, 0.08, s * hw, 1.79, zOf(u)));
  }
}

function vanExtras(P, G, { spec, zOf, rearZ }) {
  const W = spec.W;
  P.trim.push(box(0.02, 1.65, 0.012, 0, 1.4, rearZ(1.4) + 0.008));   // Hecktürfuge
  for (const s of [-1, 1]) P.trim.push(box(0.03, 0.1, spec.L - 1.2, s * (W / 2 + 0.005), 0.9, zOf(spec.L / 2)));
}

function busExtras(P, G, { spec, zOf, rearZ }) {
  const W = spec.W;
  for (let u = 0.55; u <= 10.95; u += 1.725) {
    for (const s of [-1, 1]) P.trim.push(box(0.02, 1.27, 0.1, s * (W / 2 + 0.014), 2.415, zOf(u)));
  }
  P.trim.push(box(1.6, 0.55, 0.03, 0, 1.25, rearZ(1.25) + 0.01));     // Motorgitter
  P.paint.push(box(1.6, 0.25, 2.6, 0, 3.55, zOf(6.5)));               // Klimaanlage
}

// ---------------------------------------------------------------- Modelle
export const SPECS = {
  sedan: {
    L: 4.75, W: 1.84, H: 1.45, wheelR: 0.33, wheelW: 0.23, axles: [0.98, 3.78], floorY: 0.19,
    body: [[0.04, 0.27, 0.05], [0.0, 0.5, 0.1], [0.02, 0.88, 0.12], [0.25, 1.0, 0.2], [1.15, 1.03, 0.1],
      [3.3, 0.99, 0.3], [4.35, 0.84, 0.25], [4.68, 0.66, 0.12], [4.75, 0.42, 0.08], [4.64, 0.24, 0.05]],
    cabin: [[1.08, 1.0], [1.82, 1.42], [3.0, 1.45], [3.55, 0.97]], cabinR: 0.14, cabinInset: 0.07, taper: 0.14, bPillar: 2.45,
    tail: [{ x: 0.62, y: 0.84, w: 0.44, h: 0.11 }], head: [{ x: 0.62, y: 0.66, w: 0.4, h: 0.09 }],
    grille: { y: 0.5, w: 0.75, h: 0.16 }, plateY: 0.6, plateFrontY: 0.38,
  },
  hatch: {
    L: 4.15, W: 1.78, H: 1.49, wheelR: 0.31, wheelW: 0.21, axles: [0.72, 3.27], floorY: 0.18,
    body: [[0.04, 0.26, 0.05], [0.0, 0.52, 0.1], [0.03, 0.96, 0.12], [0.15, 1.02, 0.1], [0.6, 1.03, 0.1],
      [2.85, 0.98, 0.3], [3.78, 0.82, 0.25], [4.08, 0.66, 0.12], [4.15, 0.44, 0.08], [4.05, 0.24, 0.05]],
    cabin: [[0.14, 1.0], [0.42, 1.47], [2.45, 1.49], [3.08, 0.95]], cabinR: 0.14, cabinInset: 0.06, taper: 0.13, bPillar: 1.8,
    tail: [{ x: 0.66, y: 0.9, w: 0.3, h: 0.16 }], head: [{ x: 0.6, y: 0.68, w: 0.36, h: 0.09 }],
    grille: { y: 0.52, w: 0.7, h: 0.14 }, plateY: 0.62, plateFrontY: 0.4,
  },
  suv: {
    L: 4.7, W: 1.94, H: 1.8, wheelR: 0.38, wheelW: 0.25, axles: [1.0, 3.85], floorY: 0.27,
    body: [[0.04, 0.34, 0.05], [0.0, 0.62, 0.1], [0.03, 1.08, 0.12], [0.18, 1.16, 0.12], [0.7, 1.18, 0.15],
      [3.4, 1.12, 0.3], [4.32, 1.02, 0.25], [4.66, 0.88, 0.12], [4.72, 0.58, 0.08], [4.62, 0.32, 0.05]],
    cabin: [[0.2, 1.15], [0.4, 1.74], [3.05, 1.77], [3.68, 1.1]], cabinR: 0.14, cabinInset: 0.06, taper: 0.1, bPillar: 2.25,
    tail: [{ x: 0.72, y: 1.0, w: 0.34, h: 0.14 }], head: [{ x: 0.7, y: 0.86, w: 0.4, h: 0.09 }],
    grille: { y: 0.7, w: 0.9, h: 0.2 }, plateY: 0.72, plateFrontY: 0.5, extras: suvExtras,
  },
  coupe: {
    L: 4.55, W: 1.96, H: 1.28, wheelR: 0.345, wheelW: 0.27, axles: [0.98, 3.68], floorY: 0.13,
    body: [[0.05, 0.22, 0.05], [0.0, 0.42, 0.08], [0.02, 0.8, 0.1], [0.2, 0.92, 0.15], [0.9, 0.96, 0.2],
      [3.25, 0.88, 0.35], [4.15, 0.7, 0.25], [4.48, 0.55, 0.12], [4.55, 0.36, 0.08], [4.44, 0.16, 0.04]],
    cabin: [[0.6, 0.93], [1.65, 1.26], [2.6, 1.28], [3.38, 0.86]], cabinR: 0.16, cabinInset: 0.09, taper: 0.18,
    tail: [{ x: 0.64, y: 0.78, w: 0.4, h: 0.08 }, { x: 0, y: 0.8, w: 0.82, h: 0.035, noGlow: true }],
    head: [{ x: 0.66, y: 0.6, w: 0.36, h: 0.07 }],
    grille: { y: 0.36, w: 1.1, h: 0.16 }, plateY: 0.52, plateFrontY: 0.3, extras: coupeExtras,
  },
  van: {
    L: 5.9, W: 2.0, H: 2.5, wheelR: 0.36, wheelW: 0.24, axles: [1.05, 4.72], floorY: 0.25, bevel: 0.08,
    body: [[0.03, 0.3, 0.05], [0.0, 0.55, 0.08], [0.0, 2.35, 0.15], [0.12, 2.5, 0.12], [4.3, 2.5, 0.3],
      [5.05, 1.48, 0.15], [5.55, 1.16, 0.2], [5.86, 0.9, 0.12], [5.9, 0.5, 0.08], [5.8, 0.28, 0.05]],
    glass: {
      walls: [[[5.05, 1.48], [4.3, 2.5], 0.08, 0.2, 0.13]],
      sides: [[[4.12, 1.58], [4.12, 2.28], [4.32, 2.28], [4.85, 1.6]]],
      rear: [{ x: 0.46, w: 0.74, y0: 1.5, y1: 2.2 }],
    },
    tail: [{ x: 0.9, y: 0.95, w: 0.12, h: 0.42 }], head: [{ x: 0.72, y: 0.86, w: 0.36, h: 0.12 }],
    grille: { y: 0.7, w: 1.0, h: 0.18 }, plateY: 0.62, plateFrontY: 0.45, extras: vanExtras,
  },
  bus: {
    L: 12.4, W: 2.55, H: 3.45, wheelR: 0.5, wheelW: 0.3, axles: [2.1, 3.5, 10.45], floorY: 0.38, bevel: 0.1,
    body: [[0.02, 0.45, 0.08], [0.0, 1.0, 0.1], [0.0, 3.2, 0.25], [0.3, 3.45, 0.3], [11.6, 3.45, 0.4],
      [12.25, 3.05, 0.3], [12.4, 2.2, 0.15], [12.4, 0.75, 0.12], [12.3, 0.42, 0.05]],
    glass: {
      walls: [[[12.4, 1.3], [12.4, 2.19], 0, 0, 0.16], [[12.4, 2.2], [12.25, 3.05], 0.03, 0.17, 0.18]],
      sides: [[[0.55, 1.78], [0.55, 3.05], [10.9, 3.05], [10.9, 1.78]]],
      right: [[[11.15, 0.75], [11.15, 3.0], [11.95, 3.0], [11.95, 0.75]]],
      rear: [{ x: 0, w: 2.1, y0: 2.35, y1: 3.1 }],
    },
    tail: [{ x: 1.08, y: 1.5, w: 0.16, h: 0.85 }], head: [{ x: 0.95, y: 0.95, w: 0.42, h: 0.14 }],
    grille: { y: 0.95, w: 1.1, h: 0.25 }, plateY: 0.75, plateFrontY: 0.6, extras: busExtras,
  },
  truck: { L: 16.6, W: 2.55, H: 4.0, custom: buildTruck },
};

// Modell bauen: pro Material eine zusammengeführte Geometrie
export function buildVehicle(spec) {
  const P = { paint: [], body2: [], glass: [], trim: [], chrome: [], lights: [], tail: [] };
  const G = { tail: [], head: [], indL: [], indR: [] };
  if (spec.custom) spec.custom(P, G, spec);
  else buildStandard(P, G, spec);
  if (!spec.separateTail) {
    P.lights.push(...P.tail);
    P.tail = [];
  }
  const geoms = {};
  for (const k of Object.keys(P)) geoms[k] = P[k].length ? mergeGeometries(P[k].map(finalize)) : null;
  return { geoms, glows: G, L: spec.L, W: spec.W, H: spec.H };
}

export function createVehicleMaterials() {
  return {
    paint: new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: 0.35, roughness: 0.36, clearcoat: 1, clearcoatRoughness: 0.06, envMapIntensity: 0.85 }),
    body2: new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.15, roughness: 0.5 }),
    glass: new THREE.MeshStandardMaterial({ color: 0x0b1016, metalness: 0.1, roughness: 0.05, envMapIntensity: 1.6 }),
    trim: new THREE.MeshStandardMaterial({ color: 0x17191c, metalness: 0.05, roughness: 0.8 }),
    chrome: new THREE.MeshStandardMaterial({ color: 0xc9ced3, metalness: 1, roughness: 0.22 }),
    lights: new THREE.MeshBasicMaterial({ vertexColors: true }),
  };
}

// ---------------------------------------------------------------- Verkehr per Instancing
export class TrafficRenderer {
  constructor(scene, mats, capacities, shadowTex) {
    this.types = new Map();
    let total = 0;
    for (const [name, capacity] of Object.entries(capacities)) {
      const model = buildVehicle(SPECS[name]);
      const meshes = [];
      let paint = null, body2 = null;
      for (const part of PARTS) {
        const g = model.geoms[part];
        if (!g) continue;
        const m = new THREE.InstancedMesh(g, mats[part], capacity);
        m.count = 0;
        m.frustumCulled = false;
        m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        m.castShadow = part === 'paint' || part === 'body2' || part === 'trim';
        m.receiveShadow = part !== 'lights' && part !== 'glass';
        if (part === 'paint' || part === 'body2') {
          m.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3), 3);
          m.instanceColor.setUsage(THREE.DynamicDrawUsage);
          if (part === 'paint') paint = m;
          else body2 = m;
        }
        scene.add(m);
        meshes.push(m);
      }
      this.types.set(name, { model, meshes, paint, body2, n: 0, capacity });
      total += capacity;
    }
    // Weicher Kontaktschatten unter jedem Fahrzeug
    this.shadow = new THREE.InstancedMesh(
      new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({
        color: 0x000000, map: shadowTex, transparent: true, depthWrite: false, opacity: 0.6,
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
      }),
      total
    );
    this.shadow.frustumCulled = false;
    this.shadow.renderOrder = 1;
    this.shadow.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    scene.add(this.shadow);
    this.e = new Float32Array(16);
    this.p = { x: 0, y: 0, z: 0 };
  }

  begin() {
    for (const t of this.types.values()) t.n = 0;
    this.sn = 0;
  }

  // v: Fahrzeug mit x, z, yaw, dir, color, color2, braking, lc
  add(v, glows, night, time) {
    const t = this.types.get(v.type);
    if (t.n >= t.capacity) return;
    const i = t.n++;
    const c = Math.cos(v.yaw), s = Math.sin(v.yaw), e = this.e;
    e.fill(0);
    e[0] = c; e[2] = -s; e[5] = 1; e[8] = s; e[10] = c; e[12] = v.x; e[14] = v.z; e[15] = 1;
    for (const m of t.meshes) m.instanceMatrix.array.set(e, i * 16);
    if (t.paint) t.paint.instanceColor.setXYZ(i, v.color.r, v.color.g, v.color.b);
    if (t.body2) t.body2.instanceColor.setXYZ(i, v.color2.r, v.color2.g, v.color2.b);

    const sx = t.model.W + 0.4, sz = t.model.L + 0.6;
    e[0] = c * sx; e[2] = -s * sx; e[8] = s * sz; e[10] = c * sz; e[13] = 0.02;
    this.shadow.instanceMatrix.array.set(e, this.sn++ * 16);

    // Leuchtpunkte
    const G = t.model.glows, p = this.p;
    const tf = q => {
      p.x = c * q[0] + s * q[2] + v.x;
      p.y = q[1];
      p.z = -s * q[0] + c * q[2] + v.z;
      return p;
    };
    if (v.dir > 0) {
      const k = v.braking ? 0.6 + night * 2.2 : 0.2 + night * 0.85;
      const size = v.braking ? 0.85 + night * 0.6 : 0.7 + night * 0.45;
      for (const q of G.tail) {
        tf(q);
        glows.push(p.x, p.y, p.z, k, k * 0.06, k * 0.03, size);
      }
    } else {
      const k = 0.15 + night * 1.8;
      for (const q of G.head) {
        tf(q);
        glows.push(p.x, p.y, p.z, k, k * 0.93, k * 0.8, 1.5 + night * 1.3);
      }
    }
    if (v.lc && Math.sin((time + v.blink) * 9.5) > 0) {
      const k = 1.3 + night;
      for (const q of v.lc.to < v.lc.from ? G.indL : G.indR) {
        tf(q);
        glows.push(p.x, p.y, p.z, k, k * 0.45, 0, 0.8);
      }
    }
  }

  end() {
    for (const t of this.types.values()) {
      for (const m of t.meshes) {
        m.count = t.n;
        m.instanceMatrix.needsUpdate = true;
        if (m.instanceColor) m.instanceColor.needsUpdate = true;
      }
    }
    this.shadow.count = this.sn;
    this.shadow.instanceMatrix.needsUpdate = true;
  }

  capacityOf(type) {
    return this.types.get(type).capacity;
  }
}

// ---------------------------------------------------------------- Spielerauto
function buildWheelGeometries(R, WW) {
  const ri = R * 0.66, hw = WW / 2;
  const prof = [[ri, -hw + 0.01], [R - 0.045, -hw], [R - 0.012, -hw + 0.03], [R, -hw + 0.07],
    [R, hw - 0.07], [R - 0.012, hw - 0.03], [R - 0.045, hw], [ri, hw - 0.01]];
  const tire = new THREE.LatheGeometry(prof.map(([r, y]) => new THREE.Vector2(r, y)), 32);
  tire.rotateZ(Math.PI / 2);
  const barrel = new THREE.CylinderGeometry(ri, ri, WW * 0.85, 24, 1, true);
  barrel.rotateZ(Math.PI / 2);
  const rimParts = [];
  for (let k = 0; k < 5; k++) {
    const sp = new THREE.BoxGeometry(0.03, ri * 0.95, 0.075);
    sp.translate(0, ri * 0.5, 0);
    sp.rotateX((k * Math.PI * 2) / 5);
    sp.translate(hw * 0.45, 0, 0);
    rimParts.push(sp);
  }
  const hub = new THREE.CylinderGeometry(0.065, 0.075, 0.05, 14);
  hub.rotateZ(Math.PI / 2);
  hub.translate(hw * 0.5, 0, 0);
  rimParts.push(hub);
  const lip = new THREE.TorusGeometry(ri - 0.008, 0.014, 6, 32);
  lip.rotateY(Math.PI / 2);
  lip.translate(hw * 0.52, 0, 0);
  rimParts.push(lip);
  const rim = mergeGeometries(rimParts.map(g => g.toNonIndexed()));
  const disc = new THREE.CylinderGeometry(ri * 0.82, ri * 0.82, 0.025, 24);
  disc.rotateZ(Math.PI / 2);
  disc.translate(-hw * 0.05, 0, 0);
  const caliper = new THREE.BoxGeometry(0.07, 0.12, 0.17);
  caliper.translate(hw * 0.12, ri * 0.48, ri * 0.4);
  return { tire, barrel, rim, disc, caliper };
}

export class PlayerCar {
  constructor(scene, mats, shadowTex) {
    const spec = SPECS.coupe;
    this.spec = spec;
    const model = buildVehicle({ ...spec, noWheels: true, separateTail: true });
    this.glows = model.glows;
    this.group = new THREE.Group();
    this.body = new THREE.Group();
    this.group.add(this.body);
    scene.add(this.group);

    this.paint = new THREE.MeshPhysicalMaterial({ color: 0xa50f1a, metalness: 0.3, roughness: 0.34, clearcoat: 1, clearcoatRoughness: 0.05, envMapIntensity: 0.7 });
    this.tailMat = new THREE.MeshBasicMaterial({ vertexColors: true });
    const matFor = { ...mats, paint: this.paint, tail: this.tailMat };
    for (const [part, geo] of Object.entries(model.geoms)) {
      if (!geo) continue;
      const m = new THREE.Mesh(geo, matFor[part]);
      m.castShadow = part === 'paint' || part === 'trim' || part === 'chrome';
      m.receiveShadow = part === 'paint' || part === 'trim';
      this.body.add(m);
    }

    const wg = buildWheelGeometries(spec.wheelR, spec.wheelW);
    const wm = {
      tire: new THREE.MeshStandardMaterial({ color: 0x111214, roughness: 0.92 }),
      rim: new THREE.MeshStandardMaterial({ color: 0x8a9198, metalness: 1, roughness: 0.28 }),
      barrel: new THREE.MeshStandardMaterial({ color: 0x1d2024, metalness: 0.6, roughness: 0.5, side: THREE.DoubleSide }),
      disc: new THREE.MeshStandardMaterial({ color: 0x6d7176, metalness: 0.8, roughness: 0.45 }),
      caliper: new THREE.MeshStandardMaterial({ color: 0xc01622, roughness: 0.4 }),
    };
    this.wheels = [];
    for (const ax of spec.axles) {
      for (const side of [-1, 1]) {
        const pivot = new THREE.Group();
        pivot.position.set(side * (spec.W / 2 - spec.wheelW / 2 - 0.03), spec.wheelR, spec.L / 2 - ax);
        const spin = new THREE.Group();
        pivot.add(spin);
        const tire = new THREE.Mesh(wg.tire, wm.tire);
        tire.castShadow = true;
        spin.add(tire, new THREE.Mesh(wg.rim, wm.rim), new THREE.Mesh(wg.barrel, wm.barrel), new THREE.Mesh(wg.disc, wm.disc));
        pivot.add(new THREE.Mesh(wg.caliper, wm.caliper));
        this.group.add(pivot);
        this.wheels.push({ pivot, spin, side, front: ax > spec.L / 2 });
      }
    }

    const sh = new THREE.Mesh(
      new THREE.PlaneGeometry(spec.W + 0.5, spec.L + 0.7).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({
        color: 0x000000, map: shadowTex, transparent: true, depthWrite: false, opacity: 0.7,
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
      })
    );
    sh.position.y = 0.015;
    sh.renderOrder = 1;
    this.group.add(sh);

    // Abblendlicht für die Nacht
    this.spot = new THREE.SpotLight(0xfff0dc, 0, 170, 0.44, 0.75, 1.25);
    this.spot.position.set(0, 0.75, -spec.L / 2 + 0.3);
    this.spot.target.position.set(0, -0.6, -45);
    this.group.add(this.spot, this.spot.target);

    this.wheelAngle = 0;
    this.tmp = new THREE.Vector3();
  }

  // st: { x, yaw, roll, pitch, steer, v, braking, night }
  update(dt, st) {
    this.group.position.x = st.x;
    this.group.rotation.y = st.yaw;
    this.body.rotation.set(st.pitch, 0, st.roll);
    this.wheelAngle = (this.wheelAngle + (st.v / this.spec.wheelR) * dt) % (Math.PI * 2);
    for (const w of this.wheels) {
      const steerA = w.front ? -st.steer * 0.3 : 0;
      w.pivot.rotation.y = (w.side < 0 ? Math.PI : 0) + steerA;
      w.spin.rotation.x = w.side < 0 ? this.wheelAngle : -this.wheelAngle;
    }
    this.tailMat.color.setScalar(st.braking ? 2.6 : 1);
    this.spot.intensity = st.night * 48;
  }

  // Rücklichter als Leuchtpunkte (Weltkoordinaten)
  pushGlows(glows, night, braking) {
    this.body.updateWorldMatrix(true, false);
    const k = braking ? 0.65 + night * 2.2 : 0.25 + night * 0.85;
    const size = braking ? 0.9 + night * 0.6 : 0.75 + night * 0.4;
    for (const q of this.glows.tail) {
      const p = this.tmp.set(q[0], q[1], q[2]).applyMatrix4(this.body.matrixWorld);
      glows.push(p.x, p.y, p.z, k, k * 0.06, k * 0.03, size);
    }
  }

  setClearcoat(on) {
    this.paint.clearcoat = on ? 1 : 0;
  }
}
