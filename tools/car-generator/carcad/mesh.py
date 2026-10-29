"""Geometrie-Bausteine.

Konventionen: Meter, +Y oben, +Z vorne, +X linke Fahrzeugseite (glTF).
Ein Part sammelt Dreiecke je Material. Jedes Dreieck trägt Positionen,
Normalen und UVs. UVs ohne Angabe werden aus der Lage berechnet
(Projektion auf die Hauptachse, Einheit Meter) – so funktionieren
gekachelte Texturen (Carbon, Leder, Flakes) auf allen Teilen.
"""
import math

import numpy as np

V = np.asarray


def vec(*a):
    return np.array(a, dtype=float)


def norm(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def rot_matrix(rx=0.0, ry=0.0, rz=0.0):
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def axis_angle(axis, ang):
    a = norm(axis)
    x, y, z = a
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def frame(normal, up_hint=(0, 1, 0)):
    """Orthonormale Basis (right, up, normal) mit normal als lokaler +Z."""
    n = norm(normal)
    u = np.asarray(up_hint, dtype=float)
    if abs(np.dot(norm(u), n)) > 0.98:
        u = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 0, 1.0])
    r = norm(np.cross(u, n))
    up = norm(np.cross(n, r))
    return r, up, n


def auto_uv(p, n):
    """Planare Projektion entlang der dominanten Normalenachse (Meter)."""
    ax = int(np.argmax(np.abs(n)))
    if ax == 0:
        return (p[2], p[1])
    if ax == 1:
        return (p[0], p[2])
    return (p[0], p[1])


