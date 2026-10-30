"""Aurelion S – große Luxuslimousine (langer Radstand, V12 Biturbo, Hinterradantrieb).

Design: lange Motorhaube mit stehender Kühlerfigur, aufrechter Chromgrill mit
senkrechten Streben, schmale LED-Scheinwerfer, Zweifarblackierung entlang der
Charakterlinie mit goldener Zierlinie, Chrom an Fensterrahmen, Gürtellinie,
Schwellern und Heck, vier Türen (hintere Tür mit Ausschnitt am Radlauf),
breite C-Säule mit Emblem, flache Rückleuchten mit Chromspange.
Innen: helles Leder, Walnuss, Sternenhimmel, dimmbare Ambientebeleuchtung,
Kristall-Drehsteller, Einzelsitze im Fond mit Bildschirmen und Mittelkonsole
mit Champagner.
"""
import math

import numpy as np

from . import S, C
from .. import kit
from ..mesh import Part, rot_matrix, round_rect
from ..parts import rr_outline, place_top, densify
from ..interior import CabinGeo

SPEC = {
    "id": "aurelion_s", "name": "Aurelion S", "node": "Aurelion_S",
    "desc": "Luxuslimousine mit langem Radstand, V12 Biturbo und Luftfederung – ruhig, schwer, kraftvoll",
    "class": "Luxuslimousine",
    "brand": {"mono": "A", "word": "AURELION", "caliper": "AURELION"},
    "plate": "AU 1", "number": "01",
    "deco_label": [("CUVÉE NOIR", 60), ("2049", 80)],
    "palette": {
        "paint": "#c7c1b4", "paint2": "#1b2a3a", "accent": "#d9b46a", "rim": "#c9ccd2", "caliper": "#2f3238",
        "seat": "#d8cbb5", "insert": "leather", "insert_color": "#cdbfa6", "stitch": "#8a6a48",
        "trim": "wood_walnut", "trim2": "aluminum", "dash": "#3a2c22", "door": "#cfc2aa",
        "headliner": "#141418", "carpet": "#2a2a33", "wheel_leather": "#3a2c22", "ambient": "#ffcf8a",
        "marker": "#d9b46a", "cage": "#1a1a1d", "belt": "chrome", "grille": "chrome",
    },
    "stats": {"massKg": 2350, "powerKw": 450, "drive": "RWD", "topSpeedKmh": 250, "grip": 0.92,
              "suspension": "Luftfederung, weich"},
    "physics": {
        "massKg": 2350, "cogHeight": 0.55, "weightFront": 0.52, "dragCd": 0.27, "frontalArea": 2.45,
        "powerKw": 450, "torqueNm": 900, "idleRpm": 650, "redlineRpm": 6200,
        "gears": [5.35, 3.24, 2.25, 1.64, 1.21, 1.0, 0.86, 0.72, 0.60], "finalDrive": 2.65,
        "suspension": {"springFront": 36000, "springRear": 38000, "damping": 0.24, "travel": 0.14,
                       "antiRollFront": 0.5, "antiRollRear": 0.4, "air": True},
        "tire": {"grip": 0.92, "slipPeak": 0.10}, "brakeForce": 1.05, "brakeBias": 0.6, "steerLockDeg": 33,
        "speedLimiterKmh": 250,
    },
    "tuning": {
        "engine": [{"name": "Serie V12 Biturbo", "powerKw": 450, "torqueNm": 900},
                   {"name": "Sportansaugung", "powerKw": 470, "torqueNm": 940},
                   {"name": "Ladedruck + Ladeluftkühler", "powerKw": 520, "torqueNm": 1000},
                   {"name": "Black-Badge-Paket (Carbon-Aero)", "powerKw": 560, "torqueNm": 1050}],
        "exhaust": [{"name": "Serie (verdeckt)", "loudness": 0}, {"name": "Sport (4 ovale Rohre)", "loudness": 3},
                    {"name": "Black Badge (4 Rohre)", "loudness": 6}],
        "cage": [{"name": "Kein Käfig"}, {"name": "Halbkäfig", "massKg": 18, "stiffness": 1.04},
                 {"name": "Vollkäfig", "massKg": 34, "stiffness": 1.10}],
    },
    "default_tuning": {"roofColor": "#1b2a3a"},
    "rpm_max": 7, "gauge_vmax": 280, "steer_wheel_deg": 480,
    # --------------------------------------------------------------
    "wheels": {"front": {"z": 1.66, "R": 0.385, "W": 0.255}, "rear": {"z": -1.54, "R": 0.385, "W": 0.285}},
    "rim_ratio": 0.70, "tire": "sport", "wheel_out": -0.012, "caliper_angle": 125.0, "caliper_size": 1.1,
    "arch_gap": 0.045,
    "rims": [{"style": "fine", "n": 15, "label": "Feinspeiche"},
             {"style": "aero", "n": 8, "concave": 0.02, "label": "Klassik-Scheibe"},
             {"style": "multi", "n": 10, "label": "Kreuzspeiche"}],
    "nuts": 5, "max_lowering_cm": 5,
    "section": {"bw": 0.86, "lo": 0.20, "hi": 0.22, "tum": 0.985, "sh": 0.90, "crx": 0.46,
                "radii": [0.035, 0.06, 0.028, 0.06, 0.24]},
    "two_tone": {"crease": True, "offset": 0.004},
    "seal_mat": "Chrome",
    "nose_r": 0.03, "tail_r": 0.035,
    "body": [S(2.68, 0.66, 0.30, 0.90, 0.0), S(2.665, 0.78, 0.26, 0.925, 0.006),
             S(2.63, 0.865, 0.235, 0.945, 0.012), S(2.56, 0.925, 0.215, 0.962, 0.02),
             S(2.40, 0.958, 0.205, 0.978, 0.027), S(2.20, 0.968, 0.20, 0.988, 0.031),
             S(1.66, 0.975, 0.20, 1.00, 0.035), S(1.20, 0.97, 0.20, 1.01, 0.035),
             S(0.00, 0.965, 0.20, 1.03, 0.03), S(-1.00, 0.968, 0.20, 1.04, 0.03),
             S(-1.54, 0.975, 0.205, 1.045, 0.03), S(-2.10, 0.96, 0.22, 1.04, 0.025),
             S(-2.40, 0.935, 0.245, 1.025, 0.018), S(-2.52, 0.89, 0.275, 1.0, 0.008),
             S(-2.59, 0.81, 0.31, 0.95, 0.0), S(-2.62, 0.70, 0.34, 0.88, 0.0)],
    "cabin": [C(1.20, 0.86, 0.80, -0.02, "ws"), C(0.80, 0.852, 0.745, 1.30, "ws"), C(0.40, 0.846, 0.70, 1.47, "ws"),
              C(0.28, 0.846, 0.696, 1.495, "roof"), C(-0.30, 0.848, 0.696, 1.505, "roof"),
              C(-0.40, 0.85, 0.696, 1.505, "pillar"), C(-1.30, 0.855, 0.696, 1.49, "roof"),
              C(-1.62, 0.855, 0.69, 1.46, "cpillar"), C(-2.20, 0.86, 0.70, -0.02, "rear")],
    "pillar_frac": 0.22, "rear_side": "paint", "bpillar_mat": "BlackGloss",
    "gaps": {"doors": [{"z": (1.12, -0.345), "y0": 0.33}, {"z": (-0.355, -1.40), "y0": 0.33, "arch": "rear"}],
             "lids": [{"z0": 1.30, "z1": 2.62, "x": 0.80, "cross": [1.31, 2.61]},
                      {"z0": -2.56, "z1": -2.22, "x": 0.84, "cross": [-2.23]}]},
    "plate_pos": {"front": 0.47, "rear": 0.665},
    "livery_skip_z": [(2.40, 2.65)],
    "spoiler": {"z": -2.48, "w": 0.80, "lip": (0.14, 0.03), "h2": 0.22, "h3": 0.36},
    "spoiler_labels": ["Abrisskante", "Heckflügel", "Cyber-Flügel"],
    "exhaust": {"y": 0.36, "protrude": 0.015,
                "variants": [[(0.62, 0.05, "square", "Chrome"), (-0.62, 0.05, "square", "Chrome")],
                             [(0.55, 0.036, "oval", "Chrome"), (0.67, 0.036, "oval", "Chrome"),
                              (-0.55, 0.036, "oval", "Chrome"), (-0.67, 0.036, "oval", "Chrome")],
                             [(0.54, 0.042, "round", "DarkChrome"), (0.66, 0.042, "round", "DarkChrome"),
                              (-0.54, 0.042, "round", "DarkChrome"), (-0.66, 0.042, "round", "DarkChrome")]]},
    # --------------------------------------------------------------
    "interior": {
        "floor": 0.30, "fw": 1.26, "rb": -2.18, "hpt_z": -0.12, "seat_x": 0.40, "driver_x": 0.40, "tunnel": 0.14,
        "shelf": (-1.64, -2.20, 1.04), "shelf_mat": "Carpet", "rear_wall_top": 1.04,
        "dash": {"depth": 0.62, "clear": 0.07, "binnacle": 0.03, "stack": 0.06, "height": 0.16, "knee": 0.42,
                 "upper": "Dash"},
        "cluster": {"type": "digital", "w": 0.34, "h": 0.12},
        "center": {"type": "dash", "w": 0.34, "h": 0.15},
        "vents": (0.20, -0.20, 0.64, -0.64),
        "wheel": {"r": 0.19, "tilt": 22, "dist": 0.25, "drop": 0.11, "style": "round", "grip": 0.016,
                  "marker": False, "spokes": 2, "spoke_mat": "InteriorTrim2", "paddles": False},
        "console": {"back": 0.30, "h_front": 0.30, "h_back": 0.24, "w": 0.24, "shifter_t": 0.40, "shifter": "dial",
                    "knob": "Crystal", "knob_ring": "Chrome"},
        "seat_kind": "comfort", "recline": 20, "cushion_h": 0.18, "back_h": 0.68,
        "rear": {"type": "seats", "z": -1.30, "x": 0.38, "w": 0.52, "kind": "comfort", "recline": 30, "back_h": 0.66,
                 "headrest": True, "console": True},
        "rear_cushion_h": 0.20,
        "rear_screens": True, "starlight": True,
        "eye_dist": 0.64, "head_clear": 0.12, "eye_up": 0.36,
    },
}


