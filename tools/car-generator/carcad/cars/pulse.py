"""Pulse – Kompaktsportler (Hot Hatch), Frontantrieb, Turbo-Vierzylinder, drei Türen.

Design: kurze Überhänge, breite Radhäuser, schmale LED-Scheinwerfer, die über ein
durchgehendes Lichtband verbunden sind, schmaler Wabengrill mit Akzentlinie, großer
Lufteinlass mit seitlichen Luftvorhängen, lackierte C-Säule, Dachspoiler (ab Werk),
Heckklappe mit Lichtband, Heckwischer, Diffusor mit Endrohren.
Innen: Sportsitze mit Karostoff (Limettenlinien), Flat-Bottom-Lenkrad, digitale
Instrumente, schwebender Bildschirm, Schaltknauf mit Schaltschema-Deckel.
Easter Eggs: Kaffeebecher im Halter, Blitz-Lufterfrischer, Wackel-Katze.
"""
import math

import numpy as np

from . import S, C
from .. import kit
from ..mesh import Part, rot_matrix, round_rect
from ..parts import rr_outline, decal_local, place_front, place_side, place_top, strip2d
from ..interior import CabinGeo

SPEC = {
    "id": "pulse", "name": "Pulse", "node": "Pulse",
    "desc": "Kompaktsportler mit Turbo und Frontantrieb, leicht, wendig und frech",
    "class": "Hot Hatch",
    "brand": {"mono": "P", "word": "PULSE", "caliper": "PULSE"},
    "plate": "PL 2049", "number": "24",
    "deco_label": [("NIGHT SHIFT", 66), ("COFFEE", 74)],
    "palette": {
        "paint": "#1f6fff", "accent": "#b6ff00", "rim": "#1d1f23", "caliper": "#b6ff00",
        "seat": "#18191c", "insert": "fabric", "fabric_tex": "fabric_check", "fabric_line": "#b6ff00",
        "stitch": "#b6ff00", "trim": "pianoblack", "trim2": "carbon", "dash": "#141518", "door": "#18191c",
        "headliner": "#2b2c30", "carpet": "#0f1012", "wheel_leather": "#141518", "ambient": "#b6ff00",
        "marker": "#b6ff00", "cage": "#1a1a1d", "belt": "black", "grille": "black",
    },
    "stats": {"massKg": 1250, "powerKw": 235, "drive": "FWD", "topSpeedKmh": 265, "grip": 1.0,
              "suspension": "straff"},
    "physics": {
        "massKg": 1250, "cogHeight": 0.50, "weightFront": 0.62, "dragCd": 0.32, "frontalArea": 2.20,
        "powerKw": 235, "torqueNm": 420, "idleRpm": 850, "redlineRpm": 7000,
        "gears": [3.36, 2.09, 1.47, 1.10, 0.87, 0.71], "finalDrive": 4.2, "manual": True,
        "suspension": {"springFront": 46000, "springRear": 38000, "damping": 0.40, "travel": 0.12,
                       "antiRollFront": 0.7, "antiRollRear": 0.8},
        "tire": {"grip": 1.0, "slipPeak": 0.10}, "brakeForce": 1.1, "brakeBias": 0.66, "steerLockDeg": 35,
        "frontDiffLock": 0.35, "torqueSteer": 0.12,
    },
    "tuning": {
        "engine": [{"name": "Serie 2.0 Turbo", "powerKw": 235, "torqueNm": 420},
                   {"name": "Kaltluft + Haubenschlitze", "powerKw": 250, "torqueNm": 450},
                   {"name": "Großer Turbo + Ladeluftkühler", "powerKw": 290, "torqueNm": 520},
                   {"name": "Rallye-Paket (Dachhutze, Zusatzlicht, Schmutzfänger)", "powerKw": 315, "torqueNm": 560}],
        "exhaust": [{"name": "Serie (2 Rohre)", "loudness": 2}, {"name": "Sport (4 Rohre)", "loudness": 5},
                    {"name": "Mittig (3 Rohre)", "loudness": 8}],
        "cage": [{"name": "Kein Käfig"}, {"name": "Halbkäfig", "massKg": 15, "stiffness": 1.06},
                 {"name": "Vollkäfig", "massKg": 28, "stiffness": 1.14}],
    },
    "default_tuning": {"spoiler": 1},
    "rpm_max": 8, "gauge_vmax": 300, "steer_wheel_deg": 460,
    # --------------------------------------------------------------
    "wheels": {"front": {"z": 1.30, "R": 0.33, "W": 0.235}, "rear": {"z": -1.24, "R": 0.33, "W": 0.235}},
    "rim_ratio": 0.70, "tire": "sport", "wheel_out": -0.008, "caliper_angle": 125.0, "caliper_size": 1.0,
    "arch_gap": 0.04, "flare": (0.022, 0.045),
    "rims": [{"style": "split5", "n": 5, "label": "Y-Speiche"},
             {"style": "multi", "n": 10, "label": "Kreuzspeiche"},
             {"style": "classic5", "n": 5, "concave": 0.03, "label": "Rallye 5"}],
    "max_lowering_cm": 4,
    "section": {"bw": 0.84, "lo": 0.18, "hi": 0.20, "tum": 0.988, "sh": 0.895, "crx": 0.45,
                "radii": [0.035, 0.05, 0.022, 0.05, 0.20]},
    "nose_r": 0.012, "tail_r": 0.012,
    "body": [S(2.25, 0.52, 0.30, 0.50, 0.0), S(2.24, 0.66, 0.255, 0.585, 0.0),
             S(2.22, 0.76, 0.225, 0.655, 0.0), S(2.185, 0.825, 0.20, 0.715, 0.0),
             S(2.13, 0.865, 0.182, 0.765, 0.006), S(2.05, 0.888, 0.17, 0.795, 0.014),
             S(1.90, 0.905, 0.16, 0.825, 0.024), S(1.75, 0.914, 0.155, 0.845, 0.03),
             S(1.30, 0.924, 0.15, 0.89, 0.035), S(0.94, 0.905, 0.15, 0.915, 0.035),
             S(0.30, 0.89, 0.15, 0.948, 0.03), S(-0.44, 0.893, 0.15, 0.97, 0.025),
             S(-1.00, 0.915, 0.155, 0.985, 0.02), S(-1.24, 0.934, 0.16, 0.99, 0.015),
             S(-1.60, 0.918, 0.18, 0.99, 0.008), S(-1.86, 0.88, 0.205, 0.982, 0.0),
             S(-1.93, 0.86, 0.225, 0.965, 0.0), S(-1.98, 0.83, 0.245, 0.93, 0.0),
             S(-2.01, 0.80, 0.262, 0.87, 0.0), S(-2.035, 0.76, 0.28, 0.75, 0.0),
             S(-2.05, 0.70, 0.30, 0.60, 0.0), S(-2.058, 0.60, 0.33, 0.50, 0.0)],
    "cabin": [C(0.94, 0.80, 0.74, -0.015, "ws"), C(0.52, 0.795, 0.69, 1.21, "ws"), C(0.14, 0.79, 0.645, 1.405, "ws"),
              C(0.02, 0.79, 0.635, 1.435, "roof"), C(-0.36, 0.795, 0.635, 1.45, "roof"),
              C(-0.44, 0.80, 0.635, 1.45, "pillar"), C(-1.16, 0.808, 0.635, 1.438, "roof"),
              C(-1.42, 0.80, 0.63, 1.418, "cpillar"), C(-1.88, 0.77, 0.62, -0.02, "rear")],
    "pillar_frac": 0.22, "rear_side": "paint", "bpillar_mat": "BlackGloss",
    "gaps": {"doors": [{"z": (0.80, -0.42), "y0": 0.25}],
             "lids": [{"z0": 1.00, "z1": 2.10, "x": 0.78, "cross": [1.01, 2.09]}]},
    "plate_pos": {"front": 0.40, "front_out": 0.008, "rear": 0.69},
    "livery_skip_z": [],
    "spoiler": {"z": -1.42, "w": 0.62, "lip": (0.16, 0.03), "over": 0.14, "h2": 0.07, "h3": 0.16, "roof": True},
    "spoiler_labels": ["Dachspoiler", "Rallye-Dachflügel", "Cyber-Dachflügel"],
    "exhaust": {"y": 0.33, "protrude": 0.02,
                "variants": [[(0.52, 0.042, "round", "Chrome"), (-0.52, 0.042, "round", "Chrome")],
                             [(0.46, 0.038, "round", "DarkChrome"), (0.575, 0.038, "round", "DarkChrome"),
                              (-0.46, 0.038, "round", "DarkChrome"), (-0.575, 0.038, "round", "DarkChrome")],
                             [(0.105, 0.042, "round", "Titanium"), (0.0, 0.032, "round", "Titanium"),
                              (-0.105, 0.042, "round", "Titanium")]]},
    # --------------------------------------------------------------
    "interior": {
        "floor": 0.25, "fw": 0.98, "rb": -1.92, "hpt_z": -0.24, "seat_x": 0.37, "driver_x": 0.36, "tunnel": 0.12,
        "dash": {"depth": 0.60, "clear": 0.06, "binnacle": 0.04, "stack": 0.05, "height": 0.11, "knee": 0.40,
                 "upper": "Dash"},
        "cluster": {"type": "digital", "w": 0.28, "h": 0.11},
        "center": {"type": "floating", "w": 0.30, "h": 0.17, "sink": 0.07},
        "vents": (0.19, -0.19, 0.60, -0.60),
        "wheel": {"r": 0.178, "tilt": 22, "dist": 0.24, "drop": 0.12, "style": "flat", "grip": 0.018,
                  "marker": True, "marker_mat": "MarkerRed", "spokes": 3, "spoke_mat": "InteriorTrim", "paddles": False},
        "console": {"back": 0.22, "h_front": 0.26, "h_back": 0.20, "w": 0.20, "shifter_t": 0.42, "shifter": "sport",
                    "knob": "DecoWhite", "knob_top": "EngineBlack", "knob_ring": "Accent"},
        "seat_kind": "sport", "recline": 22, "cushion_h": 0.12, "back_h": 0.66,
        "rear": {"type": "bench", "z": -0.98, "recline": 26, "back_h": 0.56, "headrest": True},
        "rear_cushion_h": 0.18,
        "eye_dist": 0.62, "head_clear": 0.10, "eye_up": 0.36,
    },
}