class Part:
    """Dreiecke je Material: (a, b, c, normals[3], uvs[3])."""

    def __init__(self, name="part"):
        self.name = name
        self.tris = {}

    # ------------------------------------------------------------------
    # Grundoperationen
    # ------------------------------------------------------------------
    def tri(self, a, b, c, mat, hint=None, normals=None, uvs=None, outward=None):
        """Dreieck hinzufügen.

        hint:    Punkt im Inneren – die Vorderseite zeigt von ihm weg.
        outward: Richtung, in die die Vorderseite zeigen soll.
        """
        if mat is None:
            return
        a = np.asarray(a, dtype=float)
        b = np.asarray(b, dtype=float)
        c = np.asarray(c, dtype=float)
        n = np.cross(b - a, c - a)
        ln = np.linalg.norm(n)
        if ln < 1e-12:
            return
        n = n / ln
        flip = False
        if hint is not None:
            cen = (a + b + c) / 3.0
            if np.dot(n, cen - np.asarray(hint, dtype=float)) < 0:
                flip = True
        elif outward is not None:
            if np.dot(n, np.asarray(outward, dtype=float)) < 0:
                flip = True
        if flip:
            b, c = c, b
            n = -n
            if normals is not None:
                normals = [normals[0], normals[2], normals[1]]
            if uvs is not None:
                uvs = [uvs[0], uvs[2], uvs[1]]
        if normals is None:
            normals = [n, n, n]
        else:
            normals = [np.asarray(x, dtype=float) for x in normals]
        if uvs is None:
            uvs = [auto_uv(a, n), auto_uv(b, n), auto_uv(c, n)]
        self.tris.setdefault(mat, []).append((a, b, c, normals, uvs))

    def quad(self, a, b, c, d, mat, hint=None, normals=None, uvs=None, outward=None):
        na = nb = None
        ua = ub = None
        if normals is not None:
            na = [normals[0], normals[1], normals[2]]
            nb = [normals[0], normals[2], normals[3]]
        if uvs is not None:
            ua = [uvs[0], uvs[1], uvs[2]]
            ub = [uvs[0], uvs[2], uvs[3]]
        self.tri(a, b, c, mat, hint, na, ua, outward)
        self.tri(a, c, d, mat, hint, nb, ub, outward)

    def count(self):
        return sum(len(v) for v in self.tris.values())

    def merge(self, other, flip=False, matmap=None):
        for mat, tris in other.tris.items():
            m = matmap.get(mat, mat) if matmap else mat
            if m is None:
                continue
            dst = self.tris.setdefault(m, [])
            for (a, b, c, ns, uv) in tris:
                if flip:
                    dst.append((a, c, b, [-ns[0], -ns[2], -ns[1]], [uv[0], uv[2], uv[1]]))
                else:
                    dst.append((a, b, c, ns, uv))
        return self

    def transformed(self, M=None, t=(0, 0, 0), name=None):
        """Kopie mit Rotation/Skalierung M (3x3) und Verschiebung t."""
        M = np.eye(3) if M is None else np.asarray(M, dtype=float)
        t = np.asarray(t, dtype=float)
        Minv_T = np.linalg.inv(M).T
        det = np.linalg.det(M)
        out = Part(name or self.name)
        for mat, tris in self.tris.items():
            dst = out.tris.setdefault(mat, [])
            for (a, b, c, ns, uv) in tris:
                pa, pb, pc = M @ a + t, M @ b + t, M @ c + t
                nn = [norm(Minv_T @ n) for n in ns]
                if det < 0:
                    dst.append((pa, pc, pb, [nn[0], nn[2], nn[1]], [uv[0], uv[2], uv[1]]))
                else:
                    dst.append((pa, pb, pc, nn, uv))
        return out

    def mirrored_x(self, name=None):
        return self.transformed(np.diag([-1.0, 1.0, 1.0]), name=name)

    def bounds(self):
        pts = [p for tris in self.tris.values() for t in tris for p in t[:3]]
        if not pts:
            return np.zeros(3), np.zeros(3)
        P = np.array(pts)
        return P.min(0), P.max(0)

    def recolor(self, mapping):
        for old, new in mapping.items():
            if old in self.tris:
                self.tris.setdefault(new, []).extend(self.tris.pop(old))
        return self

    # ------------------------------------------------------------------
    # Primitive
    # ------------------------------------------------------------------
    def hexa(self, p, mat, uv_scale=1.0):
        """8 Eckpunkte: p0..p3 unten, p4..p7 oben (p4 über p0 usw.)."""
        p = [np.asarray(x, dtype=float) for x in p]
        hint = sum(p) / 8.0
        for f in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.quad(p[f[0]], p[f[1]], p[f[2]], p[f[3]], mat, hint)

    def box(self, center, size, mat, rot=(0, 0, 0), M=None):
        sx, sy, sz = (s / 2.0 for s in size)
        loc = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz), (-sx, -sy, sz),
               (-sx, sy, -sz), (sx, sy, -sz), (sx, sy, sz), (-sx, sy, sz)]
        R = rot_matrix(*rot) if M is None else np.asarray(M, dtype=float)
        c = np.asarray(center, dtype=float)
        self.hexa([c + R @ np.array(v) for v in loc], mat)

    def rbox(self, center, size, radius, mat, M=None, segs=3, smooth=True):
        """Abgerundeter Quader (Kanten entlang lokaler Z gerundet, Enden flach gefast)."""
        sx, sy, sz = size
        r = min(radius, sx / 2 * 0.98, sy / 2 * 0.98)
        prof = round_rect(sx, sy, r, segs)
        M = np.eye(3) if M is None else np.asarray(M, dtype=float)
        c = np.asarray(center, dtype=float)
        ch = min(r * 0.6, sz * 0.25)
        secs = []
        for z, inset in ((-sz / 2, ch), (-sz / 2 + ch, 0.0), (sz / 2 - ch, 0.0), (sz / 2, ch)):
            pr = round_rect(max(sx - 2 * inset, 1e-4), max(sy - 2 * inset, 1e-4), max(r - inset, 0.0), segs)
            secs.append([c + M @ np.array([x, y, z]) for (x, y) in pr])
        self.loft(secs, lambda k, j: mat, caps=(mat, mat), smooth=smooth)

    def lathe(self, profile, segs, mat, center=(0, 0, 0), axis="x", inside=None,
              a0=0.0, a1=2 * math.pi, smooth=True, uv_mode="cyl", M=None, polar_r=None):
        """Rotationskörper. profile = [(s, r), ...] (s entlang der Achse).

        uv_mode: 'cyl' -> u = Bogenlänge um die Achse, v = Profillänge (Meter)
                 'disc' -> planare Projektion senkrecht zur Achse (Meter)
                 'unit' -> u = Winkel 0..1, v = Profilparameter 0..1
        """
        c = np.asarray(center, dtype=float)
        if inside is None:
            ss = [p[0] for p in profile]
            rr = [p[1] for p in profile]
            inside = (sum(ss) / len(ss), sum(rr) / len(rr))
        Mx = np.eye(3) if M is None else np.asarray(M, dtype=float)

        def basis(s, r, th):
            if axis == "x":
                return np.array([s, r * math.cos(th), r * math.sin(th)])
            if axis == "y":
                return np.array([r * math.cos(th), s, r * math.sin(th)])
            return np.array([r * math.cos(th), r * math.sin(th), s])

        def pt(s, r, th):
            return c + Mx @ basis(s, r, th)

        def nrm(ns, nr, th):
            return Mx @ basis(ns, nr, th)

        # Profil-Bogenlänge
        plen = [0.0]
        for i in range(1, len(profile)):
            plen.append(plen[-1] + math.hypot(profile[i][0] - profile[i - 1][0], profile[i][1] - profile[i - 1][1]))
        tot = max(plen[-1], 1e-9)
        angles = [a0 + (a1 - a0) * j / segs for j in range(segs + 1)]
        # glatte Profil-Normalen je Stützpunkt (gemittelt) für weiche Übergänge
        seg_n = []
        for i in range(len(profile) - 1):
            (s0, r0), (s1, r1) = profile[i], profile[i + 1]
            n2 = np.array([-(r1 - r0), s1 - s0])
            ln = np.linalg.norm(n2)
            if ln < 1e-12:
                seg_n.append(None)
                continue
            n2 /= ln
            mid = np.array([(s0 + s1) / 2, (r0 + r1) / 2])
            if np.dot(n2, mid - np.asarray(inside)) < 0:
                n2 = -n2
            seg_n.append(n2)

        def uvf(i, j, th):
            s, r = profile[i]
            if uv_mode == "polar":
                rm = polar_r or max(abs(q[1]) for q in profile)
                p = basis(0.0, r, th)
                if axis == "x":      # Blick von +X: rechts = -Z, oben = +Y
                    return (0.5 - p[2] / (2 * rm), 0.5 - p[1] / (2 * rm))
                if axis == "y":      # Blick von oben
                    return (0.5 + p[0] / (2 * rm), 0.5 + p[2] / (2 * rm))
                return (0.5 + p[0] / (2 * rm), 0.5 - p[1] / (2 * rm))
            if uv_mode == "unit":
                return ((th - a0) / (a1 - a0 + 1e-12), plen[i] / tot)
            if uv_mode == "disc":
                p = basis(s, r, th)
                if axis == "x":
                    return (p[2], p[1])
                if axis == "y":
                    return (p[0], p[2])
                return (p[0], p[1])
            rad = max(abs(r), 1e-3)
            return (th * max(rad, 0.02), plen[i])

        for i in range(len(profile) - 1):
            n2 = seg_n[i]
            if n2 is None:
                continue
            (s0, r0), (s1, r1) = profile[i], profile[i + 1]
            for j in range(segs):
                t0, t1 = angles[j], angles[j + 1]
                tm = (t0 + t1) / 2
                hint = pt(inside[0], inside[1], tm)
                A, B = pt(s0, r0, t0), pt(s1, r1, t0)
                Cc, D = pt(s1, r1, t1), pt(s0, r0, t1)
                uvs = [uvf(i, j, t0), uvf(i + 1, j, t0), uvf(i + 1, j + 1, t1), uvf(i, j + 1, t1)]
                if smooth:
                    nA, nC = nrm(n2[0], n2[1], t0), nrm(n2[0], n2[1], t1)
                    self.tri(A, B, Cc, mat, hint, [nA, nA, nC], [uvs[0], uvs[1], uvs[2]])
                    self.tri(A, Cc, D, mat, hint, [nA, nC, nC], [uvs[0], uvs[2], uvs[3]])
                else:
                    self.quad(A, B, Cc, D, mat, hint, uvs=uvs)

    def loft(self, sections, matfn, caps=(None, None), smooth=False, closed=True, uvs=None,
             hint_fn=None):
        """Verbindet gleich große Querschnitte (Listen von 3D-Punkten).

        matfn(k, j) -> Material oder None (Fläche auslassen).
        smooth: Gitter-Normalen (weich) statt Flächennormalen.
        uvs:    optional gleiche Struktur wie sections mit (u, v) je Punkt.
        """
        secs = [np.asarray([np.asarray(p, dtype=float) for p in s]) for s in sections]
        K, m = len(secs), len(secs[0])
        cents = [s.mean(axis=0) for s in secs]
        N = None
        if smooth:
            N = grid_normals(secs, closed, cents)
        jmax = m if closed else m - 1
        for k in range(K - 1):
            hint = (cents[k] + cents[k + 1]) / 2 if hint_fn is None else hint_fn(k)
            for j in range(jmax):
                j2 = (j + 1) % m
                mat = matfn(k, j)
                if mat is None:
                    continue
                P = [secs[k][j], secs[k][j2], secs[k + 1][j2], secs[k + 1][j]]
                nn = [N[k][j], N[k][j2], N[k + 1][j2], N[k + 1][j]] if N is not None else None
                uu = [uvs[k][j], uvs[k][j2], uvs[k + 1][j2], uvs[k + 1][j]] if uvs is not None else None
                self.quad(P[0], P[1], P[2], P[3], mat, hint, nn, uu)
        for idx, nb, cm in ((0, 1, caps[0]), (K - 1, K - 2, caps[1])):
            if cm is None:
                continue
            c = cents[idx]
            inward = c + (cents[nb] - c) * 0.5
            s = secs[idx]
            for j in range(m if closed else m - 1):
                self.tri(c, s[j], s[(j + 1) % m], cm, inward)

    def sweep(self, path, profile, mat, up=(0, 1, 0), closed_profile=True, caps=True, smooth=True,
              scale_fn=None):
        """Profil (2D-Punkte) entlang eines Pfads (3D-Polylinie) ziehen."""
        path = [np.asarray(p, dtype=float) for p in path]
        n = len(path)
        secs = []
        up = np.asarray(up, dtype=float)
        prev_r = None
        for i, p in enumerate(path):
            if i == 0:
                t = path[1] - path[0]
            elif i == n - 1:
                t = path[-1] - path[-2]
            else:
                t = norm(path[i + 1] - path[i]) + norm(path[i] - path[i - 1])
            t = norm(t)
            u = up
            if prev_r is not None:
                u = np.cross(t, prev_r)
            if np.linalg.norm(np.cross(u, t)) < 1e-6:
                u = np.array([1.0, 0, 0]) if abs(t[0]) < 0.9 else np.array([0, 0, 1.0])
            r = norm(np.cross(u, t))
            uu = norm(np.cross(t, r))
            prev_r = r
            sc = scale_fn(i / max(n - 1, 1)) if scale_fn else 1.0
            secs.append([p + (r * x + uu * y) * sc for (x, y) in profile])
        self.loft(secs, lambda k, j: mat, caps=(mat, mat) if caps else (None, None), smooth=smooth,
                  closed=closed_profile)

    def tube(self, path, radius, mat, segs=10, caps=True, up=(0, 1, 0)):
        prof = [(radius * math.cos(2 * math.pi * k / segs), radius * math.sin(2 * math.pi * k / segs))
                for k in range(segs)]
        self.sweep(path, prof, mat, up=up, caps=caps, smooth=True)

    def sphere(self, center, r, mat, segs=16, rings=10, scale=(1, 1, 1), M=None):
        prof = [(r * math.cos(a), r * math.sin(a)) for a in np.linspace(math.pi, 0, rings + 1)]
        tmp = Part("tmp")
        tmp.lathe(prof, segs, mat, center=(0, 0, 0), axis="y", inside=(0, 1e-4))
        S = np.diag(scale)
        Mm = (np.eye(3) if M is None else np.asarray(M, dtype=float)) @ S
        self.merge(tmp.transformed(Mm, center))

    def tex_quad(self, center, right, up, w, h, mat, uv_rect=(0, 0, 1, 1)):
        """Texturierte Fläche; Vorderseite zeigt in Richtung right x up.

        glTF-UVs: (0,0) = links oben im Bild.
        """
        c = np.asarray(center, dtype=float)
        r = np.asarray(right, dtype=float) * w / 2
        u = np.asarray(up, dtype=float) * h / 2
        n = norm(np.cross(right, up))
        u0, v0, u1, v1 = uv_rect
        bl, br, tr, tl = c - r - u, c + r - u, c + r + u, c - r + u
        hint = c - n
        self.tri(bl, br, tr, mat, hint, [n, n, n], [(u0, v1), (u1, v1), (u1, v0)])
        self.tri(bl, tr, tl, mat, hint, [n, n, n], [(u0, v1), (u1, v0), (u0, v0)])

    def tex_poly(self, pts3, uv2, mat, normal):
        """Konvexes texturiertes Polygon (Fächer)."""
        n = norm(normal)
        c = sum(np.asarray(p, dtype=float) for p in pts3) / len(pts3)
        cu = (sum(u for u, v in uv2) / len(uv2), sum(v for u, v in uv2) / len(uv2))
        for i in range(len(pts3)):
            j = (i + 1) % len(pts3)
            self.tri(c, pts3[i], pts3[j], mat, c - n, [n, n, n], [cu, uv2[i], uv2[j]])


