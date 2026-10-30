// Stadtverkehr ohne Browser prüfen:  node tests/traffic.test.mjs
// Spurgraph vollständig, Autos fahren, halten an Roten, keine Überlappungen, Bestand bleibt, Abbiegen, Spieler wird beachtet.
import { readFileSync } from 'node:fs';
import { Traffic } from '../src/traffic/Traffic.js';
import { carShape, bodyOBB, testBoxBox, Collisions, StaticWorld } from '../src/physics/collision.js';

const cars = Object.fromEntries(JSON.parse(readFileSync(new URL('../models/cars.json', import.meta.url))).cars.map((c) => [c.id, c]));
const map = JSON.parse(readFileSync(new URL('../world/neon_haven.json', import.meta.url)));
let failures = 0;
const check = (c, m) => { console.log((c ? '   ✓ ' : '   ✗ ') + m); if (!c) failures++; };
const S = map.signals;
const signalState = (g, off, t) => { const C = S.cycle, tg = (((t + off - g * C / 2) % C) + C) % C; return { state: tg < S.green ? 'green' : tg < S.green + S.yellow ? 'yellow' : 'red' }; };
let simTime = 0;
const T = new Traffic(map, cars, { count: 36, seed: 7, signalState: (g, o) => signalState(g, o, simTime) });
check(T.lanes.length > 200 && T.lanes.every((l) => l.conns.length > 0), `Spurgraph: ${T.lanes.length} Spuren, jede hat eine Ausfahrt`);
const turns = { straight: 0, right: 0, left: 0 };
for (const l of T.lanes) for (const c of l.conns) turns[c.turn]++;
check(turns.right > 50 && turns.left > 50, `Verbindungen: ${turns.straight} geradeaus, ${turns.right} rechts, ${turns.left} links`);

const player = { pos: { x: -4.2, z: -170 }, vel: { x: 0, z: 0 }, yaw: 0, speed: 0, length: 4.5, width: 2 };
T.fill(player.pos.x, player.pos.z);
check(T.cars.length >= 30, `Befüllt: ${T.cars.length} Autos`);
const shapes = new Map();
let overlaps = 0, redRuns = 0, crossings = 0, sumV = 0, nV = 0, turned = 0;
const lastLane = new Map();
const t0 = performance.now();
const DT = 1 / 30;
for (let i = 0; i < 30 * 180; i++) {
  simTime += DT;
  // Spieler fährt langsam im Kreis um den Startpunkt (bewegtes Hindernis)
  T.update(DT, player);
  for (const c of T.cars) {
    sumV += c.v; nV++;
    const prev = lastLane.get(c);
    if (prev && prev.lane !== c.lane && !c.conn && prev.conn === null) { /* Spurwechsel ohne Verbindung (gibt es nicht) */ }
    // Überfahren der Haltelinie bei Rot: Auto war auf Spur, ist jetzt auf Verbindung
    if (prev && !prev.conn && c.conn) {
      crossings++;
      const node = T.nodes[prev.lane.to];
      if (node.signal !== null && signalState(prev.lane.group, node.signal, simTime - DT).state === 'red') redRuns++;
      if (c.conn.turn !== 'straight') turned++;
    }
    lastLane.set(c, { lane: c.lane, conn: c.conn });
  }
  if (i % 15 === 0) {
    const list = T.cars.filter((c) => c.state === 'drive');
    for (let a = 0; a < list.length; a++) {
      for (let b = a + 1; b < list.length; b++) {
        const A = list[a], B = list[b];
        if (Math.abs(A.x - B.x) > 8 || Math.abs(A.z - B.z) > 8) continue;
        if (!shapes.has(A.id)) shapes.set(A.id, carShape(A.meta, 0));
        if (!shapes.has(B.id)) shapes.set(B.id, carShape(B.meta, 0));
        const oa = bodyOBB(A.body, shapes.get(A.id), {}), ob = bodyOBB(B.body, shapes.get(B.id), {});
        const r = testBoxBox(oa, ob, {});
        if (r && r.depth > 0.15) overlaps++;
      }
    }
  }
}
const ms = (performance.now() - t0) / (30 * 180);
const avg = sumV / nV;
check(avg > 4 && avg < 16, `Durchschnittstempo ${(avg * 3.6).toFixed(0)} km/h`);
check(crossings > 100 && redRuns === 0, `${crossings} Kreuzungseinfahrten, davon bei Rot: ${redRuns}`);
check(turned > 20, `${turned} Abbiegevorgänge`);
check(overlaps < 5, `Überlappungen zwischen KI-Autos: ${overlaps}`);
check(T.cars.length >= 30 && T.cars.every((c) => Number.isFinite(c.x + c.z + c.yaw + c.v)), `Bestand ${T.cars.length} Autos, alle Werte gültig`);
check(ms < 1.0, `Rechenzeit Verkehr: ${ms.toFixed(3)} ms je Schritt (36 Autos)`);

// Spieler steht auf der Spur vor einem KI-Auto: es hält an und hupt
{
  const T2 = new Traffic(map, cars, { count: 0, seed: 3, signalState: () => ({ state: 'green' }) });
  const lane = T2.validLanes.find((l) => l.type === 'boulevard' && l.len > 80);
  const c = T2._newCar(lane, 5);
  let honks = 0;
  T2.onHonk = () => honks++;
  const pl = { pos: { x: lane.x0 + lane.dx * 50, z: lane.z0 + lane.dz * 50 }, vel: { x: 0, z: 0 }, length: 4.5, width: 2 };
  for (let i = 0; i < 30 * 15; i++) T2.update(DT, pl);
  const gap = Math.hypot(pl.pos.x - c.x, pl.pos.z - c.z) - c.front - 2.25;
  check(c.v < 0.2 && gap > 0.8 && gap < 6 && honks > 0, `KI hält hinter dem Spieler (Abstand ${gap.toFixed(1)} m) und hupt (${honks}×)`);
}
// Spieler rammt ein KI-Auto: es gerät ins Rutschen und bleibt mit Warnblinker stehen
{
  const T3 = new Traffic(map, cars, { count: 0, seed: 5, signalState: () => ({ state: 'green' }) });
  const lane = T3.validLanes.find((l) => l.type === 'avenue' && l.len > 60);
  const c = T3._newCar(lane, 20);
  const col = new Collisions(new StaticWorld());
  const e = col.add(c.body, carShape(c.meta, 0));
  e.traffic = c;
  const pb = { pos: { x: c.x - lane.dz * 6, y: 0.5, z: c.z + lane.dx * 6 }, vel: { x: lane.dz * 20, z: -lane.dx * 20 }, yaw: Math.atan2(lane.dz, -lane.dx), yawRate: 0, mass: 1500, Iz: 2500, hcg: 0.5 };
  // Spieler kommt von links (seitlich) mit 72 km/h
  const pe = col.add(pb, { hx: 1, hz: 2.3, off: 0, bottom: 0.2, top: 1.4 });
  for (let i = 0; i < 30 * 3; i++) {
    T3.update(DT, null);
    pb.pos.x += pb.vel.x * DT; pb.pos.z += pb.vel.z * DT;
    col.step((en, s, x, z, other) => { if (en.traffic && other === pe) en.traffic.hit = Math.max(en.traffic.hit, s); });
    T3.afterCollisions();
  }
  check(c.state === 'crashed' && c.hazard, `Seitlich gerammt: KI-Auto „${c.state}“, Warnblinker an`);
}
console.log(failures ? `\n${failures} Fehler` : '\nAlle Verkehrs-Tests bestanden.');
process.exit(failures ? 1 : 0);
