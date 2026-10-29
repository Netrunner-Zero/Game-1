"""Karosserie-Modell.

Die Karosserie entsteht aus Stationen entlang der Längsachse (z) mit
Breite w, Unterkante yb, Gürtellinie yt und Wölbung cr. Daraus werden
gerundete Querschnitte erzeugt und zu einer glatten Haut verbunden.

Besonderheiten:
- Nase und Heck werden automatisch gerundet (Radius je Auto).
- Radläufe werden echt ausgeschnitten; Radhausschale und Bördelkante
  verdecken die Schnittkante.
- Über der Fahrgastzelle ist die Haut offen; dort sitzt das Glashaus,
  darunter die Fahrgastzelle (interior.py).
- Querschnitte haben feste Ankerpunkte (Unterkante Mitte, Schnittlinie
  der Kabine, Dachmitte), damit Ausschnitte saubere Kanten bekommen.
"""
import math

import numpy as np

from .mesh import Part, round_poly, resample, grid_normals, norm, round_open

LOD_RES = {
    0: {"dz": 0.03, "na": 44, "nb": 10, "round": 6, "cab_sub": 5, "cab_ns": 14, "cab_nr": 8},
    1: {"dz": 0.08, "na": 20, "nb": 5, "round": 3, "cab_sub": 2, "cab_ns": 6, "cab_nr": 4},
    2: {"dz": 0.22, "na": 9, "nb": 3, "round": 1, "cab_sub": 1, "cab_ns": 3, "cab_nr": 2},
}