# ======================================================================
# Außendetails
# ======================================================================

HEAD = {
    "w": 0.38, "h": 0.072, "depth": 0.07, "dome": 0.006, "lens": "LampGlass", "kind": "head",
    "shape": kit.rshape([(-0.19, -0.026), (0.17, -0.036), (0.19, 0.034), (-0.18, 0.030)], 0.014),
    "elements": [("chrome", rr_outline(0.34, 0.046, 0.01, 2)),
                 ("projector", 0.02, -0.004, 0.019), ("projector", 0.066, -0.006, 0.019),
                 ("projector", 0.112, -0.008, 0.019),
                 ("strip", [(-0.175, 0.020), (0.0, 0.022), (0.175, 0.027)], 0.007, "DRL"),
                 ("strip", [(-0.16, -0.020), (-0.04, -0.023)], 0.005, "Indicator")],
}
TAIL = {
    "w": 0.44, "h": 0.075, "depth": 0.05, "dome": 0.005, "lens": "TailGlass", "kind": "tail",
    "shape": kit.rshape([(-0.22, -0.030), (0.20, -0.036), (0.22, 0.036), (-0.21, 0.030)], 0.012),
    "elements": [("chrome", rr_outline(0.40, 0.05, 0.01, 2)),
                 ("strip", [(-0.205, 0.018), (0.20, 0.024)], 0.009, "Taillight"),
                 ("strip", [(-0.205, -0.016), (0.20, -0.022)], 0.009, "Taillight"),
                 ("panel", kit.rshape([(-0.16, -0.008), (0.17, -0.011), (0.17, 0.010), (-0.16, 0.008)], 0.004),
                  "Brakelight"),
                 ("panel", kit.rshape([(-0.205, -0.008), (-0.175, -0.008), (-0.175, 0.008), (-0.205, 0.008)], 0.003),
                  "Reverse"),
                 ("strip", [(0.12, 0.0), (0.205, 0.0)], 0.004, "Indicator")],
}
REFLECTOR = {"w": 0.12, "h": 0.02, "r": 0.008, "depth": 0.015, "dome": 0.002, "lens": "TailGlass", "kind": "marker",
             "elements": [("panel", rr_outline(0.10, 0.011, 0.004, 2), "Taillight")]}


