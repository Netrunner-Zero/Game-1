// Rauchtest des Spiels ohne Browser: lädt game/main.js mit Ersatz-three.js und Mini-DOM,
// startet, fährt mit Tastatur, wechselt Kameras, öffnet das Menü, wechselt Autos und Tageszeit.
//   node tests/smoke/run.mjs
import { register } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

register('./hooks.mjs', import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const { installDom } = await import('./dom.mjs');
const env = installDom(path.join(root, 'game/index.html'), path.join(root, 'game'));
let failures = 0;
const check = (c, m) => { console.log((c ? '   ✓ ' : '   ✗ ') + m); if (!c) failures++; };
process.on('unhandledRejection', (e) => { console.log('   ✗ Unbehandelter Fehler: ' + (e && e.stack || e)); failures++; });

await import(path.join(root, 'game/main.js'));
const G = globalThis.neonHaven;
const $ = (id) => document.getElementById(id);
for (let i = 0; i < 200 && $('bGo').disabled; i++) await env.frames(5);
check(!$('bGo').disabled, 'Laden fertig: ' + $('loadInfo').textContent);
check(G.world && G.car && G.phys, 'Welt, Auto und Physik vorhanden (' + (G.car && G.car.meta.name) + ')');
$('bGo').dispatch('click');
await env.frames(2);
check(G.started, 'Spiel gestartet');

// Gas geben
const z0 = G.phys.pos.z;
env.key('keydown', 'KeyW');
await env.frames(240);
env.key('keyup', 'KeyW');
check(G.phys.speedKmh > 60 && G.phys.pos.z > z0 + 30, `Gas (W): ${G.phys.speedKmh.toFixed(0)} km/h nach 4 s`);
check(G.car.object.position.z > z0 + 25 && Number.isFinite(G.car.bodyPivot.rotation.x), 'Auto-Grafik folgt der Physik');
// Lenken
const yaw0 = G.phys.yaw;
env.key('keydown', 'KeyA');
await env.frames(60);
env.key('keyup', 'KeyA');
check(G.phys.yaw > yaw0 + 0.1, `Lenken links (A): Gieren ${((G.phys.yaw - yaw0) * 57.3).toFixed(0)}°`);
// Bremsen bis Stillstand, dann rückwärts
env.key('keydown', 'KeyS');
await env.frames(360);
check(G.phys.gear === -1 && G.phys.speed < -0.5, `Bremse halten -> rückwärts (${G.phys.gearLabel()}, ${G.phys.speedKmh.toFixed(1)} km/h)`);
env.key('keyup', 'KeyS');
await env.frames(30);
// Kameras durchschalten
const seen = [];
for (let i = 0; i < 5; i++) {
  env.key('keydown', 'KeyC'); env.key('keyup', 'KeyC');
  await env.frames(20);
  seen.push(G.rig.mode);
  const c = G.rig.camera.position;
  if (![c.x, c.y, c.z].every(Number.isFinite)) { check(false, 'Kamera ' + G.rig.mode + ' liefert NaN'); break; }
}
check(new Set(seen).size === 5, 'alle 5 Kameras: ' + seen.join(', '));
// Lage der Kameras zum Auto prüfen (Blickrichtung = Fahrtrichtung, Verfolger hinten/oben)
{
  const fwd = { x: Math.sin(G.phys.yaw), z: Math.cos(G.phys.yaw) };
  for (const mode of ['chase', 'far', 'hood', 'bumper', 'cockpit']) {
    G.rig.setMode(mode);
    await env.frames(3);
    const cam = G.rig.camera;
    const dx = cam.position.x - G.phys.pos.x, dz = cam.position.z - G.phys.pos.z;
    const along = dx * fwd.x + dz * fwd.z;
    let look;
    if (cam._lookAt && (mode === 'chase' || mode === 'far')) {
      const lx = cam._lookAt.x - cam.position.x, lz = cam._lookAt.z - cam.position.z;
      look = (lx * fwd.x + lz * fwd.z) / Math.hypot(lx, lz);
    } else {
      // Kamera blickt entlang −Z ihres Quaternions
      const q = cam.quaternion;
      const v = { x: 0, y: 0, z: -1 };
      const tx = 2 * (q.y * v.z - q.z * v.y), ty = 2 * (q.z * v.x - q.x * v.z), tz = 2 * (q.x * v.y - q.y * v.x);
      const rx = v.x + q.w * tx + q.y * tz - q.z * ty, rz = v.z + q.w * tz + q.x * ty - q.y * tx;
      look = (rx * fwd.x + rz * fwd.z) / Math.hypot(rx, rz);
    }
    const h = cam.position.y;
    const ok = (mode === 'chase' || mode === 'far') ? along < -3 && h > 1.2 && look > 0.9
      : mode === 'cockpit' ? Math.abs(along) < 2.2 && h > 0.7 && h < 1.6 && look > 0.95
      : along > 0 && look > 0.95;
    check(ok, `Kamera ${mode}: ${along.toFixed(2)} m längs, ${h.toFixed(2)} m hoch, Blick·Fahrtrichtung ${look.toFixed(2)}`);
  }
  G.rig.setMode('chase');
}
// Licht, Blinker, Hupe, Zurücksetzen
env.key('keydown', 'KeyL'); await env.frames(5);
check(G.car.state.lights === true, 'Licht an (L)');
env.key('keydown', 'KeyQ'); await env.frames(5);
check(G.car.state.indicator === -1, 'Blinker links (Q)');
env.key('keydown', 'KeyR'); await env.frames(5);
check(Math.abs(G.phys.speed) < 0.01, 'Zurücksetzen (R)');
// Menü
env.key('keydown', 'Escape'); await env.frames(3);
check($('menu').open && G.paused, 'Menü offen, Spiel pausiert');
const tabs = document.querySelectorAll('#tabs .tab');
for (const t of tabs) { t.onclick(); await env.frames(1); }
check(true, 'alle Menü-Reiter aufgebaut');
// Auto über das Menü wechseln
tabs.find((t) => t.dataset.tab === 'car').onclick();
const carBtns = $('menuBody').querySelectorAll('.car');
check(carBtns.length === 6, '6 Autos im Menü');
for (const b of carBtns.slice(1)) {
  b.onclick();
  for (let i = 0; i < 50; i++) { await env.frames(2); if (G.car && !$('menu').open) break; }
  env.key('keydown', 'KeyW'); await env.frames(90); env.key('keyup', 'KeyW');
  check(G.phys.speedKmh > 20, `${G.car.meta.name}: fährt (${G.phys.speedKmh.toFixed(0)} km/h)`);
  env.key('keydown', 'Escape'); await env.frames(2);
  tabs.find((t) => t.dataset.tab === 'car').onclick();
}
$('bClose').onclick();
await env.frames(2);
check(!G.paused, 'Menü geschlossen, weiter');
// Nacht
G.setTime(22.5);
await env.frames(30);
check(G.sky.nightK > 0.9 && G.car.state.lights, `Nacht: Nachtanteil ${G.sky.nightK.toFixed(2)}, Licht automatisch an`);
G.setTime(13);
await env.frames(10);
check(G.sky.nightK < 0.05, 'Tag wieder hell');
// Touch: Gas-Pedal und Wischlenkung
const gas = $('tGas'), zone = $('steerZone');
gas.dispatch('pointerdown');
zone.dispatch('pointerdown', { clientX: 200, clientY: 500 });
zone.dispatch('pointermove', { clientX: 290, clientY: 500 });
await env.frames(120);
check(G.phys.speedKmh > 20 && G.input.out.steer > 0.5, `Touch: Gas + Wischen rechts (${G.phys.speedKmh.toFixed(0)} km/h, Lenkung ${G.input.out.steer.toFixed(2)})`);
gas.dispatch('pointerup');
zone.dispatch('pointerup');
await env.frames(30);
check(Math.abs(G.input.out.steer) < 0.01, 'Touch losgelassen: Lenkung zurück');
// lange fahren (Leistung der Logik, keine NaN)
env.key('keydown', 'KeyW');
const t0 = performance.now();
await env.frames(1200);
env.key('keyup', 'KeyW');
const ms = (performance.now() - t0) / 1200;
check([G.phys.pos.x, G.phys.pos.z, G.phys.yaw].every(Number.isFinite), `20 s Vollgas ohne NaN (${G.phys.speedKmh.toFixed(0)} km/h)`);
check(ms < 4, `Spiel-Logik je Bild: ${ms.toFixed(2)} ms (ohne Grafik)`);
console.log(failures ? `\n${failures} Fehler` : '\nRauchtest bestanden.');
process.exit(failures ? 1 : 0);
