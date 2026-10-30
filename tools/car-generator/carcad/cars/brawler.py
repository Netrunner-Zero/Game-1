"""Brawler 77 – Muscle Car im Stil der späten 70er (Restomod, V8, Heckantrieb).

Design: lange Haube mit Power-Dome, kurzes Heck, Fastback mit geschlossenen
C-Säulen, durchgehender Kühlergrill mit vier Rundscheinwerfern, verchromte
Stoßstangen, Chromleisten, Seitenmarkierungsleuchten, breite Hinterbacken.
Innen: analoge Rundinstrumente, Holz und Aluminium, Sportsitze mit
Karostoff, T-Griff-Schalthebel, Retro-Radio, 2+2-Rückbank.
"""
import math

import numpy as np

from . import S, C
from .. import kit
from ..mesh import Part, rot_matrix, round_rect
from ..parts import rr_outline

SPEC = {
    "id": "brawler_77", "name": "Brawler 77", "node": "Brawler_77",
    "desc": "Muscle Car mit großem V8, viel Drehmoment, neigt zum Driften",
    "class": "Muscle Car",
    "brand": {"mono": "B", "word": "BRAWLER", "caliper": "BRAWLER"},
    "plate": "BR 1977", "number": "77",
    "deco_label": [("MIXTAPE", 74), ("’77", 90)],
    "palette": {
        "paint": "#f5a300", "accent": "#ff3b1f", "rim": "#c9ccd2", "caliper": "#1d1f23",
        "seat": "#6b4126", "insert": "fabric", "fabric_tex": "fabric_check", "fabric_line": "#ff6a00",
        "stitch": "#e2c79a", "trim": "wood_walnut", "trim2": "aluminum", "dash": "#2a1d14", "door": "#5a3720",
        "headliner": "#cfc2aa", "carpet": "#33251a", "wheel_leather": "#2a1d14", "ambient": "#ff8a3a",
        "marker": "#c8102e", "cage": "#1a1a1d", "belt": "chrome", "grille": "black",
    },
    "stats": {"massKg": 1650, "powerKw": 450, "drive": "RWD", "topSpeedKmh": 290, "grip": 0.88,
              "suspension": "weich"},
    "physics": {
        "massKg": 1650, "cogHeight": 0.52, "weightFront": 0.55, "dragCd": 0.42, "frontalArea": 2.15,
        "powerKw": 450, "torqueNm": 820, "idleRpm": 750, "redlineRpm": 6600,
        "gears": [2.97, 2.07, 1.43, 1.0, 0.84, 0.56], "finalDrive": 3.55,
        "suspension": {"springFront": 32000, "springRear": 30000, "damping": 0.30, "travel": 0.14,
                       "antiRollFront": 0.6, "antiRollRear": 0.35},
        "tire": {"grip": 0.88, "slipPeak": 0.11, "rearGripFactor": 0.92}, "brakeForce": 1.0, "brakeBias": 0.6,
        "steerLockDeg": 34,
    },
    "tuning": {
        "engine": [{"name": "Serie V8", "powerKw": 450, "torqueNm": 820},
                   {"name": "Ram-Air-Hutze", "powerKw": 480, "torqueNm": 860},
                   {"name": "Kompressor", "powerKw": 580, "torqueNm": 980},
                   {"name": "Shotgun + Lachgas", "powerKw": 660, "torqueNm": 1080}],
        "exhaust": [{"name": "Serie (Doppelrohr)", "loudness": 2}, {"name": "Sport (4 Rohre)", "loudness": 5},
                    {"name": "Sidepipes", "loudness": 9}],
        "cage": [{"name": "Kein Käfig"}, {"name": "Halbkäfig", "massKg": 18, "stiffness": 1.06},
                 {"name": "Vollkäfig", "massKg": 34, "stiffness": 1.14}],
    },
    "rpm_max": 8, "gauge_vmax": 300, "steer_wheel_deg": 540,
    # --------------------------------------------------------------
    "wheels": {"front": {"z": 1.50, "R": 0.34, "W": 0.255}, "rear": {"z": -1.42, "R": 0.355, "W": 0.315}},
    "rim_ratio": 0.66, "tire": "sport", "wheel_out": -0.016, "caliper_angle": 120.0, "caliper_size": 1.0,
    "rims": [{"style": "classic5", "n": 5, "concave": 0.05, "label": "Klassik 5-Speiche"},
             {"style": "multi", "n": 8, "label": "Kreuzspeiche"},
             {"style": "mesh", "n": 10, "label": "Gitter"}],
    "max_lowering_cm": 5,
    "section": {"bw": 0.90, "lo": 0.12, "hi": 0.10, "tum": 1.0, "sh": 0.945, "crx": 0.5,
                "radii": [0.03, 0.04, 0.045, 0.028, 0.25]},
    "nose_r": 0.035, "tail_r": 0.035,
    "body": [S(2.42, 0.90, 0.30, 0.76, 0.00), S(2.36, 0.95, 0.25, 0.80, 0.01),
             S(2.10, 0.975, 0.21, 0.835, 0.024), S(1.50, 0.985, 0.21, 0.86, 0.03),
             S(0.70, 0.98, 0.21, 0.875, 0.035), S(0.00, 0.975, 0.21, 0.88, 0.035),
             S(-0.80, 0.99, 0.21, 0.89, 0.03), S(-1.42, 1.005, 0.21, 0.905, 0.025),
             S(-2.05, 0.99, 0.22, 0.915, 0.015), S(-2.34, 0.95, 0.25, 0.90, 0.0),
             S(-2.40, 0.90, 0.30, 0.86, 0.0)],
    "cabin": [C(0.64, 0.84, 0.80, -0.02, "ws"), C(0.22, 0.835, 0.72, 1.24, "ws"), C(0.02, 0.832, 0.69, 1.30, "ws"),
              C(-0.30, 0.835, 0.68, 1.315, "roof"), C(-0.62, 0.84, 0.68, 1.305, "roof"),
              C(-0.66, 0.84, 0.68, 1.30, "pillar"), C(-0.92, 0.845, 0.69, 1.25, "roof"),
              C(-1.20, 0.85, 0.71, 1.15, "rear"), C(-1.92, 0.86, 0.76, -0.025, "rear")],
    "pillar_frac": 0.24, "rear_side": "paint", "bpillar_mat": "Chrome",
    "gaps": {"doors": [{"z": (0.60, -0.66), "y0": 0.32}],
             "lids": [{"z0": 0.78, "z1": 2.30, "x": 0.80, "cross": [2.28]},
                      {"z0": -2.30, "z1": -1.98, "x": 0.78, "cross": [-1.99]}]},
    "plate_pos": {"front": 0.285, "rear": 0.56},
    "spoiler": {"z": -2.30, "w": 0.86, "lip": (0.24, 0.075), "h2": 0.22, "h3": 0.38},
    "exhaust": {"y": 0.27, "protrude": 0.03,
                "variants": [[(0.60, 0.042, "round", "Chrome"), (-0.60, 0.042, "round", "Chrome")],
                             [(0.52, 0.04, "round", "Chrome"), (0.65, 0.04, "round", "Chrome"),
                              (-0.52, 0.04, "round", "Chrome"), (-0.65, 0.04, "round", "Chrome")],
                             [("side", -0.90, 0.27, 0.05, "Chrome")]]},
    "livery_labels": ["Rennstreifen", "Seitenblitz", "Startnummer"],
    # --------------------------------------------------------------
    "interior": {
        "floor": 0.30, "fw": 1.08, "rb": -1.70, "hpt_z": -0.58, "seat_x": 0.38, "tunnel": 0.17,
        "shelf": (-1.70, -1.94, 0.92), "shelf_mat": "Carpet", "rear_wall_top": 0.92,
        "dash": {"depth": 0.52, "clear": 0.07, "binnacle": 0.05, "stack": 0.04, "height": 0.24, "knee": 0.40,
                 "upper": "Dash"},
        "cluster": {"type": "analog", "w": 0.34, "h": 0.15},
        "center": {"type": "retro", "w": 0.18, "h": 0.06},
        "vents": (0.62, -0.62),
        "wheel": {"r": 0.195, "tilt": 22, "dist": 0.26, "drop": 0.13, "style": "round", "grip": 0.0135,
                  "marker": False, "spokes": 3, "spoke_mat": "Aluminum", "paddles": False},
        "console": {"back": 0.30, "h_front": 0.26, "h_back": 0.20, "w": 0.24, "shifter_t": 0.40,
                    "shifter": "t_handle"},
        "seat_kind": "sport", "recline": 22, "cushion_h": 0.14, "back_h": 0.66,
        "rear": {"type": "bench", "z": -1.30, "recline": 26, "back_h": 0.48, "headrest": False},
        "eye_dist": 0.64, "head_clear": 0.12, "eye_up": 0.30,
    },
}