def _crease_y(b, z):
    p = b.params_at(z)
    return p["yt"] - b.sec["hi"] * (p["yt"] - p["yb"])


def details(ctx):
    b = ctx.b
    lod = ctx.lod
    # ---------------- Front ----------------
    kit.opening(ctx, rr_outline(0.58, 0.32, 0.03, 4), "front", 0.0, 0.72, depth=0.08, style="vslats",
                frame_mat="Chrome", mesh_mat="Mesh", cell=0.032, frame_w=0.035, blend=0.9)
    kit.lamp(ctx, HEAD, 0.665, 0.83, front=True, blend=0.6)
    kit.opening(ctx, rr_outline(1.10, 0.10, 0.03, 4), "front", 0.0, 0.35, depth=0.07, style="hslats",
                frame_mat="Chrome", mesh_mat="Mesh", cell=0.035, frame_w=0.012, blend=0.7)
    kit.opening(ctx, rr_outline(0.05, 0.16, 0.02, 4), "front", 0.74, 0.47, depth=0.05, style="hslats",
                frame_mat="Chrome", cell=0.03, mirror=True, blend=0.75)
    hit = ctx.hit_front(0.0, 0.72)
    if hit is not None:
        # Grill steht vor der Front: kräftiger Chromrahmen + Emblem oben (in allen Detailstufen – prägt das Gesicht)
        zf_ = hit[0][2]
        loop = [np.array([u, 0.72 + v, zf_ + 0.014])
                for (u, v) in densify(rr_outline(0.615, 0.355, 0.04, 6 if lod == 0 else 2), 0.02 if lod == 0 else 0.08)]
        loop.append(loop[0])
        ctx.part("Grille").sweep(loop, round_rect(0.03, 0.034, 0.012, 2), "Chrome", up=(0, 0, 1), caps=False)
        kit.emblem(ctx, np.array([0.0, 0.88, zf_ + 0.03]), np.array([0, 0.15, 1.0]), d=0.05)
        # Chromleiste unter dem Grill
        kit.face_line(ctx, [(-0.62, 0.548), (0.62, 0.548)], rear=False, width=0.012, mat="Chrome", lift=0.003)
    ht = ctx.hit_top(0.0, 2.57)
    if ht is not None:                               # stehende Kühlerfigur
        kit.hood_ornament(ctx.part("Badges"), ht[0] + np.array([0, -0.004, 0]), lod)
    # ---------------- Seite ----------------
    kit.side_mirror(ctx, 1.06, 0.98, reach=0.12, rise=0.10, length=0.19, h=0.10, depth=0.12,
                    body_mat="Paint2", stalk_mat="BlackGloss", indicator=True)
    if lod == 0:
        for z in (-0.20, -1.26):
            kit.flush_handle(ctx, z, 0.95, w=0.15, h=0.026, mat="Chrome")
        # Goldene Zierlinie auf der Trennlinie der Zweifarblackierung
        kit.side_strip(ctx, lambda z: _crease_y(b, z) + 0.004, 2.50, -2.48, width=0.005, mat="Gold", offset=0.0022,
                       n=90)
        for side in (1, -1):                         # Embleme: Kotflügel + C-Säule
            h = ctx.hit_side(1.20, 0.80, side)
            if h is not None:
                kit.emblem(ctx, h[0], h[1], d=0.045)
        cg = CabinGeo(b)
        for side in (1, -1):
            yz, zz = 1.30, -1.47
            x = cg.glass_x(zz, yz)
            nrm = np.array([side * 0.95, 0.3, 0.0])
            kit.emblem(ctx, np.array([side * (x + 0.002), yz, zz]), nrm, d=0.05)
    if lod < 2:
        kit.side_strip(ctx, 0.30, 1.20, -1.10, width=0.022, mat="Chrome", offset=0.002)
    # ---------------- Heck ----------------
    kit.lamp(ctx, TAIL, 0.62, 0.88, front=False, blend=0.6)
    kit.wordmark(ctx, 0.0, 0.79, 0.34, 0.053, rear=True)
    if lod < 2:
        kit.face_line(ctx, [(-0.40, 0.875), (0.40, 0.875)], rear=True, width=0.014, mat="Chrome", lift=0.003)
        kit.face_line(ctx, [(-0.80, 0.44), (0.80, 0.44)], rear=True, width=0.012, mat="Chrome", lift=0.003)
        kit.lamp(ctx, REFLECTOR, 0.72, 0.50, front=False, blend=0.6)
    if lod == 0:
        _trunk(ctx)
        kit.wiper(ctx, 0.56, -0.04, dz=0.07, pivots=[0.56])
        kit.wiper(ctx, 0.0, -0.58, dz=0.07, pivots=[0.0])
    # dritte Bremsleuchte innen an der Heckscheibe
    cg = CabinGeo(b)
    zb3 = -1.66
    ctx.part("Lights").box((0.0, cg.glass_y(zb3, 0.0) - 0.03, zb3 + 0.012), (0.30, 0.014, 0.012), "Brakelight")


