// Verkehr: Erzeugen, Fahrverhalten (Abstandsregelung nach dem IDM-Modell, Spurwechsel mit Blinker),
// Gegenverkehr, Kollisionen und knappe Überholmanöver
import * as THREE from 'three';
import { LANE_X, ONCOMING_X, KMH, SPAWN_AHEAD, ROAD, rand, pick } from './config.js';

const TYPES = [['sedan', 26], ['hatch', 22], ['suv', 18], ['coupe', 6], ['van', 12], ['truck', 11], ['bus', 5]];
const HEAVY = { truck: true, bus: true };
const LANE_SPEED = [[125, 148], [108, 128], [94, 112], [84, 98]];   // km/h je Spur
const ONC_SPEED = [[125, 145], [108, 125], [92, 108], [80, 92]];
const HEAVY_SPEED = { truck: [80, 88], bus: [92, 100] };

const CAR_COLORS = ['#e8e8e6', '#f4f4f2', '#111214', '#1c1e22', '#8e9399', '#5d6268', '#a7adb3', '#1f3a68',
  '#14284a', '#7b1018', '#a3141c', '#2b4a2f', '#c9b08a', '#2f6fb5', '#d4691c', '#3b3f45', '#e0b420', '#6b2c5f'];
const CAB_COLORS = ['#f2f2f0', '#e8e8e6', '#1f3a68', '#a3141c', '#2b4a2f', '#d4a017', '#111214', '#5d6268', '#ff7a00'];
const TRAILER_COLORS = ['#f4f4f2', '#e1e3e5', '#c9ccd0', '#2a3f6e', '#7b1018', '#1f4d2e', '#d9d9d9', '#f2f2f0'];
const BUS_COLORS = ['#f4f4f2', '#e8e8e6', '#1f3a68', '#c9ccd0', '#a3141c', '#e0b420', '#0f6a5a'];

// Intelligent Driver Model: Beschleunigung aus Wunschtempo und Abstand zum Vordermann
export function idm(v, v0, gap, dv) {
  const a = 1.5, b = 2.4, s0 = 4.5, T = 1.0;
  const free = 1 - Math.pow(v / Math.max(v0, 1), 4);
  if (gap > 400) return a * free;
  const sStar = s0 + Math.max(0, v * T + (v * dv) / (2 * Math.sqrt(a * b)));
  return Math.max(-9.5, a * (free - (sStar / Math.max(gap, 0.3)) ** 2));
}

export function nearestLane(x) {
  let best = 0;
  for (let i = 1; i < LANE_X.length; i++) if (Math.abs(LANE_X[i] - x) < Math.abs(LANE_X[best] - x)) best = i;
  return best;
}

export class Traffic {
  constructor(dims, capacity) {
    this.dims = dims;            // Typ → { L, W }
    this.capacity = capacity;    // Typ → max. Anzahl (Instancing)
    this.count = {};
    for (const t of Object.keys(capacity)) this.count[t] = 0;
    this.list = [];              // eigene Fahrtrichtung
    this.oncoming = [];          // Gegenfahrbahn
    this.events = { crash: null, near: [], whoosh: [] };
    this.difficulty = 0;
    this.lead = { gap: 0, v: 0 };
  }

  clear() {
    this.list.length = 0;
    this.oncoming.length = 0;
    for (const t of Object.keys(this.count)) this.count[t] = 0;
  }

  pickType(lane) {
    for (let tries = 0; tries < 10; tries++) {
      let r = Math.random() * 100, type = 'sedan';
      for (const [t, w] of TYPES) {
        if ((r -= w) < 0) {
          type = t;
          break;
        }
      }
      if (HEAVY[type] && lane < 2) continue;
      if (this.count[type] >= this.capacity[type]) continue;
      return type;
    }
    return null;
  }

  makeVehicle(type, lane, s, dir) {
    const d = this.dims[type];
    const range = HEAVY[type] ? HEAVY_SPEED[type] : (dir > 0 ? LANE_SPEED : ONC_SPEED)[lane];
    const v0 = rand(range[0], range[1]) * KMH;
    const palette = type === 'truck' ? CAB_COLORS : type === 'bus' ? BUS_COLORS : CAR_COLORS;
    this.count[type]++;
    return {
      type, L: d.L, W: d.W, lane, dir, s, v: v0, v0,
      x: dir > 0 ? LANE_X[lane] : ONCOMING_X[lane], z: 0, yaw: dir > 0 ? 0 : Math.PI,
      lc: null, cooldown: rand(1, 5), aggressive: Math.random() < 0.12 + 0.3 * this.difficulty,
      braking: false, crashed: false, spin: 0, lat: 0, minGap: 99, passed: false,
      blink: Math.random() * 10,
      color: new THREE.Color(pick(palette)),
      color2: new THREE.Color(pick(TRAILER_COLORS)),
    };
  }

