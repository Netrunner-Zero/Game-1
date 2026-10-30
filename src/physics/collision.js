// Kollisionen in der Fahrebene (x, z) – ohne Grafik-Abhängigkeiten (läuft auch in Node).
//
//  * Autos sind gedrehte Rechtecke (OBB) mit Höhe, Hindernisse sind Rechtecke oder Kreise.
//  * Statische Hindernisse (Häuser, Mauern, Leitplanken, Masten) liegen in einem Raster
//    (Spatial Hash), damit auch in einer dichten Stadt nur Hindernisse in der Nähe geprüft werden.
//  * Antwort: Eindringen auflösen und Stoß mit Reibung (Impuls) – inklusive Drehimpuls,
//    ein Treffer an der Ecke dreht das Auto also weg.
//
// Gieren wie in CarPhysics: die lokale +Z-Achse zeigt in Welt-Richtung (sin ψ, cos ψ),
// die lokale +X-Achse (links) in Richtung (cos ψ, −sin ψ).
//
// Ein „Körper“ ist jedes Objekt mit { pos:{x,y,z}, vel:{x,z}, yaw, yawRate, mass, Iz }
// – also CarPhysics oder ein KI-Auto des Verkehrs.

export class StaticWorld {
  constructor(cellSize = 24) {
    this.cell = cellSize;
    this.grid = new Map();
    this.items = [];
    this._stamp = 0;
  }

  _key(ix, iz) { return ix * 73856093 ^ iz * 19349663; }

  _insert(it) {
    const c = this.cell;
    const x0 = Math.floor(it.minX / c), x1 = Math.floor(it.maxX / c);
    const z0 = Math.floor(it.minZ / c), z1 = Math.floor(it.maxZ / c);
    for (let ix = x0; ix <= x1; ix++) {
      for (let iz = z0; iz <= z1; iz++) {
        const k = this._key(ix, iz);
        let list = this.grid.get(k);
        if (!list) { list = []; this.grid.set(k, list); }
        list.push(it);
      }
    }
    it.id = this.items.length;
    it._seen = 0;
    this.items.push(it);
    return it;
  }

  /** Rechteck: Mitte (x, z), halbe Breite hx (lokal x) und halbe Länge hz (lokal z), Drehung yaw. */
  addBox({ x, z, hx, hz, yaw = 0, top = 12, bottom = -1, kind = 'wall', mu = 0.35, e = 0.12, data = null }) {
    const c = Math.cos(yaw), s = Math.sin(yaw);
    const ax = [c, -s], az = [s, c];
    const ex = Math.abs(ax[0]) * hx + Math.abs(az[0]) * hz;
    const ez = Math.abs(ax[1]) * hx + Math.abs(az[1]) * hz;
    return this._insert({ type: 'box', cx: x, cz: z, hx, hz, ax, az, top, bottom, kind, mu, e, data,
      minX: x - ex, maxX: x + ex, minZ: z - ez, maxZ: z + ez });
  }

  /** Kreis (Mast, Baum, Poller). */
  addCircle({ x, z, r, top = 6, bottom = -1, kind = 'pole', mu = 0.3, e = 0.1, data = null }) {
    return this._insert({ type: 'circle', x, z, r, top, bottom, kind, mu, e, data,
      minX: x - r, maxX: x + r, minZ: z - r, maxZ: z + r });
  }

  /** Alle Hindernisse, deren Hülle das Rechteck berührt (ohne Doppelte). */
  query(minX, minZ, maxX, maxZ, out = []) {
    out.length = 0;
    const c = this.cell;
    const stamp = ++this._stamp;
    const x0 = Math.floor(minX / c), x1 = Math.floor(maxX / c);
    const z0 = Math.floor(minZ / c), z1 = Math.floor(maxZ / c);
    for (let ix = x0; ix <= x1; ix++) {
      for (let iz = z0; iz <= z1; iz++) {
        const list = this.grid.get(this._key(ix, iz));
        if (!list) continue;
        for (const it of list) {
          if (it._seen === stamp) continue;
          it._seen = stamp;
          if (it.maxX < minX || it.minX > maxX || it.maxZ < minZ || it.minZ > maxZ) continue;
          out.push(it);
        }
      }
    }
    return out;
  }

