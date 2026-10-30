"""Außenteile: Lampen, Grills, Einlässe, Spiegel, Griffe, Wischer, Auspuff,
Kennzeichenhalter, Logos, Unterboden.

Alle Teile werden in einem lokalen Rahmen (u = rechts, v = oben,
w = aus der Oberfläche heraus) gebaut und dann mit `conform` auf die
gekrümmte Karosserie gelegt: jeder Punkt (u, v, w) landet auf der
Oberfläche S(u, v) plus w entlang der Oberflächennormale. So sitzen
Scheinwerfer, Grills und Logos bündig, auch an gerundeten Ecken.
"""
import math

import numpy as np

from .mesh import Part, norm, frame, round_rect, resample, rot_matrix, smooth_part


class Ctx:
    """Baukontext eines Autos (eine LOD-Stufe)."""

    def __init__(self, spec, lod, body, raycaster):
        self.spec = spec
        self.lod = lod
        self.b = body
        self.rc = raycaster
        self.parts = {}
        self.helpers = {}
        self.meta = {}
        self.cuts = []          # Öffnungen in der Haut (cut.Cut), werden nach den Details angewendet

    def add_cut(self, origin, r, up, n, poly, margin=0.004, wmax=0.10):
        from .cut import Cut, shrink
        pl = shrink(poly, margin) if margin else poly
        self.cuts.append(Cut(origin, r, up, n, pl, wmax=wmax))

    def part(self, name):
        if name not in self.parts:
            self.parts[name] = Part(name)
        return self.parts[name]

    # Treffer auf der Karosserie
    def hit_front(self, x, y):
        return self.rc.cast((x, y, self.b.zf + 1.0), (0, 0, -1))

    def hit_rear(self, x, y):
        return self.rc.cast((x, y, self.b.zr - 1.0), (0, 0, 1))

    def hit_side(self, z, y, side=1):
        return self.rc.cast((side * 2.5, y, z), (-side, 0, 0))

    def hit_top(self, x, z):
        return self.rc.cast((x, 3.5, z), (0, -1, 0))


# ----------------------------------------------------------------------
# Auf Oberfläche legen
# ----------------------------------------------------------------------

class Conformer:
    """Bildet lokale Koordinaten (u, v, w) auf die Karosserie ab."""

    def __init__(self, rc, origin, r, up, n, extent, grid=(14, 10), fallback_plane=True, max_depth=0.6):
        self.o = np.asarray(origin, dtype=float)
        self.r, self.up, self.n = norm(r), norm(up), norm(n)
        hw, hh = extent[0] / 2 + 0.03, extent[1] / 2 + 0.03
        # Raster fein genug, damit die Interpolation der Krümmung folgt (~1,8 cm)
        gu = min(90, max(grid[0], int(math.ceil(2 * hw / 0.018)) + 1))
        gv = min(60, max(grid[1], int(math.ceil(2 * hh / 0.018)) + 1))
        self.us = np.linspace(-hw, hw, gu)
        self.vs = np.linspace(-hh, hh, gv)
        self.S = np.zeros((gv, gu, 3))
        self.N = np.zeros((gv, gu, 3))
        for iv, v in enumerate(self.vs):
            for iu, u in enumerate(self.us):
                p0 = self.o + self.r * u + self.up * v
                hit = rc.cast(p0 + self.n * 0.4, -self.n, max_t=0.4 + max_depth)
                if hit is None:
                    self.S[iv, iu] = p0
                    self.N[iv, iu] = self.n
                else:
                    self.S[iv, iu] = hit[0]
                    self.N[iv, iu] = hit[1]

    def map(self, u, v, w):
        us, vs = self.us, self.vs
        fu = np.clip((u - us[0]) / (us[-1] - us[0]) * (len(us) - 1), 0, len(us) - 1.0001)
        fv = np.clip((v - vs[0]) / (vs[-1] - vs[0]) * (len(vs) - 1), 0, len(vs) - 1.0001)
        iu, iv = int(fu), int(fv)
        tu, tv = fu - iu, fv - iv
        S = (self.S[iv, iu] * (1 - tu) * (1 - tv) + self.S[iv, iu + 1] * tu * (1 - tv) +
             self.S[iv + 1, iu] * (1 - tu) * tv + self.S[iv + 1, iu + 1] * tu * tv)
        N = (self.N[iv, iu] * (1 - tu) * (1 - tv) + self.N[iv, iu + 1] * tu * (1 - tv) +
             self.N[iv + 1, iu] * (1 - tu) * tv + self.N[iv + 1, iu + 1] * tu * tv)
        N = norm(N)
        # außerhalb des Rasters linear weiterführen
        du = u - np.clip(u, us[0], us[-1])
        dv = v - np.clip(v, vs[0], vs[-1])
        return S + self.r * du + self.up * dv + N * w, N

    def apply(self, local_part, out_part, flat=False):
        """local_part: Koordinaten (u, v, w) in x, y, z."""
        for mat, tris in local_part.tris.items():
            dst = out_part.tris.setdefault(mat, [])
            for (a, b, c, ns, uv) in tris:
                pts, nn = [], []
                for p, nl in zip((a, b, c), ns):
                    P, Ns = self.map(p[0], p[1], p[2])
                    pts.append(P)
                    # lokale Normale in den Oberflächenrahmen drehen
                    rr = norm(np.cross(self.up, Ns))
                    uu = norm(np.cross(Ns, rr))
                    nn.append(norm(rr * nl[0] + uu * nl[1] + Ns * nl[2]))
                if flat:
                    fn = norm(np.cross(pts[1] - pts[0], pts[2] - pts[0]))
                    nn = [fn, fn, fn]
                dst.append((pts[0], pts[1], pts[2], nn, uv))
        return out_part