# ======================================================================
# Außendetails
# ======================================================================

HEAD = {
    "w": 0.37, "h": 0.10, "depth": 0.075, "dome": 0.007, "lens": "LampGlass", "kind": "head",
    "shape": kit.rshape([(-0.185, -0.034), (0.155, -0.046), (0.185, 0.044), (-0.175, 0.034)], 0.015),
    "elements": [("projector", 0.045, -0.006, 0.025), ("projector", 0.108, -0.009, 0.023),
                 ("strip", [(-0.17, 0.018), (0.0, 0.023), (0.17, 0.030)], 0.008, "DRL"),
                 ("strip", [(-0.155, -0.019), (-0.03, -0.023)], 0.006, "Indicator")],
}
FRONT_BAR = {"w": 0.84, "h": 0.012, "r": 0.005, "depth": 0.02, "dome": 0.002, "lens": "LampGlass", "kind": "drl",
             "elements": [("strip", [(-0.41, 0.0), (0.41, 0.0)], 0.005, "DRL")]}
TAIL = {
    "w": 0.27, "h": 0.10, "depth": 0.06, "dome": 0.005, "lens": "SmokeGlass", "kind": "tail",
    "shape": kit.rshape([(-0.135, -0.040), (0.12, -0.046), (0.135, 0.046), (-0.125, 0.034)], 0.014),
    "elements": [("strip", [(-0.12, 0.020), (0.10, 0.030), (0.118, 0.0), (0.10, -0.030), (-0.12, -0.026)], 0.008,
                  "Taillight"),
                 ("panel", kit.rshape([(-0.09, -0.012), (0.08, -0.016), (0.085, 0.014), (-0.09, 0.010)], 0.005),
                  "Brakelight"),
                 ("strip", [(-0.115, -0.036), (0.06, -0.040)], 0.005, "Indicator"),
                 ("panel", kit.rshape([(-0.12, -0.010), (-0.102, -0.010), (-0.102, 0.008), (-0.12, 0.008)], 0.003),
                  "Reverse")],
}
LIGHTBAR = {"w": 0.84, "h": 0.012, "r": 0.005, "depth": 0.02, "dome": 0.002, "lens": "SmokeGlass", "kind": "tail",
            "elements": [("strip", [(-0.41, 0.0), (0.41, 0.0)], 0.005, "Taillight")]}