  /** Strahl in der Ebene (z. B. Kamera gegen Häuser): Anteil 0..1 bis zum ersten Treffer, sonst 1.
   *  filter(it) wählt die Hindernisse aus (z. B. nur große Rechtecke, keine Masten). */
  raycast(x0, z0, x1, z1, minTop = 0, filter = null) {
    const list = this.query(Math.min(x0, x1) - 0.5, Math.min(z0, z1) - 0.5, Math.max(x0, x1) + 0.5, Math.max(z0, z1) + 0.5, []);
    let best = 1;
    const dx = x1 - x0, dz = z1 - z0;
    for (const it of list) {
      if (it.top < minTop) continue;
      if (filter && !filter(it)) continue;
      let t = 1;
      if (it.type === 'box') {
        // in lokale Koordinaten, dann Slab-Test
        const ox = x0 - it.cx, oz = z0 - it.cz;
        const lx = ox * it.ax[0] + oz * it.ax[1], lz = ox * it.az[0] + oz * it.az[1];
        const ldx = dx * it.ax[0] + dz * it.ax[1], ldz = dx * it.az[0] + dz * it.az[1];
        let tmin = 0, tmax = 1, ok = true;
        for (const [p, d, h] of [[lx, ldx, it.hx], [lz, ldz, it.hz]]) {
          if (Math.abs(d) < 1e-9) { if (Math.abs(p) > h) { ok = false; break; } continue; }
          let ta = (-h - p) / d, tb = (h - p) / d;
          if (ta > tb) [ta, tb] = [tb, ta];
          tmin = Math.max(tmin, ta); tmax = Math.min(tmax, tb);
          if (tmin > tmax) { ok = false; break; }
        }
        if (ok) t = tmin;
      } else {
        const fx = x0 - it.x, fz = z0 - it.z;
        const a = dx * dx + dz * dz, b = 2 * (fx * dx + fz * dz), c = fx * fx + fz * fz - it.r * it.r;
        const disc = b * b - 4 * a * c;
        if (disc >= 0 && a > 1e-12) {
          const tt = (-b - Math.sqrt(disc)) / (2 * a);
          if (tt >= 0 && tt <= 1) t = tt; else if (c < 0) t = 0;
        }
      }
      if (t < best) best = t;
    }
    return best;
  }
}

// ----------------------------------------------------------------------
// Form eines Autos aus cars.json (relativ zum Schwerpunkt der Physik)

export function carShape(meta, zcg) {
  const b = meta.bounds || {
    min: [-meta.dimensions.width / 2, 0.15, -meta.dimensions.length / 2],
    max: [meta.dimensions.width / 2, meta.dimensions.height, meta.dimensions.length / 2],
  };
  return {
    hx: meta.dimensions.width / 2 + 0.02,
    hz: (b.max[2] - b.min[2]) / 2,
    off: (b.max[2] + b.min[2]) / 2 - zcg,          // Mitte des Rechtecks vor (+) dem Schwerpunkt
    bottom: b.min[1],
    top: b.max[1],
  };
}

/** Rechteck eines Körpers in Weltkoordinaten (wird wiederverwendet). */
export function bodyOBB(body, shape, out = {}) {
  const s = Math.sin(body.yaw), c = Math.cos(body.yaw);
  out.type = 'box';
  out.ax = [c, -s];
  out.az = [s, c];
  out.hx = shape.hx;
  out.hz = shape.hz;
  out.cx = body.pos.x + s * shape.off;
  out.cz = body.pos.z + c * shape.off;
  const ex = Math.abs(c) * shape.hx + Math.abs(s) * shape.hz;
  const ez = Math.abs(s) * shape.hx + Math.abs(c) * shape.hz;
  out.minX = out.cx - ex; out.maxX = out.cx + ex;
  out.minZ = out.cz - ez; out.maxZ = out.cz + ez;
  return out;
}

// ----------------------------------------------------------------------
// Schnitttests. Ergebnis: Normale n (zeigt von B nach A, also die Richtung, in die A
// hinausgeschoben wird), Eindringtiefe und Kontaktpunkt.