def conform_part(ctx, local, origin, normal, extent, up_hint=(0, 1, 0), dst=None, mirror=True, grid=(14, 10),
                 cut=None, cut_margin=0.004):
    """Baut ein lokal definiertes Teil an origin (rechte Seite +X) und optional gespiegelt.

    cut: konvexer Umriss (u, v) – an dieser Stelle wird die Haut exakt geöffnet."""
    origin = np.asarray(origin, dtype=float)
    normal = np.asarray(normal, dtype=float)
    r, up, n = frame(normal, up_hint)
    cf = Conformer(ctx.rc, origin, r, up, n, extent, grid)
    out = dst if dst is not None else Part(local.name)
    cf.apply(local, out)
    if cut is not None:
        ctx.add_cut(origin, r, up, n, cut, margin=cut_margin)
    if mirror:
        o2 = np.array([-origin[0], origin[1], origin[2]])
        n2 = np.array([-normal[0], normal[1], normal[2]])
        r2, up2, nn2 = frame(n2, up_hint)
        cf2 = Conformer(ctx.rc, o2, r2, up2, nn2, extent, grid)
        mirrored = local.mirrored_x()
        cf2.apply(mirrored, out)
        if cut is not None:
            ctx.add_cut(o2, r2, up2, nn2, [(-u, v) for (u, v) in cut], margin=cut_margin)
    return out


# ----------------------------------------------------------------------
# Lokale Grundformen (u, v, w)
# ----------------------------------------------------------------------

def rr_outline(w, h, r, segs=4, shape=None):
    """Umriss in (u, v): abgerundetes Rechteck oder eigenes Polygon."""
    if shape is not None:
        return shape
    return round_rect(w, h, r, segs)


def densify(poly, max_len=0.015, closed=True):
    """Polygon/Polylinie so unterteilen, dass keine Kante länger als max_len ist
    (wichtig, damit angepasste Teile der gekrümmten Oberfläche folgen)."""
    P = [np.asarray(p, dtype=float) for p in poly]
    n = len(P)
    out = []
    for i in (range(n) if closed else range(n - 1)):
        a, b = P[i], P[(i + 1) % n]
        L = float(np.linalg.norm(b - a))
        k = max(1, int(math.ceil(L / max_len)))
        for t in range(k):
            out.append(tuple(a + (b - a) * t / k))
    if not closed:
        out.append(tuple(P[-1]))
    return out


def _vrange(P, u):
    vs = []
    n = len(P)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        if (a[0] - u) * (b[0] - u) <= 0 and abs(b[0] - a[0]) > 1e-12:
            t = (u - a[0]) / (b[0] - a[0])
            vs.append(a[1] + (b[1] - a[1]) * t)
    if not vs:
        return None
    return min(vs), max(vs)