FOG = {"w": 0.11, "h": 0.024, "r": 0.008, "depth": 0.02, "dome": 0.002, "lens": "LampGlass", "kind": "fog",
       "elements": [("panel", rr_outline(0.095, 0.012, 0.005, 2), "Headlight")]}
REFLECTOR = {"w": 0.10, "h": 0.022, "r": 0.008, "depth": 0.015, "dome": 0.002, "lens": "TailGlass", "kind": "marker",
             "elements": [("panel", rr_outline(0.085, 0.012, 0.004, 2), "Taillight")]}


def details(ctx):
    b = ctx.b
    lod = ctx.lod
    # ---------------- Front ----------------
    kit.lamp(ctx, HEAD, 0.62, 0.645, front=True, blend=0.5)
    kit.lamp(ctx, FRONT_BAR, 0.0, 0.645, front=True, mirror=False, blend=0.5)
    kit.opening(ctx, kit.rshape([(-0.40, -0.026), (0.40, -0.026), (0.38, 0.026), (-0.38, 0.026)], 0.012),
                "front", 0.0, 0.598, depth=0.05, style="honeycomb", frame_mat="BlackGloss", cell=0.022, blend=0.5)
    # Akzentlinie unter dem Grill
    place_front(ctx, decal_local(0.74, 0.0065, "Accent", wv=0.0016), 0.0, 0.566, (0.74, 0.0065), ctx.part("Badges"),
                normal_blend=0.5)
    hit = ctx.hit_front(0.0, 0.598)
    if hit is not None:
        kit.emblem(ctx, hit[0] + np.array([0, 0, 0.006]), hit[1] * 0.5 + np.array([0, 0, 0.5]), d=0.062)
    # großer Lufteinlass + Luftvorhänge in den Ecken
    kit.opening(ctx, kit.rshape([(-0.50, -0.105), (0.50, -0.105), (0.43, 0.105), (-0.43, 0.105)], 0.03),
                "front", 0.0, 0.40, depth=0.08, style="honeycomb", frame_mat="BlackGloss", cell=0.032, blend=0.6)
    kit.opening(ctx, kit.rshape([(-0.045, -0.085), (0.04, -0.09), (0.045, 0.085), (-0.04, 0.075)], 0.012),
                "front", 0.70, 0.34, depth=0.06, style="hslats", frame_mat="BlackGloss", cell=0.03, mirror=True,
                blend=0.7)
    kit.lamp(ctx, FOG, 0.69, 0.47, front=True, blend=0.6)
    if lod < 2:
        kit.splitter(ctx, 0.165, 1.90, out=0.035, inset=0.08, thick=0.014, mat="BlackGloss")
    kit.hood_bulge(ctx, 1.06, 2.00, 0.70, 0.008, ramp_u=0.45, ramp_v=0.4)
    # ---------------- Seite ----------------
    kit.side_mirror(ctx, 0.84, 0.905, reach=0.11, rise=0.09, length=0.165, h=0.095, depth=0.11,
                    body_mat="Paint", cap_mat="BlackGloss", stalk_mat="BlackGloss")
    if lod == 0:
        kit.flush_handle(ctx, -0.26, 0.905, w=0.13, h=0.024, mat="BlackGloss")
        kit.side_badge(ctx, 1.02, 0.74, 0.11, 0.0172)
        # Tankklappe rechts
        loc = Part("flap")
        ring = [(0.062 * math.cos(a), 0.062 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 33)]
        strip2d(loc, ring, 0.0042, 0.0012, "Gap", thick=0.001)
        place_side(ctx, loc, -1.46, 0.83, (0.14, 0.14), ctx.part("Trim"), mirror=False, side=-1)
    if lod < 2:
        kit.side_skirt(ctx, 0.17, 0.86, -0.80, out=0.022, thick=0.02, inset=0.05, mat="BlackGloss")
    # ---------------- Heck ----------------
    kit.lamp(ctx, TAIL, 0.60, 0.845, front=False, blend=0.55)
    kit.lamp(ctx, LIGHTBAR, 0.0, 0.85, front=False, mirror=False, blend=0.5)
    kit.wordmark(ctx, 0.0, 0.795, 0.24, 0.0375, rear=True)
    if lod < 2:
        kit.rear_panel(ctx, 0.0, 0.33, 1.22, 0.15, mat="BlackGloss", r=0.04)
        kit.diffuser_fins(ctx, (0.30, 0.17, -0.17, -0.30), b.zr + 0.03, 0.22, 0.20, 0.05, mat="BlackGloss")
        kit.lamp(ctx, REFLECTOR, 0.72, 0.42, front=False, blend=0.6)
    if lod == 0:
        _tailgate(ctx)
        _rear_wiper(ctx)
        kit.wiper(ctx, 0.52, -0.06, dz=0.06, pivots=[0.52])
        kit.wiper(ctx, -0.02, -0.56, dz=0.06, pivots=[-0.02])
    # dritte Bremsleuchte innen an der Heckscheibe
    cg = CabinGeo(b)
    zb3 = -1.445
    ctx.part("Lights").box((0.0, cg.glass_y(zb3, 0.0) - 0.028, zb3 + 0.012), (0.24, 0.014, 0.012), "Brakelight")