# ----------------------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------------------

def round_rect(w, h, r, segs=3):
    """Abgerundetes Rechteck (geschlossen, gegen den Uhrzeigersinn)."""
    w2, h2 = w / 2, h / 2
    r = max(0.0, min(r, w2, h2))
    pts = []
    for cx, cy, a0 in ((w2 - r, h2 - r, 0), (-w2 + r, h2 - r, 90), (-w2 + r, -h2 + r, 180), (w2 - r, -h2 + r, 270)):
        for k in range(segs + 1):
            a = math.radians(a0 + 90 * k / segs)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def round_poly(pts, radii, n=3):
    """Rundet die Ecken eines geschlossenen 2D-Polygons (quadratische Bezier-Bögen)."""
    out = []
    m = len(pts)
    for i in range(m):
        P = np.array(pts[i], dtype=float)
        A0 = np.array(pts[i - 1], dtype=float)
        B0 = np.array(pts[(i + 1) % m], dtype=float)
        r = radii[i] if hasattr(radii, "__len__") else radii
        la, lb = np.linalg.norm(A0 - P), np.linalg.norm(B0 - P)
        fa = min(r / la, 0.45) if la > 1e-9 else 0.0
        fb = min(r / lb, 0.45) if lb > 1e-9 else 0.0
        A, B = P + (A0 - P) * fa, P + (B0 - P) * fb
        if r <= 0:
            out.append((float(P[0]), float(P[1])))
            continue
        for k in range(n + 1):
            t = k / n
            q = (1 - t) ** 2 * A + 2 * (1 - t) * t * P + t ** 2 * B
            out.append((float(q[0]), float(q[1])))
    return out


