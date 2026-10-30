// Stadtverkehr: KI-Autos fahren auf Spuren, halten an roten Ampeln, halten Abstand (Intelligent Driver
// Model), biegen ab, blinken, bremsen für den Spieler – und lassen sich anrempeln.
//
// Logik ohne Grafik (läuft auch in Node, siehe tests/traffic.test.mjs); die Darstellung (InstancedMesh)
// hängt sich über setRenderer() an.
//
// Spurgraph aus der Karten-JSON (roads): Kreuzungen (nodes) und Abschnitte (edges). Je Abschnitt und
// Richtung Spuren rechts der Mitte (Rechtsverkehr); an den Kreuzungen Verbindungen geradeaus, rechts, links.

const HALF = (t) => t.lanes * t.lane + t.median / 2;
const STOP_EXTRA = 5.2;                 // Haltelinie: so weit hinter dem Rand der Querstraße
const MODELS = [['pulse', 26], ['aurelion_s', 16], ['rhino_x', 16], ['brawler_77', 14], ['vektra_gt', 10], ['ion_spectre', 10]];
// Lackfarben (linear): weiß, schwarz, silber, grau, dunkelblau, rot, dunkelgrün, beige, Taxi-Gelb, Neon
const PAINTS = [[0.80, 0.80, 0.78], [0.012, 0.012, 0.014], [0.45, 0.47, 0.50], [0.14, 0.15, 0.16], [0.02, 0.05, 0.16],
  [0.5, 0.02, 0.02], [0.02, 0.09, 0.05], [0.55, 0.45, 0.32], [0.9, 0.55, 0.02], [0.75, 0.03, 0.5], [0.0, 0.45, 0.6]];
const PAINT_W = [14, 14, 14, 10, 8, 8, 5, 5, 6, 2, 2];

function pick(rnd, list, weights) {
  const tot = weights.reduce((a, b) => a + b, 0);
  let r = rnd() * tot;
  for (let i = 0; i < list.length; i++) { r -= weights[i]; if (r <= 0) return list[i]; }
  return list[list.length - 1];
}

