"""Vektra GT – Mittelmotor-Supersportwagen (V8, Heckantrieb).

Design: flache, breite Keilform; die vorderen Kotflügel stehen über der
Haube, schmale gepfeilte LED-Scheinwerfer, große Seiteneinlässe vor den
Hinterrädern, der V8 liegt sichtbar unter der Heckscheibe.
Innen: Rennschalen, Carbon, Alcantara, rote Nähte, Flat-Bottom-Lenkrad
mit Schaltwippen, Tastenbrücke statt Wählhebel.
"""
from . import S, C

SPEC = {
    "id": "vektra_gt", "name": "Vektra GT", "node": "Vektra_GT",
    "desc": "Mittelmotor-Sportwagen mit V8, Heckantrieb, agil und präzise",
    "class": "Supersportwagen",
    "brand": {"mono": "V", "word": "VEKTRA", "caliper": "VEKTRA"},
    "plate": "VK 77", "number": "07",
    "deco_label": [("PIT PASS", 70), ("NEON GP", 46)],
    "palette": {
        "paint": "#c8102e", "accent": "#00e5ff", "rim": "#1d1f23", "caliper": "#f0b400",
        "seat": "#6e0f18", "insert": "alcantara", "insert_color": "#1b1c20", "stitch": "#d8d8d8",
        "trim": "carbon", "trim2": "pianoblack", "dash": "#121214", "door": "#151517",
        "headliner": "#18181b", "carpet": "#0c0c0d", "wheel_leather": "#121214", "wheel_grip": "insert",
        "ambient": "#ff3040", "marker": "#e01020", "cage": "#1a1a1d", "belt": "black", "grille": "black",
    },
    "stats": {"massKg": 1380, "powerKw": 470, "drive": "RWD", "topSpeedKmh": 325, "grip": 1.10,
              "suspension": "straff"},
    "physics": {
        "massKg": 1380, "cogHeight": 0.42, "weightFront": 0.42, "dragCd": 0.31, "frontalArea": 1.92,
        "powerKw": 470, "torqueNm": 700, "idleRpm": 950, "redlineRpm": 8500,
        "gears": [3.13, 2.19, 1.69, 1.35, 1.11, 0.92, 0.76], "finalDrive": 4.1,
        "suspension": {"springFront": 54000, "springRear": 61000, "damping": 0.42, "travel": 0.10,
                       "antiRollFront": 0.85, "antiRollRear": 0.7},
        "tire": {"grip": 1.10, "slipPeak": 0.09}, "brakeForce": 1.3, "brakeBias": 0.62, "steerLockDeg": 31,
    },
    "tuning": {
        "engine": [{"name": "Serie V8", "powerKw": 470, "torqueNm": 700},
                   {"name": "Carbon-Ansaugung", "powerKw": 500, "torqueNm": 735},
                   {"name": "Biturbo", "powerKw": 560, "torqueNm": 805},
                   {"name": "Race + Dachhutze", "powerKw": 610, "torqueNm": 845}],
        "exhaust": [{"name": "Serie", "loudness": 0}, {"name": "Sport (4 Rohre)", "loudness": 4},
                    {"name": "Race (Titan, mittig)", "loudness": 8}],
        "cage": [{"name": "Kein Käfig"}, {"name": "Halbkäfig", "massKg": 16, "stiffness": 1.05},
                 {"name": "Vollkäfig", "massKg": 30, "stiffness": 1.12}],
    },
    "rpm_max": 9, "gauge_vmax": 340, "steer_wheel_deg": 400,
    # --------------------------------------------------------------
    "wheels": {"front": {"z": 1.38, "R": 0.33, "W": 0.25}, "rear": {"z": -1.32, "R": 0.355, "W": 0.31}},
    "rim_ratio": 0.70, "tire": "sport", "wheel_out": -0.014, "caliper_angle": 125.0, "caliper_size": 1.1,
    "rims": [{"style": "split5", "n": 5, "label": "Y-Speiche"},
             {"style": "multi", "n": 10, "label": "Kreuzspeiche"},
             {"style": "aero", "n": 6, "concave": 0.03, "label": "Turbine"}],
    "max_lowering_cm": 3,
    "section": {"bw": 0.86, "lo": 0.20, "hi": 0.20, "tum": 0.985, "sh": 0.89, "crx": 0.44,
                "radii": [0.035, 0.06, 0.08, 0.05, 0.20], "dent_y": 0.50, "dent_h": 0.15},
    "nose_r": 0.06, "tail_r": 0.05,
    "body": [S(2.28, 0.50, 0.25, 0.36, 0.00), S(2.22, 0.70, 0.205, 0.42, 0.00),
             S(2.10, 0.84, 0.18, 0.50, -0.012), S(1.90, 0.925, 0.17, 0.60, -0.035),
             S(1.62, 0.962, 0.17, 0.705, -0.06), S(1.38, 0.966, 0.17, 0.745, -0.075),
             S(1.15, 0.95, 0.17, 0.72, -0.035), S(0.80, 0.925, 0.17, 0.675, 0.012),
             dict(S(0.20, 0.905, 0.17, 0.69, 0.03), sd=0.0), dict(S(-0.25, 0.94, 0.17, 0.735, 0.025), sd=0.035),
             dict(S(-0.62, 0.968, 0.17, 0.78, 0.015), sd=0.062), dict(S(-0.84, 0.978, 0.175, 0.81, 0.005), sd=0.0),
             S(-1.12, 0.985, 0.18, 0.84, -0.008), S(-1.60, 0.975, 0.19, 0.855, -0.03),
             S(-1.92, 0.93, 0.21, 0.85, -0.015), S(-2.10, 0.82, 0.25, 0.82, 0.0),
             S(-2.17, 0.66, 0.30, 0.77, 0.0)],
    "cabin": [C(1.15, 0.74, 0.68, -0.015, "ws"), C(0.48, 0.725, 0.56, 1.095, "ws"), C(0.24, 0.72, 0.52, 1.135, "ws"),
              C(-0.10, 0.725, 0.52, 1.148, "roof"), C(-0.27, 0.728, 0.524, 1.143, "roof"),
              C(-0.32, 0.73, 0.526, 1.139, "pillar"), C(-0.55, 0.735, 0.535, 1.118, "roof"),
              C(-0.80, 0.745, 0.56, 1.06, "rear"), C(-1.30, 0.76, 0.60, -0.03, "rear")],
    "pillar_frac": 0.24,
    "gaps": {"doors": [{"z": (1.02, -0.28), "y0": 0.30}],
             "lids": [{"z0": 1.28, "z1": 2.12, "x": 0.66, "cross": [2.10]}]},
    "plate_pos": {"front": 0.31, "rear": 0.47},
    "livery_skip_z": [(1.90, 2.06)],
    "spoiler": {"z": -2.06, "w": 0.80, "lip": (0.22, 0.065), "h2": 0.24, "h3": 0.40},
    "exhaust": {"y": 0.30, "protrude": 0.02,
                "variants": [[(0.13, 0.042, "round", "Chrome"), (-0.13, 0.042, "round", "Chrome")],
                             [(0.20, 0.036, "oval", "DarkChrome"), (0.31, 0.036, "oval", "DarkChrome"),
                              (-0.20, 0.036, "oval", "DarkChrome"), (-0.31, 0.036, "oval", "DarkChrome")],
                             [(0.085, 0.046, "round", "Titanium", 0.655), (-0.085, 0.046, "round", "Titanium", 0.655)]]},
    # --------------------------------------------------------------
    "interior": {
        "floor": 0.22, "fw": 1.28, "rb": -0.55, "hpt_z": -0.04, "seat_x": 0.34, "tunnel": 0.15,
        "bulkhead_glass": True,
        "dash": {"depth": 0.50, "clear": 0.06, "binnacle": 0.035, "stack": 0.05, "height": 0.20, "knee": 0.40,
                 "upper": "Dash"},
        "cluster": {"type": "digital", "w": 0.30, "h": 0.12},
        "center": {"type": "dash", "w": 0.22, "h": 0.13},
        "vents": (0.19, -0.19, 0.62, -0.62),
        "wheel": {"r": 0.175, "tilt": 20, "dist": 0.24, "drop": 0.12, "style": "flat", "grip": 0.017,
                  "marker": True, "marker_mat": "MarkerRed", "spokes": 3, "spoke_mat": "InteriorTrim",
                  "paddles": True},
        "console": {"back": 0.18, "h_front": 0.26, "h_back": 0.20, "w": 0.21, "shifter_t": 0.30,
                    "shifter": "buttons"},
        "seat_kind": "bucket", "recline": 24, "cushion_h": 0.10, "back_h": 0.64,
        "eye_dist": 0.62, "head_clear": 0.11, "eye_up": 0.30,
    },
}


