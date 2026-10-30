// Bodenhöhe einer Karte aus ihren Bereichen – ohne Grafik, auch für Tests in Node.
//   ramp   Rampe/Tisch: Höhenprofil entlang der lokalen z-Achse
//   waves  Wellenstrecke
//   rect   erhöhte Fläche (Gehweg, Insel) mit Anrampung außen (Bordstein: das Rad rollt hinauf)
// Koordinaten wie bei den Autos: lokale +Z-Achse zeigt nach (sin yaw, cos yaw), lokale +X nach (cos yaw, −sin yaw).
// Viele Bereiche (Stadt: ~100 Gehwegblöcke) liegen in einem Raster, abgefragt wird nur die eigene Zelle.

const CELL = 32;

export function makeGround(regionsIn) {
  const regions = (regionsIn || []).map((r) => {
    const c = Math.cos(r.yaw || 0), s = Math.sin(r.yaw || 0);
    let hx, hz;
    if (r.t === 'ramp') { hx = r.hw; hz = Math.max(Math.abs(r.prof[0][0]), Math.abs(r.prof[r.prof.length - 1][0])); }
    else if (r.t === 'waves') { hx = r.hw; hz = r.hl; }
    else { hx = r.hx + (r.bevel || 0); hz = r.hz + (r.bevel || 0); }
    const ex = Math.abs(c) * hx + Math.abs(s) * hz, ez = Math.abs(s) * hx + Math.abs(c) * hz;
    return { ...r, c, s, minX: r.x - ex, maxX: r.x + ex, minZ: r.z - ez, maxZ: r.z + ez };
  });
  const grid = new Map();
  const key = (i, j) => i * 100003 + j;
  for (const r of regions) {
    for (let i = Math.floor(r.minX / CELL); i <= Math.floor(r.maxX / CELL); i++) {
      for (let j = Math.floor(r.minZ / CELL); j <= Math.floor(r.maxZ / CELL); j++) {
        const k = key(i, j);
        if (!grid.has(k)) grid.set(k, []);
        grid.get(k).push(r);
      }
    }
  }
  return function groundHeight(x, z) {
    const list = grid.get(key(Math.floor(x / CELL), Math.floor(z / CELL)));
    if (!list) return 0;
    let h = 0;
    for (const r of list) {
      if (x < r.minX || x > r.maxX || z < r.minZ || z > r.maxZ) continue;
      const dx = x - r.x, dz = z - r.z;
      const lx = dx * r.c - dz * r.s;
      const lz = dx * r.s + dz * r.c;
      if (r.t === 'rect') {
        const ox = Math.abs(lx) - r.hx, oz = Math.abs(lz) - r.hz;
        if (ox <= 0 && oz <= 0) { h = Math.max(h, r.h); continue; }
        const b = r.bevel || 0;
        if (b <= 0) continue;
        const d = Math.hypot(Math.max(ox, 0), Math.max(oz, 0));
        if (d < b) h = Math.max(h, r.h * (1 - d / b));
        continue;
      }
      if (Math.abs(lx) > r.hw) continue;
      if (r.t === 'ramp') {
        const p = r.prof;
        if (lz < p[0][0] || lz > p[p.length - 1][0]) continue;
        for (let i = 0; i < p.length - 1; i++) {
          if (lz <= p[i + 1][0]) {
            const t = (lz - p[i][0]) / Math.max(1e-9, p[i + 1][0] - p[i][0]);
            h = Math.max(h, p[i][1] + (p[i + 1][1] - p[i][1]) * t);
            break;
          }
        }
      } else if (r.t === 'waves') {
        if (Math.abs(lz) > r.hl) continue;
        h = Math.max(h, r.amp * 0.5 * (1 - Math.cos(2 * Math.PI * (lz + r.hl) / r.len)));
      }
    }
    return h;
  };
}
