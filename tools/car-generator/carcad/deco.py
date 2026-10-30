"""Deko und Easter Eggs im Innenraum.

Jedes Auto hat ein eigenes Fundstück; dazu kommen in allen Autos ein
Aufkleber des "Neon Haven Racing Club" und ein Zettel hinter der
Fahrer-Sonnenblende ("Wenn du das liest, schaust du nicht auf die Straße :)").
"""
import math

import numpy as np

from .mesh import Part, rot_matrix, round_rect


def common(ck, p):
    """In allen Autos: Zettel an der Sonnenblende (Unterseite) + Klub-Aufkleber am Handschuhfach."""
    vx, vy, vz = ck.anchors["visor"]
    p.tex_quad((vx, vy - 0.0085, vz), (-1, 0, 0), (0, 0, -1), 0.24, 0.12, "Secret")
    # Aufkleber auf der Beifahrerseite des Armaturenbretts (senkrechte Fläche)
    xs = sorted(ck.dash_top)
    x = min(xs, key=lambda q: abs(q + 0.36))
    y, z = ck.dash_top[x]
    p.tex_quad((-0.36, y - 0.11, z - 0.012), (-1, 0, 0), (0, 1, 0), 0.07, 0.07, "Sticker")


def helmet(ck, p, accent="Accent"):
    """Rennhelm auf dem Beifahrersitz (Vektra GT)."""
    x, y, z = ck.anchors["seat_pass"]
    c = np.array([x, y + 0.14, z + 0.02])
    p.sphere(c, 0.135, "DecoWhite", segs=24, rings=14, scale=(0.92, 0.95, 1.08))
    # Visier: dunkle Kugelkappe vorne
    vis = Part("visor")
    vis.sphere((0, 0, 0), 0.137, "Visor", segs=20, rings=10, scale=(0.93, 0.62, 1.09))
    keep = {"Visor": [t for t in vis.tris["Visor"] if ((t[0] + t[1] + t[2]) / 3)[2] > 0.05 and
                      ((t[0] + t[1] + t[2]) / 3)[1] > -0.03]}
    vis.tris = keep
    p.merge(vis.transformed(rot_matrix(-0.15, 0.0, 0.0), c + np.array([0, 0.02, 0.0])))
    # Streifen in Akzentfarbe (leuchtet nicht – Deko-Lack)
    p.tube([c + np.array([0, 0.13, -0.10]), c + np.array([0, 0.14, 0.0]), c + np.array([0, 0.12, 0.09])], 0.012,
           "MarkerRed", segs=8)
    # Kinnteil
    p.rbox(c + np.array([0, -0.11, 0.07]), (0.16, 0.05, 0.06), 0.02, "DecoWhite", segs=2)


def dice(ck, p):
    """Plüschwürfel am Innenspiegel (Brawler 77)."""
    x, y, z = ck.anchors["mirror"]
    for dx, rot in ((0.03, (0.3, 0.5, 0.2)), (-0.035, (-0.2, 0.9, 0.4))):
        p.box((dx, y - 0.04, z), (0.003, 0.08, 0.003), "Belt")
        c = np.array([dx, y - 0.11, z])
        R = rot_matrix(*rot)
        for (n, up) in (((1, 0, 0), (0, 1, 0)), ((-1, 0, 0), (0, 1, 0)), ((0, 1, 0), (0, 0, 1)),
                        ((0, -1, 0), (0, 0, 1)), ((0, 0, 1), (0, 1, 0)), ((0, 0, -1), (0, 1, 0))):
            nn = R @ np.array(n, dtype=float)
            uu = R @ np.array(up, dtype=float)
            rr = np.cross(uu, nn)
            p.tex_quad(c + nn * 0.0275, rr, uu, 0.055, 0.055, "Dice")


def cassette(ck, p):
    """Mixtape auf dem Armaturenbrett (Brawler 77)."""
    xs = sorted(ck.dash_top)
    x = min(xs, key=lambda q: abs(q + 0.30))
    y, z = ck.dash_top[x]
    c = np.array([-0.30, y + 0.009, z + 0.10])
    p.box(c, (0.10, 0.016, 0.065), "EngineBlack", rot=(0, 0.3, 0))
    p.tex_quad(c + np.array([0, 0.0085, 0]), (math.cos(0.3), 0, -math.sin(0.3)), (math.sin(0.3), 0, math.cos(0.3)),
               0.08, 0.04, "Label")


def holo_cat(ck, p):
    """Hologramm-Katze über der Mittelkonsole (Ion Spectre)."""
    x, y, z = ck.anchors["console_top"]
    p.lathe([(y - 0.004, 0.0), (y - 0.004, 0.045), (y + 0.006, 0.045), (y + 0.006, 0.0)], 20, "Chrome",
            center=(0, 0, z), axis="y", inside=(y, 0.02))
    by = y + 0.03
    for (bx_, by_, sx, sy) in ((0, 0.03, 0.07, 0.05), (0, 0.075, 0.05, 0.04), (0.018, 0.105, 0.012, 0.02),
                               (-0.018, 0.105, 0.012, 0.02), (0.045, 0.035, 0.012, 0.05)):
        p.box((x + bx_, by + by_, z), (sx, sy, 0.035), "Hologram")


