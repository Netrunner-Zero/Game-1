// Kollisions-Tests ohne Browser:  node tests/collision.test.mjs
import { readFileSync } from 'node:fs';
import { CarPhysics } from '../src/physics/CarPhysics.js';
import { StaticWorld, Collisions, carShape, testBoxBox, testBoxCircle, bodyOBB } from '../src/physics/collision.js';

const cars = JSON.parse(readFileSync(new URL('../models/cars.json', import.meta.url))).cars;
let failures = 0;
const check = (cond, msg) => { if (!cond) { failures++; console.log('   ✗ ' + msg); } else console.log('   ✓ ' + msg); };
const DT = 1 / 60;

function sim(p, col, frames, input, onImpact) {
  for (let i = 0; i < frames; i++) {
    const inp = typeof input === 'function' ? input(i) : input;
    // wie im Spiel: Physik und Kollisionen in Teilschritten von höchstens 1/120 s
    for (let k = 0; k < 2; k++) { p.step(DT / 2, inp); col.step(onImpact); }
  }
}

// --- reine Geometrie
{
  const A = { type: 'box', cx: 0, cz: 0, hx: 1, hz: 2, ax: [1, 0], az: [0, 1] };
  const B = { type: 'box', cx: 0, cz: 2.9, hx: 3, hz: 1, ax: [1, 0], az: [0, 1] };
  const r = testBoxBox(A, B, {});
  check(r && Math.abs(r.depth - 0.1) < 1e-9 && r.nz === -1 && Math.abs(r.px) < 1e-9, 'Rechteck–Rechteck: Tiefe, Normale und Kontakt in der Kantenmitte');
  const C = testBoxCircle(A, { x: 1.2, z: 0, r: 0.3 }, {});
  check(C && Math.abs(C.depth - 0.1) < 1e-9 && C.nx === -1, 'Rechteck–Kreis: seitlicher Treffer');
  check(testBoxCircle(A, { x: 1.4, z: 0, r: 0.3 }, {}) === null, 'Rechteck–Kreis: knapp vorbei');
  const w = new StaticWorld(10);
  w.addBox({ x: 50, z: 0, hx: 1, hz: 30 });
  w.addCircle({ x: -20, z: 5, r: 0.2 });
  check(w.query(40, -5, 60, 5).length === 1 && w.query(-25, 0, -15, 10).length === 1 && w.query(0, 0, 10, 10).length === 0, 'Raster findet nur nahe Hindernisse');
  check(Math.abs(w.raycast(0, 0, 100, 0) - 0.49) < 1e-6, 'Strahl trifft die Wand bei 49 m');
}

