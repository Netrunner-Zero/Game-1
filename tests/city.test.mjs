// Stadt Neon Haven ohne Browser prüfen:  node tests/city.test.mjs
// Startplätze frei und auf der Straße, Bordsteine, Ampelzyklus, Fahrt über den Boulevard, Kollisionen mit Häusern.
import { readFileSync } from 'node:fs';
import { CarPhysics } from '../src/physics/CarPhysics.js';
import { StaticWorld, Collisions, carShape, bodyOBB, testBoxBox, testBoxCircle } from '../src/physics/collision.js';
import { makeGround } from '../src/world/ground.js';

const cars = JSON.parse(readFileSync(new URL('../models/cars.json', import.meta.url))).cars;
const map = JSON.parse(readFileSync(new URL('../world/neon_haven.json', import.meta.url)));
let failures = 0;
const check = (c, m) => { console.log((c ? '   ✓ ' : '   ✗ ') + m); if (!c) failures++; };
const gh = makeGround(map.regions);
const world = { groundHeight: gh, grip: () => 1 };
const statics = new StaticWorld(24);
for (const c of map.colliders) {
  if (c.t === 'box') statics.addBox({ x: c.x, z: c.z, hx: c.hx, hz: c.hz, yaw: c.yaw, top: c.top, kind: c.kind, mu: c.mu, e: c.e });
  else statics.addCircle({ x: c.x, z: c.z, r: c.r, top: c.top, kind: c.kind });
}
for (const def of Object.values(map.instances)) for (const [x, z, , s = 1] of def.items) statics.addCircle({ x, z, r: def.collider.r * s, top: def.collider.top, kind: 'inst' });
console.log(`Karte: ${map.colliders.length} Kollisionskörper + ${Object.values(map.instances).reduce((a, d) => a + d.items.length, 0)} Wiederholteile, ${map.regions.length} Bodenbereiche, ${map.signals.heads.length} Ampelköpfe`);

// Startplätze: auf der Fahrbahn (Höhe 0), Auto passt hin (keine Überlappung mit Hindernissen)
const meta = cars[0];
for (const s of map.spawn) {
  const p = new CarPhysics(meta); p.place(s.x, s.z, s.yaw, gh(s.x, s.z));
  const A = bodyOBB(p, carShape(meta, p.zcg), {});
  const near = statics.query(A.minX, A.minZ, A.maxX, A.maxZ, []);
  const hit = near.some((it) => (it.type === 'box' ? testBoxBox(A, it, {}) : testBoxCircle(A, it, {})));
  check(gh(s.x, s.z) === 0 && !hit, `Startplatz ${s.name}: frei, auf der Straße`);
}
// Bordstein: Höhe am Rand steigt über die Anrampung
const blk = map.regions.find((r) => r.t === 'rect' && r.hx > 30);
check(gh(blk.x, blk.z) === 0.15 && gh(blk.x + blk.hx + 0.14, blk.z) > 0.05 && gh(blk.x + blk.hx + 0.3, blk.z) === 0, 'Gehweg 15 cm, Bordstein mit Anrampung');
// Ampeln: jede Kreuzung (außer Ecken) hat Köpfe für beide Gruppen, Zyklus schaltet nie beide auf Grün
const S = map.signals;
const state = (g, off, t) => { const C = S.cycle, tg = (((t + off - g * C / 2) % C) + C) % C; return tg < S.green ? 'g' : tg < S.green + S.yellow ? 'y' : 'r'; };
let bothGreen = 0;
for (let t = 0; t < S.cycle; t += 0.25) if (state(0, 0, t) !== 'r' && state(1, 0, t) !== 'r') bothGreen++;
check(bothGreen === 0, 'Ampelzyklus: Nord-Süd und Ost-West nie gleichzeitig frei');
check(S.heads.every((h) => h.length === 6 && Number.isFinite(h[0] + h[1] + h[2] + h[3])), 'Ampelköpfe vollständig');

// Fahrt über den Boulevard nach Norden: 600 m, Spur halten, keine Kollision
function drive(meta, s, ctrl, seconds) {
  const p = new CarPhysics(meta); p.place(s.x, s.z, s.yaw, gh(s.x, s.z));
  const col = new Collisions(statics);
  col.add(p, carShape(meta, p.zcg));
  let hits = 0, maxPitch = 0;
  for (let i = 0; i < seconds * 60; i++) {
    const inp = ctrl(p, i / 60);
    for (let k = 0; k < 2; k++) { p.step(1 / 120, inp, world); col.step(() => hits++); }
    maxPitch = Math.max(maxPitch, Math.abs(p.pitch));
  }
  return { p, hits, maxPitch: maxPitch * 57.3 };
}
const aimX = (p, x) => Math.max(-1, Math.min(1, (p.pos.x - x) * 0.25 - (Math.sin(p.yaw)) * 1.5));
for (const m of [cars[0], cars[3], cars[4]]) {
  const s = map.spawn[0];
  const r = drive(m, s, (p) => ({ throttle: p.pos.z < 330 && p.speedKmh < 90 ? 0.7 : 0, brake: p.pos.z > 330 && p.speed > 0.3 ? 0.8 : 0, steer: -aimX(p, s.x) }), 22);
  check(r.hits === 0 && r.p.pos.z > 250 && Math.abs(r.p.pos.x - s.x) < 1.5, `${m.name}: Boulevard nordwärts bis z ${r.p.pos.z.toFixed(0)} ohne Berührung (Spur ${(r.p.pos.x - s.x).toFixed(2)} m)`);
  // quer auf den Gehweg (Bordstein) und gegen ein Haus
  const r2 = drive(m, { x: -4.2, z: -60, yaw: -Math.PI / 2 }, (p) => ({ throttle: 0.6 }), 8);
  check(r2.hits > 0 && Number.isFinite(r2.p.pos.x) && r2.p.pos.y - r2.p.hcg > 0.1, `${m.name}: über den Bordstein auf den Gehweg und gegen ein Haus (${r2.hits} Stöße, Gehweghöhe ${(r2.p.pos.y - r2.p.hcg).toFixed(2)} m)`);
}
console.log(failures ? `\n${failures} Fehler` : '\nAlle Stadt-Tests bestanden.');
process.exit(failures ? 1 : 0);