def _trunk(ctx):
    """Fugen des Kofferraumdeckels auf der Heckfläche."""
    xg, y_lo, y_hi = 0.385, 0.60, 0.95
    for sx in (1, -1):
        kit.face_line(ctx, [(sx * xg, y_lo), (sx * xg, y_hi)], rear=True)
    kit.face_line(ctx, [(-xg, y_lo), (xg, y_lo)], rear=True)


def engine(ctx):
    lod = ctx.lod
    b = ctx.b
    sp = ctx.spec
    out = {}
    # Stufe 1: Haubenschlitze mit Chromrahmen
    s1 = Part("EngineStage_1")
    loc = kit.raised_vent_local(0.14, 0.26, 4, lod, frame_mat="Chrome", slat_mat="BlackGloss")
    place_top(ctx, loc, 0.36, 2.05, (0.14, 0.26), s1, mirror=True)
    out["EngineStage_1"] = s1
    # Stufe 2: Ladeluftkühler hinter dem unteren Einlass
    s2 = Part("EngineStage_2")
    hit = ctx.hit_front(0.0, 0.36)
    if hit is not None:
        zg = hit[0][2] - 0.05
        s2.rbox((0.0, 0.36, zg), (1.0, 0.085, 0.024), 0.006, "Aluminum", segs=1)
        if lod == 0:
            for k in range(22):
                s2.box((-0.48 + 0.96 * k / 21, 0.36, zg + 0.0125), (0.004, 0.08, 0.002), "EngineBlack")
    out["EngineStage_2"] = s2
    # Stufe 3: Black-Badge-Paket – Carbon-Frontlippe, -Schweller, -Diffusorleiste
    sub = type(ctx)(sp, lod, b, ctx.rc)
    kit.splitter(sub, 0.215, 2.30, out=0.04, inset=0.08, thick=0.014, mat="Carbon", part="S3")
    kit.side_skirt(sub, 0.215, 1.20, -1.08, out=0.03, thick=0.018, inset=0.05, mat="Carbon", part="S3")
    kit.rear_panel(sub, 0.0, 0.33, 1.30, 0.08, mat="Carbon", part="S3", r=0.03)
    if lod == 0:
        kit.diffuser_fins(sub, (0.36, 0.18, 0.0, -0.18, -0.36), b.zr + 0.04, 0.26, 0.245, 0.06, mat="Carbon",
                          part="S3")
    out["EngineStage_3"] = sub.part("S3")
    return out


# ======================================================================
# Innenraum
# ======================================================================

def deco(ck):
    from .. import deco as D
    p = Part("Deko")
    D.common(ck, p)
    D.champagne(ck, p)
    return p


SPEC.update({"details": details, "engine": engine, "deco": deco})