  // Straße füllen; direkt vor dem Spieler bleibt Platz
  populate(P, clearAhead = 110) {
    this.clear();
    for (let s = P.s + clearAhead; s < P.s + SPAWN_AHEAD; s += rand(22, 50)) {
      this.spawnAt(s, Math.floor(Math.random() * 4));
    }
    for (let s = P.s - 30; s < P.s + SPAWN_AHEAD; s += rand(45, 100)) this.spawnOncoming(s);
  }

  spawnAt(s, lane) {
    const type = this.pickType(lane);
    if (!type) return false;
    const d = this.dims[type];
    const x = LANE_X[lane];
    let occupied = 1 << lane;
    for (const o of this.list) {
      const ds = Math.abs(o.s - s);
      if (ds < (o.L + d.L) / 2 + 28 && Math.abs(o.x - x) < 2.6) return false;
      if (ds < 40) occupied |= 1 << nearestLane(o.x);
    }
    if (occupied === 15) return false; // nie alle vier Spuren gleichzeitig sperren
    this.list.push(this.makeVehicle(type, lane, s, 1));
    return true;
  }

  spawnOncoming(s) {
    const lane = Math.floor(Math.random() * 4);
    const type = this.pickType(lane);
    if (!type) return false;
    const d = this.dims[type];
    for (const o of this.oncoming) {
      if (o.lane === lane && Math.abs(o.s - s) < (o.L + d.L) / 2 + 45) return false;
    }
    this.oncoming.push(this.makeVehicle(type, lane, s, -1));
    return true;
  }

  // Nächstes Fahrzeug vor agent im eigenen Fahrkorridor (der Spieler zählt mit)
  leader(agent, P) {
    let gap = 1e9, vl = 0;
    const x1 = agent.x, x2 = agent.lc ? LANE_X[agent.lc.to] : agent.x;
    const near = ox => Math.abs(ox - x1) < 2.3 || Math.abs(ox - x2) < 2.3;
    for (const o of this.list) {
      if (o === agent) continue;
      const ds = o.s - agent.s;
      if (ds <= 0 || !near(o.x)) continue;
      const g = ds - (o.L + agent.L) / 2;
      if (g < gap) {
        gap = g;
        vl = o.v;
      }
    }
    if (P && P !== agent) {
      const ds = P.s - agent.s;
      if (ds > 0 && near(P.x)) {
        const g = ds - (P.L + agent.L) / 2;
        if (g < gap) {
          gap = g;
          vl = P.v;
        }
      }
    }
    this.lead.gap = gap;
    this.lead.v = vl;
    return this.lead;
  }

  // Ist die Zielspur frei? Nach hinten wird je nach Fahrstil mehr oder weniger Abstand verlangt.
  laneSafe(agent, lane, P) {
    const tx = LANE_X[lane];
    const tg = agent.aggressive ? 1.0 : 2.6;
    const ok = (os, ox, ov, oL) => {
      if (Math.abs(ox - tx) > 2.6) return true;
      const ds = os - agent.s, half = (oL + agent.L) / 2;
      if (ds >= 0) return ds - half > 8 + Math.max(0, agent.v - ov) * 2;
      return -ds - half > 6 + Math.max(0, ov - agent.v) * tg;
    };
    for (const o of this.list) {
      if (o === agent) continue;
      if (!ok(o.s, o.x, o.v, o.L)) return false;
      if (o.lc && o.lc.to === lane && !ok(o.s, tx, o.v, o.L)) return false;
    }
    if (P && P !== agent && !ok(P.s, P.x, P.v, P.L)) return false;
    return true;
  }

  decideLane(v, P, lead) {
    const minLane = HEAVY[v.type] ? 2 : 0;
    let target = -1;
    if (lead.gap < 60 && lead.v < v.v0 - 2.5 && v.lane > minLane) {
      target = v.lane - 1; // links überholen
    } else if (v.lane < 3 && Math.random() < 0.3) {
      // Rechtsfahrgebot: zurück nach rechts, wenn dort Platz ist
      const r = v.lane + 1;
      let free = true;
      for (const o of this.list) {
        if (o !== v && Math.abs(o.x - LANE_X[r]) < 2.6 && o.s > v.s && o.s - v.s < 90) {
          free = false;
          break;
        }
      }
      if (free) target = r;
    }
    if (target < 0 || !this.laneSafe(v, target, P)) return;
    v.lc = { from: v.lane, to: target, t: 0, dur: rand(2.2, 3.2), signal: rand(0.8, 1.3) };
  }

  moveLane(v, P, dt) {
    const lc = v.lc;
    if (lc.signal > 0) {
      // erst blinken, dabei weiter prüfen
      lc.signal -= dt;
      if (!this.laneSafe(v, lc.to, P)) {
        v.lc = null;
        v.cooldown = rand(1, 2.5);
      }
      return;
    }
    lc.t += dt;
    const k = Math.min(1, lc.t / lc.dur);
    const x0 = LANE_X[lc.from], x1 = LANE_X[lc.to];
    v.x = x0 + (x1 - x0) * k * k * (3 - 2 * k);
    const vx = ((x1 - x0) * 6 * k * (1 - k)) / lc.dur;
    v.yaw = -Math.atan2(vx, Math.max(v.v, 5));
    if (k >= 1) {
      v.lane = lc.to;
      v.lc = null;
      v.yaw = 0;
      v.cooldown = rand(3, 7);
    }
  }