function radius(o, nx, nz) {
  return o.hx * Math.abs(o.ax[0] * nx + o.ax[1] * nz) + o.hz * Math.abs(o.az[0] * nx + o.az[1] * nz);
}

// Eckpunkt(e) von o, die am weitesten in Richtung n liegen; liegt eine Kante parallel zur
// Fläche, wird die Kantenmitte genommen (sonst würde jeder flache Kontakt das Auto drehen).
function support(o, nx, nz, ref, out) {
  const dX = o.ax[0] * nx + o.ax[1] * nz;
  const dZ = o.az[0] * nx + o.az[1] * nz;
  const sx = dX >= 0 ? 1 : -1, sz = dZ >= 0 ? 1 : -1;
  let px = o.cx + o.ax[0] * o.hx * sx + o.az[0] * o.hz * sz;
  let pz = o.cz + o.ax[1] * o.hx * sx + o.az[1] * o.hz * sz;
  const par = 0.06;
  let e = null, h = 0, sgn = 0;
  if (Math.abs(dX) < par * Math.abs(dZ)) { e = o.ax; h = o.hx; sgn = sx; }        // Kante entlang lokal x
  else if (Math.abs(dZ) < par * Math.abs(dX)) { e = o.az; h = o.hz; sgn = sz; }   // Kante entlang lokal z
  if (e && ref) {
    // Kantenmitte, dann die Kante auf die Ausdehnung der Referenzfläche beschneiden
    const mx = px - e[0] * h * sgn, mz = pz - e[1] * h * sgn;
    const tx = -nz, tz = nx;                                          // Tangente der Kontaktfläche
    const half = Math.abs(e[0] * tx + e[1] * tz) * h;
    const c0 = mx * tx + mz * tz;
    const rc = ref.cx * tx + ref.cz * tz, rr = radius(ref, tx, tz);
    const a = Math.max(c0 - half, rc - rr), b = Math.min(c0 + half, rc + rr);
    const shift = a <= b ? (a + b) / 2 - c0 : 0;
    px = mx + tx * shift; pz = mz + tz * shift;
  }
  out[0] = px; out[1] = pz;
  return out;
}

const _sp = [0, 0];

export function testBoxBox(A, B, res) {
  const dx = A.cx - B.cx, dz = A.cz - B.cz;
  let best = Infinity, nx = 0, nz = 0, owner = 0;
  for (let i = 0; i < 4; i++) {
    const axis = i === 0 ? A.ax : i === 1 ? A.az : i === 2 ? B.ax : B.az;
    const d = dx * axis[0] + dz * axis[1];
    const o = radius(A, axis[0], axis[1]) + radius(B, axis[0], axis[1]) - Math.abs(d);
    if (o <= 0) return null;
    // leichte Bevorzugung der Flächen von B (Hindernis), damit Wände sauber als Fläche erkannt werden
    const ow = i < 2 ? o * 1.02 : o;
    if (ow < best) {
      best = ow;
      const s = d < 0 ? -1 : 1;
      nx = axis[0] * s; nz = axis[1] * s; owner = i < 2 ? 0 : 1;
    }
  }
  const depth = radius(A, nx, nz) + radius(B, nx, nz) - Math.abs(dx * nx + dz * nz);
  if (owner === 1) support(A, -nx, -nz, B, _sp);   // Fläche von B: tiefster Punkt von A
  else support(B, nx, nz, A, _sp);                 // Fläche von A: tiefster Punkt von B
  res.nx = nx; res.nz = nz; res.depth = depth; res.px = _sp[0]; res.pz = _sp[1];
  return res;
}