# ======================================================================
# Außendetails
# ======================================================================

HEAD = {"w": 0.15, "h": 0.15, "r": 0.075, "depth": 0.07, "dome": 0.014, "lens": "LampGlass", "kind": "head",
        "elements": [("bowl", 0.0, 0.0, 0.062, 0.05)], "bezel": (0.012, "Chrome")}
TAIL = {"w": 0.56, "h": 0.125, "r": 0.02, "depth": 0.05, "dome": 0.004, "lens": "TailGlass", "kind": "tail",
        "elements": [("panel", rr_outline(0.50, 0.08, 0.012, 3), "Taillight"),
                     ("panel", rr_outline(0.30, 0.05, 0.01, 2), "Brakelight"),
                     ("panel", [(-0.26, -0.03), (-0.20, -0.03), (-0.20, 0.03), (-0.26, 0.03)], "Reverse")],
        "bezel": (0.014, "Chrome")}
INDICATOR = {"w": 0.16, "h": 0.05, "r": 0.012, "depth": 0.025, "dome": 0.003, "lens": "LampGlass", "kind": "indicator",
             "elements": [("panel", rr_outline(0.14, 0.035, 0.01, 2), "Indicator")], "bezel": (0.008, "Chrome")}


def details(ctx):
    b = ctx.b
    lod = ctx.lod
    # ---------------- Front ----------------
    kit.opening(ctx, rr_outline(1.56, 0.22, 0.03, 4), "front", 0.0, 0.635, depth=0.08, style="eggcrate",
                frame_mat="Chrome", mesh_mat="Mesh", cell=0.055, frame_w=0.014, blend=0.75)
    for x in (0.70, 0.52):
        kit.lamp(ctx, HEAD, x, 0.635, front=True, blend=0.8)
    kit.lamp(ctx, INDICATOR, 0.58, 0.30, front=True, blend=0.6)
    hit = ctx.hit_front(0.0, 0.635)
    if hit is not None:
        kit.emblem(ctx, hit[0] + np.array([0, 0, 0.02]), np.array([0, 0, 1.0]), d=0.085)
    if lod < 2:
        kit.bumper(ctx, 0.42, 2.02, h=0.085, out=0.055, thick=0.06, front=True)
        kit.splitter(ctx, 0.215, 2.05, out=0.02, inset=0.06, thick=0.014, mat="Trim")
    kit.hood_bulge(ctx, 0.92, 2.08, 0.58, 0.028)
    # ---------------- Seite ----------------
    kit.side_lamp(ctx, 2.08, 0.56, 0.09, 0.035, mat="Indicator", lens="LampGlass")
    kit.side_lamp(ctx, -2.10, 0.60, 0.09, 0.035, mat="Taillight", lens="TailGlass", kind="tail")
    kit.side_mirror(ctx, 0.50, 0.80, reach=0.07, rise=0.09, length=0.10, h=0.075, depth=0.11,
                    body_mat="Chrome", stalk_mat="Chrome", indicator=False, stalk_w=0.035)
    if lod == 0:
        kit.pull_handle(ctx, -0.48, 0.76, w=0.15, h=0.03)
        # Chromleiste unten an der Flanke (Zierleiste)
        for side in (1, -1):
            samples = [(z, b.j_at_height(z, 0.33, side)) for z in np.linspace(1.05, -0.95, 30)]
            b.strip(ctx.part("Trim"), samples, 0.012, "Chrome", offset=0.002)
        # Tankdeckel hinten links
        hitf = ctx.hit_side(-1.85, 0.74, 1)
        if hitf is not None:
            loc = Part("cap")
            loc.lathe([(0.0, 0.0), (0.0, 0.045), (0.004, 0.044), (0.006, 0.0)], 24, "Chrome", center=(0, 0, 0),
                      axis="z", inside=(0.002, 0.02))
            kit.place_flat(ctx, loc, hitf[0], hitf[1], (0.1, 0.1), ctx.part("Trim"), lift=0.0)
    # ---------------- Heck ----------------
    kit.lamp(ctx, TAIL, 0.56, 0.715, front=False, blend=0.8)
    kit.wordmark(ctx, 0.0, 0.725, 0.32, 0.05, rear=True)
    if lod < 2:
        kit.bumper(ctx, 0.42, -2.02, h=0.085, out=0.055, thick=0.06, front=False)
    # ---------------- Oben ----------------
    if lod == 0:
        kit.wiper(ctx, 0.62, 0.06, dz=0.07, pivots=[0.62])
        kit.wiper(ctx, -0.02, -0.56, dz=0.07, pivots=[-0.02])