for (const meta of [cars[0], cars[3], cars[4]]) {
  console.log(meta.name);
  // 1) Frontalaufprall mit 300 km/h gegen eine 1 m dicke Mauer: kein Durchtunneln
  {
    const p = new CarPhysics(meta); p.place(0, 0, 0);
    p.vel.z = 300 / 3.6; for (const wh of p.wheels) wh.omega = p.vel.z / wh.R;
    const w = new StaticWorld(); w.addBox({ x: 0, z: 60, hx: 20, hz: 0.5 });
    const col = new Collisions(w); const shape = carShape(meta, p.zcg); col.add(p, shape);
    let maxHit = 0;
    sim(p, col, 120, { throttle: 0 }, (e, s) => { maxHit = Math.max(maxHit, s); });
    const front = p.pos.z + shape.off + shape.hz;
    check(front < 59.6 && p.speed < 15 && maxHit > 60, `Mauer mit 300 km/h: steht davor (Front bei ${front.toFixed(2)} m, Stoß ${maxHit.toFixed(0)} m/s)`);
  }
  // 2) Schräg an einer Wand entlang schrammen: wird abgelenkt, fährt weiter, dreht sich nicht wild
  {
    const p = new CarPhysics(meta); p.place(0, 0, 0.12);    // ~7° zur Wand
    p.vel.x = Math.sin(0.12) * 25; p.vel.z = Math.cos(0.12) * 25; for (const wh of p.wheels) wh.omega = 25 / wh.R;
    const w = new StaticWorld(); w.addBox({ x: 6, z: 100, hx: 1, hz: 200 });
    const col = new Collisions(w); col.add(p, carShape(meta, p.zcg));
    sim(p, col, 180, { throttle: 0.3 });
    check(p.pos.x < 4.2 && p.speed > 15 && Math.abs(p.yaw) < 0.6, `Wand streifen: x ${p.pos.x.toFixed(2)}, ${p.speedKmh.toFixed(0)} km/h, Gieren ${(p.yaw * 57.3).toFixed(0)}°`);
  }
  // 3) Ecke eines Pfostens mit der linken Front treffen: Auto dreht nach links weg
  {
    const p = new CarPhysics(meta, { assists: 'off' }); p.place(0, 0, 0);
    p.vel.z = 15; for (const wh of p.wheels) wh.omega = 15 / wh.R;
    const sh = carShape(meta, p.zcg);
    const w = new StaticWorld(); w.addCircle({ x: sh.hx - 0.15, z: 20, r: 0.15 });
    const col = new Collisions(w); col.add(p, sh);
    let hits = 0; sim(p, col, 90, {}, () => hits++);
    check(hits > 0 && p.yaw > 0.05, `Pfosten an der linken Ecke: dreht nach links (${(p.yaw * 57.3).toFixed(0)}°)`);
  }
  // 4) Zwei Autos frontal: Impuls bleibt erhalten, beide prallen ab, keine Überlappung
  {
    const a = new CarPhysics(meta); a.place(0, -10, 0);
    const b = new CarPhysics(cars[1]); b.place(0.3, 10, Math.PI);
    a.vel.z = 20; b.vel.z = -20;
    for (const wh of a.wheels) wh.omega = 20 / wh.R; for (const wh of b.wheels) wh.omega = 20 / wh.R;
    const w = new StaticWorld(); const col = new Collisions(w);
    const ea = col.add(a, carShape(meta, a.zcg)), eb = col.add(b, carShape(cars[1], b.zcg));
    const p0 = a.mass * a.vel.z + b.mass * b.vel.z;
    let p1 = null;
    for (let i = 0; i < 60; i++) {
      for (let k = 0; k < 2; k++) {
        a.step(DT / 2, {}); b.step(DT / 2, {});
        let hit = false; col.step(() => { hit = true; });
        if (hit && p1 === null) p1 = a.mass * a.vel.z + b.mass * b.vel.z;
      }
    }
    const A = bodyOBB(a, ea.shape, {}), B = bodyOBB(b, eb.shape, {});
    const overlap = testBoxBox(A, B, {});
    check(p1 !== null && Math.abs(p1 - p0) / (a.mass * 20) < 0.05 && !overlap && a.pos.z < b.pos.z,
      `Frontal Auto gegen Auto: Impuls erhalten (${p0.toFixed(0)} → ${p1 && p1.toFixed(0)}), getrennt`);
  }
  // 5) Über niedrigen Bordstein-Collider (nur 10 cm hoch) fährt man drüber
  {
    const p = new CarPhysics(meta); p.place(0, 0, 0); p.vel.z = 10; for (const wh of p.wheels) wh.omega = 10 / wh.R;
    const w = new StaticWorld(); w.addBox({ x: 0, z: 15, hx: 5, hz: 0.5, top: 0.1 });
    const col = new Collisions(w); col.add(p, carShape(meta, p.zcg));
    let hits = 0; sim(p, col, 120, { throttle: 0.2 }, () => hits++);
    check(hits === 0 && p.pos.z > 20, 'niedriges Hindernis (10 cm) unter der Karosserie wird ignoriert');
  }
}
console.log(failures ? `\n${failures} Fehler` : '\nAlle Kollisions-Tests bestanden.');
process.exit(failures ? 1 : 0);
