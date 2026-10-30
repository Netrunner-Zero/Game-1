"""Räder: Reifen mit Profil und Flanke, Felgen (mehrere Designs), Bremsen.

Lokaler Rahmen eines Rades: Ursprung = Radmitte, Achse = X.
side = +1: Außenseite bei +X (linke Fahrzeugseite), side = -1: rechts.
"""
import math

import numpy as np

from .mesh import Part, round_rect, norm


# ----------------------------------------------------------------------
# Reifen
# ----------------------------------------------------------------------

def tire(R, W, Rr, side, lod=0, kind="sport"):
    p = Part("Tire")
    segs = {0: 64, 1: 22}[min(lod, 1)]
    sh = min(0.03, W * 0.12)          # Schulterrundung
    bulge = 0.006 if kind == "sport" else 0.012
    o, i = side, -side                # außen/innen in x
    xo, xi = o * W / 2, i * W / 2
    # Lauffläche (mit Rillen bei LOD0)
    if lod == 0 and kind == "sport":
        tread = [(xi + o * sh, R - 0.002)]
        for gx in (-0.3, 0.0, 0.3):
            g = gx * W
            tread += [(g - 0.006, R), (g - 0.005, R - 0.007), (g + 0.005, R - 0.007), (g + 0.006, R)]
        tread.append((xo - o * sh, R - 0.002))
        tread = sorted(tread, key=lambda q: q[0])
        # Material: Rillenboden dunkel
        for a, b in zip(tread[:-1], tread[1:]):
            mat = "Groove" if (a[1] < R - 0.004 and b[1] < R - 0.004) else "Tire"
            p.lathe([a, b], segs, mat, inside=(0, (R + Rr) / 2))
    elif lod == 0 and kind == "at":
        p.lathe([(xi + o * sh, R - 0.012), (xo - o * sh, R - 0.012)], segs, "Tire", inside=(0, (R + Rr) / 2))
    else:
        p.lathe([(xi + o * sh, R - 0.002), (xo - o * sh, R - 0.002)], segs, "Tire", inside=(0, (R + Rr) / 2))
    # Schultern
    for xs, sgn in ((xo, o), (xi, i)):
        prof = [(xs - sgn * sh, R - 0.002 - (0.010 if kind == "at" and lod == 0 else 0.0)),
                (xs - sgn * sh * 0.35, R - sh * 0.35), (xs, R - sh), (xs + sgn * bulge, R - sh - (R - Rr) * 0.25)]
        if sgn == o:
            prof = prof
        p.lathe(prof, segs, "Tire", inside=(0, (R + Rr) / 2))
    # Flanken: außen mit Beschriftung (u = Umfang 0..1, v = radial)
    yb_top = R - sh - (R - Rr) * 0.25
    outer = Part("sw")
    outer.lathe([(xo + o * bulge, yb_top), (xo + o * bulge * 0.6, (yb_top + Rr) / 2 + 0.01), (xo, Rr + 0.018),
                 (xo - o * 0.006, Rr + 0.004)], segs, "Sidewall", inside=(0, (R + Rr) / 2), uv_mode="unit")
    if side > 0:  # Schrift sonst gespiegelt
        for mat, tl in outer.tris.items():
            outer.tris[mat] = [(a, b, c, ns, [(1 - u, v) for (u, v) in uv]) for (a, b, c, ns, uv) in tl]
    p.merge(outer)
    p.lathe([(xi + i * bulge, yb_top), (xi + i * bulge * 0.6, (yb_top + Rr) / 2 + 0.01), (xi, Rr + 0.018),
             (xi - i * 0.006, Rr + 0.004)], segs, "Tire", inside=(0, (R + Rr) / 2))
    # Allterrain-Stollen
    if lod == 0 and kind == "at":
        n = 34
        for k in range(n):
            a = 2 * math.pi * k / n
            for row, (u0, u1) in enumerate(((-0.46, -0.16), (-0.12, 0.12), (0.16, 0.46))):
                off = (0.5 if row == 1 else 0.0) * (2 * math.pi / n)
                aa = a + off
                ua, ub = u0 * W, u1 * W
                rr = R - 0.012
                h = 0.016
                ang_w = (2 * math.pi / n) * 0.62
                pts = []
                for (uu, da) in ((ua, -ang_w / 2), (ub, -ang_w / 2 + 0.02 * (1 if row != 1 else 0)),
                                 (ub, ang_w / 2), (ua, ang_w / 2 - 0.02 * (1 if row != 1 else 0))):
                    pts.append((uu, aa + da))
                bot = [np.array([uu, rr * math.cos(t), rr * math.sin(t)]) for (uu, t) in pts]
                top = [np.array([uu, (rr + h) * math.cos(t), (rr + h) * math.sin(t)]) for (uu, t) in pts]
                p.hexa(bot + top, "Tire")
            # Flankenstollen außen
            for xs, sgn in ((xo, o), (xi, i)):
                aa = a + math.pi / n
                ang_w = (2 * math.pi / n) * 0.45
                rr0, rr1 = R - 0.05, R - 0.006
                bot = [np.array([xs, r_ * math.cos(aa + da), r_ * math.sin(aa + da)]) for (r_, da) in
                       ((rr0, -ang_w / 2), (rr1, -ang_w / 2), (rr1, ang_w / 2), (rr0, ang_w / 2))]
                top = [q + np.array([sgn * 0.01, 0, 0]) for q in bot]
                p.hexa(bot + top, "Tire")
    return p