def resample(poly, count, closed=False):
    """Polylinie auf count Punkte mit gleichmäßigem Bogenabstand umrechnen."""
    P = np.asarray(poly, dtype=float)
    if closed:
        P = np.vstack([P, P[:1]])
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    tot = cum[-1]
    if tot < 1e-12:
        return [tuple(P[0])] * count
    n = count if not closed else count + 1
    ts = np.linspace(0, tot, n)
    out = []
    for t in ts:
        i = min(np.searchsorted(cum, t, side="right") - 1, len(seg) - 1)
        f = (t - cum[i]) / max(seg[i], 1e-12)
        out.append(tuple(P[i] + (P[i + 1] - P[i]) * f))
    return out[:-1] if closed else out


def grid_normals(secs, closed, cents=None):
    """Glatte Normalen für ein Loft-Gitter (zentrale Differenzen), nach außen orientiert."""
    K, m = len(secs), len(secs[0])
    S = np.asarray(secs)  # K x m x 3
    if closed:
        du = np.roll(S, -1, axis=1) - np.roll(S, 1, axis=1)
    else:
        du = np.zeros_like(S)
        du[:, 1:-1] = S[:, 2:] - S[:, :-2]
        du[:, 0] = S[:, 1] - S[:, 0]
        du[:, -1] = S[:, -1] - S[:, -2]
    dv = np.zeros_like(S)
    if K > 1:
        dv[1:-1] = S[2:] - S[:-2]
        dv[0] = S[1] - S[0]
        dv[-1] = S[-1] - S[-2]
    N = np.cross(du, dv)
    ln = np.linalg.norm(N, axis=2, keepdims=True)
    N = N / np.maximum(ln, 1e-12)
    if cents is None:
        cents = S.mean(axis=1)
    cents = np.asarray(cents)
    out_dir = S - cents[:, None, :]
    s = np.sign(np.sum(N * out_dir, axis=2))
    s[s == 0] = 1
    # Mehrheitsentscheid je Querschnitt (stabiler als punktweise)
    for k in range(K):
        if np.sum(s[k] < 0) > m / 2:
            N[k] = -N[k]
    return N