def pchip(xs, ys, xq):
    """Monotone kubische Interpolation."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(ys) - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    out = []
    for x in np.atleast_1d(xq):
        i = int(min(max(np.searchsorted(xs, x) - 1, 0), len(xs) - 2))
        t = (x - xs[i]) / h[i]
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        out.append(h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1])
    return np.array(out)


class Body:
    def __init__(self, spec, lod=0):
        self.spec = spec
        self.lod = lod
        self.res = LOD_RES[lod]
        keys = sorted(spec["body"], key=lambda s: s["z"])
        self.keys = keys
        self.zr, self.zf = keys[0]["z"], keys[-1]["z"]
        sec = {"bw": 0.86, "lo": 0.15, "hi": 0.15, "tum": 1.0, "sh": 0.88, "crx": 0.45,
               "radii": [0.04, 0.05, 0.07, 0.10, 0.18]}
        sec.update(spec.get("section", {}))
        self.sec = sec
        self.cabin = spec["cabin"]
        self.wheels = spec["wheels"]
        self._build_stations()
        self._build_sections()

    # ------------------------------------------------------------------
    # Stationen
    # ------------------------------------------------------------------
    def params_at(self, z):
        """Interpolierte Stationsparameter (ohne Endrundung)."""
        ks = self.keys
        zs = [k["z"] for k in ks]
        z = min(max(z, zs[0]), zs[-1])
        out = {"z": z}
        for key in ("w", "yb", "yt", "cr", "sd"):
            out[key] = float(pchip(zs, [k.get(key, 0.0) for k in ks], [z])[0])
        return out

    def _build_stations(self):
        dz = self.res["dz"]
        nose_r = self.spec.get("nose_r", 0.07)
        tail_r = self.spec.get("tail_r", 0.06)
        z0 = self.zr + tail_r
        z1 = self.zf - nose_r
        n = max(2, int(math.ceil((z1 - z0) / dz)))
        zs = list(np.linspace(z0, z1, n + 1))
        # Schlüsselstationen exakt aufnehmen
        for k in self.keys:
            if z0 < k["z"] < z1 and min(abs(k["z"] - z) for z in zs) > dz * 0.3:
                zs.append(k["z"])
        zs = sorted(zs)
        st = [dict(self.params_at(z), inset=0.0) for z in zs]
        # Rundung an Nase und Heck: Querschnitt schrumpft auf einem Viertelkreis
        steps = {0: 6, 1: 3, 2: 1}[self.lod]
        front, rear = [], []
        for i in range(1, steps + 1):
            a = (math.pi / 2) * i / steps
            pf = self.params_at(self.zf)
            front.append(dict(pf, z=z1 + nose_r * math.sin(a), inset=nose_r * (1 - math.cos(a))))
            pr = self.params_at(self.zr)
            rear.append(dict(pr, z=z0 - tail_r * math.sin(a), inset=tail_r * (1 - math.cos(a))))
        self.stations = list(reversed(rear)) + st + front
        self.zs = np.array([s["z"] for s in self.stations])

    # ------------------------------------------------------------------
    # Querschnitte
    # ------------------------------------------------------------------
    def x_cut(self, z):
        """Seitliche Position der Kabinen-Schnittlinie (knapp innerhalb des Glashausfußes)."""
        cz = [c["z"] for c in self.cabin]
        cw = [c["wb"] for c in self.cabin]
        order = np.argsort(cz)
        cz = np.array(cz)[order]
        cw = np.array(cw)[order]
        z = min(max(z, cz[0]), cz[-1])
        return float(np.interp(z, cz, cw)) - 0.012

    def section_points(self, st):
        w, yb, yt, cr = st["w"], st["yb"], st["yt"], st["cr"]
        ins = st.get("inset", 0.0)
        s = self.sec
        h = yt - yb
        w_ = max(w - ins, 0.05)
        yb_ = yb + ins * 0.9
        yt_ = yt - ins * 0.55
        cr_ = cr * max(0.0, 1 - ins / 0.08)
        h_ = yt_ - yb_
        pts = [(0.0, yb_), (s["bw"] * w_, yb_), (w_, yb_ + s["lo"] * h_), (w_ * s["tum"], yt_ - s["hi"] * h_),
               (s["sh"] * w_, yt_), (s["crx"] * w_, yt_ + cr_), (0.0, yt_ + cr_ * 1.04)]
        radii = list(s["radii"])
        r_scale = max(0.35, 1 - ins / 0.12)
        radii = [0.0] + [r * r_scale for r in radii] + [0.0]
        full = pts + [(-x, y) for (x, y) in reversed(pts[1:-1])]
        rfull = radii + list(reversed(radii[1:-1]))
        poly = round_poly(full, rfull, self.res["round"])
        # Seitliche Sicke (z. B. Lufthutze vor dem Hinterrad): Flanke nach innen drücken
        sd = st.get("sd", 0.0)
        if sd > 1e-4:
            yc, hh = s.get("dent_y", 0.5), s.get("dent_h", 0.12)
            dented = []
            for (x, y) in poly:
                t = (y - yc) / hh
                if abs(t) < 1.0 and abs(x) > 0.3:
                    f = 0.5 * (1 + math.cos(math.pi * t))
                    x = x - math.copysign(sd * f, x)
                dented.append((x, y))
            poly = dented
        # rechte Hälfte: Unterkante Mitte -> Dachmitte
        half = []
        top_idx = None
        for i, (x, y) in enumerate(poly):
            half.append((x, y))
            if abs(x) < 1e-9 and y > yb_ + 0.01:
                top_idx = i
                break
        if top_idx is None:  # Dachmitte suchen (x ~ 0, oben)
            i = int(np.argmax([y for (x, y) in poly]))
            half = poly[: i + 1]
        # Schnittpunkt x = x_cut auf der Oberseite (von oben kommend suchen)
        xc = min(self.x_cut(st["z"]), w_ * s["sh"] - 0.02)
        ci = None
        for i in range(len(half) - 1, 0, -1):
            (x0, y0), (x1, y1) = half[i - 1], half[i]
            if (x0 - xc) * (x1 - xc) <= 0 and y0 > yb_ + 0.5 * h_:
                f = (xc - x0) / (x1 - x0) if abs(x1 - x0) > 1e-12 else 0.0
                cp = (xc, y0 + (y1 - y0) * f)
                A = half[:i] + [cp]
                B = [cp] + half[i:]
                ci = i
                break
        if ci is None:
            A, B = half[: len(half) - 2], half[len(half) - 3:]
        na, nb = self.res["na"], self.res["nb"]
        Ar = resample(A, na + 1)
        Br = resample(B, nb + 1)
        right = Ar[:-1] + Br
        left = [(-x, y) for (x, y) in reversed(right[1:-1])]
        return right + left

    def _build_sections(self):
        secs = []
        for st in self.stations:
            pts = self.section_points(st)
            secs.append([(x, y, st["z"]) for (x, y) in pts])
        self.S = np.array(secs)  # K x m x 3
        self.K, self.m = self.S.shape[0], self.S.shape[1]
        self.na, self.nb = self.res["na"], self.res["nb"]
        self.j_cut_r = self.na
        self.j_top = self.na + self.nb
        self.j_cut_l = self.na + 2 * self.nb
        cents = self.S.mean(axis=1)
        self.N = grid_normals(self.S, True, cents)
        # UV: Bogenlänge um den Querschnitt (u) und Länge (v), in Metern
        U = np.zeros((self.K, self.m))
        for k in range(self.K):
            d = np.linalg.norm(np.diff(self.S[k], axis=0), axis=1)
            U[k, 1:] = np.cumsum(d)
        self.U = U

    # ------------------------------------------------------------------
    # Abfragen
    # ------------------------------------------------------------------
    def station_index(self, z):
        return int(np.clip(np.searchsorted(self.zs, z) - 1, 0, self.K - 2))

    def point(self, z, j):
        """Punkt + Normale bei Länge z und (gebrochenem) Querschnittsindex j."""
        k = self.station_index(z)
        t = (z - self.zs[k]) / max(self.zs[k + 1] - self.zs[k], 1e-9)
        t = min(max(t, 0.0), 1.0)
        j0 = int(math.floor(j)) % self.m
        j1 = (j0 + 1) % self.m
        f = j - math.floor(j)
        P = (1 - t) * ((1 - f) * self.S[k, j0] + f * self.S[k, j1]) + t * ((1 - f) * self.S[k + 1, j0] + f * self.S[k + 1, j1])
        Nn = (1 - t) * ((1 - f) * self.N[k, j0] + f * self.N[k, j1]) + t * ((1 - f) * self.N[k + 1, j0] + f * self.N[k + 1, j1])
        return P, norm(Nn)

    def j_at_height(self, z, y, side=1):
        """Querschnittsindex auf der Flanke (Unterkante bis Schnittlinie) bei Höhe y."""
        k = self.station_index(z)
        sec = self.S[k]
        rng = range(0, self.j_cut_r) if side > 0 else range(self.m - 1, self.j_cut_l, -1)
        idx = list(rng)
        best = None
        for a, b in zip(idx[:-1], idx[1:]):
            y0, y1 = sec[a][1], sec[b][1]
            if (y0 - y) * (y1 - y) <= 0 and abs(y1 - y0) > 1e-9:
                f = (y - y0) / (y1 - y0)
                best = a + (b - a) * f
                break
        if best is None:
            best = float(idx[-1])
        return best % self.m

    def j_at_x_top(self, z, x):
        """Querschnittsindex auf der Oberseite bei seitlicher Position x (rechts > 0)."""
        k = self.station_index(z)
        sec = self.S[k]
        if x >= 0:
            idx = list(range(self.j_cut_r - 6, self.j_top + 1))
        else:
            idx = list(range(self.j_top, self.j_cut_l + 7))
        for a, b in zip(idx[:-1], idx[1:]):
            x0, x1 = sec[a % self.m][0], sec[b % self.m][0]
            if (x0 - x) * (x1 - x) <= 0 and abs(x1 - x0) > 1e-12:
                return (a + (b - a) * (x - x0) / (x1 - x0)) % self.m
        return float(self.j_top)

    def side_x(self, z, y, side=1):
        P, _ = self.point(z, self.j_at_height(z, y, side))
        return abs(P[0])

    def top_y(self, z, x=0.0):
        if abs(x) < 1e-6:
            P, _ = self.point(z, self.j_top)
        else:
            P, _ = self.point(z, self.j_at_x_top(z, x))
        return float(P[1])

    def width_at(self, z):
        k = self.station_index(z)
        return float(np.max(np.abs(self.S[k][:, 0])))

    # ------------------------------------------------------------------
    # Haut
    # ------------------------------------------------------------------
    def cabin_open_range(self):
        cz = [c["z"] for c in self.cabin]
        return min(cz) - 0.01, max(cz) + 0.01

    def build_skin(self, mat_fn=None, open_cabin=True, cut_arches=True, extra_cuts=(), cuts=None):
        """Karosseriehaut. mat_fn(j, centroid) -> Material (Standard 'Paint', None = Fläche weglassen).

        cuts: Liste cut.Cut – exakte Öffnungen für Lampen, Einlässe, Grills."""
        part = Part("Skin")
        zo0, zo1 = self.cabin_open_range()
        wheels = []
        for axle in ("front", "rear"):
            wd = self.wheels[axle]
            gap = wd.get("gap", self.spec.get("arch_gap", 0.045))
            wheels.append((wd["z"], wd["R"], wd["R"] + gap, wd["W"]))
        S, N, U = self.S, self.N, self.U
        for k in range(self.K - 1):
            z0, z1 = self.zs[k], self.zs[k + 1]
            for j in range(self.m):
                j2 = (j + 1) % self.m
                P = [S[k, j], S[k, j2], S[k + 1, j2], S[k + 1, j]]
                c = (P[0] + P[1] + P[2] + P[3]) / 4
                if open_cabin and self.j_cut_r <= j < self.j_cut_l and zo0 < c[2] < zo1:
                    continue
                skip = False
                if cut_arches:
                    for (zc, R, rc, W) in wheels:
                        if (c[2] - zc) ** 2 + (c[1] - R) ** 2 < rc ** 2:
                            wloc = self.width_at(c[2])
                            if abs(c[0]) > wloc - W - 0.07:
                                skip = True
                                break
                for fn in extra_cuts:
                    if fn(c, j, k):
                        skip = True
                if skip:
                    continue
                mat = mat_fn(j, c) if mat_fn else "Paint"
                nn = [N[k, j], N[k, j2], N[k + 1, j2], N[k + 1, j]]
                uu = [(U[k, j], z0), (U[k, j2], z0), (U[k + 1, j2], z1), (U[k + 1, j], z1)]
                part.quad(P[0], P[1], P[2], P[3], mat, normals=nn, uvs=uu, outward=nn[0] + nn[2])
        # Endkappen (klein dank Rundung)
        for k, sgn in ((0, -1), (self.K - 1, 1)):
            sec = S[k]
            cen = sec.mean(axis=0)
            nrm = np.array([0.0, 0.0, float(sgn)])
            for j in range(self.m):
                part.tri(cen, sec[j], sec[(j + 1) % self.m], mat_fn(j, cen) if mat_fn else "Paint",
                         outward=nrm, normals=[nrm, nrm, nrm])
        if cuts:
            from .cut import cut_triangles
            for m in list(part.tris):
                part.tris[m] = cut_triangles(part.tris[m], cuts)
        return part

    # ------------------------------------------------------------------
    # Radläufe: Bördelkante und Radhausschale
    # ------------------------------------------------------------------
    def wheel_arches(self, lip_mat="Paint", liner_mat="Liner", flare=None):
        part = Part("Arches")
        segs = {0: 36, 1: 16, 2: 8}[self.lod]
        for axle in ("front", "rear"):
            wd = self.wheels[axle]
            zc, R, W = wd["z"], wd["R"], wd["W"]
            gap = wd.get("gap", self.spec.get("arch_gap", 0.045))
            rc = R + gap
            # Winkelbereich: oberhalb der Unterkante der Karosserie
            yb = self.params_at(zc)["yb"]
            s = (yb + 0.01 - R) / rc
            s = min(max(s, -0.99), 0.99)
            a_lo = math.asin(s)
            a0, a1 = a_lo, math.pi - a_lo
            for side in (1, -1):
                secs_lip = []
                liner_out, liner_in = [], []
                for i in range(segs + 1):
                    a = a0 + (a1 - a0) * i / segs
                    z = zc + rc * math.cos(a)
                    y = R + rc * math.sin(a)
                    j = self.j_at_height(z, y, side)
                    P, Nn = self.point(z, j)
                    radial = np.array([0.0, math.sin(a), math.cos(a)])
                    nrm = Nn - radial * np.dot(Nn, radial)
                    nrm = norm(nrm) if np.linalg.norm(nrm) > 1e-6 else np.array([float(side), 0, 0])
                    C = np.array([P[0], y, z])
                    if flare:
                        fo, fw = flare
                        prof = [(0.0, fw + 0.02), (fo * 0.5, fw), (fo, fw * 0.5), (fo + 0.004, 0.0),
                                (fo, -0.012), (fo - 0.02, -0.02), (-0.05, -0.02)]
                    else:
                        prof = [(0.0015, 0.026), (0.004, 0.010), (0.0038, -0.010), (0.0005, -0.018),
                                (-0.008, -0.022), (-0.03, -0.024), (-0.06, -0.024)]
                    secs_lip.append([C + nrm * dn + radial * dr for (dn, dr) in prof])
                    xin = (P[0] - side * (W + 0.10))
                    liner_out.append(np.array([P[0] - side * 0.04, R + (rc - 0.012) * math.sin(a), zc + (rc - 0.012) * math.cos(a)]))
                    liner_in.append(np.array([xin, R + (rc - 0.012) * math.sin(a), zc + (rc - 0.012) * math.cos(a)]))
                tmp = Part("lip")
                tmp.loft(secs_lip, lambda k, j: lip_mat, closed=False, smooth=True,
                         hint_fn=lambda k, _zc=zc: np.array([0.0, R, _zc]))
                part.merge(tmp)
                part.merge(tmp, flip=True)   # dünnes Blech: beidseitig sichtbar
                # Radhausschale (Innenseite zum Rad)
                hub = np.array([0.0, R, zc])
                for i in range(segs):
                    a_, b_ = liner_out[i], liner_out[i + 1]
                    c_, d_ = liner_in[i + 1], liner_in[i]
                    mid = (a_ + b_ + c_ + d_) / 4
                    toward = np.array([0.0, R, zc]) - np.array([0.0, mid[1], mid[2]])
                    part.quad(a_, b_, c_, d_, liner_mat, outward=toward)
                # Innenwand der Schale
                cin = np.array([liner_in[0][0], R, zc])
                for i in range(segs):
                    part.tri(cin, liner_in[i], liner_in[i + 1], liner_mat, outward=np.array([float(side), 0, 0]))
        return part

    # ------------------------------------------------------------------
    # Linien auf der Oberfläche (Fugen, Zierleisten)
    # ------------------------------------------------------------------
    def strip(self, part, samples, width, mat, offset=0.0015):
        """samples: Liste (z, j). Streifen folgt der Oberfläche."""
        pts, nrs = [], []
        for (z, j) in samples:
            P, Nn = self.point(z, j)
            pts.append(P + Nn * offset)
            nrs.append(Nn)
        for i in range(len(pts) - 1):
            t = norm(pts[i + 1] - pts[i])
            for (p0, p1, n0, n1) in ((pts[i], pts[i + 1], nrs[i], nrs[i + 1]),):
                s0 = norm(np.cross(n0, t)) * width / 2
                s1 = norm(np.cross(n1, t)) * width / 2
                part.quad(p0 - s0, p0 + s0, p1 + s1, p1 - s1, mat, normals=[n0, n0, n1, n1], outward=n0 + n1)

    def gap_lines(self, part, gaps, mat="Gap", width=0.0045):
        """Fugen aus der Fahrzeugbeschreibung."""
        for door in gaps.get("doors", []):
            for side in (1, -1):
                for zg in door["z"]:
                    y_lo = door.get("y0", None)
                    lo = self.j_at_height(zg, y_lo if y_lo else self.params_at(zg)["yb"] + 0.09, side)
                    hi = self.j_cut_r - 0.6 if side > 0 else self.j_cut_l + 0.6
                    n = 12
                    samples = [(zg, lo + (hi - lo) * i / n) for i in range(n + 1)]
                    self.strip(part, samples, width, mat)
                # Unterkante der Tür (Schwellerlinie)
                if door.get("sill", True):
                    zs = list(np.linspace(door["z"][1], door["z"][0], 14))
                    y_lo = door.get("y0", None)
                    samples = [(z, self.j_at_height(z, y_lo if y_lo else self.params_at(z)["yb"] + 0.09, side)) for z in zs]
                    self.strip(part, samples, width, mat)
        for lid in gaps.get("lids", []):
            # Hauben/Deckel: zwei Längslinien + Querlinie
            z0, z1, xf = lid["z0"], lid["z1"], lid["x"]
            for sx in (1, -1):
                zs = list(np.linspace(z0, z1, 16))
                samples = [(z, self.j_at_x_top(z, sx * xf * self.params_at(z)["w"])) for z in zs]
                self.strip(part, samples, width, mat)
            for zq in lid.get("cross", []):
                xs = list(np.linspace(-xf, xf, 16))
                samples = [(zq, self.j_at_x_top(zq, x * self.params_at(zq)["w"])) for x in xs]
                self.strip(part, samples, width, mat)

    # ------------------------------------------------------------------
    # Glashaus
    # ------------------------------------------------------------------
    def cabin_stations(self):
        """Feinere Kabinenstationen; Breiten und Höhen glatt (monoton kubisch) interpoliert."""
        cab = sorted(self.cabin, key=lambda c: -c["z"])
        sub = self.res["cab_sub"]
        zk = [c["z"] for c in reversed(cab)]
        def interp(key):
            vals = [(self._y1abs(c) if key == "y1" else c[key]) for c in reversed(cab)]
            return lambda z: float(pchip(zk, vals, [z])[0])
        f_wb, f_wt, f_y1 = interp("wb"), interp("wt"), interp("y1")
        out = []
        for i in range(len(cab) - 1):
            a, b = cab[i], cab[i + 1]
            n = sub if b["kind"] != "pillar" else max(1, sub // 2)
            for s_ in range(n):
                t = s_ / n
                z = a["z"] + (b["z"] - a["z"]) * t
                out.append({"z": z, "wb": f_wb(z), "wt": f_wt(z), "y1": f_y1(z), "kind": b["kind"], "t": t, "i": i})
        last = cab[-1]
        out.append({"z": last["z"], "wb": last["wb"], "wt": last["wt"], "y1": self._y1abs(last),
                    "kind": last["kind"], "t": 1.0, "i": len(cab) - 2})
        return out

    def _y1abs(self, c):
        if c["y1"] > 0:
            return c["y1"]
        p = self.params_at(c["z"])
        return p["yt"] + p["cr"] + (-c["y1"])

    def _y1(self, a, b, t):
        ya, yb_ = self._y1abs(a), self._y1abs(b)
        # leichte Wölbung (Scheibe/Dach gehen weich ineinander über)
        lin = ya + (yb_ - ya) * t
        bulge = 0.012 * math.sin(math.pi * t) if a is not b else 0.0
        return lin + bulge

    def roof_y(self, z):
        cab = sorted(self.cabin, key=lambda c: c["z"])
        zs = [c["z"] for c in cab]
        ys = [self._y1abs(c) for c in cab]
        return float(np.interp(z, zs, ys))

    def cabin_section(self, c):
        """Querschnitt des Glashauses: Seite (Scheibe/Säule) + Dach, feste Ankerpunkte."""
        p = self.params_at(c["z"])
        y0 = p["yt"] - 0.04
        y1 = c["y1"]
        wb, wt = c["wb"], c["wt"]
        wm = (wb + wt) / 2 * 1.03
        ym = y0 + 0.55 * (y1 - y0)
        nr_ = max(2, self.res["round"] * 2)
        nr_ += nr_ % 2
        chain = round_open([(wb, y0), (wm, ym), (wt, y1), (0.0, y1 + 0.006)], [0.0, 0.06, 0.085, 0.0], nr_)
        # Übergang Seite -> Dach: Mitte der Dachkanten-Rundung (stetig von Station zu Station,
        # damit Säulen, Dachrahmen und Scheibenkanten glatt verlaufen)
        split = nr_ + 2 + nr_ // 2
        side, roof = chain[: split + 1], chain[split:]
        ns, nr = self.res["cab_ns"], self.res["cab_nr"]
        A = resample(side, ns + 1)
        B = resample(roof, nr + 1)
        right = A[:-1] + B
        left = [(-x, y) for (x, y) in reversed(right[:-1])]
        return [(x, y, c["z"]) for (x, y) in right + left], ns

    def glasshouse(self, glass="Glass", roof="Paint", pillar="Paint", bpillar="BlackGloss", seal="Seal",
                   belt="BeltTrim", glass_roof=None):
        """Scheiben, Dach, Säulen, Dichtungen und Gürtellinien-Leiste."""
        part = Part("Glasshouse")
        cst = self.cabin_stations()
        secs, tags_side = [], None
        for c in cst:
            sec, ns = self.cabin_section(c)
            secs.append(sec)
        S = np.array(secs)
        K, m = S.shape[0], S.shape[1]
        cents = S.mean(axis=1)
        Nn = grid_normals(S, True, cents)
        ns = self.res["cab_ns"]
        nr = self.res["cab_nr"]
        # Flächenklassen
        classes = {}

        def face_class(k, j):
            kind = cst[k + 1]["kind"]
            # j: 0..ns-1 rechte Seite, ns..ns+2nr-1 Dach, danach linke Seite; letzte Kante = Boden
            if j == m - 1:
                return None  # Boden offen (Fahrgastzelle)
            on_roof = ns <= j < ns + 2 * nr
            P = S[k, j]
            Q = S[k + 1, (j + 1) % m]
            nrm = norm(np.cross(S[k, (j + 1) % m] - S[k, j], S[k + 1, j] - S[k, j]))
            if np.dot(nrm, (P + Q) / 2 - cents[k]) < 0:
                nrm = -nrm
            if kind == "pillar":
                return "bpillar" if not on_roof else "roof"
            # A-/C-Säulen: feste Indexbänder an der Ecke Seite/Dach (gerade Kanten)
            band_side = max(1, int(round(ns * self.spec.get("pillar_frac", 0.22))))
            jr = j if j < m // 2 else (m - 2 - j)       # gespiegelter Index (rechte Seite)
            corner = (ns - band_side <= jr < ns + 1)
            if kind in ("ws", "rear") and corner:
                return "pillar"
            if kind == "roof" and corner:
                return "roof"          # Dachrahmen über den Seitenscheiben (gleiche Breite wie die Säulen)
            if on_roof:
                if kind == "roof":
                    return "roof"
                return "glass"
            return "glass"

        mats = {"glass": glass, "roof": roof, "pillar": pillar, "bpillar": bpillar}
        for k in range(K - 1):
            for j in range(m):
                fc = face_class(k, j)
                classes[(k, j)] = fc
                if fc is None:
                    continue
                j2 = (j + 1) % m
                P = [S[k, j], S[k, j2], S[k + 1, j2], S[k + 1, j]]
                nn = [Nn[k, j], Nn[k, j2], Nn[k + 1, j2], Nn[k + 1, j]]
                mat = mats[fc] if fc != "roof" or glass_roof is None else glass_roof
                part.quad(P[0], P[1], P[2], P[3], mat, normals=nn, outward=nn[0] + nn[2])
        # Dichtungen zwischen Glas und lackierten Flächen
        w_seal = 0.011 if self.lod == 0 else 0.0
        if w_seal > 0:
            def is_glass(fc):
                return fc == "glass"
            for k in range(K - 1):
                for j in range(m - 1):
                    a, b = classes.get((k, j)), classes.get((k, j + 1))
                    if a is None or b is None:
                        continue
                    if is_glass(a) != is_glass(b):
                        p0, p1 = S[k, j + 1], S[k + 1, j + 1]
                        n0, n1 = Nn[k, j + 1], Nn[k + 1, j + 1]
                        t = norm(p1 - p0)
                        s0 = norm(np.cross(n0, t)) * w_seal / 2
                        part.quad(p0 - s0 + n0 * 0.002, p0 + s0 + n0 * 0.002, p1 + s0 + n1 * 0.002,
                                  p1 - s0 + n1 * 0.002, seal, normals=[n0, n0, n1, n1], outward=n0 + n1)
                for j in range(m):
                    if k + 1 >= K - 1:
                        break
                    a, b = classes.get((k, j)), classes.get((k + 1, j))
                    if a is None or b is None:
                        continue
                    if is_glass(a) != is_glass(b):
                        p0, p1 = S[k + 1, j], S[k + 1, (j + 1) % m]
                        n0, n1 = Nn[k + 1, j], Nn[k + 1, (j + 1) % m]
                        t = norm(p1 - p0)
                        s0 = norm(np.cross(n0, t)) * w_seal / 2
                        part.quad(p0 - s0 + n0 * 0.002, p0 + s0 + n0 * 0.002, p1 + s0 + n1 * 0.002,
                                  p1 - s0 + n1 * 0.002, seal, normals=[n0, n0, n1, n1], outward=n0 + n1)
        # Gürtellinien-Leiste über der Schnittkante der Karosserie
        if belt:
            zo0, zo1 = self.cabin_open_range()
            for side in (1, -1):
                zs = list(np.linspace(zo1 - 0.005, zo0 + 0.005, max(6, int((zo1 - zo0) / 0.04))))
                samples = []
                for z in zs:
                    j = self.j_cut_r if side > 0 else self.j_cut_l
                    samples.append((z, j))
                self.strip(part, samples, 0.026, belt, offset=0.003)
            # Querleisten vorne (Windlauf-Abdeckung) und hinten
            for zq in (zo1 - 0.006, zo0 + 0.006):
                samples = [(zq, self.j_cut_r + (self.j_cut_l - self.j_cut_r) * i / 20) for i in range(21)]
                self.strip(part, samples, 0.03, belt, offset=0.003)
        self.cab_S, self.cab_N, self.cab_classes, self.cab_st = S, Nn, classes, cst
        return part
