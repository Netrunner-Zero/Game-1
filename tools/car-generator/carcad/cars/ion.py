"""Ion Spectre – Elektro-Hypercar (vier Motoren, Allrad).

Design: flach, sehr breit, tropfenförmige Glaskanzel mit Glasdach und
schwarzen Säulen ("schwebendes Dach"), durchgehendes Lichtband vorne und
hinten, kein Kühlergrill, Kameras statt Außenspiegeln, tiefe Seitensicken
mit Einlässen, Haifischflosse auf der Heckscheibe, riesiger Diffusor.
Unter der langen Heckscheibe sieht man den E-Antrieb (Motoren, Inverter,
orange Hochvoltleitungen, leuchtende Kühlleitungen).
Innen: Yoke-Lenkrad, schwebendes Mittel-Display, Tasten statt Wählhebel,
helles Leder mit Magenta-Nähten, Hologramm-Katze.
"""
import math

import numpy as np

from . import S, C
from .. import kit
from ..mesh import Part, rot_matrix, round_rect
from ..parts import rr_outline

SPEC = {
    "id": "ion_spectre", "name": "Ion Spectre", "node": "Ion_Spectre",
    "desc": "Elektro-Hypercar mit vier Motoren, Allrad, extreme Beschleunigung",
    "class": "Elektro-Hypercar",
    "brand": {"mono": "I", "word": "ION", "caliper": "ION"},
    "plate": "E 2077", "number": "01",
    "deco_label": [("ION", 90)],
    "palette": {
        "paint": "#e9edf3", "accent": "#ff2bd6", "rim": "#9aa1ab", "caliper": "#ff2bd6",
        "seat": "#d9dce2", "insert": "alcantara", "insert_color": "#2b2e36", "stitch": "#ff2bd6",
        "trim": "carbon", "trim2": "pianoblack", "dash": "#1a1c22", "door": "#d9dce2",
        "headliner": "#22252c", "carpet": "#121318", "wheel_leather": "#1a1c22", "wheel_grip": "insert",
        "ambient": "#ff2bd6", "marker": "#ff2bd6", "cage": "#202228", "belt": "black", "grille": "black",
    },
    "stats": {"massKg": 1850, "powerKw": 1100, "drive": "AWD", "topSpeedKmh": 350, "grip": 1.20,
              "suspension": "adaptiv"},
    "physics": {
        "massKg": 1850, "cogHeight": 0.38, "weightFront": 0.46, "dragCd": 0.28, "frontalArea": 1.98,
        "powerKw": 1100, "torqueNm": 2300, "idleRpm": 0, "redlineRpm": 20000, "electric": True,
        "gears": [1.0], "finalDrive": 8.2,
        "suspension": {"springFront": 50000, "springRear": 56000, "damping": 0.45, "travel": 0.11,
                       "antiRollFront": 0.8, "antiRollRear": 0.75, "adaptive": True},
        "tire": {"grip": 1.2, "slipPeak": 0.09}, "brakeForce": 1.4, "brakeBias": 0.58, "steerLockDeg": 30,
        "torqueVectoring": True,
    },
    "tuning": {
        "engine": [{"name": "Serie (4 Motoren)", "powerKw": 1100, "torqueNm": 2300},
                   {"name": "Overboost", "powerKw": 1250, "torqueNm": 2450},
                   {"name": "Track-Paket", "powerKw": 1350, "torqueNm": 2550},
                   {"name": "Hyper-Modus", "powerKw": 1500, "torqueNm": 2700}],
        "exhaust": [{"name": "Lautlos", "loudness": 0}, {"name": "Sound-Modul Synth", "loudness": 3},
                    {"name": "Sound-Modul Turbine", "loudness": 5}],
        "cage": [{"name": "Kein Käfig"}, {"name": "Halbkäfig", "massKg": 15, "stiffness": 1.04},
                 {"name": "Vollkäfig", "massKg": 28, "stiffness": 1.1}],
    },
    "rpm_max": 20, "gauge_vmax": 400, "steer_wheel_deg": 360,
    # --------------------------------------------------------------
    "wheels": {"front": {"z": 1.42, "R": 0.35, "W": 0.28}, "rear": {"z": -1.40, "R": 0.36, "W": 0.32}},
    "rim_ratio": 0.72, "tire": "sport", "wheel_out": -0.014, "caliper_angle": 110.0, "caliper_size": 1.15,
    "rims": [{"style": "aero", "n": 7, "concave": 0.03, "label": "Aero-Turbine"},
             {"style": "fine", "n": 14, "concave": 0.035, "label": "Vielspeiche"},
             {"style": "split5", "n": 5, "label": "Y-Speiche"}],
    "max_lowering_cm": 4,
    "section": {"bw": 0.84, "lo": 0.22, "hi": 0.22, "tum": 0.97, "sh": 0.86, "crx": 0.42,
                "radii": [0.04, 0.07, 0.10, 0.07, 0.24], "dent_y": 0.47, "dent_h": 0.14},
    "nose_r": 0.06, "tail_r": 0.05,
    "body": [S(2.36, 0.55, 0.22, 0.32, 0.0), S(2.28, 0.76, 0.18, 0.40, 0.0),
             S(2.10, 0.90, 0.15, 0.50, -0.012), S(1.80, 0.97, 0.14, 0.62, -0.04),
             S(1.42, 1.00, 0.14, 0.72, -0.07), S(1.05, 0.97, 0.14, 0.665, -0.03),
             S(0.60, 0.93, 0.14, 0.62, 0.03), dict(S(0.0, 0.925, 0.14, 0.64, 0.04), sd=0.035),
             dict(S(-0.55, 0.97, 0.14, 0.71, 0.03), sd=0.065), dict(S(-0.90, 1.0, 0.145, 0.77, 0.0), sd=0.0),
             S(-1.40, 1.02, 0.15, 0.80, -0.02), S(-1.90, 0.99, 0.17, 0.80, -0.01),
             S(-2.20, 0.90, 0.21, 0.76, 0.0), S(-2.32, 0.72, 0.27, 0.70, 0.0)],
    "cabin": [C(1.12, 0.74, 0.66, -0.015, "ws"), C(0.38, 0.72, 0.50, 1.075, "ws"), C(0.14, 0.72, 0.48, 1.10, "ws"),
              C(-0.10, 0.722, 0.48, 1.105, "glassroof"), C(-0.38, 0.728, 0.485, 1.095, "glassroof"),
              C(-0.42, 0.73, 0.49, 1.09, "pillar"), C(-0.75, 0.745, 0.52, 1.035, "rear"),
              C(-1.85, 0.77, 0.60, -0.02, "rear")],
    "pillar_frac": 0.24, "pillar_mat": "BlackGloss", "roof_mat": "BlackGloss", "bpillar_mat": "BlackGloss",
    "gaps": {"doors": [{"z": (1.00, -0.40), "y0": 0.24}],
             "lids": [{"z0": 1.30, "z1": 2.18, "x": 0.62, "cross": [2.16]}]},
    "plate_pos": {"front": 0.25, "rear": 0.44},
    "livery_skip_z": [(1.68, 1.98)],
    "spoiler": {"z": -2.14, "w": 0.84, "lip": (0.22, 0.06), "h2": 0.24, "h3": 0.40},
    "exhaust": {"y": 0.30, "protrude": 0.0,
                "variants": [[],
                             [("panel", 0.16, 0.30, 0.14, 0.022, "Accent")],
                             [("panel", 0.12, 0.30, 0.12, 0.02, "Accent"), ("panel", 0.30, 0.30, 0.12, 0.02, "Accent")]]},
    # --------------------------------------------------------------
    "interior": {
        "floor": 0.21, "fw": 1.22, "rb": -0.74, "hpt_z": -0.12, "seat_x": 0.35, "tunnel": 0.12,
        "bulkhead_glass": True,
        "dash": {"depth": 0.55, "clear": 0.06, "binnacle": 0.02, "stack": 0.02, "height": 0.18, "knee": 0.40,
                 "upper": "Dash"},
        "cluster": {"type": "digital", "w": 0.28, "h": 0.10},
        "center": {"type": "floating", "w": 0.32, "h": 0.17, "sink": 0.075},
        "vents": (0.62, -0.62),
        "wheel": {"r": 0.17, "tilt": 18, "dist": 0.24, "drop": 0.12, "style": "yoke", "grip": 0.018,
                  "marker": False, "spokes": 2, "spoke_mat": "Carbon", "paddles": True},
        "console": {"back": 0.14, "h_front": 0.24, "h_back": 0.20, "w": 0.22, "shifter_t": 0.32,
                    "shifter": "buttons"},
        "seat_kind": "bucket", "recline": 24, "cushion_h": 0.11, "back_h": 0.66,
        "eye_dist": 0.62, "head_clear": 0.10, "eye_up": 0.30,
    },
}