function mulberry(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class Traffic {
  /**
   * @param {object} map   Karten-JSON (roads, signals)
   * @param {object} cars  cars.json-Einträge je id (für Maße und Masse)
   * @param {object} opts  { count, seed, signalState(group, offset) }
   */
  constructor(map, cars, opts = {}) {
    this.map = map;
    this.carsMeta = cars;
    this.rnd = mulberry(opts.seed || 12345);
    this.signalState = opts.signalState || (() => ({ state: 'green', left: 99 }));
    this.target = opts.count !== undefined ? opts.count : 24;
    this.cars = [];
    this.time = 0;
    this._spawnT = 0;
    this.renderer = null;
    this.models = MODELS.filter(([id]) => cars[id]);
    this._buildGraph();
  }

  // ------------------------------------------------------------------ Spurgraph
  _buildGraph() {
    const R = this.map.roads;
    this.lanes = [];
    this.nodes = R.nodes.map((n) => ({ ...n, out: [], in: [] }));
    const types = R.types;
    const ny = R.ew.length;
    const nodeAt = (ia, ib) => this.nodes[ia * ny + ib];
    // Index im Raster je Knoten
    this.nodes.forEach((n, i) => { n.ia = Math.floor(i / ny); n.ib = i % ny; });
    const stopDist = (node, dx, dz) => {
      // Fahrtrichtung entlang z -> Querstraße ist die Ost-West-Straße des Knotens (und umgekehrt)
      const cross = Math.abs(dz) > 0.5 ? types[node.ew] : types[node.ns];
      return HALF(cross) + STOP_EXTRA;
    };
    for (const e of R.edges) {
      const t = types[e.type];
      const A = this.nodes[e.a], B = this.nodes[e.b];
      for (const [P, Q] of [[A, B], [B, A]]) {
        const L = Math.hypot(Q.x - P.x, Q.z - P.z);
        const dx = (Q.x - P.x) / L, dz = (Q.z - P.z) / L;
        const rx = -dz, rz = dx;                     // rechts
        const s0 = stopDist(P, dx, dz), s1 = stopDist(Q, dx, dz);
        for (let k = 0; k < t.lanes; k++) {
          const off = t.median / 2 + (k + 0.5) * t.lane;
          const lane = {
            id: this.lanes.length, from: P.id, to: Q.id, dx, dz, k, count: t.lanes, type: e.type,
            x0: P.x + dx * s0 + rx * off, z0: P.z + dz * s0 + rz * off,
            x1: Q.x - dx * s1 + rx * off, z1: Q.z - dz * s1 + rz * off,
            speed: { boulevard: 60, avenue: 50, street: 35 }[e.type] / 3.6,
            group: Math.abs(dz) > 0.5 ? 0 : 1, conns: [], cars: [],
          };
          lane.len = Math.hypot(lane.x1 - lane.x0, lane.z1 - lane.z0);
          this.lanes.push(lane);
          P.out.push(lane);
          Q.in.push(lane);
        }
      }
    }
    // Verbindungen an den Kreuzungen
    for (const n of this.nodes) {
      for (const L of n.in) {
        for (const O of n.out) {
          const dot = L.dx * O.dx + L.dz * O.dz;
          if (dot < -0.5) continue;                                  // kein Wenden
          const right = O.dx * -L.dz + O.dz * L.dx;                  // O in Richtung „rechts von L“?
          let turn;
          if (dot > 0.5) turn = 'straight';
          else turn = right > 0.5 ? 'right' : 'left';
          if (turn === 'straight' && O.k !== Math.min(L.k, O.count - 1)) continue;
          if (turn === 'right' && (L.k !== L.count - 1 || O.k !== O.count - 1)) continue;
          if (turn === 'left' && (L.k !== 0 || O.k !== 0)) continue;
          L.conns.push(this._connector(L, O, turn));
        }
      }
    }
    // Spuren ohne erlaubte Fahrtrichtung (z. B. linke Spur an einer Ecke mit Rechtskurve):
    // dann jede Ausfahrt erlauben, damit kein Auto steckenbleibt
    for (const n of this.nodes) {
      for (const L of n.in) {
        if (L.conns.length) continue;
        for (const O of n.out) {
          const dot = L.dx * O.dx + L.dz * O.dz;
          if (dot < -0.5) continue;
          const right = O.dx * -L.dz + O.dz * L.dx;
          const turn = dot > 0.5 ? 'straight' : right > 0.5 ? 'right' : 'left';
          if (O.k !== Math.min(L.k, O.count - 1)) continue;
          L.conns.push(this._connector(L, O, turn));
        }
      }
    }
    this.validLanes = this.lanes.filter((l) => l.conns.length && l.len > 8);
  }

  _connector(L, O, turn) {
    const ax = L.x1, az = L.z1, bx = O.x0, bz = O.z0;
    let cx, cz;
    if (turn === 'straight') { cx = (ax + bx) / 2; cz = (az + bz) / 2; }
    else {
      // Schnittpunkt der beiden Spurgeraden (stehen senkrecht aufeinander)
      if (Math.abs(L.dz) > 0.5) { cx = ax; cz = bz; } else { cx = bx; cz = az; }
    }
    const pts = [];
    let len = 0;
    const N = turn === 'straight' ? 2 : 10;
    for (let i = 0; i <= N; i++) {
      const t = i / N, u = 1 - t;
      const x = u * u * ax + 2 * u * t * cx + t * t * bx, z = u * u * az + 2 * u * t * cz + t * t * bz;
      if (i > 0) len += Math.hypot(x - pts[i - 1].x, z - pts[i - 1].z);
      pts.push({ x, z, s: len });
    }
    return { from: L, to: O, turn, pts, len, speed: turn === 'straight' ? L.speed : turn === 'right' ? 6.5 : 8.0 };
  }

  // ------------------------------------------------------------------ Autos
  _newCar(lane, s) {
    const id = pick(this.rnd, this.models.map((m) => m[0]), this.models.map((m) => m[1]));
    const meta = this.carsMeta[id];
    const b = meta.bounds || { min: [0, 0, -meta.dimensions.length / 2], max: [0, 0, meta.dimensions.length / 2] };
    const paint = pick(this.rnd, PAINTS, PAINT_W);
    const car = {
      id, meta, lane, s, conn: null, cs: 0, v: lane.speed * (0.6 + 0.3 * this.rnd()), a: 0,
      front: b.max[2], back: -b.min[2], halfW: meta.dimensions.width / 2,
      speedK: 0.85 + this.rnd() * 0.3, paint, next: null, state: 'drive', brake: 0, blink: 0, hazard: false,
      // Körper für die Kollisionen (wie CarPhysics: Position = Ursprung des Modells)
      body: { pos: { x: 0, y: 0.5, z: 0 }, vel: { x: 0, z: 0 }, yaw: 0, yawRate: 0, mass: meta.stats.massKg,
        Iz: meta.stats.massKg * (meta.dimensions.length ** 2 + meta.dimensions.width ** 2) / 12, hcg: 0.5 },
      crashT: 0, x: 0, z: 0, yaw: 0, dist: 0, stuckT: 0, hit: 0, honkT: 0,
    };
    car.next = this._chooseNext(lane);
    this._place(car);
    car.body.vel.x = Math.sin(car.yaw) * car.v;
    car.body.vel.z = Math.cos(car.yaw) * car.v;
    lane.cars.push(car);
    this.cars.push(car);
    if (this.onAdd) this.onAdd(car);
    return car;
  }

  _chooseNext(lane) {
    const w = { straight: 6, right: 2.5, left: 1.8 };
    return pick(this.rnd, lane.conns, lane.conns.map((c) => w[c.turn]));
  }

  _place(car) {
    let x, z, yaw;
    if (car.conn) {
      const p = car.conn.pts;
      let i = 1;
      while (i < p.length - 1 && p[i].s < car.cs) i++;
      const a = p[i - 1], b = p[i];
      const t = Math.min(1, Math.max(0, (car.cs - a.s) / Math.max(1e-6, b.s - a.s)));
      x = a.x + (b.x - a.x) * t; z = a.z + (b.z - a.z) * t;
      yaw = Math.atan2(b.x - a.x, b.z - a.z);
    } else {
      const L = car.lane;
      x = L.x0 + L.dx * car.s; z = L.z0 + L.dz * car.s;
      yaw = Math.atan2(L.dx, L.dz);
    }
    const dyaw = car.yaw === undefined ? 0 : Math.atan2(Math.sin(yaw - car.yaw), Math.cos(yaw - car.yaw));
    car.x = x; car.z = z; car.yaw = yaw;
    car.body.pos.x = x; car.body.pos.z = z; car.body.yaw = yaw;
    car.dyaw = dyaw;
  }

  remove(car) {
    const i = this.cars.indexOf(car);
    if (i >= 0) this.cars.splice(i, 1);
    if (car.lane) { const j = car.lane.cars.indexOf(car); if (j >= 0) car.lane.cars.splice(j, 1); }
    if (this.onRemove) this.onRemove(car);
  }

  clear() { for (const c of this.cars.slice()) this.remove(c); }

  // Spur-Abschnitt nahe der Position (für das Befüllen)
  _spawnOne(px, pz, minD, maxD) {
    for (let tries = 0; tries < 30; tries++) {
      const lane = this.validLanes[Math.floor(this.rnd() * this.validLanes.length)];
      const s = 4 + this.rnd() * Math.max(1, lane.len - 24);
      const x = lane.x0 + lane.dx * s, z = lane.z0 + lane.dz * s;
      const d = Math.hypot(x - px, z - pz);
      if (d < minD || d > maxD) continue;
      if (lane.cars.some((c) => Math.abs(c.s - s) < 14)) continue;
      return this._newCar(lane, s);
    }
    return null;
  }

  /** Erstbefüllung um den Spieler. */
  fill(px, pz) {
    for (let i = 0; i < this.target * 3 && this.cars.length < this.target; i++) this._spawnOne(px, pz, 25, 170);
  }

  // ------------------------------------------------------------------ Schritt
  /**
   * @param {number} dt
   * @param {object} player  { pos:{x,z}, vel:{x,z}, yaw, speed, length, width } (oder null)
   */
  update(dt, player) {
    this.time += dt;
    const px = player ? player.pos.x : 0, pz = player ? player.pos.z : 0;
    // Bestand halten: ferne Autos entfernen, neue weit weg einsetzen
    for (const c of this.cars.slice()) {
      c.dist = player ? Math.hypot(c.x - px, c.z - pz) : 0;
      if (!player) continue;
      if (c.dist > 200 || (c.state === 'crashed' && c.crashT > 25 && c.dist > 60) || (c.stuckT > 30 && c.dist > 70)) this.remove(c);
    }
    this._spawnT -= dt;
    if (this._spawnT <= 0 && this.cars.length < this.target) {
      this._spawnT = 0.35;
      if (player) this._spawnOne(px, pz, 95, 175);
    }
    for (const c of this.cars) {
      if (c.state === 'crashed') { this._crashed(c, dt); continue; }
      this._drive(c, dt, player);
    }
  }

  _gapAhead(c, player) {
    // nächstes Hindernis in einem Schlauch vor dem Auto: andere Autos und der Spieler
    const fx = Math.sin(c.yaw), fz = Math.cos(c.yaw);
    const width = c.conn ? 2.2 : 1.55;
    let best = 1e9, vLead = 0;
    const test = (x, z, back, vx, vz, halfW) => {
      const dx = x - c.x, dz = z - c.z;
      const along = dx * fx + dz * fz;
      if (along <= 0 || along > 70) return;
      const lat = Math.abs(dx * fz - dz * fx);
      if (lat > width + halfW - 0.9) return;
      const gap = along - c.front - back;
      if (gap < best) { best = gap; vLead = vx * fx + vz * fz; isPlayer = false; }
    };
    let isPlayer = false;
    for (const o of this.cars) {
      if (o === c) continue;
      if (Math.abs(o.x - c.x) > 72 || Math.abs(o.z - c.z) > 72) continue;
      test(o.x, o.z, o.back, o.body.vel.x, o.body.vel.z, o.halfW);
    }
    if (player) {
      const before = best;
      test(player.pos.x, player.pos.z, player.length / 2, player.vel.x, player.vel.z, player.width / 2);
      if (best < before) isPlayer = true;
    }
    return { gap: best, vLead, player: isPlayer };
  }

  _idm(v, v0, gap, vLead) {
    const a = 1.7, b = 2.8, T = 1.25, s0 = 2.2;
    const dv = v - vLead;
    const ss = s0 + Math.max(0, v * T + v * dv / (2 * Math.sqrt(a * b)));
    const free = 1 - Math.pow(v / Math.max(0.1, v0), 4);
    const inter = gap < 1e8 ? Math.pow(ss / Math.max(0.3, gap), 2) : 0;
    return a * (free - inter);
  }

  _drive(c, dt, player) {
    const v0 = (c.conn ? c.conn.speed : c.lane.speed) * c.speedK;
    let acc;
    const ahead = this._gapAhead(c, player);
    acc = this._idm(c.v, v0, ahead.gap, ahead.vLead);
    // steht lange hinter dem Spieler: hupen
    if (ahead.player && ahead.gap < 12 && c.v < 0.5) {
      c.honkT += dt;
      if (c.honkT > 4 && this.onHonk) { c.honkT = -3; this.onHonk(c); }
    } else if (c.honkT > 0) c.honkT = 0;
    // Ampel/Vorfahrt vor der Haltelinie
    c.blink = 0;
    if (!c.conn) {
      const L = c.lane;
      const toStop = L.len - c.s - c.front;
      const node = this.nodes[L.to];
      if (c.next && toStop < 45 && c.next.turn !== 'straight') c.blink = c.next.turn === 'left' ? 1 : 2;
      let stop = false;
      if (node.signal !== null && node.signal !== undefined && toStop > -1) {
        const st = this.signalState(L.group, node.signal).state;
        if (st === 'red') stop = toStop > c.v * c.v / (2 * 7.0) - 0.5;
        else if (st === 'yellow') stop = toStop > c.v * c.v / (2 * 3.5) - 1;
        else if (c.next && c.next.turn === 'left' && toStop < 30) stop = this._mustYield(c, node);
      } else if (c.next && c.next.turn === 'left' && toStop < 20) {
        stop = this._mustYield(c, node);
      }
      if (stop) acc = Math.min(acc, this._idm(c.v, v0, Math.max(0.05, toStop + 0.4), 0));
    }
    acc = Math.max(-7.5, acc);
    c.a = acc;
    c.v = Math.max(0, c.v + acc * dt);
    c.brake = acc < -0.8 || c.v < 0.3 ? 1 : 0;
    c.stuckT = c.v < 0.2 ? c.stuckT + dt : 0;
    const ds = c.v * dt;
    // vorwärts entlang Spur -> Verbindung -> nächste Spur
    if (!c.conn) {
      c.s += ds;
      if (c.s >= c.lane.len) {
        const over = c.s - c.lane.len;
        const j = c.lane.cars.indexOf(c);
        if (j >= 0) c.lane.cars.splice(j, 1);
        c.conn = c.next;
        c.cs = over;
      }
    } else {
      c.cs += ds;
      if (c.cs >= c.conn.len) {
        const over = c.cs - c.conn.len;
        c.lane = c.conn.to;
        c.lane.cars.push(c);
        c.s = over;
        c.conn = null;
        c.next = this._chooseNext(c.lane);
      }
    }
    this._place(c);
    c.body.vel.x = Math.sin(c.yaw) * c.v;
    c.body.vel.z = Math.cos(c.yaw) * c.v;
    c.body.yawRate = dt > 0 ? c.dyaw / dt : 0;
    c.kinematic = { x: c.x, z: c.z, vx: c.body.vel.x, vz: c.body.vel.z, yaw: c.yaw, yr: c.body.yawRate };
  }

  /** Links abbiegen: warten, solange Gegenverkehr kommt. */
  _mustYield(c, node) {
    for (const o of this.cars) {
      if (o === c || o.conn || o.state !== 'drive') continue;
      const L = o.lane;
      if (L.to !== node.id) continue;
      if (L.dx * c.lane.dx + L.dz * c.lane.dz > -0.5) continue;      // nur Gegenrichtung
      const toStop = L.len - o.s;
      if (toStop < 45 && o.v > 1.5) return true;
    }
    return false;
  }

  _crashed(c, dt) {
    const b = c.body;
    c.crashT += dt;
    const sp = Math.hypot(b.vel.x, b.vel.z);
    const dec = Math.min(sp, 7.0 * dt);
    if (sp > 1e-4) { b.vel.x -= b.vel.x / sp * dec; b.vel.z -= b.vel.z / sp * dec; }
    b.yawRate *= Math.exp(-dt * 2.5);
    b.pos.x += b.vel.x * dt; b.pos.z += b.vel.z * dt;
    b.yaw += b.yawRate * dt;
    c.x = b.pos.x; c.z = b.pos.z; c.yaw = b.yaw;
    c.v = 0;
    c.brake = 1;
    c.hazard = true;
    c.blink = 3;
  }

  /**
   * Nach dem Kollisionsschritt aufrufen: wurde ein fahrendes Auto deutlich angestoßen, rutscht es
   * physikalisch aus („Unfall“) und bleibt mit Warnblinker stehen. Leichte Berührungen ignoriert es.
   */
  afterCollisions() {
    for (const c of this.cars) {
      if (c.state !== 'drive' || !c.kinematic) { c.hit = 0; continue; }
      const k = c.kinematic, b = c.body;
      const dv = Math.hypot(b.vel.x - k.vx, b.vel.z - k.vz);
      // nur Stöße durch den Spieler (oder Wände) werfen ein KI-Auto aus der Spur, KI untereinander nicht
      if (c.hit > 1.5 && (dv > 2.0 || Math.abs(b.yawRate - k.yr) > 1.0)) {
        c.state = 'crashed';
        c.crashT = 0;
        if (c.lane) { const j = c.lane.cars.indexOf(c); if (j >= 0) c.lane.cars.splice(j, 1); }
        c.x = b.pos.x; c.z = b.pos.z; c.yaw = b.yaw;
      } else {
        // leichte Berührung: zurück auf die Spur (das KI-Auto ist „schwer“)
        b.pos.x = k.x; b.pos.z = k.z; b.yaw = k.yaw;
        b.vel.x = k.vx; b.vel.z = k.vz; b.yawRate = k.yr;
      }
      c.hit = 0;
    }
  }

  /** Blinker-/Bremslicht-Zustand für die Darstellung. */
  lights(c, time) {
    const on = Math.floor(time * 2.6) % 2 === 0;
    const L = on && (c.blink === 1 || c.blink === 3);
    const Rr = on && (c.blink === 2 || c.blink === 3);
    return [c.brake, L ? 1 : 0, Rr ? 1 : 0];
  }
}