def smooth_part(part, crease_deg=38.0, mats=None):
    """Weiche Normalen über Kanten flacher als crease_deg (harte Kanten bleiben)."""
    cos_c = math.cos(math.radians(crease_deg))
    for mat, tris in list(part.tris.items()):
        if mats is not None and mat not in mats:
            continue
        fns, buckets = [], {}
        for ti, (a, b, c, _n, _uv) in enumerate(tris):
            cr = np.cross(b - a, c - a)
            ln = np.linalg.norm(cr)
            fns.append((cr / ln if ln > 0 else cr, cr))
            for p in (a, b, c):
                buckets.setdefault((round(p[0], 4), round(p[1], 4), round(p[2], 4)), []).append(ti)
        new = []
        for ti, (a, b, c, ns, uvs) in enumerate(tris):
            un = fns[ti][0]
            corner = []
            for p in (a, b, c):
                acc = np.zeros(3)
                for tj in buckets[(round(p[0], 4), round(p[1], 4), round(p[2], 4))]:
                    if np.dot(un, fns[tj][0]) >= cos_c:
                        acc += fns[tj][1]
                l = np.linalg.norm(acc)
                corner.append(acc / l if l > 0 else un)
            new.append((a, b, c, corner, uvs))
        part.tris[mat] = new
    return part