# ======================================================================
# Außendetails
# ======================================================================
import math

import numpy as np

from .. import kit
from ..mesh import Part, rot_matrix, round_rect
from ..parts import rr_outline


def skin_mat(j, c, lod, b):
    x, y, z = c
    if z > b.zf - 0.16 and y < 0.212:                       # Frontlippe
        return "Carbon"
    return False


HEAD = {
    "w": 0.40, "h": 0.10, "depth": 0.07, "dome": 0.007, "lens": "LampGlass", "kind": "head",
    "shape": kit.rshape([(-0.20, -0.036), (0.17, -0.026), (0.20, 0.05), (-0.175, 0.03)], 0.016),
    "elements": [("projector", 0.055, 0.008, 0.022), ("projector", 0.122, 0.013, 0.020),
                 ("strip", [(-0.18, -0.019), (-0.02, -0.014), (0.155, -0.006), (0.18, 0.032)], 0.008, "DRL"),
                 ("strip", [(-0.15, 0.014), (-0.02, 0.019)], 0.006, "Indicator")],
}
TAIL = {
    "w": 0.52, "h": 0.062, "depth": 0.05, "dome": 0.004, "lens": "SmokeGlass", "kind": "tail",
    "shape": kit.rshape([(-0.26, -0.024), (0.235, -0.031), (0.26, 0.031), (-0.25, 0.026)], 0.012),
    "elements": [("strip", [(-0.24, 0.013), (0.215, 0.018), (0.238, -0.004), (0.215, -0.02), (-0.24, -0.013)], 0.008,
                  "Taillight"),
                 ("panel", kit.rshape([(-0.20, -0.006), (0.18, -0.009), (0.19, 0.006), (-0.20, 0.004)], 0.004),
                  "Brakelight"),
                 ("panel", kit.rshape([(-0.245, -0.009), (-0.215, -0.009), (-0.215, 0.008), (-0.245, 0.008)], 0.003),
                  "Reverse"),
                 ("strip", [(0.0, 0.022), (0.2, 0.026)], 0.004, "Indicator")],
}
LIGHTBAR = {
    "w": 0.60, "h": 0.016, "r": 0.006, "depth": 0.025, "dome": 0.002, "lens": "SmokeGlass", "kind": "tail",
    "elements": [("strip", [(-0.29, 0.0), (0.29, 0.0)], 0.006, "Taillight")],
}