def duck(ck, p):
    """Quietscheente auf dem Armaturenbrett (Rhino X)."""
    xs = sorted(ck.dash_top)
    x = min(xs, key=lambda q: abs(q + 0.32))
    y, z = ck.dash_top[x]
    c = np.array([-0.32, y, z + 0.08])
    p.sphere(c + np.array([0, 0.035, 0]), 0.04, "DuckYellow", scale=(0.9, 0.85, 1.25))
    p.sphere(c + np.array([0, 0.085, -0.03]), 0.026, "DuckYellow")
    p.box(c + np.array([0, 0.08, -0.06]), (0.02, 0.008, 0.025), "DuckBeak")
    for sx in (1, -1):
        p.sphere(c + np.array([sx * 0.012, 0.094, -0.048]), 0.004, "EngineBlack", segs=8, rings=5)


def pizza(ck, p):
    """Pizzakarton auf der Rückbank (Rhino X)."""
    x, y, z = ck.anchors.get("rear_seat", ck.anchors["seat_pass"])
    p.box((x + 0.25, y + 0.07, z), (0.34, 0.035, 0.34), "Cardboard")
    p.tex_quad((x + 0.25, y + 0.088, z), (-1, 0, 0), (0, 0, 1), 0.30, 0.15, "Label")


def coffee(ck, p):
    """Kaffeebecher im Getränkehalter (Pulse)."""
    x, y, z = ck.anchors["cup"]
    p.lathe([(y - 0.04, 0.0), (y - 0.04, 0.026), (y + 0.06, 0.034), (y + 0.06, 0.0)], 16, "DecoWhite",
            center=(x, 0, z), axis="y", inside=(y, 0.01))
    p.lathe([(y + 0.06, 0.0), (y + 0.06, 0.036), (y + 0.075, 0.03), (y + 0.075, 0.0)], 16, "Trim",
            center=(x, 0, z), axis="y", inside=(y + 0.067, 0.01))


def freshener(ck, p):
    """Blitz-Lufterfrischer am Innenspiegel (Pulse)."""
    x, y, z = ck.anchors["mirror"]
    p.box((0, y - 0.03, z), (0.003, 0.06, 0.003), "Belt")
    for (ox, oy, r) in ((0.0, -0.08, 0.5), (0.012, -0.11, -0.5), (0.0, -0.14, 0.5)):
        p.box((ox, y + oy, z), (0.012, 0.045, 0.004), "MarkerRed", rot=(0, 0, r))


def bobble_cat(ck, p):
    """Wackel-Katze auf dem Armaturenbrett (Pulse)."""
    xs = sorted(ck.dash_top)
    x = min(xs, key=lambda q: abs(q + 0.30))
    y, z = ck.dash_top[x]
    c = np.array([-0.30, y + 0.005, z + 0.07])
    p.sphere(c + np.array([0, 0.03, 0]), 0.03, "DecoWhite")
    p.rbox(c + np.array([0, 0.08, 0]), (0.06, 0.05, 0.05), 0.015, "DecoWhite", segs=2)
    for ex in (0.02, -0.02):
        p.box(c + np.array([ex, 0.11, 0]), (0.014, 0.02, 0.012), "DecoWhite", rot=(0, 0, ex * 20))
        p.box(c + np.array([ex, 0.085, -0.026]), (0.01, 0.01, 0.003), "EngineBlack")


def champagne(ck, p):
    """Champagner + zwei Gläser in der Fond-Mittelkonsole (Aurelion S)."""
    x, y, z = ck.anchors.get("rear_console", ck.anchors.get("rear_seat", ck.anchors["seat_pass"]))
    c = np.array([0.0, y, z])
    prof = [(0.0, 0.0), (0.0, 0.037), (0.20, 0.037), (0.24, 0.016), (0.30, 0.013), (0.31, 0.0)]
    p.lathe([(c[1] + a, r) for (a, r) in prof], 18, "Bottle", center=(c[0], 0, c[2]), axis="y",
            inside=(c[1] + 0.1, 0.01))
    p.lathe([(c[1] + 0.27, 0.0), (c[1] + 0.27, 0.0145), (c[1] + 0.315, 0.0145), (c[1] + 0.315, 0.0)], 14, "Gold",
            center=(c[0], 0, c[2]), axis="y", inside=(c[1] + 0.29, 0.005))
    p.tex_quad(c + np.array([0, 0.11, 0.0372]), (1, 0, 0), (0, 1, 0), 0.05, 0.06, "Label")
    for sx in (1, -1):
        g = c + np.array([sx * 0.07, 0.0, -0.02])
        p.lathe([(g[1], 0.0), (g[1], 0.025), (g[1] + 0.004, 0.025), (g[1] + 0.006, 0.004), (g[1] + 0.09, 0.003),
                 (g[1] + 0.1, 0.02), (g[1] + 0.17, 0.024), (g[1] + 0.17, 0.0)], 14, "Crystal",
                center=(g[0], 0, g[2]), axis="y", inside=(g[1] + 0.13, 0.005))