def polyline_len(pts):
    return sum(np.linalg.norm(np.asarray(pts[i + 1]) - np.asarray(pts[i])) for i in range(len(pts) - 1))


def arc(center, radius, a0, a1, segs, plane="zy"):
    """Kreisbogen-Punkte in einer Ebene (für Pfade)."""
    c = np.asarray(center, dtype=float)
    out = []
    for k in range(segs + 1):
        a = a0 + (a1 - a0) * k / segs
        if plane == "zy":
            out.append(c + np.array([0.0, radius * math.sin(a), radius * math.cos(a)]))
        elif plane == "xy":
            out.append(c + np.array([radius * math.cos(a), radius * math.sin(a), 0.0]))
        else:
            out.append(c + np.array([radius * math.cos(a), 0.0, radius * math.sin(a)]))
    return out


def round_open(pts, radii, n=3):
    """Rundet die inneren Ecken einer offenen Polylinie (Endpunkte bleiben)."""
    out = [tuple(pts[0])]
    m = len(pts)
    for i in range(1, m - 1):
        P = np.array(pts[i], dtype=float)
        A0 = np.array(pts[i - 1], dtype=float)
        B0 = np.array(pts[i + 1], dtype=float)
        r = radii[i]
        if r <= 0:
            out.append(tuple(P))
            continue
        la, lb = np.linalg.norm(A0 - P), np.linalg.norm(B0 - P)
        fa = min(r / la, 0.45) if la > 1e-9 else 0.0
        fb = min(r / lb, 0.45) if lb > 1e-9 else 0.0
        A, B = P + (A0 - P) * fa, P + (B0 - P) * fb
        for k in range(n + 1):
            t = k / n
            q = (1 - t) ** 2 * A + 2 * (1 - t) * t * P + t ** 2 * B
            out.append((float(q[0]), float(q[1])))
    out.append(tuple(pts[-1]))
    return out