  // Fahrzeug wurde vom Spieler getroffen
  hit(v, P) {
    v.crashed = true;
    v.lc = null;
    const side = Math.sign(v.x - P.x) || 1, heavy = HEAVY[v.type] ? 0.25 : 1;
    v.spin = side * rand(0.8, 1.8) * heavy;
    v.lat = side * rand(1.5, 3) * heavy;
    if (v.s > P.s) v.v = Math.max(v.v, P.v * 0.75); // von hinten angeschoben
  }

  crashMotion(v, dt) {
    v.v = Math.max(0, v.v - 8 * dt);
    v.s += v.v * dt;
    v.yaw += v.spin * dt;
    v.spin *= Math.max(0, 1 - 1.5 * dt);
    v.x += v.lat * dt;
    v.lat *= Math.max(0, 1 - 2 * dt);
    v.x = Math.max(ROAD.median + 0.4 + v.W / 2, Math.min(ROAD.railRight - 0.1 - v.W / 2, v.x));
    v.braking = true;
  }

  // opts: { active: Kollisionen/Punkte an, difficulty: 0..1 }
  update(dt, P, opts) {
    const ev = this.events;
    ev.crash = null;
    ev.near.length = 0;
    ev.whoosh.length = 0;
    this.difficulty = opts.difficulty;

    // Nachschub weit vorn im Dunst
    const target = Math.round(12 + 14 * opts.difficulty);
    let ahead = 0;
    for (const v of this.list) if (v.s > P.s) ahead++;
    if (ahead < target) this.spawnAt(P.s + SPAWN_AHEAD + rand(0, 40), Math.floor(Math.random() * 4));
    if (this.oncoming.length < 9 + 6 * opts.difficulty && Math.random() < dt * 3) {
      this.spawnOncoming(P.s + SPAWN_AHEAD + rand(0, 60));
    }

    for (const v of this.list) {
      if (v.crashed) {
        this.crashMotion(v, dt);
        continue;
      }
      const lead = this.leader(v, P);
      const acc = idm(v.v, v.v0, lead.gap, v.v - lead.v);
      v.v = Math.max(0, v.v + acc * dt);
      v.braking = acc < -1.3;
      v.s += v.v * dt;
      if (v.lc) this.moveLane(v, P, dt);
      else if ((v.cooldown -= dt) <= 0) {
        v.cooldown = rand(0.4, 0.9);
        this.decideLane(v, P, lead);
      }
    }

    for (const o of this.oncoming) {
      let gap = 1e9, vl = 0;
      for (const q of this.oncoming) {
        if (q === o || q.lane !== o.lane) continue;
        const ds = o.s - q.s;
        if (ds > 0 && ds - (o.L + q.L) / 2 < gap) {
          gap = ds - (o.L + q.L) / 2;
          vl = q.v;
        }
      }
      const acc = idm(o.v, o.v0, gap, o.v - vl);
      o.v = Math.max(0, o.v + acc * dt);
      o.s -= o.v * dt;
    }

    // Spieler: Kollision, knappe Überholer, Vorbeifahrgeräusche
    for (const v of this.list) {
      const ds = v.s - P.s, halfL = (v.L + P.L) / 2;
      const dx = Math.abs(v.x - P.x), gap = dx - (v.W + P.W) / 2;
      if (opts.active && !v.crashed && Math.abs(ds) < halfL - 0.25 && dx < (v.W + P.W) / 2 - 0.12) ev.crash = v;
      if (Math.abs(ds) < halfL) {
        if (gap < v.minGap) v.minGap = gap;
      } else if (ds < -halfL && !v.passed) {
        v.passed = true;
        if (opts.active && v.minGap < 1.1 && P.v > 22 && P.v - v.v > 3) ev.near.push(v.minGap);
        if (v.minGap < 3.5) ev.whoosh.push({ pan: Math.sign(v.x - P.x), vol: 1 - v.minGap / 4, heavy: !!HEAVY[v.type] });
      } else if (ds > halfL + 3 && v.passed) {
        v.passed = false;
        v.minGap = 99;
      }
    }
    for (const o of this.oncoming) {
      if (!o.passed && o.s < P.s) {
        o.passed = true;
        ev.whoosh.push({ pan: -1, vol: 0.3, heavy: !!HEAVY[o.type] });
      }
    }

    this.removeIf(this.list, v => v.s < P.s - 45 - v.L / 2 || v.s > P.s + SPAWN_AHEAD + 220);
    this.removeIf(this.oncoming, o => o.s < P.s - 60);
    for (const v of this.list) v.z = P.s - v.s;
    for (const o of this.oncoming) o.z = P.s - o.s;
  }

  removeIf(arr, fn) {
    for (let i = arr.length - 1; i >= 0; i--) {
      if (fn(arr[i])) {
        this.count[arr[i].type]--;
        arr[i] = arr[arr.length - 1];
        arr.pop();
      }
    }
  }
}
