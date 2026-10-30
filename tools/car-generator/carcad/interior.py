"""Fahrgastzelle und Cockpit.

Die Karosserie ist über der Kabine offen (body.build_skin). Darunter
entsteht hier eine echte Fahrgastzelle: Boden mit Mitteltunnel,
Fußraum mit Spritzwand, Seitenwände (Türverkleidungen), Rückwand,
dazu Armaturenbrett, Instrumente, Lenkrad, Pedale, Konsole, Sitze,
Gurte, Dachhimmel, Säulenverkleidungen, Innenspiegel, Sonnenblenden.

Fahrer sitzt links (+X).
"""
import math

import numpy as np

from .mesh import Part, norm, round_rect, resample, round_open, rot_matrix, round_poly


# ----------------------------------------------------------------------
# Geometrie des Glashauses abfragen
# ----------------------------------------------------------------------

class CabinGeo:
    def __init__(self, body):
        self.b = body
        S = body.cab_S
        order = np.argsort(S[:, 0, 2])
        self.S = S[order]
        self.zs = self.S[:, 0, 2]
        self.half = body.res["cab_ns"] + body.res["cab_nr"] + 1

    def section(self, z):
        zs = self.zs
        z = min(max(z, zs[0]), zs[-1])
        k = int(np.clip(np.searchsorted(zs, z) - 1, 0, len(zs) - 2))
        t = (z - zs[k]) / max(zs[k + 1] - zs[k], 1e-9)
        return self.S[k] * (1 - t) + self.S[k + 1] * t

    def glass_x(self, z, y):
        """Innenkante der Seitenscheibe bei Höhe y (rechte Seite, x > 0)."""
        sec = self.section(z)[: self.half]
        for a, b in zip(sec[:-1], sec[1:]):
            if (a[1] - y) * (b[1] - y) <= 0 and abs(b[1] - a[1]) > 1e-9:
                f = (y - a[1]) / (b[1] - a[1])
                return float(a[0] + (b[0] - a[0]) * f)
        return float(sec[0][0]) if y < sec[0][1] else 0.0

    def glass_y(self, z, x):
        """Höhe der Scheibe/des Dachs bei seitlicher Position |x|."""
        x = abs(x)
        sec = self.section(z)[: self.half]
        for a, b in zip(sec[:-1], sec[1:]):
            if (a[0] - x) * (b[0] - x) <= 0 and abs(b[0] - a[0]) > 1e-9:
                f = (x - a[0]) / (b[0] - a[0])
                return float(a[1] + (b[1] - a[1]) * f)
        return float(sec[-1][1])

    def roof(self, z):
        return self.glass_y(z, 0.0)


# ----------------------------------------------------------------------
# Hilfen
# ----------------------------------------------------------------------

def sym_quads(part, rows, mat, outward):
    for i in range(len(rows) - 1):
        a, b = rows[i]
        c, d = rows[i + 1]
        part.quad(a, b, d, c, mat, outward=outward)


def loft_profiles(part, profiles, matfn, closed=False, outward_hint=None, smooth=True, caps=(None, None)):
    part.loft(profiles, matfn, closed=closed, smooth=smooth, caps=caps,
              hint_fn=(lambda k: outward_hint(k)) if outward_hint else None)


def stitch_line(part, pts, nrm, width=0.004, offset=0.0015):
    """Ziernaht als schmales Band mit Stichmuster (Material Stitch, UV entlang der Linie)."""
    pts = [np.asarray(p, dtype=float) for p in pts]
    nrm = norm(nrm)
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        t = norm(b - a)
        s = norm(np.cross(nrm, t)) * width / 2
        L = np.linalg.norm(b - a)
        uv = [(acc, 0.0), (acc, 0.004), (acc + L, 0.004), (acc + L, 0.0)]
        o = nrm * offset
        part.quad(a - s + o, a + s + o, b + s + o, b - s + o, "Stitch", normals=[nrm] * 4, uvs=uv, outward=nrm)
        acc += L


# ----------------------------------------------------------------------
# Hauptfunktion
# ----------------------------------------------------------------------