# ======================================================================
# Außendetails
# ======================================================================

HEAD = {"w": 0.38, "h": 0.064, "depth": 0.05, "dome": 0.004, "lens": "SmokeGlass", "kind": "head",
        "shape": kit.rshape([(-0.19, -0.02), (0.17, -0.032), (0.19, 0.03), (-0.18, 0.026)], 0.012),
        "elements": [("projector", 0.03, 0.0, 0.012), ("projector", 0.068, 0.0, 0.012), ("projector", 0.106, 0.0, 0.012),
                     ("strip", [(-0.15, -0.006), (0.155, -0.012)], 0.006, "DRL")]}
FRONT_BAR = {"w": 1.12, "h": 0.03, "r": 0.01, "depth": 0.02, "dome": 0.002, "lens": "SmokeGlass", "kind": "drl",
             "elements": [("strip", [(-0.54, 0.0), (0.54, 0.0)], 0.007, "DRL")]}
TAIL_BAR = {"w": 1.58, "h": 0.045, "r": 0.012, "depth": 0.03, "dome": 0.003, "lens": "SmokeGlass", "kind": "tail",
            "elements": [("strip", [(-0.77, 0.009), (0.77, 0.009)], 0.008, "Taillight"),
                         ("strip", [(-0.70, -0.009), (-0.30, -0.009)], 0.006, "Brakelight"),
                         ("strip", [(0.30, -0.009), (0.70, -0.009)], 0.006, "Brakelight"),
                         ("strip", [(-0.05, -0.01), (0.05, -0.01)], 0.006, "Reverse"),
                         ("strip", [(-0.77, -0.012), (-0.72, -0.012)], 0.006, "Indicator"),
                         ("strip", [(0.72, -0.012), (0.77, -0.012)], 0.006, "Indicator")]}


