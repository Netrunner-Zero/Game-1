// Fahrphysik-Tests ohne Browser:  node tests/physics.test.mjs
// Prüft für alle Autos Beschleunigung, Höchstgeschwindigkeit, Bremsweg, Kurvengrip,
// Geradeauslauf, Rückwärtsgang, Handbremse und numerische Stabilität.

import { readFileSync } from 'node:fs';
import { CarPhysics } from '../src/physics/CarPhysics.js';

const cars = JSON.parse(readFileSync(new URL('../models/cars.json', import.meta.url))).cars;
const DT = 1 / 60;
let failures = 0;

function check(cond, msg) {
  if (!cond) { failures++; console.log('   ✗ ' + msg); }
}

function accelTest(meta) {
  const p = new CarPhysics(meta);
  p.place(0, 0, 0);
  let t = 0, t100 = null, t200 = null;
  while (t < 90) {
    p.step(DT, { throttle: 1, brake: 0, steer: 0 });
    t += DT;
    if (t100 === null && p.speedKmh >= 100) t100 = t;
    if (t200 === null && p.speedKmh >= 200) t200 = t;
  }
  return { t100, t200, vmax: p.speedKmh, heading: p.yaw * 180 / Math.PI, x: p.pos.x };
}

function brakeTest(meta) {
  const p = new CarPhysics(meta);
  p.place(0, 0, 0);
  let t = 0;
  while (p.speedKmh < 100 && t < 30) { p.step(DT, { throttle: 1 }); t += DT; }
  const z0 = p.pos.z;
  let n = 0;
  while (p.speed > 0.1 && n < 1200) { p.step(DT, { throttle: 0, brake: 1 }); n++; }
  return { dist: p.pos.z - z0, time: n * DT };
}

function skidpad(meta) {
  // konstante 70 km/h, Lenkung langsam steigern, maximale Querbeschleunigung messen
  const p = new CarPhysics(meta);
  p.place(0, 0, 0);
  let t = 0, maxLat = 0;
  while (p.speedKmh < 70 && t < 30) { p.step(DT, { throttle: 1 }); t += DT; }
  for (let i = 0; i < 600; i++) {
    const steer = Math.min(1, i / 400);
    const thr = Math.max(0, Math.min(1, (70 - p.speedKmh) * 0.2 + 0.25));
    p.step(DT, { throttle: thr, steer });
    if (i > 60) maxLat = Math.max(maxLat, Math.abs(p.accLat));
  }
  return { latG: maxLat / 9.81, speed: p.speedKmh };
}

function reverseTest(meta) {
  const p = new CarPhysics(meta);
  p.place(0, 0, 0);
  for (let i = 0; i < 240; i++) p.step(DT, { brake: 1 });
  return { gear: p.gearLabel(), speed: p.speedKmh, z: p.pos.z };
}

function handbrakeTest(meta) {
  const p = new CarPhysics(meta, { assists: 'off' });
  p.place(0, 0, 0);
  let t = 0;
  while (p.speedKmh < 60 && t < 20) { p.step(DT, { throttle: 1 }); t += DT; }
  const y0 = p.yaw;
  for (let i = 0; i < 60; i++) p.step(DT, { throttle: 0, steer: -0.6, handbrake: 1 });
  return { dyaw: (p.yaw - y0) * 180 / Math.PI };
}

function chaos(meta) {
  const p = new CarPhysics(meta, { assists: 'sport' });
  p.place(0, 0, 0);
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  let inp = { throttle: 1, brake: 0, steer: 0, handbrake: 0 };
  let maxPitch = 0, maxRoll = 0;
  for (let i = 0; i < 60 * 90; i++) {
    if (i % 30 === 0) inp = { throttle: rnd(), brake: rnd() < 0.2 ? rnd() : 0, steer: rnd() * 2 - 1, handbrake: rnd() < 0.05 ? 1 : 0 };
    p.step(DT, inp);
    maxPitch = Math.max(maxPitch, Math.abs(p.pitch));
    maxRoll = Math.max(maxRoll, Math.abs(p.roll));
  }
  const finite = [p.pos.x, p.pos.y, p.pos.z, p.yaw, p.vel.x, p.vel.z, p.rpm].every(Number.isFinite);
  return { finite, maxPitch: maxPitch * 180 / Math.PI, maxRoll: maxRoll * 180 / Math.PI, y: p.pos.y };
}

function settle(meta) {
  // im Stand: Federung kommt zur Ruhe, Auto bleibt stehen
  const p = new CarPhysics(meta);
  p.place(0, 0, 0);
  for (let i = 0; i < 300; i++) p.step(DT, {});
  return { drift: Math.hypot(p.pos.x, p.pos.z), y: p.pos.y - p.hcg, pitch: p.pitch * 180 / Math.PI };
}

console.log('Auto           0-100   0-200   Vmax   Bremsweg  Quer-g  HB-Gier  Rück  max Nicken/Wanken');
for (const meta of cars) {
  const a = accelTest(meta);
  const b = brakeTest(meta);
  const s = skidpad(meta);
  const r = reverseTest(meta);
  const h = handbrakeTest(meta);
  const c = chaos(meta);
  const st = settle(meta);
  const f = (v, d = 1) => (v === null ? '  –  ' : v.toFixed(d));
  console.log(`${meta.name.padEnd(13)} ${f(a.t100).padStart(6)}s ${f(a.t200).padStart(6)}s ${a.vmax.toFixed(0).padStart(5)} ` +
    `${b.dist.toFixed(1).padStart(7)} m ${s.latG.toFixed(2).padStart(6)} ${h.dyaw.toFixed(0).padStart(7)}° ${r.gear.padStart(4)} ` +
    `   ${c.maxPitch.toFixed(1)}° / ${c.maxRoll.toFixed(1)}°`);
  check(a.t100 !== null && a.t100 > 1.8 && a.t100 < 9.5, `${meta.name}: 0-100 ${a.t100}`);
  check(Math.abs(a.vmax - meta.stats.topSpeedKmh) < meta.stats.topSpeedKmh * 0.12, `${meta.name}: Vmax ${a.vmax.toFixed(0)} statt ~${meta.stats.topSpeedKmh}`);
  check(Math.abs(a.heading) < 1.0, `${meta.name}: Geradeauslauf weicht ${a.heading.toFixed(2)}° ab`);
  check(b.dist > 28 && b.dist < 48, `${meta.name}: Bremsweg 100-0 ${b.dist.toFixed(1)} m`);
  check(s.latG > 0.75 && s.latG < 1.35, `${meta.name}: Querbeschleunigung ${s.latG.toFixed(2)} g`);
  check(r.gear === 'R' && r.speed < -1, `${meta.name}: Rückwärtsgang (${r.gear}, ${r.speed.toFixed(1)} km/h)`);
  check(Math.abs(h.dyaw) > 25, `${meta.name}: Handbremse dreht nur ${h.dyaw.toFixed(0)}°`);
  check(c.finite && c.maxPitch < 15 && c.maxRoll < 15, `${meta.name}: instabil (${JSON.stringify(c)})`);
  check(st.drift < 0.05 && Math.abs(st.y) < 0.05, `${meta.name}: steht nicht ruhig (${JSON.stringify(st)})`);
}
console.log(failures ? `\n${failures} Fehler` : '\nAlle Physik-Tests bestanden.');
process.exit(failures ? 1 : 0);