class Cockpit:
    def __init__(self, ctx):
        self.ctx = ctx
        self.b = ctx.b
        self.sp = ctx.spec
        self.I = ctx.spec["interior"]
        self.cg = CabinGeo(ctx.b)
        self.part = Part("Interior")
        self.anchors = {}
        self.nodes = {}       # bewegliche Teile: name -> (Part, translation, rotation_quat)
        b = self.b
        cab = sorted(self.sp["cabin"], key=lambda c: -c["z"])
        self.zws = cab[0]["z"]
        self.zend = cab[-1]["z"]
        self.zo0, self.zo1 = b.cabin_open_range()
        self.floor = self.I["floor"]
        self.fw = self.I["fw"]
        self.rb = self.I["rb"]
        self.seat_x = self.I.get("seat_x", 0.37)
        self.hz = self.I["hpt_z"]          # Sitz-Referenzpunkt (H-Punkt) z

    # --------------------------------------------------------------
    def x_in(self, z):
        """Innenkante der Seitenwand (berücksichtigt Radkästen)."""
        b = self.b
        w = b.params_at(z)["w"]
        x = w - 0.09
        for axle in ("front", "rear"):
            wd = self.sp["wheels"][axle]
            d = abs(z - wd["z"])
            lim = wd["R"] + 0.12
            if d < lim + 0.12:
                f = min(1.0, max(0.0, (lim + 0.12 - d) / 0.12))
                x = min(x, (1 - f) * x + f * (w - wd["W"] - 0.11))
        return x

    def y_cut(self, z):
        b = self.b
        z = min(max(z, self.zo0 + 0.005), self.zo1 - 0.005)
        P, _ = b.point(z, b.j_cut_r)
        return float(P[1]), float(P[0])

    # --------------------------------------------------------------
    def build(self):
        self.tub()
        self.inner_shell()
        self.dash()
        self.steering()
        self.pedals()
        self.console()
        self.seats()
        self.doors()
        self.belts()
        self.mirror_visors()
        self.anchors["eye"] = self.eye
        return self

    # --------------------------------------------------------------
    # Fahrgastzelle
    # --------------------------------------------------------------
    def tub(self):
        p = self.part
        b = self.b
        fl = self.floor
        tunnel = self.I.get("tunnel", 0.13)
        z_toe = self.fw - 0.24
        zs = list(np.linspace(self.rb, self.fw, 40))
        # Boden (mit Tunnel) – Querprofil je z
        rows = []
        for z in zs:
            xi = self.x_in(z)
            yf = fl if z < z_toe else fl + (z - z_toe) / (self.fw - z_toe) * 0.20
            prof = [(xi, yf), (0.16, yf), (0.11, yf + tunnel), (-0.11, yf + tunnel), (-0.16, yf), (-xi, yf)]
            rows.append([np.array([x, y, z]) for (x, y) in prof])
        tmp = Part("floor")
        tmp.loft(rows, lambda k, j: "Carpet", closed=False, smooth=False,
                 hint_fn=lambda k: np.array([0.0, fl - 1.0, zs[k]]))
        p.merge(tmp)
        # Fußmatten (leicht erhöht)
        for sx in (1, -1):
            xc = sx * self.seat_x
            z0, z1 = self.hz + 0.15, z_toe - 0.02
            p.rbox((xc, fl + 0.006, (z0 + z1) / 2), (0.42, 0.008, z1 - z0), 0.03, "FloorMat", segs=2)
        # Seitenwände (Türverkleidungen / Seitenteile)
        for side in (1, -1):
            rows = []
            for z in zs:
                xi = self.x_in(z)
                yf = fl if z < z_toe else fl + (z - z_toe) / (self.fw - z_toe) * 0.20
                if self.zo0 + 0.004 < z < self.zo1 - 0.004:
                    yc, xc = self.y_cut(z)
                else:
                    yc = b.params_at(z)["yt"] - 0.02
                    xc = xi + 0.02
                # Innenkante Schweller -> Fensterbrüstung (leicht nach innen gewölbt)
                prof = [np.array([side * xi, yf - 0.01, z]), np.array([side * xi, yc - 0.16, z]),
                        np.array([side * (xi - 0.03), yc - 0.06, z]), np.array([side * (xc - 0.004), yc - 0.004, z])]
                rows.append(prof)
            tmp = Part("wall")
            tmp.loft(rows, lambda k, j: "Interior" if j < 1 else "Dash", closed=False, smooth=True,
                     hint_fn=lambda k, s=side: np.array([s * 3.0, fl + 0.3, zs[k]]))
            p.merge(tmp)
        # Spritzwand (vorne) und Rückwand
        for z, out in ((self.fw, -1.0), (self.rb, 1.0)):
            xi = self.x_in(z)
            yt = b.params_at(z)["yt"]
            yb_ = fl + (0.20 if out < 0 else 0.0) - 0.01
            if out > 0 and self.I.get("rear_wall_top") is not None:
                yt = self.I["rear_wall_top"]
            p.quad((xi, yb_, z), (-xi, yb_, z), (-xi, yt, z), (xi, yt, z), "Carpet" if out < 0 else "Interior",
                   outward=(0, 0, out))
        # Glas-Trennwand hinter den Sitzen (Mittelmotor: Blick auf den Motor)
        if self.I.get("bulkhead_glass"):
            z = self.rb - 0.004
            sec = self.cg.section(z)
            yb_ = b.params_at(z)["yt"] - 0.03
            pts = [np.array([q[0] * 0.95, q[1] - 0.03, z]) for q in sec if q[1] >= yb_ + 0.01]
            if len(pts) >= 3:
                pts = [np.array([pts[0][0], yb_, z])] + pts + [np.array([pts[-1][0], yb_, z])]
                c = sum(pts) / len(pts)
                for i in range(len(pts) - 1):
                    p.tri(c, pts[i], pts[i + 1], "Glass", outward=(0, 0, 1))
                for i in range(len(pts) - 1):
                    p.tube([pts[i], pts[i + 1]], 0.008, "InteriorPlastic", segs=6, caps=False)
        # Ablage hinter der Rückwand (bis zur Heckscheibe) bzw. Hutablage
        shelf = self.I.get("shelf")
        if shelf:
            z0, z1, ys = shelf
            rows = []
            for z in np.linspace(z0, z1, 10):
                yc, xc = self.y_cut(z)
                rows.append((np.array([xc + 0.01, ys, z]), np.array([-xc - 0.01, ys, z])))
            sym_quads(p, rows, self.I.get("shelf_mat", "Carpet"), (0, 1, 0))
            # Front der Ablage
            xi = self.x_in(z1)
            p.quad((xi, fl, z1), (-xi, fl, z1), (-xi, ys, z1), (xi, ys, z1), "Interior", outward=(0, 0, 1))

    # --------------------------------------------------------------
    def inner_shell(self):
        """Dachhimmel und Säulenverkleidungen als Innenseite des Glashauses."""
        b = self.b
        S, Nn, classes = b.cab_S, b.cab_N, b.cab_classes
        K, m = S.shape[0], S.shape[1]
        star = self.I.get("starlight", False)
        for (k, j), fc in classes.items():
            if fc in (None, "glass"):
                continue
            j2 = (j + 1) % m
            d = 0.018
            P = [S[k, j] - Nn[k, j] * d, S[k, j2] - Nn[k, j2] * d, S[k + 1, j2] - Nn[k + 1, j2] * d,
                 S[k + 1, j] - Nn[k + 1, j] * d]
            nn = [-Nn[k, j], -Nn[k, j2], -Nn[k + 1, j2], -Nn[k + 1, j]]
            mat = "Headliner"
            if fc == "roof" and star:
                mat = "Starlight"
            self.part.quad(P[0], P[1], P[2], P[3], mat, normals=nn, outward=nn[0] + nn[2])

    # --------------------------------------------------------------
    # Armaturenbrett
    # --------------------------------------------------------------
    def dash(self):
        I, b, cg = self.I, self.b, self.cg
        p = self.part
        D = I.get("dash", {})
        z_face = self.zws - D.get("depth", 0.50)            # Hinterkante (Fahrerseite)
        self.z_face = z_face
        z_front = self.zws + 0.02
        xi = min(self.x_in(z_face), self.x_in(z_front)) + 0.01
        nx = 30
        xs = np.linspace(-xi, xi, nx)
        profiles = []
        tops = []
        for x in xs:
            # Höhe unter der Scheibe
            y_glass_face = cg.glass_y(z_face, x) - D.get("clear", 0.06)
            y_glass_front = cg.glass_y(z_front - 0.05, x) - 0.02
            hump = math.exp(-((x - 0.33) / 0.16) ** 2) * D.get("binnacle", 0.035)
            stack = math.exp(-(x / 0.18) ** 2) * D.get("stack", 0.06)
            ytop = min(y_glass_face + hump, b.params_at(z_face)["yt"] + D.get("height", 0.20))
            ytop = min(ytop, y_glass_face + hump)
            yfront = min(y_glass_front, ytop)
            zf2 = z_face - stack
            knee = self.floor + D.get("knee", 0.42)
            prof = [(z_front, yfront - 0.005), ((z_front + zf2) / 2, (yfront + ytop) / 2 + 0.01), (zf2 + 0.03, ytop),
                    (zf2, ytop - 0.03), (zf2 - 0.01, ytop - 0.16), (zf2 + 0.05, knee + 0.05), (zf2 + 0.12, knee),
                    (self.fw - 0.02, knee - 0.02)]
            chain = round_open(prof, [0, 0.05, 0.03, 0.03, 0.04, 0.05, 0.02, 0], 3)
            chain = resample(chain, 22)
            profiles.append([np.array([x, y, z]) for (z, y) in chain])
            tops.append((x, ytop, zf2))
        tmp = Part("dash")
        upper = D.get("upper", "Dash")
        trim_j = (11, 13)
        tmp.loft(profiles, lambda k, j: "InteriorTrim" if trim_j[0] <= j < trim_j[1] else (upper if j < 9 else "InteriorPlastic"),
                 closed=False, smooth=True, caps=("Dash", "Dash"),
                 hint_fn=lambda k: np.array([xs[k], self.floor + D.get("knee", 0.42) + 0.12, z_face + 0.22]))
        p.merge(tmp)
        self.dash_top = {round(x, 3): (y, z) for (x, y, z) in tops}

        def face_at(x):
            # Punkt auf der Dash-Rückseite bei x (Höhe ~ Instrumente)
            i = int(np.argmin(np.abs(xs - x)))
            prof = profiles[i]
            return prof, tops[i]

        # Ambiente-Leiste entlang der Dash-Kante
        prof_l, _ = face_at(-xi + 0.05)
        pts = []
        for x in np.linspace(-xi + 0.06, xi - 0.06, 24):
            i = int(np.argmin(np.abs(xs - x)))
            q = profiles[i][9]
            pts.append(q + np.array([0, 0, -0.004]))
        for a_, b_ in zip(pts[:-1], pts[1:]):
            p.box((a_ + b_) / 2, (np.linalg.norm(b_ - a_) + 0.002, 0.005, 0.006), "InteriorAmbient")
        # Instrumente
        gx = 0.33
        prof, (_, ytop, zf2) = face_at(gx)
        cl = I.get("cluster", {"type": "digital", "w": 0.30, "h": 0.12})
        self.cluster_type = cl["type"]
        cw, chh = cl.get("w", 0.30), cl.get("h", 0.12)
        cy = ytop - 0.03 - chh / 2
        cz = zf2 - 0.012
        # Hutze über den Instrumenten
        hood = Part("hood")
        secs = []
        for t in np.linspace(-1, 1, 9):
            x = gx + t * (cw / 2 + 0.03)
            hgt = 0.035 * (1 - t * t) ** 0.5 + 0.006
            secs.append([np.array([x, ytop - 0.006, zf2 + 0.06]), np.array([x, ytop + hgt, zf2 + 0.04]),
                         np.array([x, ytop + hgt * 0.9, zf2 - 0.03]), np.array([x, ytop - 0.004, zf2 - 0.05])])
        hood.loft(secs, lambda k, j: "Dash", closed=False, smooth=True,
                  hint_fn=lambda k: np.array([gx, ytop - 0.5, zf2]))
        p.merge(hood)
        p.merge(hood, flip=True)
        if cl["type"] == "analog":
            p.rbox((gx, cy, cz + 0.006), (cw + 0.02, chh + 0.02, 0.012), 0.02, "InteriorTrim2", segs=2)
            p.tex_quad((gx, cy, cz - 0.0005), (-1, 0, 0), (0, 1, 0), cw, chh, "Display_Cluster")
            dial_r = chh * 0.43
            for name, dx in (("Needle_Speed", 0.25), ("Needle_RPM", -0.25)):
                npart = Part(name)
                ang = math.radians(225)
                vec = np.array([-math.cos(ang), math.sin(ang), 0.0])
                L = dial_r * 0.92
                npart.box(vec * L * 0.42 + np.array([0, 0, -0.002]), (0.004, L, 0.002), "Needle",
                          rot=(0, 0, math.atan2(vec[1], vec[0]) - math.pi / 2))
                npart.lathe([(-0.004, 0.0), (-0.004, 0.009), (0.0, 0.009), (0.0, 0.0)], 12, "InteriorPlastic",
                            center=(0, 0, -0.002), axis="z", inside=(-0.002, 0.004))
                self.nodes[name] = (npart, (gx + dx * cw, cy, cz - 0.003), None)
            # Glas vor den Uhren
            p.tex_quad((gx, cy, cz - 0.012), (-1, 0, 0), (0, 1, 0), cw + 0.01, chh + 0.01, "LampGlass")
        else:
            p.rbox((gx, cy, cz + 0.008), (cw + 0.016, chh + 0.016, 0.012), 0.01, "DisplayGlass", segs=2)
            p.tex_quad((gx, cy, cz - 0.0005), (-1, 0, 0), (0, 1, 0), cw, chh, "Display_Cluster")
        self.anchors["cluster"] = (gx, cy, cz)
        # Mittel-Display
        ce = I.get("center", {"type": "dash", "w": 0.26, "h": 0.15})
        prof_c, (_, ytop_c, zf2_c) = face_at(0.0)
        if ce["type"] == "floating":
            w_, h_ = ce.get("w", 0.36), ce.get("h", 0.20)
            ccy = ytop_c + h_ / 2 - 0.02
            ccz = zf2_c - 0.02
            p.rbox((0, ccy, ccz + 0.008), (w_ + 0.014, h_ + 0.014, 0.014), 0.012, "DisplayGlass", segs=2)
            p.tex_quad((0, ccy, ccz), (-1, 0, 0), (0, 1, 0), w_, h_, "Display_Center")
            p.box((0, ytop_c - 0.005, ccz + 0.03), (0.05, 0.05, 0.03), "Aluminum")
        elif ce["type"] == "retro":
            w_, h_ = ce.get("w", 0.18), ce.get("h", 0.06)
            ccy = ytop_c - 0.07
            ccz = zf2_c - 0.004
            p.rbox((0, ccy, ccz + 0.006), (w_ + 0.05, h_ + 0.04, 0.012), 0.008, "Chrome", segs=2)
            p.tex_quad((0, ccy, ccz - 0.001), (-1, 0, 0), (0, 1, 0), w_, h_, "Display_Center")
            for k in (-1, 1):
                p.lathe([(0.0, 0.0), (0.0, 0.012), (-0.012, 0.011), (-0.014, 0.0)], 14, "Chrome",
                        center=(k * (w_ / 2 + 0.03), ccy, ccz - 0.006), axis="z", inside=(-0.006, 0.004))
        else:
            w_, h_ = ce.get("w", 0.26), ce.get("h", 0.15)
            ccy = ytop_c - 0.03 - h_ / 2
            ccz = zf2_c - 0.006
            p.rbox((0, ccy, ccz + 0.006), (w_ + 0.014, h_ + 0.014, 0.012), 0.01, "DisplayGlass", segs=2)
            p.tex_quad((0, ccy, ccz - 0.0005), (-1, 0, 0), (0, 1, 0), w_, h_, "Display_Center")
        self.anchors["center"] = (0.0, ccy, ccz)
        # Lüftungsdüsen
        for vx in I.get("vents", (0.19, -0.19, 0.62, -0.62)):
            if abs(vx) > xi - 0.06:
                continue
            prof_v, (_, ytop_v, zf2_v) = face_at(vx)
            vy = ytop_v - 0.05
            vz = zf2_v - 0.004
            p.rbox((vx, vy, vz + 0.004), (0.11, 0.045, 0.01), 0.012, "InteriorTrim2", segs=2)
            for k in range(4):
                p.box((vx, vy - 0.015 + k * 0.01, vz - 0.004), (0.09, 0.003, 0.012), "Aluminum")
        # Handschuhfach-Fuge und Startknopf
        prof_g, (_, ytop_g, zf2_g) = face_at(-0.36)
        p.box((-0.36, ytop_g - 0.17, zf2_g - 0.003), (0.30, 0.003, 0.004), "Gap")
        p.lathe([(0.0, 0.0), (0.0, 0.014), (-0.006, 0.013), (-0.008, 0.0)], 16, "StartButton",
                center=(0.13, ytop_c - 0.20, zf2_c - 0.004), axis="z", inside=(-0.004, 0.006))

    # --------------------------------------------------------------
    # Lenkrad
    # --------------------------------------------------------------
    def steering(self):
        I = self.I
        W = I.get("wheel", {})
        gx, cy, cz = self.anchors["cluster"]
        r = W.get("r", 0.185)
        tilt = math.radians(W.get("tilt", 22))
        zc = cz - W.get("dist", 0.24)
        yc = cy - W.get("drop", 0.12)
        style = W.get("style", "round")
        sw = Part("SteeringWheel")
        # Kranz als Rohr entlang eines 2D-Pfads (lokal: x rechts, y oben, z nach vorne)
        path = []
        n = 48
        for k in range(n + 1):
            a = 2 * math.pi * k / n
            x, y = r * math.cos(a), r * math.sin(a)
            if style in ("flat", "yoke") and y < -r * 0.78:
                y = -r * 0.78
            if style == "yoke":
                x = math.copysign(min(abs(x), r * 0.92), x)
                if y > r * 0.55:
                    continue
            path.append(np.array([x, y, 0.0]))
        if style == "yoke":
            path = path + [path[0]]
        grip_r = W.get("grip", 0.016)
        prof = [(grip_r * 1.1 * math.cos(2 * math.pi * k / 10), grip_r * math.sin(2 * math.pi * k / 10)) for k in range(10)]
        tmp = Part("rim")
        tmp.sweep(path, prof, "SteeringGrip", up=(0, 0, 1), caps=(style == "yoke"))
        sw.merge(tmp)
        # obere Markierung
        if W.get("marker", True) and style != "yoke":
            sw.box((0, r - 0.002, 0.0), (0.02, 0.026, 0.038), W.get("marker_mat", "MarkerRed"))
        # Speichen
        for a in (0.0, math.pi, -math.pi / 2):
            if a == -math.pi / 2 and W.get("spokes", 3) == 2:
                continue
            p0 = np.array([0.045 * math.cos(a), 0.045 * math.sin(a), 0.012])
            p1 = np.array([(r - 0.012) * math.cos(a), (r - 0.012) * math.sin(a), 0.0])
            if a == -math.pi / 2 and style in ("flat", "yoke"):
                p1 = np.array([0.0, -r * 0.76, 0.0])
            wsp = 0.05 if a != -math.pi / 2 else 0.04
            secs = []
            for t in np.linspace(0, 1, 5):
                c = p0 + (p1 - p0) * t
                d = norm(p1 - p0)
                side = norm(np.cross(d, np.array([0, 0, 1.0])))
                ww = wsp * (1 - 0.35 * t)
                secs.append([c + side * u + np.array([0, 0, 1.0]) * v for (u, v) in round_rect(ww, 0.022, 0.009, 2)])
            sw.loft(secs, lambda k, j: W.get("spoke_mat", "InteriorPlastic"), caps=(None, None), smooth=True)
        # Prallplatte mit Logo
        sw.rbox((0, 0, 0.02), (0.13, 0.11, 0.05), 0.035, "SteeringLeather", segs=3)
        sw.lathe([(-0.0055, 0.0), (-0.0055, 0.024)], 24, "CenterCap", center=(0, 0, 0), axis="z",
                 inside=(0.01, 0.01), uv_mode="polar", polar_r=0.024)
        # Fix: Logo-Scheibe vor die Prallplatte setzen
        # Tasten
        for x in (-0.085, 0.085):
            for k in range(3):
                sw.box((x, 0.012 - k * 0.016, -0.004), (0.016, 0.01, 0.006), "ButtonGlow")
        # Schaltwippen
        if W.get("paddles", False):
            for x in (-1, 1):
                sw.rbox((x * 0.11, 0.02, 0.05), (0.07, 0.11, 0.008), 0.02, "Aluminum", segs=2)
        # Lenksäule + Verkleidung (fest)
        dirv = np.array([0.0, -math.sin(tilt), math.cos(tilt)])
        q = np.array([math.sin(tilt / 2), 0.0, 0.0, math.cos(tilt / 2)])
        center = np.array([gx, yc, zc])
        self.nodes["SteeringWheel"] = (sw, tuple(center), tuple(q))
        col0 = center + dirv * 0.06
        col1 = center + dirv * 0.28
        self.part.tube([col0, col1], 0.024, "InteriorPlastic", segs=12)
        Mrot = rot_matrix(tilt, 0, 0)
        self.part.rbox(center + dirv * 0.16, (0.11, 0.09, 0.2), 0.035, "InteriorPlastic", M=Mrot, segs=3)
        for sx in (1, -1):
            a0 = center + dirv * 0.1 + np.array([sx * 0.05, 0.01, 0])
            a1 = a0 + np.array([sx * 0.11, 0.012, -0.02])
            self.part.tube([a0, a1], 0.006, "InteriorPlastic", segs=6)
        self.anchors["wheel"] = tuple(center)
        # Augpunkt (Cockpit-Kamera): hinter dem Lenkrad
        ez = zc - I.get("eye_dist", 0.62)
        ey = min(self.cg.roof(ez) - I.get("head_clear", 0.12), yc + I.get("eye_up", 0.30))
        self.eye = (gx, ey, ez)

    # --------------------------------------------------------------
    def pedals(self):
        I = self.I
        z_toe = self.fw - 0.24
        fl = self.floor
        gx = self.anchors["wheel"][0]
        zp = z_toe + 0.02
        for name, dx, w_, h_ in (("Pedal_Brake", 0.05, 0.075, 0.07), ("Pedal_Throttle", -0.09, 0.05, 0.13)):
            pp = Part(name)
            top = np.array([0.0, 0.0, 0.0])
            arm_end = np.array([0.0, -0.20, -0.04])
            pp.tube([top, arm_end], 0.008, "InteriorPlastic", segs=6)
            pp.rbox(arm_end + np.array([0, -h_ / 2 + 0.02, -0.006]), (w_, h_, 0.012), 0.01, "Pedal", segs=2)
            for k in range(3):
                pp.box(arm_end + np.array([0, -h_ / 2 + 0.02 - h_ * 0.3 + k * h_ * 0.3, -0.0135]), (w_ * 0.8, 0.006, 0.003),
                       "PedalRubber")
            self.nodes[name] = (pp, (gx + dx, fl + 0.36, zp), None)
        # Fußstütze
        self.part.rbox((gx + 0.18, fl + 0.1, z_toe + 0.03), (0.07, 0.16, 0.012), 0.008, "Pedal",
                       M=rot_matrix(-0.7, 0, 0), segs=2)

    # --------------------------------------------------------------
    def console(self):
        I = self.I
        p = self.part
        C = I.get("console", {})
        fl = self.floor
        tunnel = I.get("tunnel", 0.13)
        z0 = self.z_face - 0.02
        z1 = self.hz - C.get("back", 0.25)
        yb_ = fl + tunnel
        h0 = C.get("h_front", 0.30)
        h1 = C.get("h_back", 0.22)
        w_ = C.get("w", 0.21)
        secs = []
        for t in np.linspace(0, 1, 12):
            z = z0 + (z1 - z0) * t
            hh = h0 + (h1 - h0) * t
            secs.append([np.array([x, yb_ + y, z]) for (x, y) in
                         round_open([(w_ / 2, 0.0), (w_ / 2, hh), (-w_ / 2, hh), (-w_ / 2, 0.0)], [0, 0.03, 0.03, 0], 3)])
        tmp = Part("console")
        tmp.loft(secs, lambda k, j: "InteriorTrim" if 3 <= j < 6 else "Dash", closed=False, smooth=True,
                 caps=("Dash", "Dash"), hint_fn=lambda k: np.array([0.0, yb_ - 0.5, z0 + (z1 - z0) * k / 11]))
        p.merge(tmp)
        top = lambda t: yb_ + h0 + (h1 - h0) * t
        # Wählhebel
        t_s = C.get("shifter_t", 0.35)
        zs = z0 + (z1 - z0) * t_s
        ys = top(t_s)
        st = C.get("shifter", "sport")
        if st == "sport":
            p.tube([np.array([0, ys, zs]), np.array([0, ys + 0.09, zs - 0.01])], 0.009, "InteriorPlastic", segs=8)
            p.sphere((0, ys + 0.105, zs - 0.012), 0.026, C.get("knob", "Aluminum"), segs=16, rings=10, scale=(1, 0.85, 1.15))
            p.lathe([(ys + 0.001, 0.0), (ys + 0.001, 0.04), (ys + 0.012, 0.03), (ys + 0.02, 0.012)], 16, "SteeringLeather",
                    center=(0, 0, zs), axis="y", inside=(ys + 0.005, 0.0))
        elif st == "t_handle":
            p.tube([np.array([0, ys, zs]), np.array([0, ys + 0.14, zs - 0.02])], 0.008, "Chrome", segs=8)
            p.rbox((0, ys + 0.15, zs - 0.02), (0.1, 0.03, 0.035), 0.012, "InteriorTrim", segs=2)
            p.lathe([(ys + 0.001, 0.0), (ys + 0.001, 0.05), (ys + 0.03, 0.02)], 16, "Rubber",
                    center=(0, 0, zs), axis="y", inside=(ys + 0.01, 0.0))
        elif st == "dial":
            p.lathe([(ys, 0.0), (ys, 0.035), (ys + 0.025, 0.033), (ys + 0.026, 0.0)], 24, "Aluminum",
                    center=(0, 0, zs), axis="y", inside=(ys + 0.01, 0.01))
        elif st == "buttons":
            for k, x in enumerate((-0.05, 0.0, 0.05)):
                p.rbox((x, ys + 0.006, zs), (0.035, 0.012, 0.025), 0.006, "ButtonGlow" if k == 1 else "DisplayGlass", segs=2)
        # Getränkehalter
        tc = min(0.85, t_s + 0.3)
        zc = z0 + (z1 - z0) * tc
        for x in (0.045, -0.045):
            p.lathe([(top(tc) + 0.001, 0.036), (top(tc) - 0.06, 0.034), (top(tc) - 0.06, 0.0)], 16, "InteriorPlastic",
                    center=(x, 0, zc), axis="y", inside=(top(tc) + 0.2, 0.0))
        self.anchors["cup"] = (0.045, top(tc) - 0.055, zc)
        # Armlehne
        p.rbox((0, top(1.0) + 0.03, z1 + 0.12), (w_ - 0.01, 0.05, 0.26), 0.022, "Seat", segs=3)
        self.anchors["console_top"] = (0.0, top(t_s + 0.15), z0 + (z1 - z0) * (t_s + 0.15))

    # --------------------------------------------------------------
    # Sitze
    # --------------------------------------------------------------
    def seat(self, x, z, kind="bucket", recline=18.0, width=0.52, back_h=None, rear=False, headrest=True):
        """Sitz in Fahrtrichtung: gepolsterte Sitzfläche und Lehne als geschlossene Körper
        mit Seitenwangen, Mittelbahn (SeatInsert), Ziernähten und Rückschale.

        kind: bucket (Schalensitz, Kopfstütze integriert, Carbon-Rückschale),
              sport (Sportsitz, integrierte Kopfstütze, Leder-Rückschale),
              comfort (Komfortsitz, flache Wangen, Kopfstütze auf Stangen)."""
        p = self.part
        I = self.I
        fl = self.floor
        bucket = kind in ("bucket", "sport")
        cushion_h = I.get("cushion_h", 0.12 if bucket else 0.22)
        if rear:
            cushion_h = I.get("rear_cushion_h", cushion_h + 0.02)
        W = width
        bb = 0.07 if kind == "bucket" else 0.05 if kind == "sport" else 0.025       # Wangenhöhe
        bw = 0.09 if bucket else 0.075                                              # Wangenbreite
        yc = fl + cushion_h
        y0 = fl + 0.045
        L = 0.50 if not rear else 0.47
        zf, zb = z + L / 2, z - L / 2
        M = 12 * 4                      # 12 Eckpunkte x (3 + 1) Rundungspunkte

        def cushion_section(t):
            yct = yc + 0.028 * (1 - t) ** 2 - 0.012 * t
            bbt = bb * (0.55 + 0.45 * math.sin(math.pi * min(1.0, t * 1.2)))
            Wt = W * (1 - 0.05 * (1 - t) ** 2)
            h2 = Wt / 2
            pts = [(-h2 + 0.02, y0), (h2 - 0.02, y0), (h2, y0 + 0.04), (h2, yct + bbt * 0.55),
                   (h2 - bw * 0.45, yct + bbt), (h2 - bw, yct + 0.012), (h2 - bw - 0.03, yct),
                   (-(h2 - bw - 0.03), yct), (-(h2 - bw), yct + 0.012), (-(h2 - bw * 0.45), yct + bbt),
                   (-h2, yct + bbt * 0.55), (-h2, y0 + 0.04)]
            rad = [0.015, 0.015, 0.03, 0.035, 0.03, 0.03, 0.02, 0.02, 0.03, 0.03, 0.035, 0.03]
            return round_poly(pts, rad, 3), yct, h2         # feste Punktzuordnung je Ecke (kein Verdrehen)

        # Sitzfläche: Schnitte von vorne nach hinten, vorne gerundet
        secs, uvs = [], []
        r_front = 0.035
        ts = list(np.linspace(0, 1, 10))
        prof0, yc0, h20 = cushion_section(0.0)
        c0 = np.mean(np.array(prof0), axis=0)
        for a in np.linspace(math.pi / 2, 0, 4)[:-1]:        # Rundung der Vorderkante
            sc = 0.55 + 0.45 * math.cos(a)
            zz = zf + r_front * math.sin(a)
            secs.append([np.array([x + c0[0] + (u - c0[0]) * sc, c0[1] + (v - c0[1]) * sc, zz]) for (u, v) in prof0])
        for t in ts:
            prof, _yct, _h2 = cushion_section(t)
            zz = zf + (zb - zf) * t
            secs.append([np.array([x + u, v, zz]) for (u, v) in prof])
        mid = cushion_section(0.5)
        ins = []
        for j in range(M):
            (u0, v0), (u1, v1) = mid[0][j], mid[0][(j + 1) % M]
            um, vm = (u0 + u1) / 2, (v0 + v1) / 2
            ins.append(abs(um) < mid[2] - bw - 0.012 and vm > mid[1] - 0.01)
        tmp = Part("cushion")
        tmp.loft(secs, lambda k, j: "SeatInsert" if ins[j] else "Seat", closed=True, smooth=True,
                 caps=("Seat", "Seat"))
        p.merge(tmp)
        # Nähte entlang der Mittelbahn
        jb = [j for j in range(M) if ins[j] != ins[j - 1]]
        for j0 in jb:
            pts = [secs[k][j0] for k in range(3, len(secs) - 1)]
            stitch_line(p, pts, (0, 1, 0), width=0.0035, offset=0.002)
        # Querteilung (Steppung) der Mittelbahn
        if bucket:
            for k in (6, 9):
                row = [secs[k][j] for j in range(M) if ins[j] or ins[j - 1]]
                if len(row) > 2:
                    stitch_line(p, row, (0, 1, 0), width=0.003, offset=0.002)

        # Lehne
        rec = math.radians(recline)
        up = np.array([0.0, math.cos(rec), -math.sin(rec)])
        fwd = np.array([0.0, math.sin(rec), math.cos(rec)])
        base = np.array([x, yc - 0.02, zb + 0.07])
        H = back_h or I.get("back_h", 0.66 if bucket else 0.58)
        integrated = bucket
        T = 0.07 if kind == "bucket" else 0.08                    # Dicke hinter der Polsterfläche
        wing = 0.11 if kind == "bucket" else 0.07 if kind == "sport" else 0.035

        def back_width(h):
            f = h / H
            if not integrated:
                return W * (0.98 - 0.08 * f)
            if f < 0.62:
                return W * (1.0 - 0.06 * f)
            if f < 0.76:                                         # Schulter -> Kopfstütze
                s_ = (f - 0.62) / 0.14
                return W * ((1.0 - 0.06 * 0.62) * (1 - s_) + 0.54 * s_)
            return W * 0.54

        def wing_depth(h):
            f = h / H
            if integrated and f > 0.76:
                return wing * 0.25
            return wing * (0.75 + 0.25 * math.sin(math.pi * min(1.0, f / 0.7)))

        def back_section(h):
            w2 = back_width(h) / 2
            wd = wing_depth(h)
            bwi = min(bw, w2 * 0.38)
            db = min(0.03, 0.55 * wd)                 # Wangen-Ansatz bleibt immer unter der Wangenspitze
            pts = [(-w2 + 0.03, -T), (w2 - 0.03, -T), (w2, -T + 0.03), (w2, wd - 0.03), (w2 - 0.025, wd),
                   (w2 - bwi, db), (w2 - bwi - 0.03, 0.0), (-(w2 - bwi - 0.03), 0.0), (-(w2 - bwi), db),
                   (-(w2 - 0.025), wd), (-w2, wd - 0.03), (-w2, -T + 0.03)]
            rad = [0.03, 0.03, 0.03, 0.03, 0.025, 0.035, 0.02, 0.02, 0.035, 0.025, 0.03, 0.03]
            return round_poly(pts, rad, 3), w2, bwi

        shell = I.get("seat_shell", "Carbon" if kind == "bucket" else "Seat")
        hs = list(np.linspace(0.0, H, 14))
        bsecs = []
        for h in hs:
            prof, w2, bwi = back_section(h)
            c = base + up * h
            bsecs.append([c + np.array([u, 0, 0]) + fwd * d for (u, d) in prof])
        # obere Rundung
        prof_t, w2t, _ = back_section(H)
        ct = np.mean(np.array(prof_t), axis=0)
        for a in np.linspace(0, math.pi / 2, 4)[1:]:
            sc = 0.45 + 0.55 * math.cos(a)
            hh = H + 0.045 * math.sin(a)
            c = base + up * hh
            bsecs.append([c + np.array([ct[0] + (u - ct[0]) * sc, 0, 0]) + fwd * (ct[1] + (d - ct[1]) * sc)
                          for (u, d) in prof_t])
        midb, w2m, bwm = back_section(H * 0.4)
        cls = []
        for j in range(M):
            (u0, d0), (u1, d1) = midb[j], midb[(j + 1) % M]
            um, dm = (u0 + u1) / 2, (d0 + d1) / 2
            if dm < -T + 0.012:
                cls.append("back")
            elif abs(um) < w2m - bwm - 0.012 and dm > -0.01:
                cls.append("insert")
            else:
                cls.append("side")
        n_ins = len(hs) - (4 if integrated else 2)
        tmp = Part("back")
        tmp.loft(bsecs, lambda k, j: (shell if cls[j] == "back" else
                                      "SeatInsert" if (cls[j] == "insert" and k < n_ins) else "Seat"),
                 closed=True, smooth=True, caps=(shell, None))
        p.merge(tmp)
        jb = [j for j in range(M) if (cls[j] == "insert") != (cls[j - 1] == "insert")]
        for j0 in jb:
            pts = [bsecs[k][j0] for k in range(1, n_ins)]
            stitch_line(p, pts, fwd, width=0.0035, offset=0.002)
        if bucket:
            for k in (4, 7):
                row = [bsecs[k][j] for j in range(M) if cls[j] == "insert" or cls[j - 1] == "insert"]
                if len(row) > 2:
                    stitch_line(p, row, fwd, width=0.003, offset=0.002)
        top = base + up * H
        if integrated:
            # Gurtdurchführungen zwischen Schulter und Kopfstütze
            hb = H * 0.69
            cb = base + up * hb
            wbelt = back_width(hb) / 2 - 0.05
            for sx in (-1, 1):
                p.box(cb + np.array([sx * wbelt, 0, 0]) + fwd * 0.012, (0.05, 0.022, 0.03), "Gap",
                      M=rot_matrix(-rec, 0, 0))
            # Logo/Prägung in der Kopfstütze
            p.tex_quad(base + up * (H * 0.88) + fwd * 0.0045, (-1, 0, 0), up, 0.07, 0.07, "Badge")
        elif headrest:
            # Kopfstütze auf Stangen
            hr = top + up * 0.13 + fwd * 0.015
            p.rbox(hr, (0.27, 0.16, 0.10), 0.045, "Seat", M=rot_matrix(-rec, 0, 0), segs=3)
            for sx in (-1, 1):
                p.tube([top - up * 0.03 + np.array([sx * 0.075, 0, 0]), hr - up * 0.05 + np.array([sx * 0.075, 0, 0])],
                       0.0065, "Chrome", segs=8)
        # Sockel, Schienen, Hebel
        p.rbox((x, fl + 0.03, z), (W * 0.62, 0.05, L * 0.78), 0.012, "InteriorPlastic", segs=2)
        for sx in (-1, 1):
            p.box((x + sx * W * 0.28, fl + 0.008, z + 0.02), (0.03, 0.016, L * 0.95), "Aluminum")
        side = 1 if x > 0 else -1
        p.rbox((x + side * (W / 2 + 0.008), y0 + 0.03, z + 0.08), (0.012, 0.03, 0.10), 0.008, "InteriorPlastic", segs=2)
        return {"top": top, "base": base, "up": up, "fwd": fwd, "H": H, "z_back": zb}

    def seats(self):
        I = self.I
        kind = I.get("seat_kind", "bucket")
        self.seat_info = {}
        for sx, name in ((1, "driver"), (-1, "passenger")):
            self.seat_info[name] = self.seat(sx * self.seat_x, self.hz, kind, I.get("recline", 18))
        rear = I.get("rear")
        if rear:
            zr_ = rear["z"]
            if rear.get("type") == "bench":
                for sx in (1, 0, -1):
                    w_ = 0.42 if sx != 0 else 0.34
                    self.seat(sx * 0.4, zr_, "comfort", rear.get("recline", 24), width=w_, back_h=rear.get("back_h", 0.5),
                              rear=True, headrest=rear.get("headrest", sx != 0))
            else:
                for sx, name in ((1, "rear_l"), (-1, "rear_r")):
                    self.seat_info[name] = self.seat(sx * rear.get("x", 0.36), zr_, rear.get("kind", "comfort"),
                                                     rear.get("recline", 26), width=rear.get("w", 0.54),
                                                     back_h=rear.get("back_h", 0.56), rear=True,
                                                     headrest=rear.get("headrest", True))
                if rear.get("console"):
                    self.part.rbox((0, self.floor + 0.3, zr_ + 0.05), (0.2, 0.18, 0.5), 0.03, "Seat", segs=3)
                    self.part.rbox((0, self.floor + 0.395, zr_ + 0.05), (0.12, 0.012, 0.3), 0.004, "InteriorTrim", segs=2)
        # Bildschirme an den Rückseiten der Vordersitze
        if I.get("rear_screens"):
            for name in ("driver", "passenger"):
                si = self.seat_info[name]
                c = si["base"] + si["up"] * (si["H"] * 0.72) - si["fwd"] * 0.135
                right = np.array([-1.0, 0, 0])
                upv = si["up"]
                self.part.rbox(c - si["fwd"] * 0.004, (0.26, 0.17, 0.012), 0.012, "DisplayGlass",
                               M=rot_matrix(-math.radians(I.get("recline", 18)), 0, 0), segs=2)
                self.part.tex_quad(c - si["fwd"] * 0.012, right, upv, 0.24, 0.15, "Display_Rear")
        si = self.seat_info["passenger"]
        self.anchors["seat_pass"] = tuple(np.array([-self.seat_x, self.floor + self.I.get("cushion_h", 0.16) + 0.04,
                                                    self.hz + 0.08]))
        if rear:
            self.anchors["rear_seat"] = (0.0, self.floor + I.get("rear_cushion_h", 0.2) + 0.04, rear["z"] + 0.08)

    # --------------------------------------------------------------
    def doors(self):
        """Armlehnen, Griffe, Lautsprecher, Fensterheberschalter an den Seitenwänden."""
        p = self.part
        fl = self.floor
        for door in self.sp.get("gaps", {}).get("doors", []):
            zf_, zr_ = door["z"]
            zm = (zf_ + zr_) / 2
            for side in (1, -1):
                xi = self.x_in(zm)
                yc, xc = self.y_cut(zm)
                # Armlehne
                p.rbox((side * (xi - 0.05), yc - 0.2, zm - 0.03), (0.09, 0.05, (zf_ - zr_) * 0.55), 0.02, "Seat", segs=3)
                # Zierleiste
                p.rbox((side * (xi - 0.012), yc - 0.11, zm), (0.012, 0.035, (zf_ - zr_) * 0.75), 0.006, "InteriorTrim", segs=2)
                # Ambiente-Licht über der Zierleiste
                p.box((side * (xi - 0.019), yc - 0.088, zm), (0.004, 0.005, (zf_ - zr_) * 0.72), "InteriorAmbient")
                # Türöffner
                p.rbox((side * (xi - 0.016), yc - 0.07, zf_ - 0.16), (0.012, 0.025, 0.09), 0.008, "Chrome", segs=2)
                # Lautsprecher
                sc = (side * (xi - 0.004), fl + 0.17, zf_ - 0.18)
                p.lathe([(0.0, 0.0), (0.0, 0.07)], 24, "Speaker", center=sc, axis="x",
                        inside=(-side * 0.01, 0.03), uv_mode="polar", polar_r=0.07)
                p.lathe([(0.0, 0.07), (side * 0.006, 0.074), (side * 0.004, 0.08)], 24, "Aluminum", center=sc, axis="x",
                        inside=(-side * 0.01, 0.075))
                # Fensterheber-Schalter (Fahrertür)
                for k in range(2):
                    p.box((side * (xi - 0.065), yc - 0.172, zm + 0.05 - k * 0.03), (0.018, 0.008, 0.018), "ButtonGlow")

    # --------------------------------------------------------------
    def belts(self):
        """Sicherheitsgurte hängen an der B-Säule (Gurtband als flacher Streifen)."""
        p = self.part
        cg = self.cg
        for name in ("driver", "passenger"):
            si = self.seat_info[name]
            side = 1 if name == "driver" else -1
            zb = si["z_back"] - 0.06
            ya = cg.roof(zb) - 0.16
            xa = cg.glass_x(zb, ya) - 0.05
            anchor = np.array([side * xa, ya, zb])
            shoulder = si["top"] + np.array([side * 0.2, -0.12, 0.05])
            lap = np.array([side * (self.x_in(zb) - 0.04), self.floor + 0.18, zb + 0.12])
            path = [anchor, anchor * 0.6 + shoulder * 0.4, shoulder, lap]
            prof = [(-0.024, -0.002), (0.024, -0.002), (0.024, 0.002), (-0.024, 0.002)]
            tmp = Part("belt")
            tmp.sweep(path, prof, "Belt", up=(1, 0, 0), caps=False, smooth=True)
            p.merge(tmp)
            p.rbox(anchor, (0.03, 0.06, 0.05), 0.01, "InteriorPlastic", segs=2)
            # Gurtschloss neben dem Sitz
            p.rbox((side * (self.seat_x - 0.29), self.floor + 0.22, si["z_back"] + 0.25), (0.03, 0.08, 0.04), 0.01,
                   "InteriorPlastic", segs=2)
            p.box((side * (self.seat_x - 0.29), self.floor + 0.265, si["z_back"] + 0.25), (0.02, 0.01, 0.025), "BeltMetal")

    # --------------------------------------------------------------
    def mirror_visors(self):
        p = self.part
        cg = self.cg
        cab = sorted(self.sp["cabin"], key=lambda c: -c["z"])
        z_head = cab[1]["z"] + 0.02           # Oberkante Frontscheibe
        y_head = cg.roof(z_head)
        # Innenspiegel
        mz = z_head - 0.06
        my = y_head - 0.1
        p.tube([np.array([0, y_head - 0.02, z_head - 0.02]), np.array([0, my + 0.03, mz])], 0.008, "InteriorPlastic", segs=6)
        p.rbox((0, my, mz), (0.25, 0.065, 0.03), 0.02, "InteriorPlastic", segs=3)
        p.rbox((0, my, mz - 0.016), (0.235, 0.052, 0.003), 0.016, "Mirror", segs=3)
        self.anchors["mirror"] = (0.0, my - 0.035, mz)
        # Sonnenblenden
        vz = z_head - 0.13
        for sx in (1, -1):
            vy = cg.glass_y(vz, sx * 0.3) - 0.035
            p.rbox((sx * 0.3, vy, vz), (0.34, 0.016, 0.15), 0.02, "Headliner", segs=2)
        # Deckenleuchte
        dz = cg.zs[len(cg.zs) // 2]
        dy = cg.roof(dz) - 0.03
        p.rbox((0, dy, dz), (0.16, 0.018, 0.08), 0.01, "InteriorPlastic", segs=2)
        p.rbox((0, dy - 0.009, dz), (0.12, 0.004, 0.05), 0.004, "DomeLight", segs=2)
        self.anchors["visor"] = (0.3, cg.glass_y(vz, 0.3) - 0.035, vz)

    # --------------------------------------------------------------
    # Überrollkäfig (Tuning)
    # --------------------------------------------------------------
    def cage(self, level=1):
        """level 1: Halbkäfig (Bügel, Diagonale, Streben nach hinten, Gurtbügel)
           level 2: Vollkäfig (zusätzlich A-Säulen-, Dach- und Türstreben)."""
        cg = self.cg
        p = Part("RollCage_%d" % level)
        r = 0.021
        fl = self.floor
        zh = self.seat_info["driver"]["z_back"] - 0.16
        # Hauptbügel entlang der Innenkontur
        pts = []
        roof_h = cg.roof(zh) - 0.05
        for t in np.linspace(0, 1, 12):
            y = fl + 0.02 + (roof_h - 0.06 - fl) * t
            xg = min(cg.glass_x(zh, y) - 0.055, self.x_in(zh) - 0.04)
            pts.append(np.array([xg, y, zh]))
        top_r = pts[-1]
        hoop = pts + [np.array([0.0, roof_h, zh])] + [np.array([-q[0], q[1], q[2]]) for q in reversed(pts)]
        p.tube(hoop, r, "Cage", segs=12, caps=True)
        # Diagonale
        p.tube([hoop[1], np.array([-top_r[0], top_r[1], zh])], r * 0.9, "Cage", segs=10)
        # Gurtbügel
        hb = fl + 0.6
        xg = min(cg.glass_x(zh, hb) - 0.055, self.x_in(zh) - 0.04)
        p.tube([np.array([xg, hb, zh]), np.array([-xg, hb, zh])], r * 0.85, "Cage", segs=10)
        # Streben nach hinten
        zr_ = max(self.rb + 0.08, zh - 0.7)
        for sx in (1, -1):
            a = np.array([sx * top_r[0], top_r[1], zh])
            bpt = np.array([sx * (self.x_in(zr_) - 0.06), fl + 0.15, zr_])
            p.tube([a, bpt], r * 0.85, "Cage", segs=10)
        if level >= 2:
            cab = sorted(self.sp["cabin"], key=lambda c: -c["z"])
            z_head = cab[1]["z"] - 0.04
            for sx in (1, -1):
                # Dachstrebe nach vorne und A-Säulen-Strebe nach unten
                path = []
                for t in np.linspace(0, 1, 8):
                    z = zh + (z_head - zh) * t
                    y = cg.roof(z) - 0.05
                    xg = cg.glass_x(z, y - 0.04) - 0.07
                    path.append(np.array([sx * xg, y - 0.04, z]))
                zf_ = self.z_face + 0.05
                for t in np.linspace(0.15, 1, 7):
                    z = z_head + (zf_ - z_head) * t
                    y = cg.glass_y(z, 0.5) - 0.06 - (cg.glass_y(z, 0.5) - fl - 0.1) * max(0.0, t - 0.6) * 1.8
                    y = max(y, fl + 0.12)
                    xg = min(cg.glass_x(z, y) - 0.07, self.x_in(z) - 0.05)
                    path.append(np.array([sx * xg, y, z]))
                p.tube(path, r, "Cage", segs=12)
                # Türkreuz
                xd = self.x_in((zh + zf_) / 2) - 0.06
                a = np.array([sx * xd, fl + 0.45, zh])
                b = np.array([sx * xd, fl + 0.2, zf_])
                c = np.array([sx * xd, fl + 0.2, zh])
                d = np.array([sx * xd, fl + 0.45, zf_])
                p.tube([a, b], r * 0.85, "Cage", segs=10)
                p.tube([c, d], r * 0.85, "Cage", segs=10)
            # Dachkreuz
            y0 = cg.roof(zh) - 0.09
            p.tube([np.array([top_r[0], y0, zh]), np.array([-top_r[0] * 0.8, cg.roof(z_head) - 0.09, z_head])], r * 0.85,
                   "Cage", segs=10)
        return p

    # --------------------------------------------------------------
    def lod1(self, body1=None):
        """Vereinfachter Innenraum für mittlere Entfernung (Silhouette, kein Durchblick).

        body1: Karosserie der LOD1-Stufe – Seitenwände und Dachhimmel folgen ihr,
        damit man durch die Scheiben nicht durch das Auto hindurchsieht."""
        p = Part("Interior_L1")
        fl = self.floor
        b1 = body1 or self.b
        zs = np.linspace(self.rb, self.fw, 6)
        for i in range(len(zs) - 1):
            xi = self.x_in((zs[i] + zs[i + 1]) / 2)
            p.quad((xi, fl, zs[i]), (-xi, fl, zs[i]), (-xi, fl, zs[i + 1]), (xi, fl, zs[i + 1]), "Carpet", outward=(0, 1, 0))
        # Seitenwände bis zur Schnittkante, Spritz- und Rückwand
        zo0, zo1 = b1.cabin_open_range()
        zw = np.linspace(max(self.rb, zo0 + 0.01), min(self.fw, zo1 - 0.01), 8)
        for side in (1, -1):
            for i in range(len(zw) - 1):
                za, zb = zw[i], zw[i + 1]
                Pa, _ = b1.point(za, b1.j_cut_r if side > 0 else b1.j_cut_l)
                Pb, _ = b1.point(zb, b1.j_cut_r if side > 0 else b1.j_cut_l)
                xa, xb = side * (self.x_in(za) + 0.02), side * (self.x_in(zb) + 0.02)
                p.quad((xa, fl, za), (xb, fl, zb), (Pb[0] - side * 0.01, Pb[1] - 0.005, zb),
                       (Pa[0] - side * 0.01, Pa[1] - 0.005, za), "Interior", outward=(-side, 0, 0))
        for z, out in ((self.fw, -1.0), (self.rb, 1.0)):
            xi = self.x_in(z)
            yt = b1.params_at(z)["yt"]
            p.quad((xi, fl, z), (-xi, fl, z), (-xi, yt, z), (xi, yt, z), "Interior", outward=(0, 0, out))
        # Dachhimmel/Säulen innen (aus dem LOD1-Glashaus)
        S, Nn, classes = b1.cab_S, b1.cab_N, b1.cab_classes
        m = S.shape[1]
        for (k, j), fc in classes.items():
            if fc in (None, "glass"):
                continue
            j2 = (j + 1) % m
            d = 0.02
            P4 = [S[k, j] - Nn[k, j] * d, S[k, j2] - Nn[k, j2] * d, S[k + 1, j2] - Nn[k + 1, j2] * d,
                  S[k + 1, j] - Nn[k + 1, j] * d]
            p.quad(P4[0], P4[1], P4[2], P4[3], "Headliner", outward=-(Nn[k, j] + Nn[k + 1, j2]))
        for sx in (1, -1):
            x = sx * self.seat_x
            si = self.seat_info["driver"]
            top = si["top"]
            p.box((x, fl + 0.1, self.hz), (0.48, 0.2, 0.46), "Seat")
            p.box((x, (fl + top[1]) / 2 + 0.05, si["z_back"] - 0.02), (0.48, top[1] - fl - 0.1, 0.12), "Seat",
                  rot=(math.radians(self.I.get("recline", 18)) * -1, 0, 0))
        # Armaturenbrett als Block – bleibt unter der Scheibe und innerhalb der Kabine
        zc = self.z_face + 0.10
        top = min(self.cg.glass_y(self.z_face + 0.18, 0.3) - 0.04, b1.params_at(zc)["yt"] + 0.16)
        xi = min(self.x_in(self.z_face), self.cg.glass_x(self.z_face + 0.1, top - 0.05)) - 0.05
        p.box((0, (fl + 0.25 + top) / 2, zc), (2 * xi, top - fl - 0.25, 0.22), "Dash")
        return p