export function testBoxCircle(A, C, res) {
  const ox = C.x - A.cx, oz = C.z - A.cz;
  const lx = ox * A.ax[0] + oz * A.ax[1];
  const lz = ox * A.az[0] + oz * A.az[1];
  const qx = Math.max(-A.hx, Math.min(A.hx, lx));
  const qz = Math.max(-A.hz, Math.min(A.hz, lz));
  const ddx = lx - qx, ddz = lz - qz;
  const d2 = ddx * ddx + ddz * ddz;
  if (d2 > C.r * C.r) return null;
  if (d2 > 1e-10) {
    const d = Math.sqrt(d2);
    // Normale vom Kreis zum Rechteck (A wird weggeschoben)
    const nlx = -ddx / d, nlz = -ddz / d;
    res.nx = nlx * A.ax[0] + nlz * A.az[0];
    res.nz = nlx * A.ax[1] + nlz * A.az[1];
    res.depth = C.r - d;
  } else {
    // Mittelpunkt im Rechteck: über die nächste Seite hinausschieben
    const px = A.hx - Math.abs(lx), pz = A.hz - Math.abs(lz);
    if (px < pz) {
      const s = lx > 0 ? -1 : 1;
      res.nx = A.ax[0] * s; res.nz = A.ax[1] * s; res.depth = px + C.r;
    } else {
      const s = lz > 0 ? -1 : 1;
      res.nx = A.az[0] * s; res.nz = A.az[1] * s; res.depth = pz + C.r;
    }
  }
  res.px = A.cx + qx * A.ax[0] + qz * A.az[0];
  res.pz = A.cz + qx * A.ax[1] + qz * A.az[1];
  return res;
}

// ----------------------------------------------------------------------
// Stoßantwort

function applyImpulse(b, rx, rz, jx, jz) {
  b.vel.x += jx / b.mass;
  b.vel.z += jz / b.mass;
  b.yawRate += (rz * jx - rx * jz) / b.Iz;
}

/** Körper gegen festes Hindernis. Gibt die Stoßstärke als Geschwindigkeitsänderung (m/s) zurück. */
export function resolveStatic(b, c, mu = 0.35, e = 0.12) {
  const nx = c.nx, nz = c.nz;
  b.pos.x += nx * (c.depth + 0.002);
  b.pos.z += nz * (c.depth + 0.002);
  const rx = c.px - b.pos.x, rz = c.pz - b.pos.z;
  const vx = b.vel.x + b.yawRate * rz, vz = b.vel.z - b.yawRate * rx;
  const vn = vx * nx + vz * nz;
  if (vn >= 0) return 0;
  const cr = rz * nx - rx * nz;
  const jn = -(1 + e) * vn / (1 / b.mass + cr * cr / b.Iz);
  applyImpulse(b, rx, rz, jn * nx, jn * nz);
  // Reibung entlang der Wand (Coulomb, höchstens µ·Normalstoß)
  const vx2 = b.vel.x + b.yawRate * rz, vz2 = b.vel.z - b.yawRate * rx;
  const vn2 = vx2 * nx + vz2 * nz;
  let tx = vx2 - vn2 * nx, tz = vz2 - vn2 * nz;
  const vt = Math.hypot(tx, tz);
  if (vt > 1e-6) {
    tx /= vt; tz /= vt;
    const ct = rz * tx - rx * tz;
    let jt = vt / (1 / b.mass + ct * ct / b.Iz);
    jt = Math.min(jt, mu * jn);
    applyImpulse(b, rx, rz, -jt * tx, -jt * tz);
  }
  return jn / b.mass;
}