def engine(ctx):
    """Motorstufen: Hutze (1), Kompressor durch die Haube (2), Shotgun-Hutzen (3)."""
    lod = ctx.lod
    out = {}
    sub = type(ctx)(ctx.spec, lod, ctx.b, ctx.rc)
    kit.hood_scoop(sub, 0.98, 1.36, 0.42, 0.075, mat="BlackGloss", inner="Mesh", part="S1", open_front=False)
    out["EngineStage_1"] = sub.part("S1")
    s2 = Part("EngineStage_2")
    hit = ctx.hit_top(0.0, 1.62)
    y0 = hit[0][1] + 0.028 if hit is not None else 0.92
    kit.blower(s2, (0.0, y0 - 0.02, 1.64), length=0.38, width=0.30, height=0.17, lod=lod, hat=True)
    # Ausschnitt-Rand in der Haube
    s2.rbox((0.0, y0 - 0.012, 1.64), (0.40, 0.02, 0.48), 0.03, "EngineBlack", segs=2)
    out["EngineStage_2"] = s2
    s3 = Part("EngineStage_3")
    kit.shotgun_scoops(s3, (0.0, y0 + 0.30, 1.66), spread=0.075, length=0.34, r=0.052, lod=lod)
    if lod == 0:
        for (x, z) in ((0.70, 2.25), (-0.70, 2.25), (0.70, 0.96), (-0.70, 0.96)):      # Haubenstifte
            h = ctx.hit_top(x, z)
            if h is not None:
                s3.lathe([(0.0, 0.0), (0.0, 0.016), (0.006, 0.014), (0.008, 0.0)], 12, "Chrome",
                         center=tuple(h[0]), axis="y", inside=(0.003, 0.004))
    out["EngineStage_3"] = s3
    return out


def deco(ck):
    from .. import deco as D
    p = Part("Deko")
    D.common(ck, p)
    D.dice(ck, p)
    D.cassette(ck, p)
    return p


SPEC.update({"details": details, "engine": engine, "deco": deco})
