"""Strahltests gegen Dreiecke (Möller-Trumbore, vektorisiert).

Wird benutzt, um Anbauteile exakt auf die Karosserie zu setzen
(Punkt + Normale an einer Stelle der Oberfläche).
"""
import numpy as np


class Raycaster:
    def __init__(self, parts, mats=None):
        tris = []
        for p in parts:
            for m, tl in p.tris.items():
                if mats is not None and m not in mats:
                    continue
                for t in tl:
                    tris.append((t[0], t[1], t[2]))
        T = np.asarray(tris, dtype=float) if tris else np.zeros((0, 3, 3))
        self.v0 = T[:, 0]
        self.e1 = T[:, 1] - T[:, 0]
        self.e2 = T[:, 2] - T[:, 0]
        n = np.cross(self.e1, self.e2)
        self.n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    def cast(self, origin, direction, max_t=10.0):
        """Liefert (Punkt, Normale zur Strahlquelle hin, t) oder None."""
        o = np.asarray(origin, dtype=float)
        d = np.asarray(direction, dtype=float)
        d = d / np.linalg.norm(d)
        p = np.cross(d, self.e2)
        det = np.einsum("ij,ij->i", self.e1, p)
        ok = np.abs(det) > 1e-12
        inv = np.zeros_like(det)
        inv[ok] = 1.0 / det[ok]
        s = o - self.v0
        u = np.einsum("ij,ij->i", s, p) * inv
        q = np.cross(s, self.e1)
        v = (q @ d) * inv
        t = np.einsum("ij,ij->i", self.e2, q) * inv
        hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-6) & (t < max_t)
        if not hit.any():
            return None
        idx = np.where(hit)[0]
        k = idx[np.argmin(t[idx])]
        pt = o + d * t[k]
        nn = self.n[k]
        if np.dot(nn, d) > 0:
            nn = -nn
        return pt, nn, float(t[k])

    def surface(self, origin, direction, max_t=10.0):
        r = self.cast(origin, direction, max_t)
        if r is None:
            raise ValueError("Kein Treffer: %s -> %s" % (origin, direction))
        return r