def _tailgate(ctx):
    """Fugen der Heckklappe (seitlich, unten, über die Kante bis zur Scheibe)."""
    b = ctx.b
    xg, y_lo, y_hi = 0.445, 0.63, 0.915
    for sx in (1, -1):
        kit.face_line(ctx, [(sx * xg, y_lo), (sx * xg, y_hi)], rear=True)
        zs = np.linspace(b.zr + 0.03, -1.885, 8)
        b.strip(ctx.part("Trim"), [(z, b.j_at_x_top(z, sx * xg)) for z in zs], 0.0045, "Gap")
    kit.face_line(ctx, [(-xg, y_lo), (xg, y_lo)], rear=True)


def _rear_wiper(ctx):
    """Heckwischer auf der Heckscheibe (Drehpunkt unten in der Mitte)."""
    cg = CabinGeo(ctx.b)
    p = ctx.part("Trim")
    z0, x0 = -1.80, 0.0
    pts = []
    for t in np.linspace(0.0, 1.0, 10):
        x = 0.035 + 0.40 * t
        z = -1.79 + 0.22 * t
        pts.append(np.array([x, cg.glass_y(z, x) + 0.012, z]))
    p.sweep(pts, round_rect(0.014, 0.010, 0.003, 1), "Wiper", up=(0, 1, 0))
    y0 = cg.glass_y(z0, x0)
    p.lathe([(0.0, 0.0), (0.0, 0.017), (0.013, 0.014), (0.02, 0.0)], 12, "Wiper", center=(x0, y0, z0),
            axis="y", inside=(0.006, 0.0))
    p.tube([np.array([x0, y0 + 0.016, z0]), pts[2] + np.array([0, 0.006, 0])], 0.006, "Wiper", segs=8)