def details(ctx):
    b = ctx.b
    lod = ctx.lod
    # ---------------- Front ----------------
    kit.lamp(ctx, HEAD, 0.60, 0.462, front=True, blend=0.35)
    kit.opening(ctx, kit.rshape([(-0.34, -0.068), (0.34, -0.068), (0.30, 0.064), (-0.30, 0.064)], 0.02),
                "front", 0.0, 0.292, depth=0.07, style="honeycomb", frame_mat="BlackGloss", cell=0.028)
    kit.opening(ctx, kit.rshape([(-0.12, -0.066), (0.16, -0.07), (0.15, 0.066), (-0.10, 0.058)], 0.018),
                "front", 0.63, 0.298, depth=0.07, style="honeycomb", frame_mat="BlackGloss", cell=0.024,
                mirror=True, blend=0.6)
    if lod < 2:
        kit.splitter(ctx, 0.186, 1.80, out=0.05, inset=0.10, thick=0.016)
    kit.louvres(ctx, 0.0, 1.98, 0.46, 0.13, 3, angle=40, mat="BlackGloss", frame_mat="BlackGloss")
    hit = ctx.hit_front(0.0, 0.43)
    if hit is not None:
        kit.emblem(ctx, hit[0], hit[1] * 0.6 + np.array([0, 0, 0.4]), d=0.07)
    # ---------------- Seite ----------------
    kit.opening(ctx, kit.rshape([(-0.23, -0.025), (0.19, -0.10), (0.23, 0.095), (-0.21, 0.05)], 0.03),
                "side", -0.60, 0.515, depth=0.12, style="hslats", frame_mat="BlackGloss", cell=0.045, mirror=True)
    kit.side_mirror(ctx, 0.93, 0.64, reach=0.12, rise=0.10, length=0.17, h=0.085, depth=0.12,
                    body_mat="Paint", cap_mat="Carbon", stalk_mat="BlackGloss")
    if lod == 0:
        kit.flush_handle(ctx, -0.07, 0.64, w=0.13, h=0.024)
    if lod < 2:
        kit.side_skirt(ctx, 0.192, 0.94, -0.86, out=0.022, thick=0.02, mat="Carbon")
    # ---------------- Heck ----------------
    kit.lamp(ctx, TAIL, 0.585, 0.768, front=False, blend=0.5)
    kit.lamp(ctx, LIGHTBAR, 0.0, 0.792, front=False, mirror=False, blend=0.5)
    kit.opening(ctx, rr_outline(0.96, 0.10, 0.02, 4), "rear", 0.0, 0.665, depth=0.08, style="honeycomb",
                frame_mat="BlackGloss", cell=0.03)
    kit.wordmark(ctx, 0.0, 0.567, 0.30, 0.042, rear=True)
    if lod < 2:
        kit.rear_panel(ctx, 0.0, 0.30, 1.42, 0.19, mat="Carbon")
        kit.diffuser_fins(ctx, (0.45, 0.63, -0.45, -0.63), b.zr + 0.01, 0.45, 0.185, 0.16)
        kit.lamp(ctx, {"w": 0.10, "h": 0.026, "r": 0.008, "depth": 0.02, "dome": 0.002, "lens": "TailGlass",
                       "kind": "fog", "elements": [("panel", rr_outline(0.08, 0.012, 0.004, 2), "Brakelight")]},
                 0.735, 0.305, front=False, blend=0.5)
    # ---------------- Oben ----------------
    kit.louvres(ctx, 0.0, -1.61, 0.78, 0.40, 6, angle=32)
    if lod == 0:
        kit.wiper(ctx, 0.40, -0.38, dz=0.07, pivots=[0.40])
    # ---------------- Motorraum (unter der Heckscheibe sichtbar) ----------------
    engine_base(ctx)