# ----------------------------------------------------------------------
# Felgen
# ----------------------------------------------------------------------

def _spoke(part, a, r0, r1, x0, x1, w0, w1, t0, t1, side, mat, twist=0.0, segs=6, curve=0.7, round_r=0.4):
    """Speiche von Nabe (r0, x0) zum Felgenrand (r1, x1); Querschnitt abgerundet."""
    secs = []
    for k in range(segs + 1):
        s = k / segs
        r = r0 + (r1 - r0) * s
        x = x0 + (x1 - x0) * (s ** curve)
        th = a + twist * s
        P = np.array([x, r * math.cos(th), r * math.sin(th)])
        et = np.array([0.0, -math.sin(th), math.cos(th)])
        ex = np.array([float(side), 0.0, 0.0])
        w = w0 + (w1 - w0) * s
        t = t0 + (t1 - t0) * s
        sec = []
        for (u, v) in round_rect(w, t, min(w, t) * round_r, 2):
            sec.append(P + et * u + ex * v)
        secs.append(sec)
    part.loft(secs, lambda k, j: mat, caps=(mat, mat), smooth=True)


def rim(R, W, Rr, side, design, lod=0, nuts=5):
    """design: dict(style=..., n=..., concave=..., ...)."""
    p = Part("Rim")
    st = design["style"]
    n = design.get("n", 5)
    conc = design.get("concave", 0.045)
    xl = side * (W / 2 - 0.012)                 # Felgenhorn (außen)
    xh = side * (W / 2 - 0.012 - conc)          # Nabenfläche
    xin = -side * (W / 2 - 0.02)                # Innenseite Felgenbett
    segs = 48 if lod == 0 else 18
    lip_mat = design.get("lip", "RimLip")
    # Felgenbett (innen, dunkel) und Felgenhorn
    p.lathe([(xin, Rr - 0.004), (xl - side * 0.012, Rr - 0.004)], segs, "RimDark", inside=(0, Rr + 0.05))
    p.lathe([(xl - side * 0.014, Rr - 0.026), (xl, Rr - 0.022), (xl + side * 0.002, Rr - 0.008),
             (xl, Rr + 0.004), (xl - side * 0.012, Rr + 0.004)], segs, lip_mat, inside=(xl - side * 0.008, Rr - 0.01))
    hub_r = design.get("hub", 0.075)
    r_out = Rr - 0.022
    if lod >= 1:
        # vereinfachte Felge: Scheibe + Speichen als Quader
        p.lathe([(xh, 0.0), (xh, hub_r)], 12, "Rim", inside=(xh - side * 0.01, 0.0))
        k = n if st != "aero" else 0
        for i in range(k):
            a = 2 * math.pi * i / n
            rc = (hub_r + r_out) / 2
            p.box(((xh + xl) / 2, rc * math.cos(a), rc * math.sin(a)), (abs(xl - xh) * 0.5 + 0.01, r_out - hub_r, 0.05),
                  "Rim", rot=(a, 0, 0))
        if st == "aero":
            p.lathe([(xl - side * 0.012, hub_r), (xl - side * 0.012, r_out)], 18, "Rim",
                    inside=(xl - side * 0.03, (hub_r + r_out) / 2), smooth=False)
        return p
    # Nabe mit Schüssel
    p.lathe([(xh - side * 0.03, hub_r + 0.012), (xh - side * 0.004, hub_r + 0.01), (xh, hub_r),
             (xh + side * 0.004, hub_r * 0.6), (xh + side * 0.006, 0.0)], 32, "Rim", inside=(xh - side * 0.02, 0.0))
    # Radmuttern
    for i in range(nuts):
        a = 2 * math.pi * i / nuts + math.pi / nuts
        rn = hub_r * 0.66
        c = (xh + side * 0.006, rn * math.cos(a), rn * math.sin(a))
        p.lathe([(0.0, 0.0105), (side * 0.012, 0.0105), (side * 0.016, 0.006), (side * 0.016, 0.0)], 6, "LugNut",
                center=c, axis="x", inside=(side * 0.008, 0.004), smooth=False)
    # Nabendeckel mit Logo
    p.lathe([(xh + side * 0.008, hub_r * 0.42), (xh + side * 0.016, hub_r * 0.4)], 24, "Rim",
            inside=(xh, hub_r * 0.2))
    cap = Part("cap")
    cap.lathe([(xh + side * 0.0165, 0.0), (xh + side * 0.0165, hub_r * 0.4)], 24, "CenterCap",
              inside=(xh, hub_r * 0.2), uv_mode="polar", polar_r=hub_r * 0.4)
    if side < 0:  # Logo nicht spiegeln
        for mat, tl in cap.tris.items():
            cap.tris[mat] = [(a, b, c, ns, [(1 - u, v) for (u, v) in uv]) for (a, b, c, ns, uv) in tl]
    p.merge(cap)
    # Speichen-Designs
    if st == "split5":        # 5 Doppelspeichen
        for i in range(n):
            a = 2 * math.pi * i / n
            for d in (-0.085, 0.085):
                _spoke(p, a, hub_r * 0.85, r_out, xh, xl - side * 0.004, 0.034, 0.024, 0.026, 0.016, side, "Rim",
                       twist=d, segs=7)
    elif st == "classic5":    # 5 kräftige Speichen
        for i in range(n):
            a = 2 * math.pi * i / n
            _spoke(p, a, hub_r * 0.8, r_out, xh, xl - side * 0.004, 0.07, 0.05, 0.03, 0.018, side, "Rim", segs=7)
    elif st == "multi":       # viele feine Speichen (Kreuzspeichen)
        for i in range(n):
            a = 2 * math.pi * i / n
            for d in (-0.12, 0.12):
                _spoke(p, a, hub_r * 0.85, r_out, xh, xl - side * 0.004, 0.016, 0.011, 0.016, 0.012, side, "Rim",
                       twist=d * (1 if i % 2 else -1), segs=6)
        # Ring für Kreuzspeichen
        rr = hub_r + (r_out - hub_r) * 0.55
        p.lathe([(xh + (xl - xh) * 0.6, rr - 0.006), (xh + (xl - xh) * 0.62 + side * 0.006, rr), (xh + (xl - xh) * 0.6, rr + 0.006)],
                48, "Rim", inside=(xh, rr))
    elif st == "fine":        # Luxus: viele dünne, leicht gedrehte Speichen
        for i in range(n):
            a = 2 * math.pi * i / n
            _spoke(p, a, hub_r * 0.85, r_out, xh, xl - side * 0.004, 0.013, 0.010, 0.02, 0.012, side, "Rim",
                   twist=0.18, segs=8, curve=0.55)
    elif st == "aero":        # Aero-Scheibe mit Turbinenschlitzen
        disc_x = xl - side * 0.014
        p.lathe([(xh, hub_r), (disc_x - side * 0.004, hub_r + 0.02), (disc_x, r_out - 0.01), (disc_x - side * 0.002, r_out + 0.004)],
                64, "Rim", inside=(xh - side * 0.04, (hub_r + r_out) / 2), smooth=True)
        for i in range(n):
            a = 2 * math.pi * i / n
            for k in range(3):
                rr = hub_r + 0.03 + (r_out - hub_r - 0.05) * (k + 0.5) / 3
                aa = a + k * 0.14
                p.box((disc_x + side * 0.0012, rr * math.cos(aa), rr * math.sin(aa)), (0.003, 0.03, 0.012), "RimDark",
                      rot=(aa + 0.9, 0, 0))
    elif st == "beadlock":    # Offroad: 6 breite Speichen + Beadlock-Ring mit Schrauben
        for i in range(n):
            a = 2 * math.pi * i / n
            _spoke(p, a, hub_r * 0.8, r_out, xh, xl - side * 0.006, 0.06, 0.07, 0.028, 0.022, side, "Rim", segs=6)
        p.lathe([(xl - side * 0.01, Rr - 0.04), (xl + side * 0.006, Rr - 0.036), (xl + side * 0.006, Rr - 0.006),
                 (xl - side * 0.004, Rr)], 48, "RimDark", inside=(xl - side * 0.02, Rr - 0.02))
        for k in range(24):
            a = 2 * math.pi * k / 24
            rr = Rr - 0.021
            p.lathe([(0.0, 0.0), (0.0, 0.006), (side * 0.006, 0.005), (side * 0.006, 0.0)], 6, "LugNut",
                    center=(xl + side * 0.006, rr * math.cos(a), rr * math.sin(a)), axis="x",
                    inside=(side * 0.003, 0.002), smooth=False)
    elif st == "mesh":        # Netzfelge (Kreuzgitter)
        for i in range(n):
            a = 2 * math.pi * i / n
            _spoke(p, a, hub_r * 0.85, r_out, xh, xl - side * 0.004, 0.022, 0.014, 0.022, 0.012, side, "Rim", segs=6)
        for i in range(n * 2):
            a = 2 * math.pi * i / (n * 2)
            _spoke(p, a, hub_r + 0.035, r_out, xh + (xl - xh) * 0.35, xl - side * 0.004, 0.01, 0.009, 0.012, 0.009,
                   side, "Rim", twist=0.35 if i % 2 else -0.35, segs=5)
    # Ventil
    va = math.radians(20)
    p.tube([np.array([xl - side * 0.006, (Rr - 0.03) * math.cos(va), (Rr - 0.03) * math.sin(va)]),
            np.array([xl + side * 0.004, (Rr - 0.034) * math.cos(va), (Rr - 0.034) * math.sin(va)])],
           0.0035, "RimDark", segs=6)
    return p