/** Zwei bewegliche Körper (Normale zeigt von B nach A). Gibt den Normalstoß (N·s) zurück. */
export function resolvePair(A, B, c, mu = 0.3, e = 0.18) {
  const nx = c.nx, nz = c.nz;
  const ia = 1 / A.mass, ib = 1 / B.mass;
  const share = (c.depth + 0.002) / (ia + ib);
  A.pos.x += nx * share * ia; A.pos.z += nz * share * ia;
  B.pos.x -= nx * share * ib; B.pos.z -= nz * share * ib;
  const rax = c.px - A.pos.x, raz = c.pz - A.pos.z;
  const rbx = c.px - B.pos.x, rbz = c.pz - B.pos.z;
  const rel = () => {
    const vax = A.vel.x + A.yawRate * raz, vaz = A.vel.z - A.yawRate * rax;
    const vbx = B.vel.x + B.yawRate * rbz, vbz = B.vel.z - B.yawRate * rbx;
    return [vax - vbx, vaz - vbz];
  };
  let [vx, vz] = rel();
  const vn = vx * nx + vz * nz;
  if (vn >= 0) return 0;
  const ca = raz * nx - rax * nz, cb = rbz * nx - rbx * nz;
  const jn = -(1 + e) * vn / (ia + ib + ca * ca / A.Iz + cb * cb / B.Iz);
  applyImpulse(A, rax, raz, jn * nx, jn * nz);
  applyImpulse(B, rbx, rbz, -jn * nx, -jn * nz);
  [vx, vz] = rel();
  const vn2 = vx * nx + vz * nz;
  let tx = vx - vn2 * nx, tz = vz - vn2 * nz;
  const vt = Math.hypot(tx, tz);
  if (vt > 1e-6) {
    tx /= vt; tz /= vt;
    const cta = raz * tx - rax * tz, ctb = rbz * tx - rbx * tz;
    let jt = vt / (ia + ib + cta * cta / A.Iz + ctb * ctb / B.Iz);
    jt = Math.min(jt, mu * jn);
    applyImpulse(A, rax, raz, -jt * tx, -jt * tz);
    applyImpulse(B, rbx, rbz, jt * tx, jt * tz);
  }
  return jn;
}

// ----------------------------------------------------------------------
// Verwaltung: alle Körper gegen die Welt und gegeneinander

export class Collisions {
  constructor(world) {
    this.world = world;
    this.bodies = [];          // { body, shape, obb, kind, onHit }
    this._near = [];
    this._res = { nx: 0, nz: 0, depth: 0, px: 0, pz: 0 };
  }

  add(body, shape, opts = {}) {
    const e = { body, shape, obb: {}, kind: opts.kind || 'car', onHit: opts.onHit || null, enabled: true };
    this.bodies.push(e);
    return e;
  }

  remove(entry) {
    const i = this.bodies.indexOf(entry);
    if (i >= 0) this.bodies.splice(i, 1);
  }

  /** Ein Durchgang: Eindringen auflösen und Stöße berechnen. onImpact(entry, stärke m/s, x, z, other) */
  step(onImpact) {
    const res = this._res;
    for (const e of this.bodies) {
      if (!e.enabled) continue;
      const b = e.body;
      const bottomY = (b.pos.y - (b.hcg || 0.5)) + e.shape.bottom;   // Unterkante über dem Boden
      for (let iter = 0; iter < 2; iter++) {
        const A = bodyOBB(b, e.shape, e.obb);
        const near = this.world.query(A.minX - 0.1, A.minZ - 0.1, A.maxX + 0.1, A.maxZ + 0.1, this._near);
        let hitAny = false;
        for (const it of near) {
          if (it.top < bottomY + 0.05 || it.bottom > bottomY + (e.shape.top - e.shape.bottom)) continue;   // drüber/drunter
          const c = it.type === 'box' ? testBoxBox(A, it, res) : testBoxCircle(A, it, res);
          if (!c) continue;
          const s = resolveStatic(b, c, it.mu, it.e);
          hitAny = true;
          if (s > 0.3 && onImpact) onImpact(e, s, c.px, c.pz, it);
          bodyOBB(b, e.shape, A);
        }
        if (!hitAny) break;
      }
    }
    // Körper untereinander
    const n = this.bodies.length;
    for (let i = 0; i < n; i++) {
      const a = this.bodies[i];
      if (!a.enabled) continue;
      for (let j = i + 1; j < n; j++) {
        const bb = this.bodies[j];
        if (!bb.enabled) continue;
        const A = bodyOBB(a.body, a.shape, a.obb), B = bodyOBB(bb.body, bb.shape, bb.obb);
        if (A.maxX < B.minX || A.minX > B.maxX || A.maxZ < B.minZ || A.minZ > B.maxZ) continue;
        const c = testBoxBox(A, B, res);
        if (!c) continue;
        const jn = resolvePair(a.body, bb.body, c);
        const sa = jn / a.body.mass, sb = jn / bb.body.mass;
        if (onImpact && sa > 0.3) onImpact(a, sa, c.px, c.pz, bb);
        if (onImpact && sb > 0.3) onImpact(bb, sb, c.px, c.pz, a);
      }
    }
  }
}