def skin_mat(j, c, lod, b):
    x, y, z = c
    if z > b.zf - 0.14 and y < 0.19:                        # schwarze Frontlippe
        return "Carbon"
    return False


def details(ctx):
    b = ctx.b
    lod = ctx.lod
    # ---------------- Front ----------------
    kit.lamp(ctx, HEAD, 0.64, 0.415, front=True, blend=0.4)
    kit.lamp(ctx, FRONT_BAR, 0.0, 0.392, front=True, mirror=False, blend=0.6)
    kit.opening(ctx, kit.rshape([(-0.17, -0.07), (0.17, -0.06), (0.16, 0.06), (-0.14, 0.055)], 0.02),
                "front", 0.66, 0.255, depth=0.08, style="honeycomb", frame_mat="Carbon", cell=0.024, mirror=True,
                blend=0.6)
    kit.opening(ctx, rr_outline(0.74, 0.07, 0.03, 4), "front", 0.0, 0.215, depth=0.06, style="hslats",
                frame_mat="Carbon", cell=0.02, blend=0.6)
    if lod < 2:
        kit.splitter(ctx, 0.152, 1.78, out=0.055, inset=0.1, thick=0.014)
    # Haube: zwei Aero-Tunnel (S-Duct)
    for x in (0.26, -0.26):
        kit.louvres(ctx, x, 1.83, 0.22, 0.26, 4, angle=38, mat="Carbon", frame_mat="BlackGloss")
    hit = ctx.hit_front(0.0, 0.36)
    if hit is not None:
        kit.emblem(ctx, hit[0], hit[1] * 0.5 + np.array([0, 0, 0.5]), d=0.06)
    # ---------------- Seite ----------------
    kit.opening(ctx, kit.rshape([(-0.20, -0.02), (0.17, -0.085), (0.20, 0.08), (-0.18, 0.045)], 0.03),
                "side", -0.74, 0.47, depth=0.12, style="honeycomb", frame_mat="Carbon", cell=0.03, mirror=True)
    kit.camera_mirror(ctx, 0.92, 0.62, reach=0.10)
    if lod == 0:
        kit.flush_handle(ctx, -0.15, 0.58, w=0.12, h=0.022, mat="BlackGloss")
    if lod < 2:
        kit.side_skirt(ctx, 0.16, 0.98, -0.95, out=0.03, thick=0.02, mat="Carbon", fence=0.025)
    # ---------------- Heck ----------------
    kit.lamp(ctx, TAIL_BAR, 0.0, 0.69, front=False, mirror=False, blend=0.6)
    kit.wordmark(ctx, 0.0, 0.615, 0.16, 0.05, rear=True)
    kit.opening(ctx, rr_outline(1.20, 0.08, 0.02, 4), "rear", 0.0, 0.54, depth=0.06, style="hslats",
                frame_mat="Carbon", cell=0.025)
    if lod < 2:
        kit.rear_panel(ctx, 0.0, 0.29, 1.56, 0.20, mat="Carbon")
        kit.diffuser_fins(ctx, (0.24, 0.42, 0.60, -0.24, -0.42, -0.60), b.zr + 0.01, 0.55, 0.165, 0.18)
    # ---------------- Oben ----------------
    kit.center_fin(ctx, -0.80, -2.18, 0.15, mat="Paint", edge="Accent")
    if lod == 0:
        kit.wiper(ctx, 0.36, -0.36, dz=0.08, pivots=[0.36])
    drive_base(ctx)


