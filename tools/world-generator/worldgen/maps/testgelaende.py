"""Testgelände am Stadtrand von Neon Haven.

1,15 km lange Gerade (Höchstgeschwindigkeit, Bremspunkte bei 300/200/100 m), Kreisbahn (Querbeschleunigung),
Slalom und Ausweichtest (Pylonen fliegen weg), Tisch-Sprung und Kicker, Wellen- und
Rüttelstrecke (Federung), Crashwand mit Reifenstapeln, Container zum Umdriften.
Rundherum Betonleitwände, in der Ferne die Skyline.
"""
import math

import numpy as np

from carcad.mesh import Part
from .. import geom as G
from ..geom import Frame

NAME = "Testgelände"
ID = "testgelaende"

PAD_X, PAD_Z = 260.0, 600.0          # halbe Ausdehnung der Asphaltfläche
WALL_IN = 2.0                        # Leitwand steht so weit innen
SPAWN = {"x": 0.0, "z": -532.0, "yaw": 0.0, "name": "Start"}
STRAIGHT = 575.0                     # Gerade von −575 bis +575 m


def build(rnd):
    parts = {k: Part(k) for k in ("Ground", "Markings", "Structures", "Skyline", "Lamps")}
    ground, marks, st, sky, lamps = (parts[k] for k in ("Ground", "Markings", "Structures", "Skyline", "Lamps"))
    data = {"colliders": [], "regions": [], "props": [], "lights": [], "zones": []}
    col = data["colliders"]

    def box_col(x, z, hx, hz, yaw=0.0, top=2.0, kind="wall", mu=0.35, e=0.12):
        col.append({"t": "box", "x": round(x, 3), "z": round(z, 3), "hx": round(hx, 3), "hz": round(hz, 3),
                    "yaw": round(yaw, 5), "top": round(top, 3), "kind": kind, "mu": mu, "e": e})

    def circ_col(x, z, r, top=3.0, kind="pole", mu=0.3, e=0.1):
        col.append({"t": "circle", "x": round(x, 3), "z": round(z, 3), "r": r, "top": top, "kind": kind, "mu": mu, "e": e})

    # ------------------------------------------------------------------ Boden
    G.quad_up(ground, -PAD_X, -PAD_Z, PAD_X, PAD_Z, 0.0, "Asphalt")
    R = 2600.0
    y_out = -0.03
    for (x0, z0, x1, z1) in ((-R, -R, R, -PAD_Z), (-R, PAD_Z, R, R), (-R, -PAD_Z, -PAD_X, PAD_Z), (PAD_X, -PAD_Z, R, PAD_Z)):
        G.quad_up(ground, x0, z0, x1, z1, y_out, "Dirt")
    # Betonstreifen unter den Leitwänden
    w = 3.2
    for (x0, z0, x1, z1) in ((-PAD_X, -PAD_Z, PAD_X, -PAD_Z + w), (-PAD_X, PAD_Z - w, PAD_X, PAD_Z),
                             (-PAD_X, -PAD_Z + w, -PAD_X + w, PAD_Z - w), (PAD_X - w, -PAD_Z + w, PAD_X, PAD_Z - w)):
        G.quad_up(marks, x0, z0, x1, z1, 0.004, "ConcreteDark")

    # ------------------------------------------------------------------ Leitwände (Jersey-Profil)
    jersey = [(-0.3, 0.0), (-0.3, 0.07), (-0.16, 0.33), (-0.09, 0.81), (0.09, 0.81), (0.16, 0.33), (0.3, 0.07), (0.3, 0.0)]
    ex, ez = PAD_X - WALL_IN, PAD_Z - WALL_IN
    rect = [(-ex, -ez), (ex, -ez), (ex, ez), (-ex, ez)]
    for i in range(4):
        a, b = np.array(rect[i]), np.array(rect[(i + 1) % 4])
        L = float(np.linalg.norm(b - a))
        n = int(L // 4.0)
        d = (b - a) / L
        for k in range(n):
            p0 = a + d * (k * L / n + 0.02)
            p1 = a + d * ((k + 1) * L / n - 0.02)
            G.extrude(st, jersey, p0, p1, "Concrete")
        # Kollision: dicker Block nach außen (gegen Durchtunneln)
        mid = (a + b) / 2
        out = np.array([mid[0], mid[1]])
        out = out / np.linalg.norm(out)
        nrm = np.array([d[1], -d[0]])
        if np.dot(nrm, out) < 0:
            nrm = -nrm
        c = mid + nrm * 1.2
        yaw = math.atan2(d[0], d[1])
        box_col(c[0], c[1], 1.5, L / 2 + 1.5, yaw, top=0.81, kind="barrier", mu=0.3, e=0.1)

    # ------------------------------------------------------------------ Hauptgerade
    y_m = 0.006
    for x in (-7.0, 7.0):
        G.strip(marks, [(x, -STRAIGHT), (x, STRAIGHT)], 0.2, y_m, "Paint")
    G.dashed(marks, 0, -STRAIGHT + 5, 0, STRAIGHT - 5, 0.15, y_m, "Paint", dash=6, gap=6)
    # Startlinie (Schachbrett, 14 × 3,5 m) und Startaufstellung
    z_start = -510.0
    a, b, c, d = G.P(-7, y_m + 0.001, z_start - 1.75), G.P(7, y_m + 0.001, z_start - 1.75), G.P(7, y_m + 0.001, z_start + 1.75), G.P(-7, y_m + 0.001, z_start + 1.75)
    marks.quad(a, b, c, d, "Checker", uvs=[(1, 0), (0, 0), (0, 1), (1, 1)], outward=G.UP, normals=[G.UP] * 4)
    for k in range(4):
        for side in (-3.5, 3.5):
            zz = z_start - 10 - k * 9 - (4.5 if side > 0 else 0)
            G.strip(marks, [(side - 1.2, zz), (side + 1.2, zz)], 0.25, y_m, "Paint")
            for sx in (side - 1.2, side + 1.2):
                G.strip(marks, [(sx, zz), (sx, zz - 1.2)], 0.2, y_m, "Paint")
    # Bremspunkte (300 / 200 / 100 m vor dem Ende der Geraden): dicke Balken außen (3, 2, 1 Balken)
    for i, dz in enumerate((300, 200, 100)):
        zz = STRAIGHT - dz
        for side in (-1, 1):
            for k in range(3 - i):
                x0 = side * (7.6 + k * 0.9)
                G.strip(marks, [(x0, zz - 2.5), (x0, zz + 2.5)], 0.5, y_m, "PaintYellow")

    # Neon-Tor über der Startlinie
    f = Frame(0, z_start, 0)
    for sx in (-9.6, 9.6):
        G.box(st, f, sx, 3.6, 0, 1.0, 7.2, 1.0, "DarkMetal")
        G.box(st, f, sx - math.copysign(0.52, sx), 3.6, 0.36, 0.06, 6.8, 0.06, "NeonCyan")
        G.box(st, f, sx - math.copysign(0.52, sx), 3.6, -0.36, 0.06, 6.8, 0.06, "NeonCyan")
        box_col(sx, z_start, 0.5, 0.5, 0, top=7.2, kind="pillar")
    G.box(st, f, 0, 7.6, 0, 20.4, 1.6, 1.0, "DarkMetal")
    for sz, nx in ((-0.51, -1), (0.51, 1)):
        p = [f.w(-8.6, 6.95, sz), f.w(8.6, 6.95, sz), f.w(8.6, 8.25, sz), f.w(-8.6, 8.25, sz)]
        uv = [(0, 1), (1, 1), (1, 0), (0, 0)] if nx > 0 else [(1, 1), (0, 1), (0, 0), (1, 0)]
        st.quad(*p, "Sign", uvs=uv, outward=G.P(0, 0, nx))
    G.box(st, f, 0, 6.78, 0, 20.4, 0.06, 0.08, "NeonPink")

    # Laternen entlang der Geraden
    for z in range(-550, 551, 50):
        for side in (-1, 1):
            x = side * 11.5
            G.cylinder(st, x, z, 0, 9.6, 0.13, "Metal", segs=10, r_top=0.09)
            arm = Frame(x, z, 0)
            G.box(st, arm, -side * 1.1, 9.55, 0, 2.3, 0.12, 0.14, "Metal")
            G.box(lamps, arm, -side * 2.0, 9.45, 0, 0.7, 0.1, 0.32, "LampHead")
            circ_col(x, z, 0.2, top=9.6, kind="pole")
            data["lights"].append({"kind": "street", "x": round(x - side * 2.0, 2), "y": 9.3, "z": float(z)})

    # ------------------------------------------------------------------ Kreisbahn (Skidpad)
    cx, cz = 150.0, -170.0
    for r_ in (30.0, 45.0):
        G.ring(marks, cx, cz, r_, 0.25, y_m, "Paint", step=1.5)
    G.ring(marks, cx, cz, 37.5, 0.12, y_m, "PaintYellow", step=1.5)
    for k in range(12):
        a_ = 2 * math.pi * k / 12
        data["props"].append({"type": "cone", "x": round(cx + 47 * math.sin(a_), 2), "z": round(cz + 47 * math.cos(a_), 2)})
    data["zones"].append({"name": "Kreisbahn", "x": cx, "z": cz, "r": 50})

    # ------------------------------------------------------------------ Slalom und Ausweichtest
    for k in range(16):
        data["props"].append({"type": "cone", "x": -60.0, "z": -300.0 + k * 18.0})
    G.strip(marks, [(-60, -330), (-60, -310)], 0.15, y_m, "PaintYellow")
    data["zones"].append({"name": "Slalom", "x": -60, "z": -165, "r": 20})
    # Ausweichtest (Elchtest): Gasse 3 m breit, Spurversatz 3,5 m
    lane = [(-250, -238, 0.0), (-222, -211, 3.5), (-196, -184, 0.0)]
    for (z0, z1, off) in lane:
        n = int((z1 - z0) / 3) + 1
        for k in range(n):
            zz = z0 + (z1 - z0) * k / max(1, n - 1)
            for sx in (-1.6, 1.6):
                data["props"].append({"type": "cone", "x": round(-120.0 + off + sx, 2), "z": round(zz, 2)})
    data["zones"].append({"name": "Ausweichtest", "x": -118, "z": -215, "r": 25})

    # ------------------------------------------------------------------ Sprünge
    def add_ramp(cx_, cz_, yaw_, hw, prof, name):
        f_ = Frame(cx_, cz_, yaw_)
        G.ramp(st, f_, hw, prof, "Asphalt", "Concrete")
        data["regions"].append({"t": "ramp", "x": cx_, "z": cz_, "yaw": yaw_, "hw": hw,
                                "prof": [[round(z, 3), round(h, 3)] for (z, h) in prof]})
        # Seitenwände als Kollision (abschnittsweise mit passender Höhe)
        for (z0, h0), (z1, h1) in zip(prof[:-1], prof[1:]):
            segs = max(1, int(abs(z1 - z0) / 3.5))
            for k in range(segs):
                za = z0 + (z1 - z0) * k / segs
                zb = z0 + (z1 - z0) * (k + 1) / segs
                top = max(G.ramp_height(prof, za + 1e-6), G.ramp_height(prof, zb - 1e-6))
                if top < 0.25:
                    continue
                for sx in (-1, 1):
                    c_ = f_.w(sx * (hw + 0.75), 0, (za + zb) / 2)
                    box_col(c_[0], c_[2], 0.75, (zb - za) / 2, yaw_, top=top, kind="ramp")
        # senkrechte Rückseite (Kicker)
        if prof[-1][1] > 0.25:
            c_ = f_.w(0, 0, prof[-1][0] + 0.75)
            box_col(c_[0], c_[2], hw, 0.75, yaw_, top=prof[-1][1], kind="ramp")
        # Warnstreifen am Anfang
        for k in range(int(hw * 2 / 1.0)):
            x0 = -hw + 0.5 + k * 1.0
            pa = f_.w(x0 - 0.25, 0.008, prof[0][0] - 0.2)
            pb = f_.w(x0 + 0.25, 0.008, prof[0][0] - 1.4)
            G.strip(marks, [(pa[0], pa[2]), (pb[0], pb[2])], 0.32, y_m, "PaintYellow")
        data["zones"].append({"name": name, "x": cx_, "z": cz_, "r": 25})

    add_ramp(150.0, 110.0, 0.0, 4.5, [(-19.0, 0.0), (-5.0, 1.7), (5.0, 1.7), (19.0, 0.0)], "Tisch-Sprung")
    add_ramp(205.0, -40.0, 0.0, 3.5, [(-5.0, 0.0), (5.0, 1.1)], "Kicker")

    # ------------------------------------------------------------------ Rüttel- und Wellenstrecke
    for (cx_, cz_, hl, amp, length, name) in ((-170.0, 110.0, 30.0, 0.045, 2.4, "Rüttelstrecke"),
                                               (-170.0, 185.0, 30.0, 0.32, 10.0, "Bodenwellen")):
        f_ = Frame(cx_, cz_, 0.0)
        G.wave_surface(st, f_, 3.6, hl, amp, length, "Asphalt", "Concrete")
        data["regions"].append({"t": "waves", "x": cx_, "z": cz_, "yaw": 0.0, "hw": 3.6, "hl": hl, "amp": amp, "len": length})
        for sx in (-4.0, 4.0):
            G.strip(marks, [(cx_ + sx, cz_ - hl), (cx_ + sx, cz_ + hl)], 0.2, y_m, "Paint")
        data["zones"].append({"name": name, "x": cx_, "z": cz_, "r": 30})

    # ------------------------------------------------------------------ Crashwand mit Reifenstapeln
    wf = Frame(-215.0, -385.0, 0.0)          # Crashwand quer zur Anlaufbahn (Anlauf von Norden)
    for k in range(10):
        G.box(st, wf, -15 + 1.5 + k * 3.0, 0.8, 0, 2.94, 1.6, 0.9, "Concrete")
    box_col(-215.0, -385.6, 15.0, 1.05, 0.0, top=1.6, kind="wall", mu=0.4, e=0.08)
    for k in range(14):
        x = -229.0 + k * 2.15
        for lvl in range(4):
            y0 = lvl * 0.25
            G.cylinder(st, x, -383.3, y0 + 0.01, y0 + 0.24, 0.36, "Rubber", segs=12, top=lvl == 3)
        circ_col(x, -383.3, 0.38, top=1.0, kind="tires", mu=0.6, e=0.25)
    data["zones"].append({"name": "Crashwand", "x": -215, "z": -375, "r": 25})

    # ------------------------------------------------------------------ Container zum Umdriften
    conts = [(60.0, 250.0, 0.4, "ContainerRed"), (95.0, 290.0, -0.9, "ContainerBlue"), (40.0, 320.0, 1.3, "ContainerGrey"),
             (-90.0, 300.0, 0.2, "ContainerBlue"), (-130.0, 260.0, -0.5, "ContainerRed"), (-60.0, 360.0, 1.1, "ContainerGrey")]
    for (x, z, yaw, m) in conts:
        f_ = Frame(x, z, yaw)
        G.box(st, f_, 0, 1.3, 0, 2.44, 2.6, 12.2, m)
        # Rippen an den Längsseiten (Andeutung)
        for k in range(-5, 6):
            for sx in (-1.235, 1.235):
                G.box(st, f_, sx, 1.3, k * 1.05, 0.04, 2.4, 0.12, m)
        box_col(x, z, 1.22, 6.1, yaw, top=2.6, kind="container", mu=0.35, e=0.1)
    data["zones"].append({"name": "Container", "x": 20, "z": 300, "r": 90})

    # ------------------------------------------------------------------ Skyline in der Ferne
    towers = []
    for i in range(170):
        ang = rnd.random() * 2 * math.pi
        r_ = 800 + rnd.random() ** 0.7 * 700
        x, z = r_ * math.sin(ang), r_ * math.cos(ang)
        # in Richtung der Geraden (Norden) dichter und höher: dort liegt die Stadt
        north = max(0.0, math.cos(ang))
        h = 30 + rnd.random() ** 1.6 * (140 + 220 * north)
        w = 22 + rnd.random() * 38
        d = 22 + rnd.random() * 38
        towers.append((x, z, w, d, h, rnd.random() * math.pi))
    for k in range(40):
        ang = (rnd.random() - 0.5) * 1.3
        r_ = 900 + rnd.random() * 500
        towers.append((r_ * math.sin(ang), r_ * math.cos(ang), 30 + rnd.random() * 30, 30 + rnd.random() * 30,
                       160 + rnd.random() * 260, rnd.random() * math.pi))
    for (x, z, w, d, h, yaw) in towers:
        G.building(sky, x, z, w, d, h, yaw, "Facade", "Roof", u_off=rnd.random() * 48, v_off=rnd.random() * 48)
        f_ = Frame(x, z, yaw)
        if h > 140 and rnd.random() < 0.7:
            m = ("NeonPink", "NeonCyan", "NeonViolet")[int(rnd.random() * 3)]
            for (sx, sz) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                G.box(sky, f_, sx * (w / 2 + 0.3), h * 0.5, sz * (d / 2 + 0.3), 0.8, h * 0.96, 0.8, m)
            G.box(sky, f_, 0, h + 1.5, 0, w * 0.8, 3.0, d * 0.8, m)
        if h > 220:
            G.box(sky, f_, 0, h + 20, 0, 1.6, 40, 1.6, "DarkMetal")

    # ------------------------------------------------------------------ Vorlage: Pylone (wird im Spiel instanziert)
    cone = Part("Prop_Cone")
    f0 = Frame(0, 0, 0)
    G.box(cone, f0, 0, 0.015, 0, 0.38, 0.03, 0.38, "Rubber")
    G.cylinder(cone, 0, 0, 0.03, 0.34, 0.15, "Cone", segs=14, top=False, r_top=0.095)
    G.cylinder(cone, 0, 0, 0.34, 0.47, 0.095, "ConeBand", segs=14, top=False, r_top=0.062)
    G.cylinder(cone, 0, 0, 0.47, 0.70, 0.062, "Cone", segs=14, top=True, r_top=0.022)

    meta = {
        "id": ID, "name": NAME,
        "bounds": [-PAD_X, -PAD_Z, PAD_X, PAD_Z],
        "spawn": [SPAWN,
                  {"x": 150.0, "z": -225.0, "yaw": 0.0, "name": "Kreisbahn"},
                  {"x": 150.0, "z": 40.0, "yaw": 0.0, "name": "Tisch-Sprung"},
                  {"x": -170.0, "z": 50.0, "yaw": 0.0, "name": "Wellenstrecke"}],
        "env": {"ground": "Dirt", "fogNear": 250, "fogFar": 1700},
        "props_templates": {"cone": "Prop_Cone"},
    }
    meta.update(data)
    extras = {"Ground": {"shadow": "receive"}, "Markings": {"shadow": "receive"}, "Structures": {"shadow": "both"},
              "Lamps": {"shadow": "none"}, "Skyline": {"shadow": "none", "far": True}}
    return {"nodes": [(k, p, extras.get(k, {})) for k, p in parts.items()], "templates": {"Prop_Cone": cone}, "meta": meta}