def fill_grid(outline, max_du=0.02, max_dv=0.02):
    """Konvexen Umriss (u, v) als Gitter aus Spalten (u) und Reihen (v) füllen.

    Rückgabe: Gitter grid[i][j] = (u, v) sowie relative Koordinaten (su, sv) je Punkt."""
    P = np.asarray(outline, dtype=float)
    umin, umax = float(P[:, 0].min()), float(P[:, 0].max())
    nu = max(2, int(math.ceil((umax - umin) / max_du)))
    us = umin + (umax - umin) * (0.5 - 0.5 * np.cos(np.linspace(0, math.pi, nu + 1)))
    cols = []
    for u in us:
        uu = min(max(u, umin + 1e-7), umax - 1e-7)
        r = _vrange(P, uu)
        if r is None:
            r = (0.0, 0.0)
        cols.append((float(u), r))
    hmax = max(r[1] - r[0] for (_u, r) in cols)
    nv = max(1, int(math.ceil(hmax / max_dv)))
    grid, rel = [], []
    for i, (u, r) in enumerate(cols):
        grid.append([(u, r[0] + (r[1] - r[0]) * j / nv) for j in range(nv + 1)])
        rel.append([((u - umin) / max(umax - umin, 1e-9), j / nv) for j in range(nv + 1)])
    return grid, rel


def fill_shape(part, outline, wfn, mat, outward=(0, 0, 1), max_du=0.02, max_dv=0.02, smooth=False):
    """Fläche über einem konvexen Umriss; wfn(u, v, su, sv) -> w (Höhe über der Oberfläche)."""
    grid, rel = fill_grid(outline, max_du, max_dv)
    tmp = Part("fill")
    for i in range(len(grid) - 1):
        for j in range(len(grid[0]) - 1):
            q = []
            for (ii, jj) in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                (u, v), (su, sv) = grid[ii][jj], rel[ii][jj]
                q.append(np.array([u, v, wfn(u, v, su, sv)]))
            tmp.quad(q[0], q[1], q[2], q[3], mat, outward=outward)
    if smooth:
        smooth_part(tmp, 70.0)
    part.merge(tmp)


def tray(part, outline, depth, mat_wall, mat_back, lip=0.0):
    """Offene Wanne (Lampengehäuse/Einlass): Rand bei w=lip, Boden bei w=-depth; innen sichtbar."""
    outer = densify(outline, 0.015)
    cen = np.mean(np.array(outer), axis=0)
    secs = []
    for wv, s in ((lip, 1.0), (-depth * 0.6, 0.97), (-depth, 0.9)):
        secs.append([np.array([cen[0] + (u - cen[0]) * s, cen[1] + (v - cen[1]) * s, wv]) for (u, v) in outer])
    tmp = Part("tray")
    tmp.loft(secs, lambda k, j: mat_wall, caps=(None, None), smooth=True)
    part.merge(tmp, flip=True)
    back = [(cen[0] + (u - cen[0]) * 0.9, cen[1] + (v - cen[1]) * 0.9) for (u, v) in outline]
    fill_shape(part, back, lambda u, v, su, sv: -depth, mat_back, outward=(0, 0, 1), max_du=0.03, max_dv=0.03)


def pillow(part, outline, dome, mat, w0=0.0, grid=10):
    """Gewölbte Abdeckung (Linse) über einem Umriss, fein unterteilt."""
    def wfn(u, v, su, sv):
        b = (math.sin(math.pi * min(max(su, 0), 1)) * math.sin(math.pi * min(max(sv, 0), 1))) ** 0.35
        return w0 + dome * b
    fill_shape(part, outline, wfn, mat, outward=(0, 0, 1), max_du=0.015, max_dv=0.012, smooth=True)


def flat_shape(part, outline, wv, mat, outward=(0, 0, 1)):
    fill_shape(part, outline, lambda u, v, su, sv: wv, mat, outward=outward, max_du=0.025, max_dv=0.025)


def strip2d(part, path, width, wv, mat, thick=0.003, round_cap=False):
    """Leuchtstreifen/Leiste entlang eines 2D-Pfads (u, v) als flacher Quader (fein unterteilt)."""
    path = [np.array(p, dtype=float) for p in densify(path, 0.02, closed=False)]
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        if np.linalg.norm(b - a) < 1e-9:
            continue
        d = norm(np.append(b - a, 0))[:2]
        nrm = np.array([-d[1], d[0]]) * width / 2
        ext = d * (width * 0.25 if i > 0 else 0.0)
        a2 = a - ext
        q = [np.append(a2 - nrm, wv), np.append(a2 + nrm, wv), np.append(b + nrm, wv), np.append(b - nrm, wv)]
        q2 = [x + np.array([0, 0, -thick]) for x in q]
        part.hexa(q2 + q, mat)


