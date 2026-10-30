// Testgelände ohne Browser durchfahren:  node tests/world.test.mjs
// Prüft Bodenhöhen (Rampen, Wellen) gegen die Kartendaten und fährt die Stationen mit echter Physik ab.
import { readFileSync } from 'node:fs';
import { CarPhysics } from '../src/physics/CarPhysics.js';
import { StaticWorld, Collisions, carShape, bodyOBB } from '../src/physics/collision.js';
import { makeGround } from '../src/world/ground.js';

const cars = JSON.parse(readFileSync(new URL('../models/cars.json', import.meta.url))).cars;
const map = JSON.parse(readFileSync(new URL('../world/testgelaende.json', import.meta.url)));
let failures = 0;
const check = (c, m) => { console.log((c ? '   ✓ ' : '   ✗ ') + m); if (!c) failures++; };
const gh = makeGround(map.regions);
const world = { groundHeight: gh, grip: () => 1 };
const statics = new StaticWorld(24);
for (const c of map.colliders) {
  if (c.t === 'box') statics.addBox({ x: c.x, z: c.z, hx: c.hx, hz: c.hz, yaw: c.yaw, top: c.top, kind: c.kind, mu: c.mu, e: c.e });
  else statics.addCircle({ x: c.x, z: c.z, r: c.r, top: c.top, kind: c.kind, mu: c.mu, e: c.e });
}

// Bodenhöhen
const table = map.regions.find((r) => r.t === 'ramp' && r.prof.length === 4);
check(Math.abs(gh(table.x, table.z) - 1.7) < 1e-9 && gh(table.x, table.z - 12) > 0.4 && gh(table.x, table.z - 25) === 0, 'Tisch-Sprung: Höhe oben 1,7 m, Auffahrt steigt, davor 0');
const waves = map.regions.find((r) => r.t === 'waves' && r.amp > 0.2);
check(Math.abs(gh(waves.x, waves.z) - waves.amp * 0.5 * (1 - Math.cos(2 * Math.PI * waves.hl / waves.len))) < 1e-9, 'Bodenwellen: Höhe passt zur Formel');
check(gh(0, -532) === 0, 'Startplatz eben');

function drive(meta, start, ctrl, seconds, onImpact) {
  const p = new CarPhysics(meta, { assists: 'full' });
  p.place(start.x, start.z, start.yaw || 0, gh(start.x, start.z));
  const col = new Collisions(statics);
  const e = col.add(p, carShape(meta, p.zcg));
  const DT = 1 / 60, n = 2;
  let maxPitch = 0, maxRoll = 0, air = 0, hits = 0, maxHit = 0;
  for (let i = 0; i < seconds * 60; i++) {
    const inp = ctrl(p, i * DT);
    for (let k = 0; k < n; k++) {
      p.step(DT / n, inp, world);
      col.step((en, s) => { hits++; maxHit = Math.max(maxHit, s); if (onImpact) onImpact(s); });
    }
    maxPitch = Math.max(maxPitch, Math.abs(p.pitch)); maxRoll = Math.max(maxRoll, Math.abs(p.roll));
    air = Math.max(air, p.airTime);
  }
  return { p, e, maxPitch: maxPitch * 57.3, maxRoll: maxRoll * 57.3, air, hits, maxHit };
}

// Lenkregler: Kurs auf einen Punkt halten (wie ein Fahrer)
const aim = (p, tx, tz) => {
  const want = Math.atan2(tx - p.pos.x, tz - p.pos.z);
  let d = want - p.yaw;
  while (d > Math.PI) d -= 2 * Math.PI;
  while (d < -Math.PI) d += 2 * Math.PI;
  return Math.max(-1, Math.min(1, -d * 2.5));
};