def engine_base(ctx):
    lod = ctx.lod
    if lod == 2:
        return
    p = ctx.part("Engine")
    kit.bay_box(p, 0.70, 0.27, 0.80, -0.57, -1.95, mat="EngineBlack")
    top = kit.v_engine(p, (0.0, 0.40, -1.16), 0.62, 4, bank_angle=90, cover_mat="EngineRed", lod=lod)
    if lod == 0:
        # Luftfilterkästen + Ansaugrohre
        for sx in (1, -1):
            box = np.array([sx * 0.47, 0.58, -0.98])
            p.rbox(box, (0.16, 0.14, 0.30), 0.04, "EngineBlack", segs=3)
            p.tube([box + np.array([-sx * 0.06, 0.02, -0.10]), np.array([sx * 0.2, 0.66, -1.3]),
                    np.array([sx * 0.06, top[1] - 0.02, -1.42])], 0.035, "EngineBlack", segs=12)
        # Domstrebe
        p.tube([np.array([0.62, 0.74, -1.56]), np.array([0.0, 0.76, -1.56]), np.array([-0.62, 0.74, -1.56])], 0.018,
               "Aluminum", segs=10)
        for sx in (1, -1):
            p.rbox((sx * 0.62, 0.74, -1.56), (0.08, 0.03, 0.10), 0.01, "Aluminum", segs=1)
        # Kühlwasser-/Öl-Behälter
        p.lathe([(0.0, 0.0), (0.0, 0.05), (0.12, 0.05), (0.13, 0.03), (0.13, 0.0)], 14, "DecoWhite",
                center=(0.42, 0.50, -1.70), axis="y", inside=(0.06, 0.02))
        p.lathe([(0.13, 0.0), (0.13, 0.025), (0.15, 0.022), (0.15, 0.0)], 14, "EngineRed",
                center=(0.42, 0.50, -1.70), axis="y", inside=(0.14, 0.01))


def engine(ctx):
    """Tuning-Stufen des Motors (sichtbar unter der Heckscheibe bzw. am Dach)."""
    lod = ctx.lod
    out = {}
    # Stufe 1: Carbon-Ansaugung
    s1 = Part("EngineStage_1")
    s1.rbox((0.0, 0.69, -1.16), (0.26, 0.05, 0.60), 0.03, "Carbon", segs=3)
    if lod == 0:
        s1.tex_quad((0.0, 0.7165, -1.16), (-1, 0, 0), (0, 0, 1), 0.16, 0.025, "Wordmark")
        for sx in (1, -1):
            s1.rbox((sx * 0.47, 0.655, -0.98), (0.165, 0.012, 0.305), 0.02, "Carbon", segs=2)
    out["EngineStage_1"] = s1
    # Stufe 2: Biturbo
    s2 = Part("EngineStage_2")
    for sx in (1, -1):
        kit.turbo(s2, (sx * 0.40, 0.46, -1.62), axis=(sx, 0, 0), r=0.07, lod=lod)
        if lod == 0:
            s2.tube([np.array([sx * 0.50, 0.46, -1.62]), np.array([sx * 0.56, 0.6, -1.4]),
                     np.array([sx * 0.50, 0.64, -1.10])], 0.03, "Aluminum", segs=10)
            s2.tube([np.array([sx * 0.30, 0.43, -1.62]), np.array([sx * 0.22, 0.36, -1.55])], 0.026, "Titanium", segs=8)
    out["EngineStage_2"] = s2
    # Stufe 3: Dachhutze + Ansaugschacht über die Heckscheibe
    s3 = Part("EngineStage_3")
    sub = type(ctx)(ctx.spec, lod, ctx.b, ctx.rc)
    kit.roof_scoop(sub, 0.06, -1.22, w=0.32, h=0.085, mat="Carbon", part="Scoop")
    s3.merge(sub.part("Scoop"))
    out["EngineStage_3"] = s3
    return out


SPEC.update({"skin_mat": skin_mat, "details": details, "engine": engine})


def deco(ck):
    from .. import deco as D
    p = Part("Deko")
    D.common(ck, p)
    D.helmet(ck, p)
    return p


SPEC["deco"] = deco