def seg_box(part, center, size, mat, rot=(0, 0, 0), n=None, max_len=0.03):
    """Langer Quader in n Stücke entlang der lokalen x-Achse geteilt (folgt angepasst der Krümmung)."""
    sx = size[0]
    n = n or max(1, int(math.ceil(sx / max_len)))
    R = rot_matrix(*rot)
    c = np.asarray(center, dtype=float)
    for k in range(n):
        x0 = -sx / 2 + sx * k / n
        cc = c + R @ np.array([x0 + sx / (2 * n), 0.0, 0.0])
        part.box(cc, (sx / n * 1.001, size[1], size[2]), mat, M=R)


def projector(part, u, v, r, wv, lens="LampGlass", core="Headlight", ring="Reflector"):
    """Projektor-Linse: Chromring, leuchtender Kern, gewölbte Glaslinse."""
    part.lathe([(wv - 0.03, r * 1.35), (wv - 0.004, r * 1.35), (wv - 0.002, r * 1.05)], 20, ring,
               center=(u, v, 0), axis="z", inside=(wv - 0.04, 0.0))
    part.lathe([(wv - 0.025, 0.0), (wv - 0.025, r * 0.9)], 16, core, center=(u, v, 0), axis="z",
               inside=(wv - 0.04, 0.0))
    prof = [(wv - 0.012 + r * 0.5 * math.sin(a), r * math.cos(a)) for a in np.linspace(0, math.pi / 2, 7)]
    part.lathe(prof, 20, lens, center=(u, v, 0), axis="z", inside=(wv - 0.05, 0.0))


def reflector_bowl(part, u, v, r, wv, depth, bulb="Headlight", mat="Reflector", segs=24):
    prof = []
    for k in range(9):
        t = k / 8
        prof.append((wv - depth * (1 - t) ** 1.6, r * t))
    part.lathe(prof, segs, mat, center=(u, v, 0), axis="z", inside=(wv + 0.05, 0.0))
    part.sphere((u, v, wv - depth * 0.55), r * 0.16, bulb, segs=10, rings=6)


# ----------------------------------------------------------------------
# Lampen
# ----------------------------------------------------------------------

def lamp_local(spec, lod=0):
    """Lokale Lampe aus einer Beschreibung.

    spec = {"w": .., "h": .., "r": .., "shape": [(u,v),...] optional, "depth": .., "dome": ..,
            "lens": "LampGlass"|"TailGlass"|"SmokeGlass",
            "elements": [ ("projector", u, v, r), ("bowl", u, v, r, depth), ("strip", [(u,v)...], width, mat),
                          ("panel", outline, mat), ("dots", [(u,v)..], r, mat) ]}
    """
    p = Part("lamp")
    outline = rr_outline(spec["w"], spec["h"], spec.get("r", 0.02), 5 if lod == 0 else 2, spec.get("shape"))
    depth = spec.get("depth", 0.06)
    if lod >= 1:
        flat_shape(p, outline, 0.002, spec.get("lod_mat", "LampHousing"))
        for el in spec["elements"]:
            if el[0] == "strip":
                strip2d(p, el[1], el[2], 0.004, el[3], thick=0.002)
            elif el[0] == "panel":
                flat_shape(p, el[1], 0.003, el[2])
        return p
    tray(p, outline, depth, "LampHousing", spec.get("back", "LampHousing"))
    wv = -0.004
    for el in spec["elements"]:
        kind = el[0]
        if kind == "projector":
            projector(p, el[1], el[2], el[3], wv)
        elif kind == "bowl":
            reflector_bowl(p, el[1], el[2], el[3], wv, el[4])
        elif kind == "strip":
            strip2d(p, el[1], el[2], wv - 0.002, el[3], thick=0.006)
        elif kind == "panel":
            flat_shape(p, el[1], wv - 0.012, el[2])
        elif kind == "dots":
            for (u, v) in el[1]:
                p.lathe([(wv - 0.004, 0.0), (wv - 0.004, el[2])], 10, el[3], center=(u, v, 0), axis="z",
                        inside=(wv - 0.01, 0.0))
        elif kind == "chrome":
            flat_shape(p, el[1], wv - 0.02, "Reflector")
    pillow(p, outline, spec.get("dome", 0.006), spec.get("lens", "LampGlass"), w0=0.001)
    if spec.get("bezel"):
        # Zierring (z. B. Chrom) um die Lampe, deckt den Glasrand ab
        bw, bmat = spec["bezel"]
        P = np.array(densify(outline, 0.012))
        cen = P.mean(axis=0)
        hx = (P[:, 0].max() - P[:, 0].min()) / 2
        hy = (P[:, 1].max() - P[:, 1].min()) / 2
        k = np.array([1 - bw / max(hx, 1e-6), 1 - bw / max(hy, 1e-6)])
        inner = cen + (P - cen) * k
        n = len(P)
        for i in range(n):
            j = (i + 1) % n
            a0, a1 = np.array([*P[i], 0.005]), np.array([*P[j], 0.005])
            b0, b1 = np.array([*inner[i], 0.004]), np.array([*inner[j], 0.004])
            p.quad(a0, a1, b1, b0, bmat, outward=(0, 0, 1))
            p.quad(np.array([*P[i], -0.002]), np.array([*P[j], -0.002]), a1, a0, bmat,
                   hint=np.array([cen[0], cen[1], 0.0]))
    return p