# ----------------------------------------------------------------------
# Bremsen
# ----------------------------------------------------------------------

def brake_geometry(W, Rr, design, side):
    conc = design.get("concave", 0.045)
    xd = side * (W / 2 - 0.012 - conc - 0.034)     # Außenfläche der Scheibe
    rd = Rr - 0.045
    return xd, rd


def brake_disc(R, W, Rr, side, design, lod=0):
    p = Part("Brake")
    if lod >= 1:
        return p
    xd, rd = brake_geometry(W, Rr, design, side)
    t = 0.03
    # Reibflächen (polare UVs) + belüfteter Rand
    p.lathe([(xd, 0.068), (xd, rd)], 48, "BrakeDisc", inside=(xd - side * 0.01, (rd + 0.07) / 2),
            uv_mode="polar", polar_r=rd)
    p.lathe([(xd, rd), (xd - side * 0.004, rd + 0.001), (xd - side * (t - 0.004), rd + 0.001), (xd - side * t, rd)], 48,
            "BrakeHat", inside=(xd - side * t / 2, rd - 0.02))
    # Topf
    p.lathe([(xd + side * 0.002, 0.068), (xd + side * 0.012, 0.064), (xd + side * 0.016, 0.05), (xd + side * 0.016, 0.0)],
            32, "BrakeHat", inside=(xd, 0.03))
    return p