def _wheel_x(sp, b, axle):
    wd = sp["wheels"][axle]
    return b.params_at(wd["z"])["w"] + wd.get("out", sp.get("wheel_out", -0.012)) - wd["W"] / 2


def _rally_light(p, c, r, lod):
    c = np.asarray(c, dtype=float)
    segs = 24 if lod == 0 else 10
    p.lathe([(-0.07, 0.0), (-0.07, r * 0.55), (-0.035, r * 0.95), (0.0, r), (0.006, r * 1.03), (0.006, r * 0.9)], segs,
            "BlackGloss", center=tuple(c), axis="z", inside=(-0.035, r * 0.4))
    p.lathe([(-0.004, 0.0), (-0.004, r * 0.9)], segs, "Headlight", center=tuple(c), axis="z", inside=(-0.02, 0.0))
    p.lathe([(0.014, 0.0), (0.010, r * 0.55), (0.002, r * 0.9)], segs, "LampGlass", center=tuple(c), axis="z",
            inside=(-0.01, 0.0))
    if lod == 0:
        p.lathe([(0.016, 0.0), (0.016, r * 0.2), (0.012, r * 0.22)], 12, "Chrome", center=tuple(c), axis="z",
                inside=(0.008, 0.0))


def engine(ctx):
    lod = ctx.lod
    b = ctx.b
    sp = ctx.spec
    out = {}
    # Stufe 1: aufgesetzte Haubenschlitze
    s1 = Part("EngineStage_1")
    loc = kit.raised_vent_local(0.15, 0.22, 4, lod)
    place_top(ctx, loc, 0.30, 1.56, (0.15, 0.22), s1, mirror=True)
    out["EngineStage_1"] = s1
    # Stufe 2: Ladeluftkühler hinter dem Wabengitter
    s2 = Part("EngineStage_2")
    hit = ctx.hit_front(0.0, 0.40)
    if hit is not None:
        zg = hit[0][2] - 0.05
        s2.rbox((0.0, 0.40, zg), (0.84, 0.18, 0.024), 0.006, "Aluminum", segs=1)
        if lod == 0:
            for k in range(18):
                s2.box((-0.40 + 0.80 * k / 17, 0.40, zg + 0.0125), (0.004, 0.17, 0.002), "EngineBlack")
    out["EngineStage_2"] = s2
    # Stufe 3: Rallye-Paket (Dachhutze, vier Zusatzscheinwerfer, Schmutzfänger)
    sub = type(ctx)(sp, lod, b, ctx.rc)
    kit.roof_scoop(sub, 0.0, -0.60, w=0.26, h=0.07, mat="Paint2", part="S3")
    s3 = sub.part("S3")
    xs = (0.39, 0.13, -0.13, -0.39)
    zl = max(ctx.hit_front(x, 0.62)[0][2] for x in xs) + 0.055
    yl = 0.72
    for x in xs:
        _rally_light(s3, (x, yl, zl), 0.066, lod)
    s3.tube([np.array([-0.50, yl - 0.02, zl - 0.075]), np.array([0.50, yl - 0.02, zl - 0.075])], 0.014, "BlackGloss",
            segs=10)
    for x in (0.50, -0.50):
        hb = ctx.hit_front(x * 0.98, 0.62)
        if hb is not None:
            s3.tube([np.array([x, yl - 0.02, zl - 0.075]), hb[0] + np.array([0, 0.02, -0.01])], 0.012, "BlackGloss",
                    segs=8)
    for axle in ("front", "rear"):
        wd = sp["wheels"][axle]
        zf_ = wd["z"] - (wd["R"] + 0.065)
        wx = _wheel_x(sp, b, axle)
        top = b.params_at(zf_)["yb"] + 0.02
        for sx in (1, -1):
            s3.rbox((sx * wx, top - 0.06, zf_), (wd["W"] + 0.03, 0.12, 0.008), 0.004, "Rubber", segs=1)
            s3.box((sx * wx, top - 0.10, zf_ - 0.0045), (wd["W"] + 0.01, 0.02, 0.002), "Accent")
    out["EngineStage_3"] = s3
    return out


# ======================================================================
# Innenraum
# ======================================================================

def deco(ck):
    from .. import deco as D
    p = Part("Deko")
    D.common(ck, p)
    D.coffee(ck, p)
    D.freshener(ck, p)
    D.bobble_cat(ck, p)
    return p


SPEC.update({"details": details, "engine": engine, "deco": deco})