def drive_base(ctx):
    lod = ctx.lod
    if lod == 2:
        return
    p = ctx.part("Engine")
    kit.bay_box(p, 0.72, 0.24, 0.77, -0.76, -1.95, mat="EngineBlack")
    kit.e_drive(p, (0.0, 0.40, -1.40), lod=lod, glow="Accent", width=1.4)


def engine(ctx):
    """E-Stufen: Overboost (leuchtende Kühlung), Track-Paket (Canards), Hyper (große Flosse + Kühler)."""
    lod = ctx.lod
    out = {}
    s1 = Part("EngineStage_1")
    for sx in (1, -1):
        pts = [np.array([sx * 0.55, 0.36, -1.0]), np.array([sx * 0.50, 0.55, -1.15]), np.array([sx * 0.28, 0.66, -1.32])]
        s1.tube(pts, 0.014, "Accent", segs=8)
        s1.rbox((sx * 0.48, 0.52, -1.72), (0.16, 0.18, 0.06), 0.02, "Carbon", segs=2)
    out["EngineStage_1"] = s1
    sub = type(ctx)(ctx.spec, lod, ctx.b, ctx.rc)
    kit.canards(sub, 0.80, 0.30, size=0.14, mat="Carbon", part="S2")
    s2 = sub.part("S2")
    s2.rbox((0.0, 0.70, -1.40), (0.62, 0.03, 0.38), 0.02, "Carbon", segs=2)
    out["EngineStage_2"] = s2
    sub3 = type(ctx)(ctx.spec, lod, ctx.b, ctx.rc)
    kit.center_fin(sub3, -0.60, -2.20, 0.26, thick=0.016, mat="Carbon", edge="Accent", part="S3")
    s3 = sub3.part("S3")
    out["EngineStage_3"] = s3
    return out


def deco(ck):
    from .. import deco as D
    p = Part("Deko")
    D.common(ck, p)
    D.holo_cat(ck, p)
    return p


SPEC.update({"skin_mat": skin_mat, "details": details, "engine": engine, "deco": deco})
