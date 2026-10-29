"""Exakte Ausschnitte in der Karosseriehaut.

Lampen, Lufteinlässe, Grills und Lamellen sitzen in echten Öffnungen:
Ein Ausschnitt ist ein konvexes Polygon im lokalen Rahmen eines
Anbauteils (u = rechts, v = oben, w = Oberflächennormale). Dreiecke der
Haut, die das Polygon schneiden, werden exakt beschnitten
(Dreieck minus konvexes Polygon = Vereinigung konvexer Stücke, je ein
Stück pro Polygonkante, Sutherland-Hodgman). So entsteht eine saubere
Kante ohne Treppen, unabhängig von der Netzauflösung.
"""
import numpy as np


class Cut:
    def __init__(self, origin, r, up, n, poly, wmax=0.10, min_dot=0.12):
        self.o = np.asarray(origin, dtype=float)
        self.r = np.asarray(r, dtype=float)
        self.up = np.asarray(up, dtype=float)
        self.n = np.asarray(n, dtype=float)
        P = np.asarray(poly, dtype=float)
        # gegen den Uhrzeigersinn erzwingen
        area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
        if area < 0:
            P = P[::-1]
        self.poly = P
        self.lo = P.min(axis=0)
        self.hi = P.max(axis=0)
        self.wmax = wmax
        self.min_dot = min_dot

    def project(self, pts):
        d = np.asarray(pts, dtype=float) - self.o
        return np.stack([d @ self.r, d @ self.up], -1), d @ self.n

    def inside(self, uv):
        P = self.poly
        a = P
        b = np.roll(P, -1, axis=0)
        cross = (b[:, 0] - a[:, 0]) * (uv[1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (uv[0] - a[:, 0])
        return bool(np.all(cross >= 0))


def _clip(poly, a, b, keep_left):
    """Sutherland-Hodgman: Polygon (Liste von (uv, bary)) an der Geraden a->b."""
    out = []
    n = len(poly)
    if n == 0:
        return out

    def side(p):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])

    for i in range(n):
        cur, nxt = poly[i], poly[(i + 1) % n]
        sc, sn = side(cur[0]), side(nxt[0])
        ic = sc >= 0 if keep_left else sc < 0
        inn = sn >= 0 if keep_left else sn < 0
        if ic:
            out.append(cur)
        if ic != inn:
            t = sc / (sc - sn)
            out.append((cur[0] + (nxt[0] - cur[0]) * t, cur[1] + (nxt[1] - cur[1]) * t))
    return out


def tri_minus(tri_uv, cut):
    """Dreieck (3 uv-Punkte) minus konvexes Polygon -> Liste konvexer Stücke.

    Jeder Stückpunkt trägt baryzentrische Koordinaten bezüglich des Dreiecks.
    Rückgabe None = Dreieck unberührt (liegt komplett außerhalb).
    """
    rest = [(np.asarray(tri_uv[i], dtype=float), np.eye(3)[i]) for i in range(3)]
    P = cut.poly
    pieces = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        outside = _clip(rest, a, b, keep_left=False)
        inside = _clip(rest, a, b, keep_left=True)
        if len(outside) >= 3 and _area(outside) > 1e-12:
            pieces.append(outside)
        rest = inside
        if len(rest) < 3 or _area(rest) < 1e-12:
            return None      # Dreieck berührt das Polygon nicht
    return pieces


def _area(poly):
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i][0]
        x1, y1 = poly[(i + 1) % n][0]
        s += x0 * y1 - x1 * y0
    return abs(s) * 0.5


def cut_triangles(tris, cuts):
    """tris: Liste (a, b, c, normals, uvs) eines Materials. Liefert neue Liste."""
    for cut in cuts:
        if not tris:
            break
        A = np.array([t[0] for t in tris])
        B = np.array([t[1] for t in tris])
        Cc = np.array([t[2] for t in tris])
        cen = (A + B + Cc) / 3.0
        fn = np.cross(B - A, Cc - A)
        ln = np.linalg.norm(fn, axis=1)
        ok = ln > 1e-14
        fn = fn / np.maximum(ln, 1e-14)[:, None]
        w = (cen - cut.o) @ cut.n
        cand = ok & (np.abs(w) <= cut.wmax) & (fn @ cut.n >= cut.min_dot)
        U = np.stack([(A - cut.o) @ cut.r, (B - cut.o) @ cut.r, (Cc - cut.o) @ cut.r], 1)
        V = np.stack([(A - cut.o) @ cut.up, (B - cut.o) @ cut.up, (Cc - cut.o) @ cut.up], 1)
        cand &= ~((U.max(1) < cut.lo[0]) | (U.min(1) > cut.hi[0]) | (V.max(1) < cut.lo[1]) | (V.min(1) > cut.hi[1]))
        idx = np.where(cand)[0]
        if len(idx) == 0:
            continue
        cand_set = set(idx.tolist())
        out = []
        for i, t in enumerate(tris):
            if i not in cand_set:
                out.append(t)
                continue
            a, b, c, ns, uvs = t
            uv = np.stack([U[i], V[i]], -1)
            res = tri_minus(uv, cut)
            if res is None:
                out.append(t)
                continue
            P3 = np.array([a, b, c])
            N3 = np.array(ns, dtype=float)
            T3 = np.array(uvs, dtype=float)
            for piece in res:
                verts = []
                for (_p2, bc) in piece:
                    nrm = bc @ N3
                    nrm = nrm / max(np.linalg.norm(nrm), 1e-12)
                    verts.append((bc @ P3, nrm, tuple(bc @ T3)))
                for k in range(1, len(verts) - 1):
                    v0, v1, v2 = verts[0], verts[k], verts[k + 1]
                    if np.linalg.norm(np.cross(v1[0] - v0[0], v2[0] - v0[0])) < 1e-13:
                        continue
                    out.append((v0[0], v1[0], v2[0], [v0[1], v1[1], v2[1]], [v0[2], v1[2], v2[2]]))
        tris = out
    return tris


def shrink(poly, d):
    """Konvexes Polygon um d nach innen versetzen (Kantenversatz, Ecken geschnitten)."""
    P = np.asarray(poly, dtype=float)
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    if area < 0:
        P = P[::-1]
    c = P.mean(axis=0)
    out = []
    n = len(P)
    for i in range(n):
        p = P[i]
        a, b = P[i - 1], P[(i + 1) % n]
        e1 = p - a
        e2 = b - p
        n1 = np.array([-e1[1], e1[0]])
        n2 = np.array([-e2[1], e2[0]])
        n1 /= max(np.linalg.norm(n1), 1e-12)
        n2 /= max(np.linalg.norm(n2), 1e-12)
        m = n1 + n2
        lm = np.linalg.norm(m)
        if lm < 1e-9:
            out.append(p + n1 * d)
            continue
        m /= lm
        cosh = max(float(m @ n1), 0.3)
        out.append(p + m * d / cosh)      # n zeigt bei CCW nach innen (links)
    return [tuple(q) for q in out]