for (const meta of cars) {
  console.log(meta.name);
  // 1) Gerade bis zum Ende: Bremsen vor der Leitwand, kein Aufprall
  {
    // bremsen bis zum Stillstand, dann loslassen (Bremse im Stand halten = Rückwärtsgang)
    const r = drive(meta, map.spawn[0], (p) => ({ throttle: p.pos.z < 270 ? 1 : 0, brake: p.pos.z >= 270 && p.speed > 0.3 ? 1 : 0,
      steer: aim(p, 0, 500) }), 30);
    check(r.hits === 0 && r.p.pos.z > 300 && r.p.pos.z < 594 && Math.abs(r.p.speed) < 0.5,
      `Gerade + Vollbremsung: steht bei z ${r.p.pos.z.toFixed(0)} m ohne Aufprall (Treffer ${r.hits}, x ${r.p.pos.x.toFixed(2)}, v ${r.p.speed.toFixed(2)})`);
  }
  // 2) Tisch-Sprung mit 75 km/h: hebt ab, landet gerade, keine Wand berührt
  {
    const s = map.spawn.find((q) => q.name === 'Tisch-Sprung');
    const r = drive(meta, s, (p) => ({ throttle: p.speedKmh < 85 ? 1 : 0.15, brake: p.pos.z > 150 && p.speed > 0.3 ? 0.6 : 0, steer: aim(p, s.x, 400) }), 12);
    check(r.air > 0.1 && r.hits === 0 && r.maxPitch < 20 && Math.abs(r.p.pos.x - s.x) < 2.5 && Math.abs(r.p.yaw) < 0.25,
      `Tisch-Sprung (85 km/h): ${r.air.toFixed(2)} s in der Luft, Nicken max ${r.maxPitch.toFixed(1)}°, Spur ${(r.p.pos.x - s.x).toFixed(2)} m`);
  }
  // 3) Bodenwellen mit 60 km/h: bleibt stabil
  {
    const s = map.spawn.find((q) => q.name === 'Wellenstrecke');
    const r = drive(meta, s, (p) => ({ throttle: p.speedKmh < 60 ? 0.8 : 0.1, steer: aim(p, s.x, 400) }), 12);
    check(r.maxPitch < 15 && r.maxRoll < 8 && Math.abs(r.p.pos.x - s.x) < 2 && r.p.pos.z > 215,
      `Wellenstrecke: Nicken max ${r.maxPitch.toFixed(1)}°, Wanken max ${r.maxRoll.toFixed(1)}°, Spur ${(r.p.pos.x - s.x).toFixed(2)} m`);
  }
  // 4) Crashwand mit 60 km/h: prallt ab, steht davor, Stoß gemeldet
  {
    const r = drive(meta, { x: -215, z: -330, yaw: Math.PI }, (p) => ({ throttle: p.speedKmh < 60 && p.pos.z > -370 ? 1 : 0, steer: 0 }), 6);
    const A = bodyOBB(r.p, r.e.shape, {});
    check(r.maxHit > 10 && A.minZ > -385.6 - 0.3 - 1.05 && r.p.pos.z > -386, `Crashwand: Stoß ${r.maxHit.toFixed(1)} m/s, steht davor`);
  }
  // 5) Kreisbahn r = 37,5 m: Querbeschleunigung im erwarteten Bereich
  {
    const cx = 150, cz = -170, R = 37.5;
    let maxG = 0;
    const r = drive(meta, { x: cx, z: cz - R, yaw: -Math.PI / 2 }, (p, t) => {
      // tangential im Uhrzeigersinn um die Mitte (von oben), Abstand halten
      const dx = p.pos.x - cx, dz = p.pos.z - cz;
      const dist = Math.hypot(dx, dz);
      const tx = cx + (dx / dist) * R + (dz / dist) * 8, tz = cz + (dz / dist) * R - (dx / dist) * 8;
      if (t > 10) maxG = Math.max(maxG, Math.abs(p.accLat) / 9.81);
      return { throttle: p.speedKmh < 20 + t * 6 ? 0.5 : 0, steer: aim(p, tx, tz) };
    }, 20);
    check(maxG > 0.7 && maxG < 1.4 && r.hits === 0, `Kreisbahn: bis ${maxG.toFixed(2)} g quer`);
  }
}
console.log(failures ? `\n${failures} Fehler` : '\nAlle Welt-Tests bestanden.');
process.exit(failures ? 1 : 0);