def caliper(R, W, Rr, side, design, lod=0, angle_deg=125.0, size=1.0, logo=True):
    """Bremssattel (fester Knoten an der Radmitte, lenkt mit, dreht nicht)."""
    p = Part("Caliper")
    if lod >= 1:
        return p
    xd, rd = brake_geometry(W, Rr, design, side)
    span = math.radians(48 * size)
    a_c = math.radians(angle_deg)
    a0, a1 = a_c - span / 2, a_c + span / 2
    r_in, r_out = rd - 0.042 * size, min(rd + 0.016, Rr - 0.014)
    x_out, x_in = xd + side * 0.022, xd - side * 0.055
    # gewölbter Block (Lathe-Segment) mit Endkappen
    prof = [(x_in, r_in), (x_in, r_out), (x_out - side * 0.006, r_out), (x_out, r_out - 0.006), (x_out, r_in + 0.006),
            (x_out - side * 0.006, r_in), (x_in, r_in)]
    p.lathe(prof, 10, "Caliper", a0=a0, a1=a1, inside=((x_in + x_out) / 2, (r_in + r_out) / 2), smooth=False)
    for aa in (a0, a1):
        pts = [np.array([s, r * math.cos(aa), r * math.sin(aa)]) for (s, r) in prof[:-1]]
        c = sum(pts) / len(pts)
        outward = np.array([0, -math.sin(aa), math.cos(aa)]) * (1 if aa == a1 else -1)
        for i in range(len(pts)):
            p.tri(c, pts[i], pts[(i + 1) % len(pts)], "Caliper", outward=outward)
    # Schriftzug auf der Außenseite
    if logo:
        rm = (r_in + r_out) / 2
        cpos = np.array([x_out + side * 0.0015, rm * math.cos(a_c), rm * math.sin(a_c)])
        tang = np.array([0.0, -math.sin(a_c), math.cos(a_c)])
        radial = np.array([0.0, math.cos(a_c), math.sin(a_c)])
        right = tang if side < 0 else -tang
        p.tex_quad(cpos, right, radial, 0.09 * size, 0.022 * size, "CaliperLogo")
    # Entlüftungsschraube
    bp = np.array([x_out - side * 0.002, (r_out - 0.004) * math.cos(a1 - 0.08), (r_out - 0.004) * math.sin(a1 - 0.08)])
    p.lathe([(0.0, 0.0), (0.0, 0.004), (side * 0.006, 0.003), (side * 0.006, 0.0)], 6, "LugNut", center=bp, axis="x",
            inside=(side * 0.003, 0.001), smooth=False)
    return p
