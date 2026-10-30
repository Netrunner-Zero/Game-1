// Bodenhöhe einer Karte aus ihren Bereichen (Rampen, Wellen) – ohne Grafik, auch für Tests in Node.
// Koordinaten wie bei den Autos: lokale +Z-Achse zeigt nach (sin yaw, cos yaw), lokale +X nach (cos yaw, −sin yaw).

export function makeGround(regionsIn) {
  const regions = (regionsIn || []).map((r) => {
    const c = Math.cos(r.yaw || 0), s = Math.sin(r.yaw || 0);
    const hl = r.t === 'ramp' ? Math.max(Math.abs(r.prof[0][0]), Math.abs(r.prof[r.prof.length - 1][0])) : r.hl;
    return { ...r, c, s, reach: Math.hypot(r.hw, hl) + 0.5 };
  });
  return function groundHeight(x, z) {
    let h = 0;
    for (const r of regions) {
      const dx = x - r.x, dz = z - r.z;
      if (dx * dx + dz * dz > r.reach * r.reach) continue;
      const lx = dx * r.c - dz * r.s;
      const lz = dx * r.s + dz * r.c;
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