def place_lamp(ctx, spec, x, y, front=True, dst=None, mirror=True, normal_blend=0.55):
    """Lampe an Karosserie-Punkt (x, y) vorne/hinten platzieren."""
    hit = ctx.hit_front(x, y) if front else ctx.hit_rear(x, y)
    if hit is None:
        raise ValueError("Lampe trifft Karosserie nicht: x=%.2f y=%.2f" % (x, y))
    P, Nn, _ = hit
    axis = np.array([0, 0, 1.0 if front else -1.0])
    n = norm(Nn * normal_blend + axis * (1 - normal_blend))
    local = lamp_local(spec, ctx.lod)
    outline = rr_outline(spec["w"], spec["h"], spec.get("r", 0.02), 5 if ctx.lod == 0 else 2, spec.get("shape"))
    ctx.meta.setdefault("lights", {}).setdefault(spec.get("kind", "head" if front else "tail"), []).append(
        [round(float(v), 3) for v in P])
    return conform_part(ctx, local, P, n, (spec["w"], spec["h"]), dst=dst, mirror=mirror,
                        cut=outline if ctx.lod == 0 else None)


# ----------------------------------------------------------------------
# Grills und Einlässe
# ----------------------------------------------------------------------

def grille_local(w, h, style, r=0.02, depth=0.05, frame_w=0.012, frame_mat="Grille", mesh_mat="Mesh",
                 lod=0, cell=0.028, shape=None):
    p = Part("grille")
    outline = rr_outline(w, h, r, 4 if lod == 0 else 2, shape)
    if lod >= 1:
        flat_shape(p, outline, 0.0015, "Mesh")
        return p
    tray(p, outline, depth, "Mesh", "Mesh")
    outline = densify(outline, 0.015)
    # Rahmen
    ol = np.array(outline)
    cen = ol.mean(axis=0)
    inner = [(cen[0] + (u - cen[0]) * (1 - frame_w / (w / 2)), cen[1] + (v - cen[1]) * (1 - frame_w / (h / 2))) for (u, v) in outline]
    if frame_mat:
        n = len(outline)
        for i in range(n):
            j = (i + 1) % n
            a0, a1 = np.array([*outline[i], 0.004]), np.array([*outline[j], 0.004])
            b0, b1 = np.array([*inner[i], 0.004]), np.array([*inner[j], 0.004])
            p.quad(a0, a1, b1, b0, frame_mat, outward=(0, 0, 1))
            mid = (b0[:2] + b1[:2]) / 2
            outside = np.append(mid + (mid - cen) * 0.5, -0.006)
            p.quad(b0, b1, b1 + np.array([0, 0, -0.012]), b0 + np.array([0, 0, -0.012]), frame_mat, hint=outside)
    # Muster
    hw, hh = w / 2 - frame_w, h / 2 - frame_w
    def inside(u, v, m=0.0):
        return abs(u) < hw - m and abs(v) < hh - m
    wv = -0.012
    if style == "honeycomb":
        rr_ = cell * 0.5
        dx = rr_ * 1.75
        dy = rr_ * 1.52
        j = 0
        v = -hh
        while v < hh:
            u = -hw + (dx / 2 if j % 2 else 0)
            while u < hw:
                if inside(u, v, rr_ * 0.6):
                    ring_o = [(u + rr_ * math.cos(math.radians(30 + 60 * k)), v + rr_ * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
                    ring_i = [(u + rr_ * 0.72 * math.cos(math.radians(30 + 60 * k)), v + rr_ * 0.72 * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
                    for k in range(6):
                        k2 = (k + 1) % 6
                        a0, a1 = np.array([*ring_o[k], wv]), np.array([*ring_o[k2], wv])
                        b0, b1 = np.array([*ring_i[k], wv]), np.array([*ring_i[k2], wv])
                        p.quad(a0, a1, b1, b0, frame_mat or "Grille", outward=(0, 0, 1))
                        mid = (np.array(ring_i[k]) + np.array(ring_i[k2])) / 2
                        outside = np.append(np.array([u, v]) + (mid - np.array([u, v])) * 2.0, wv - 0.006)
                        p.quad(b0, b1, b1 - np.array([0, 0, 0.012]), b0 - np.array([0, 0, 0.012]),
                               frame_mat or "Grille", hint=outside)
                u += dx
            v += dy
            j += 1
    elif style in ("hslats", "vslats", "eggcrate"):
        n_h = int(h / cell) if style in ("hslats", "eggcrate") else 0
        n_v = int(w / cell) if style in ("vslats", "eggcrate") else 0
        t = cell * 0.22
        for i in range(1, n_h):
            v = -hh + 2 * hh * i / n_h
            seg_box(p, (0, v, wv - 0.006), (2 * hw, t, 0.02), frame_mat or "Grille")
        for i in range(1, n_v):
            u = -hw + 2 * hw * i / n_v
            seg_box(p, (u, 0, wv - 0.006), (2 * hh, t, 0.02), frame_mat or "Grille", rot=(0, 0, math.pi / 2))
    elif style == "mesh":
        t = cell * 0.18
        n = int((w + h) / cell)
        for i in range(-n, n):
            for sgn in (1, -1):
                u0 = i * cell
                pts = []
                for vv in (-hh, hh):
                    uu = u0 + sgn * vv
                    pts.append((uu, vv))
                (ua, va), (ub, vb) = pts
                # auf das Rechteck beschneiden
                seg = clip_seg(ua, va, ub, vb, hw, hh)
                if seg:
                    (ua, va), (ub, vb) = seg
                    strip2d(p, [(ua, va), (ub, vb)], t, wv, frame_mat or "Mesh", thick=0.008)
    return p


def clip_seg(x0, y0, x1, y1, hw, hh):
    """Strecke auf Rechteck [-hw,hw]x[-hh,hh] beschneiden (Liang-Barsky)."""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p_, q_ in ((-dx, x0 + hw), (dx, hw - x0), (-dy, y0 + hh), (dy, hh - y0)):
        if abs(p_) < 1e-12:
            if q_ < 0:
                return None
        else:
            t = q_ / p_
            if p_ < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    if t0 > t1:
        return None
    return (x0 + dx * t0, y0 + dy * t0), (x0 + dx * t1, y0 + dy * t1)


def place_front(ctx, local, x, y, extent, dst, mirror=False, normal_blend=0.5, rear=False, cut=None):
    hit = ctx.hit_rear(x, y) if rear else ctx.hit_front(x, y)
    if hit is None:
        raise ValueError("kein Treffer bei x=%.2f y=%.2f" % (x, y))
    P, Nn, _ = hit
    axis = np.array([0, 0, -1.0 if rear else 1.0])
    n = norm(Nn * normal_blend + axis * (1 - normal_blend))
    return conform_part(ctx, local, P, n, extent, dst=dst, mirror=mirror, cut=cut)


def place_side(ctx, local, z, y, extent, dst, mirror=True, side=1, cut=None, normal=None):
    hit = ctx.hit_side(z, y, side)
    if hit is None:
        raise ValueError("kein Treffer an der Seite z=%.2f y=%.2f" % (z, y))
    P, Nn, _ = hit
    return conform_part(ctx, local, P, Nn if normal is None else normal, extent, dst=dst, mirror=mirror, cut=cut)


def place_flat(ctx, local, origin, normal, extent, dst, lift=0.003, up_hint=(0, 1, 0), mirror=False):
    """Flaches, starres Teil (Kennzeichen, Embleme, Gitter) an einer Ebene ausrichten.

    Die Ebene liegt am äußersten Oberflächenpunkt im Bereich extent, damit nichts
    einsinkt; lift hebt zusätzlich an. Lokale Koordinaten wie bei conform (u, v, w)."""
    o = np.asarray(origin, dtype=float)
    nrm = np.asarray(normal, dtype=float)
    for k, sgn in enumerate((1, -1) if mirror else (1,)):
        oo = o * np.array([sgn, 1, 1])
        nn_ = nrm * np.array([sgn, 1, 1])
        r, up, n = frame(nn_, up_hint)
        hw, hh = extent[0] / 2, extent[1] / 2
        off = 0.0
        for (u, v) in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh), (0, -hh), (0, hh), (-hw, 0), (hw, 0), (0, 0)):
            p0 = oo + r * u + up * v
            hit = ctx.rc.cast(p0 + n * 0.4, -n, max_t=0.8)
            if hit is not None:
                off = max(off, float(np.dot(hit[0] - oo, n)))
        M = np.column_stack([r, up, n])
        # Gegenseite: echtes Spiegelbild (u -> -u), wie bei conform_part.
        # Schrift-Decals deshalb ohne mirror je Seite einzeln platzieren.
        src = local if sgn > 0 else local.mirrored_x()
        dst.merge(src.transformed(M, oo + n * (off + lift)))
    return dst


def place_top(ctx, local, x, z, extent, dst, mirror=False, up_hint=(0, 0, 1), cut=None):
    hit = ctx.hit_top(x, z)
    if hit is None:
        raise ValueError("kein Treffer oben x=%.2f z=%.2f" % (x, z))
    P, Nn, _ = hit
    return conform_part(ctx, local, P, Nn, extent, dst=dst, mirror=mirror, up_hint=up_hint, cut=cut)


# ----------------------------------------------------------------------
# Logos, Kennzeichen, Kleinteile
# ----------------------------------------------------------------------

def decal_local(w, h, mat, wv=0.0015, uv=(0, 0, 1, 1), max_len=0.025):
    """Textur-Aufkleber, fein unterteilt (folgt angepasst der Krümmung)."""
    p = Part("decal")
    nu = max(1, int(math.ceil(w / max_len)))
    nv = max(1, int(math.ceil(h / max_len)))
    u0, v0, u1, v1 = uv
    n = np.array([0.0, 0.0, 1.0])
    for i in range(nu):
        for j in range(nv):
            xa, xb = -w / 2 + w * i / nu, -w / 2 + w * (i + 1) / nu
            ya, yb = -h / 2 + h * j / nv, -h / 2 + h * (j + 1) / nv
            ua, ub = u0 + (u1 - u0) * i / nu, u0 + (u1 - u0) * (i + 1) / nu
            va, vb = v1 - (v1 - v0) * j / nv, v1 - (v1 - v0) * (j + 1) / nv
            P = [np.array([xa, ya, wv]), np.array([xb, ya, wv]), np.array([xb, yb, wv]), np.array([xa, yb, wv])]
            p.tri(P[0], P[1], P[2], mat, normals=[n, n, n], uvs=[(ua, va), (ub, va), (ub, vb)], outward=n)
            p.tri(P[0], P[2], P[3], mat, normals=[n, n, n], uvs=[(ua, va), (ub, vb), (ua, vb)], outward=n)
    return p


def plate_holder_local(lod=0):
    p = Part("plate")
    if lod < 2:                     # Halter nur in der Nähe (spart in der Ferne einen Draw Call je Schild)
        p.rbox((0, 0, -0.004), (0.54, 0.13, 0.012), 0.01, "Trim", segs=2)
    p.tex_quad((0, 0, 0.0035), (1, 0, 0), (0, 1, 0), 0.52, 0.11, "Plate")
    if lod == 0:
        for u in (-0.2, 0.2):
            p.lathe([(0.003, 0.0), (0.003, 0.006), (0.0045, 0.004), (0.0045, 0.0)], 8, "Chrome",
                    center=(u, 0.045, 0), axis="z", inside=(0.002, 0.002))
    return p


def mirror_local(side_len=0.17, h=0.085, depth=0.11, lod=0, body_mat="Paint", cap_mat=None):
    """Außenspiegel: Gehäuse nach außen (+u), Spiegelglas nach hinten (-z global später)."""
    p = Part("mirror")
    segs = 6 if lod == 0 else 2
    secs = []
    for t in np.linspace(0, 1, 7 if lod == 0 else 3):
        ww = side_len * (0.35 + 0.65 * t)
        hh = h * (0.55 + 0.45 * math.sin(t * math.pi / 2))
        d = depth * (0.5 + 0.5 * math.sin(t * math.pi / 2))
        sec = []
        for (a, b) in round_rect(d, hh, min(d, hh) * 0.45, segs):
            sec.append(np.array([ww * 0.1 + t * side_len, b, a]))
        secs.append(sec)
    p.loft(secs, lambda k, j: cap_mat or body_mat, caps=(None, cap_mat or body_mat), smooth=True)
    return p


def wiper_blade(part, base, tip, mat="Wiper", lod=0):
    base, tip = np.asarray(base, dtype=float), np.asarray(tip, dtype=float)
    part.tube([base, base + (tip - base) * 0.25, tip], 0.006, mat, segs=6 if lod == 0 else 3)
    if lod == 0:
        part.box((base * 0.0 + base), (0.03, 0.02, 0.03), mat)


def exhaust_tip(part, center, r, length, style="round", mat="Chrome", inner="ExhaustInner", lod=0, M=None):
    """Endrohr. center = Mündung; das Rohr reicht length nach vorne (+z) in die Karosserie.

    M optional: Drehung (z. B. für Sidepipes, die zur Seite zeigen).
    """
    c = np.asarray(center, dtype=float)
    segs = 24 if lod == 0 else 10
    tmp = Part("tip")
    if style in ("round", "oval", "twin"):
        prof = [(length, r * 0.94), (length * 0.35, r), (0.0, r * 1.03), (-0.005, r * 0.99), (-0.003, r * 0.88),
                (length * 0.25, r * 0.86)]
        tmp.lathe(prof, segs, mat, center=(0, 0, 0), axis="z", inside=(length * 0.5, r * 0.93))
        tmp.lathe([(length * 0.25, r * 0.86), (length * 0.25, 0.0)], segs, inner, center=(0, 0, 0), axis="z",
                  inside=(length * 0.25 + 0.01, 0.0))
        if style == "oval":
            tmp = tmp.transformed(np.diag([1.4, 0.78, 1.0]))
    else:  # square / trapez
        o = round_rect(r * 2.8, r * 1.5, r * 0.35, 4)
        secs = [[np.array([u * sc, v * sc, zz]) for (u, v) in o] for zz, sc in ((length, 0.94), (0.004, 1.0), (0.0, 1.0))]
        tmp.loft(secs, lambda k, j: mat, smooth=True, hint_fn=lambda k: np.array([0, 0, length / 2]))
        inn = [(u * 0.86, v * 0.8) for (u, v) in o]
        for i in range(len(o)):
            j = (i + 1) % len(o)
            a0, a1 = np.array([*o[i], 0.0]), np.array([*o[j], 0.0])
            b0, b1 = np.array([*inn[i], 0.0]), np.array([*inn[j], 0.0])
            tmp.quad(a0, a1, b1, b0, mat, outward=(0, 0, -1))
            tmp.quad(b0, b1, b1 + np.array([0, 0, 0.03]), b0 + np.array([0, 0, 0.03]), mat,
                     hint=np.array([0, 0, 0.015]) + np.append((np.array(inn[i]) + np.array(inn[j])) / 2, 0) * 2.0)
        flat_shape(tmp, inn, 0.03, inner, outward=(0, 0, -1))
    part.merge(tmp.transformed(M, c))


def underbody(part, body, inset=0.06):
    """Dunkle Bodenplatte (verhindert Durchblick von unten)."""
    zs = np.linspace(body.zr + 0.15, body.zf - 0.15, 24)
    rows = []
    for z in zs:
        p = body.params_at(z)
        w = p["w"] * 0.82 - inset
        y = p["yb"] + 0.012
        rows.append((np.array([w, y, z]), np.array([-w, y, z])))
    for i in range(len(rows) - 1):
        a, b = rows[i]
        c, d = rows[i + 1]
        part.quad(a, b, d, c, "Underbody", outward=(0, -1, 0))
