"""Rhino X – schwerer Offroad-SUV (Allrad, hohe Federung, Leiterrahmen, Starrachsen).

Design: kantige Box mit fast senkrechter Frontscheibe, flachem Dach mit
Dachreling, runden LED-Scheinwerfern mit Leuchtringen, Grill mit Querstreben
und RHINO-Schriftzug, massive Kunststoff-Stoßfänger mit Unterfahrschutz und
roten Abschleppösen, schwarze Kotflügelverbreiterungen, Trittbretter,
Reserverad an der seitlich angeschlagenen Hecktür, senkrechte Rückleuchten.
Unter dem Auto: Leiterrahmen, Starrachsen mit Differentialen, Längslenker,
Verteilergetriebe, Kardanwellen, Tank und Endschalldämpfer.
Innen: robust, Aluminium und Waben-Struktur, Komfortsitze mit orangen Nähten,
Haltegriff vor dem Beifahrer, drei Differentialsperren-Schalter,
Quietscheente auf dem Armaturenbrett, Pizzakarton auf der Rückbank.
"""
import math

import numpy as np

from . import S, C
from .. import kit
from ..mesh import Part, rot_matrix, round_rect
from ..parts import rr_outline, decal_local, place_flat

SPEC = {
    "id": "rhino_x", "name": "Rhino X", "node": "Rhino_X",
    "desc": "Schwerer Offroad-SUV mit Allrad, Starrachsen und viel Bodenfreiheit",
    "class": "Geländewagen",
    "brand": {"mono": "R", "word": "RHINO", "caliper": "RHINO"},
    "plate": "RX 404", "number": "44",
    "deco_label": [("NEON PIZZA", 70), ("extra scharf", 46)],
    "palette": {
        "paint": "#3d4a3e", "accent": "#ff8a00", "rim": "#2a2c30", "caliper": "#ff8a00",
        "seat": "#3a2a20", "insert": "alcantara", "insert_color": "#23211e", "stitch": "#ff8a00",
        "trim": "honeycomb", "trim2": "aluminum", "dash": "#1a1a1c", "door": "#24221f",
        "headliner": "#2a2a2c", "carpet": "#151516", "wheel_leather": "#1a1a1c", "ambient": "#ff8a00",
        "marker": "#ff8a00", "cage": "#1a1a1d", "belt": "black", "grille": "black", "tire": "at",
    },
    "stats": {"massKg": 2400, "powerKw": 330, "drive": "AWD", "topSpeedKmh": 220, "grip": 0.95,
              "suspension": "lang, weich"},
    "physics": {
        "massKg": 2400, "cogHeight": 0.80, "weightFront": 0.52, "dragCd": 0.50, "frontalArea": 3.2,
        "powerKw": 330, "torqueNm": 700, "idleRpm": 700, "redlineRpm": 6200,
        "gears": [4.7, 3.14, 2.11, 1.67, 1.29, 1.0, 0.84, 0.67], "finalDrive": 3.9, "lowRange": 2.7,
        "suspension": {"springFront": 42000, "springRear": 46000, "damping": 0.35, "travel": 0.26,
                       "antiRollFront": 0.4, "antiRollRear": 0.35},
        "tire": {"grip": 0.95, "slipPeak": 0.12, "offroadGrip": 1.25}, "brakeForce": 0.95, "brakeBias": 0.62,
        "steerLockDeg": 36, "groundClearance": 0.27,
    },
    "tuning": {
        "engine": [{"name": "Serie V8", "powerKw": 330, "torqueNm": 700},
                   {"name": "Schnorchel + Luftfilter", "powerKw": 345, "torqueNm": 730},
                   {"name": "Biturbo + Ladeluftkühler", "powerKw": 420, "torqueNm": 850},
                   {"name": "Expedition (Bügel, Winde, LED)", "powerKw": 440, "torqueNm": 880}],
        "exhaust": [{"name": "Serie", "loudness": 1}, {"name": "Doppelrohr Sport", "loudness": 4},
                    {"name": "Hochauspuff (Wattiefe)", "loudness": 6}],
        "cage": [{"name": "Kein Käfig"}, {"name": "Halbkäfig", "massKg": 22, "stiffness": 1.05},
                 {"name": "Vollkäfig", "massKg": 40, "stiffness": 1.12}],
    },
    "rpm_max": 7, "gauge_vmax": 260, "steer_wheel_deg": 560,
    # --------------------------------------------------------------
    "wheels": {"front": {"z": 1.45, "R": 0.42, "W": 0.30}, "rear": {"z": -1.45, "R": 0.42, "W": 0.30}},
    "rim_ratio": 0.60, "tire": "at", "wheel_out": 0.035, "caliper_angle": 120.0, "caliper_size": 1.1,
    "arch_gap": 0.055, "arch_mat": "Cladding", "flare": (0.075, 0.075),
    "rims": [{"style": "beadlock", "n": 6, "concave": 0.04, "label": "Beadlock"},
             {"style": "classic5", "n": 5, "concave": 0.05, "label": "Gelände 5"},
             {"style": "split5", "n": 6, "label": "Y-Speiche"}],
    "nuts": 6, "max_lowering_cm": 6,
    "section": {"bw": 0.93, "lo": 0.08, "hi": 0.06, "tum": 0.99, "sh": 0.965, "crx": 0.6,
                "radii": [0.03, 0.03, 0.04, 0.035, 0.3]},
    "nose_r": 0.03, "tail_r": 0.025,
    "body": [S(2.38, 0.92, 0.48, 1.02, 0.0), S(2.31, 0.975, 0.42, 1.10, 0.015),
             S(2.10, 0.995, 0.40, 1.14, 0.02), S(1.45, 1.0, 0.40, 1.16, 0.025),
             S(0.80, 1.0, 0.40, 1.17, 0.025), S(-1.00, 1.0, 0.40, 1.18, 0.02),
             S(-1.45, 1.0, 0.40, 1.18, 0.02), S(-2.25, 0.99, 0.42, 1.18, 0.01),
             S(-2.38, 0.95, 0.48, 1.14, 0.0)],
    "cabin": [C(0.80, 0.92, 0.88, -0.02, "ws"), C(0.52, 0.915, 0.865, 1.86, "ws"), C(0.44, 0.915, 0.865, 1.885, "roof"),
              C(-0.30, 0.915, 0.865, 1.895, "roof"), C(-0.38, 0.915, 0.865, 1.895, "pillar"),
              C(-1.38, 0.915, 0.865, 1.895, "roof"), C(-1.46, 0.915, 0.865, 1.895, "pillar"),
              C(-2.16, 0.915, 0.865, 1.89, "roof"), C(-2.36, 0.91, 0.86, 1.87, "pillar")],
    "pillar_frac": 0.2, "bpillar_mat": "BlackGloss", "rear_cap_mat": "Paint2",
    "gaps": {"doors": [{"z": (0.78, -0.355), "y0": 0.47},
                       {"z": (-0.365, -1.42), "y0": 0.47, "arch": "rear"}],
             "lids": [{"z0": 0.93, "z1": 2.28, "x": 0.80, "cross": [0.94, 2.27]}]},
    "plate_pos": {"front": 0.575, "front_out": 0.105, "rear": 0.53, "rear_out": 0.095},
    "livery_skip_z": [(1.45, 1.80)],
    "spoiler": {"z": -2.30, "y": 1.89, "w": 0.80, "lip": (0.22, 0.035), "over": 0.10, "h2": 0.10, "h3": 0.18,
                "roof": True},
    "spoiler_labels": ["Dachkante", "Dachflügel", "Cyber-Dachflügel"],
    "exhaust": {"y": 0.395, "protrude": 0.05, "tail_pipe": 0.45,
                "variants": [[(-0.62, 0.042, "round", "DarkChrome", 0.395, -2.43)],
                             [(0.62, 0.045, "round", "DarkChrome", 0.392, -2.44),
                              (-0.62, 0.045, "round", "DarkChrome", 0.392, -2.44)],
                             [("stack", -2.25, 0.70, 1.78, 0.045, "Titanium")]]},
    # --------------------------------------------------------------
    "interior": {
        "floor": 0.60, "fw": 0.86, "rb": -2.24, "hpt_z": -0.42, "seat_x": 0.42, "driver_x": 0.40, "tunnel": 0.16,
        "dash": {"depth": 0.46, "clear": 0.09, "binnacle": 0.05, "stack": 0.07, "height": 0.16, "knee": 0.44,
                 "upper": "Dash"},
        "cluster": {"type": "digital", "w": 0.30, "h": 0.12},
        "center": {"type": "dash", "w": 0.28, "h": 0.16},
        "vents": (0.20, -0.20, 0.66, -0.66),
        "wheel": {"r": 0.19, "tilt": 24, "dist": 0.26, "drop": 0.09, "style": "round", "grip": 0.018,
                  "marker": True, "marker_mat": "MarkerRed", "spokes": 3, "spoke_mat": "InteriorPlastic"},
        "console": {"back": 0.28, "h_front": 0.30, "h_back": 0.24, "w": 0.26, "shifter_t": 0.38, "shifter": "sport",
                    "knob": "Aluminum"},
        "seat_kind": "comfort", "recline": 20, "cushion_h": 0.28, "back_h": 0.62,
        "rear": {"type": "bench", "z": -1.34, "recline": 24, "back_h": 0.60, "headrest": True},
        "rear_cushion_h": 0.30,
        "eye_dist": 0.68, "head_clear": 0.16, "eye_up": 0.49,
    },
}


# ======================================================================
# Außendetails
# ======================================================================

def _ring(r, n=28):
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]


HEAD = {"w": 0.23, "h": 0.23, "r": 0.115, "depth": 0.08, "dome": 0.016, "lens": "LampGlass", "kind": "head",
        "elements": [("bowl", 0.0, 0.0, 0.098, 0.05), ("strip", _ring(0.066), 0.022, "Trim"),
                     ("strip", _ring(0.090), 0.011, "DRL"), ("projector", 0.0, 0.0, 0.042)],
        "bezel": (0.012, "Trim"), "lod_mat": "Reflector"}
TAIL = {"w": 0.11, "h": 0.40, "r": 0.02, "depth": 0.05, "dome": 0.004, "lens": "TailGlass", "kind": "tail",
        "elements": [("panel", rr_outline(0.08, 0.13, 0.012, 2), "Taillight"),
                     ("panel", [(-0.04, 0.078), (0.04, 0.078), (0.04, 0.17), (-0.04, 0.17)], "Brakelight"),
                     ("panel", [(-0.04, -0.17), (0.04, -0.17), (0.04, -0.11), (-0.04, -0.11)], "Indicator"),
                     ("panel", [(-0.04, -0.10), (0.04, -0.10), (0.04, -0.072), (-0.04, -0.072)], "Reverse")],
        "bezel": (0.01, "Trim")}
INDICATOR = {"w": 0.12, "h": 0.04, "r": 0.012, "depth": 0.025, "dome": 0.003, "lens": "LampGlass", "kind": "indicator",
             "elements": [("panel", rr_outline(0.10, 0.026, 0.01, 2), "Indicator")]}


def _plate(p, a, b, w, t, mat, r=0.006):
    """Platte zwischen zwei Mittelpunkten a -> b (Breite w entlang x, Dicke t)."""
    p.sweep([np.asarray(a, dtype=float), np.asarray(b, dtype=float)], round_rect(w, t, r, 1), mat, up=(0, 1, 0))


def _shackle(p, c, r=0.032, t=0.010):
    """Rote Abschlepp-Öse (Torus, Ebene y-z)."""
    prof = [(t * math.cos(a), r + t * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)]
    p.lathe(prof, 18, "EngineRed", center=tuple(c), axis="x", inside=(0.0, r))


def details(ctx):
    b = ctx.b
    lod = ctx.lod
    # ---------------- Front ----------------
    kit.opening(ctx, rr_outline(0.92, 0.24, 0.03, 4), "front", 0.0, 0.84, depth=0.10, style="hslats",
                frame_mat="Trim", mesh_mat="Mesh", cell=0.05, frame_w=0.02, blend=0.85)
    kit.lamp(ctx, HEAD, 0.68, 0.85, front=True, blend=0.85)
    kit.lamp(ctx, INDICATOR, 0.68, 0.70, front=True, blend=0.85)
    hit = ctx.hit_front(0.0, 0.84)
    if hit is not None:                              # RHINO-Schriftzug auf dem Grill
        loc = decal_local(0.40, 0.0625, "Wordmark", wv=0.0)
        place_flat(ctx, loc, hit[0], np.array([0, 0, 1.0]), (0.40, 0.0625), ctx.part("Badges"), lift=0.008)
    kit.louvres(ctx, 0.52, 1.70, 0.28, 0.26, 4, angle=30, mat="Trim", frame_mat="Trim", mirror=True)
    if lod < 2:
        kit.bumper(ctx, 0.575, 2.0, h=0.19, out=0.10, thick=0.12, front=True, mat="Cladding")
        hb = ctx.hit_front(0.0, 0.575)
        if hb is not None:
            zb = hb[0][2] + 0.10                     # Vorderseite des Stoßfängers
            p = ctx.part("Bumpers")
            _plate(p, (0.0, 0.47, zb - 0.06), (0.0, 0.355, 1.72), 1.0, 0.014, "Aluminum")   # Unterfahrschutz
            if lod == 0:
                for sx in (1, -1):
                    _shackle(p, (sx * 0.44, 0.575, zb + 0.012))
                    p.rbox((sx * 0.44, 0.575, zb - 0.004), (0.035, 0.05, 0.03), 0.008, "EngineBlack", segs=1)
                # Nebelscheinwerfer im Stoßfänger
                for sx in (1, -1):
                    c = (sx * 0.72, 0.575, zb + 0.002)
                    p.lathe([(0.0, 0.0), (0.0, 0.034), (-0.01, 0.04)], 20, "Trim", center=c, axis="z",
                            inside=(-0.02, 0.0))
                    p.lathe([(0.003, 0.0), (0.003, 0.03)], 20, "Headlight", center=c, axis="z", inside=(-0.01, 0.0))
    # ---------------- Seite ----------------
    kit.side_mirror(ctx, 0.70, 1.10, reach=0.12, rise=0.15, length=0.20, h=0.15, depth=0.10,
                    body_mat="Trim", stalk_mat="Trim", indicator=True, stalk_w=0.07)
    if lod == 0:
        for z in (0.10, -0.98):
            kit.pull_handle(ctx, z, 1.06, w=0.16, h=0.03, mat="Trim")
        kit.side_lamp(ctx, 2.17, 0.95, 0.07, 0.03, mat="Indicator")
    if lod < 2:
        p = ctx.part("Steps")
        for sx in (1, -1):                           # Trittbretter mit Gummiauflage
            p.rbox((sx * 1.005, 0.42, 0.0), (0.17, 0.035, 1.70), 0.012, "Aluminum", segs=2)
            if lod == 0:
                for dx in (-0.05, 0.0, 0.05):
                    p.rbox((sx * (1.005 + dx), 0.439, 0.0), (0.026, 0.006, 1.60), 0.003, "Rubber", segs=1)
                for z in (0.62, 0.0, -0.62):
                    p.rbox((sx * 0.93, 0.405, z), (0.10, 0.03, 0.05), 0.006, "Trim", segs=1)
    kit.roof_rails(ctx, 0.30, -2.12, 0.78, h=0.06, cross=(0.10, -1.0) if lod < 2 else ())
    # ---------------- Heck ----------------
    kit.lamp(ctx, TAIL, 0.86, 0.95, front=False, blend=0.7)
    if lod < 2:
        kit.bumper(ctx, 0.53, -2.02, h=0.17, out=0.09, thick=0.11, front=False, mat="Cladding")
        kit.spare_wheel(ctx, (0.0, 1.09, b.zr - 0.17), R=0.40, W=0.26)
        hr = ctx.hit_rear(0.0, 0.53)
        if hr is not None:                           # Anhängerkupplung unter dem Stoßfänger
            zr = hr[0][2] - 0.09                     # Rückseite des Stoßfängers
            p = ctx.part("Bumpers")
            p.rbox((0.0, 0.415, zr - 0.02), (0.07, 0.07, 0.16), 0.01, "Trim", segs=1)
            p.sphere((0.0, 0.485, zr - 0.10), 0.025, "Chrome", segs=12, rings=8)
            p.tube([np.array([0.0, 0.43, zr - 0.09]), np.array([0.0, 0.47, zr - 0.10])], 0.012, "Chrome", segs=8)
            if lod == 0:
                for sx in (1, -1):
                    _shackle(ctx.part("Bumpers"), (sx * 0.56, 0.53, zr - 0.004), r=0.028)
    kit.wordmark(ctx, -0.52, 0.72, 0.26, 0.04, rear=True)
    if lod == 0:
        _tailgate(ctx)
        kit.wiper(ctx, 0.60, -0.05, dz=0.03, pivots=[0.60])
        kit.wiper(ctx, 0.0, -0.62, dz=0.03, pivots=[0.0])
    ctx.part("Lights").box((0.0, 1.853, b.zr + 0.012), (0.30, 0.018, 0.012), "Brakelight")   # 3. Bremsleuchte
    if lod < 2:
        _chassis(ctx)


def _tailgate(ctx):
    """Fugen, Scharniere und Griff der seitlich angeschlagenen Hecktür."""
    b = ctx.b
    p = ctx.part("Trim")
    zr = b.zr - 0.0015
    cap = getattr(b, "rear_cap", None)
    zc = (cap["z"] - 0.0015) if cap else zr
    y_belt = b.params_at(b.zr + 0.03)["yt"] - 0.03
    y_top = (cap["y1"] - 0.03) if cap else y_belt
    xg, w = 0.785, 0.0045

    def vline(x, y0, y1, z):
        p.quad((x - w / 2, y0, z), (x + w / 2, y0, z), (x + w / 2, y1, z), (x - w / 2, y1, z), "Gap", outward=(0, 0, -1))

    def hline(y, x0, x1, z):
        p.quad((x0, y - w / 2, z), (x1, y - w / 2, z), (x1, y + w / 2, z), (x0, y + w / 2, z), "Gap", outward=(0, 0, -1))

    for sx in (1, -1):
        vline(sx * xg, 0.635, y_belt + 0.03, zr)
        vline(sx * xg, y_belt + 0.03, y_top, zc)
    hline(0.635, -xg, xg, zr)
    hline(y_top, -xg, xg, zc)
    # Scharniere rechts (x < 0), Griff links
    for y in (0.80, 1.05):
        p.rbox((-xg - 0.01, y, b.zr - 0.012), (0.05, 0.08, 0.024), 0.008, "Trim", segs=1)
    p.rbox((xg - 0.08, 0.98, b.zr - 0.012), (0.10, 0.03, 0.02), 0.009, "Trim", segs=2)


def _chassis(ctx):
    """Gefederte Fahrwerksteile unter der Karosserie (Rahmen, Getriebe, Tank, Auspuff)."""
    lod = ctx.lod
    p = ctx.part("Chassis")
    mat = "Underbody"
    for sx in (1, -1):                               # Leiterrahmen
        p.rbox((sx * 0.43, 0.335, 0.0), (0.08, 0.13, 4.30), 0.01, mat, segs=1)
    for z in (2.05, 0.95, -0.55, -2.05):
        p.rbox((0.0, 0.345, z), (0.86, 0.07, 0.07), 0.008, mat, segs=1)
    # Motorölwanne + Verteilergetriebe
    p.rbox((0.0, 0.40, 1.80), (0.40, 0.16, 0.50), 0.03, "EngineBlack", segs=2)
    p.rbox((0.0, 0.33, 0.50), (0.32, 0.18, 0.42), 0.03, "EngineBlack", segs=2)
    # Kardanwellen
    p.tube([np.array([0.06, 0.32, 0.72]), np.array([0.12, 0.40, 1.34])], 0.035, "EngineMetal", segs=10)
    p.tube([np.array([0.06, 0.32, 0.28]), np.array([0.10, 0.40, -1.32])], 0.04, "EngineMetal", segs=10)
    # Tank
    p.rbox((0.0, 0.36, -0.95), (0.70, 0.18, 0.56), 0.04, mat, segs=2)
    # Auspuff: Rohr unter dem Auto, Mittel- und Endschalldämpfer (quer)
    pts = [np.array([-0.22, 0.30, 1.55]), np.array([-0.26, 0.29, 0.70]), np.array([-0.30, 0.30, -0.30]),
           np.array([-0.36, 0.32, -1.25]), np.array([-0.30, 0.34, -1.85])]
    p.tube(pts, 0.03, "EngineMetal", segs=10 if lod == 0 else 6)
    p.rbox((-0.27, 0.30, 0.15), (0.16, 0.12, 0.50), 0.04, "EngineMetal", segs=2)
    p.rbox((0.0, 0.36, -1.98), (1.30, 0.14, 0.24), 0.05, "EngineMetal", segs=2)


def unsprung(ctx):
    """Starrachsen mit Differentialen und Lenkern (bleiben beim Tieferlegen auf Radhöhe)."""
    lod = ctx.lod
    sp = ctx.spec
    p = Part("Axles")
    segs = 16 if lod == 0 else 8
    for axle, sgn in (("front", 1.0), ("rear", -1.0)):
        wd = sp["wheels"][axle]
        z, y = wd["z"], wd["R"]
        p.tube([np.array([-0.74, y, z]), np.array([0.74, y, z])], 0.045, "EngineBlack", segs=segs)
        c = np.array([0.12, y - 0.02, z])
        p.sphere(c, 0.12, "EngineMetal", segs=segs, rings=8 if lod == 0 else 5, scale=(1.0, 0.92, 1.08))
        # Deckel des Differentials (zeigt zur Fahrzeugmitte)
        p.lathe([(0.0, 0.10), (0.012, 0.095), (0.016, 0.06), (0.018, 0.0)], segs, "EngineBlack",
                center=tuple(c + np.array([0, 0, -sgn * 0.10])), axis="z", inside=(0.0, 0.0),
                M=rot_matrix(0, math.pi if sgn > 0 else 0.0, 0))
        for sx in (1, -1):
            # Längslenker zum Rahmen, Federteller
            p.tube([np.array([sx * 0.56, y - 0.03, z]), np.array([sx * 0.45, y - 0.09, z - sgn * 0.62])], 0.022,
                   "EngineBlack", segs=8)
            p.lathe([(0.0, 0.0), (0.0, 0.075), (0.012, 0.075)], segs, "EngineBlack",
                    center=(sx * 0.62, y + 0.05, z - sgn * 0.08), axis="y", inside=(0.006, 0.03))
            if lod == 0:
                # Stoßdämpfer (unterer Teil sichtbar)
                p.tube([np.array([sx * 0.66, y - 0.02, z + sgn * 0.10]), np.array([sx * 0.68, y + 0.16, z + sgn * 0.12])],
                       0.022, "Accent", segs=10)
        # Panhardstab
        p.tube([np.array([-0.60, y + 0.01, z - sgn * 0.12]), np.array([0.42, y - 0.05, z - sgn * 0.15])], 0.018,
               "EngineBlack", segs=8)
    if lod == 0:
        # Spurstange vorne
        zf = sp["wheels"]["front"]["z"]
        p.tube([np.array([-0.70, 0.40, zf + 0.16]), np.array([0.70, 0.40, zf + 0.16])], 0.016, "EngineMetal", segs=8)
    return p


def engine(ctx):
    lod = ctx.lod
    out = {}
    b = ctx.b
    # Stufe 1: Schnorchel an der rechten A-Säule
    s1 = Part("EngineStage_1")
    hit = ctx.hit_side(1.02, 1.08, -1)
    if hit is not None:
        kit.snorkel(s1, hit[0] + np.array([-0.012, 0.0, 0.0]), (-0.935, 1.78, 0.60), r=0.045, mat="Trim")
    out["EngineStage_1"] = s1
    # Stufe 2: Ladeluftkühler hinter dem Grill + Hutze auf der Haube
    s2 = Part("EngineStage_2")
    hitg = ctx.hit_front(0.0, 0.84)
    if hitg is not None:
        zg = hitg[0][2] - 0.085
        s2.rbox((0.0, 0.84, zg), (0.86, 0.20, 0.02), 0.006, "Aluminum", segs=1)
        if lod == 0:
            for k in range(16):
                s2.box((-0.40 + 0.80 * k / 15, 0.84, zg + 0.011), (0.005, 0.19, 0.003), "EngineBlack")
    sub = type(ctx)(ctx.spec, lod, b, ctx.rc)
    kit.hood_scoop(sub, 1.25, 1.78, 0.42, 0.07, mat="Paint", inner="Mesh", part="S2", open_front=True)
    s2.merge(sub.part("S2"))
    out["EngineStage_2"] = s2
    # Stufe 3: Frontbügel mit Seilwinde + LED-Leiste auf dem Dach
    sub3 = type(ctx)(ctx.spec, lod, b, ctx.rc)
    kit.bull_bar(sub3, 0.62, out=0.175, w=1.0, part="S3")
    kit.light_bar(sub3, 0.36, w=1.25, part="S3")
    out["EngineStage_3"] = sub3.part("S3")
    return out


# ======================================================================
# Innenraum
# ======================================================================

def cockpit_extra(ck):
    p = ck.part
    # Haltegriff vor dem Beifahrer (Aluminium mit Gummigriff)
    xs = sorted(ck.dash_top)
    xa, xb = -0.58, -0.22
    ya, za = ck.dash_top[min(xs, key=lambda q: abs(q - xa))]
    yb, zb = ck.dash_top[min(xs, key=lambda q: abs(q - xb))]
    y = min(ya, yb) - 0.06
    z = max(za, zb) - 0.012
    path = [np.array([xa, y, z + 0.005]), np.array([xa + 0.02, y, z - 0.045]), np.array([xb - 0.02, y, z - 0.045]),
            np.array([xb, y, z + 0.005])]
    p.tube(path, 0.012, "Aluminum", segs=12)
    p.tube([path[1] + np.array([0.03, 0, 0]), path[2] - np.array([0.03, 0, 0])], 0.0155, "SteeringGrip", segs=12)
    for x in (xa, xb):
        p.rbox((x, y, z + 0.004), (0.04, 0.05, 0.012), 0.006, "InteriorPlastic", segs=1)
    # Drei Differentialsperren-Schalter unter dem Mittelbildschirm
    cx, cy, cz = ck.anchors["center"]
    h = ck.I.get("center", {}).get("h", 0.16)
    yy = cy - h / 2 - 0.035
    p.rbox((0.0, yy, cz - 0.004), (0.17, 0.04, 0.012), 0.008, "InteriorTrim", segs=2)
    for k, x in enumerate((-0.05, 0.0, 0.05)):
        p.rbox((x, yy, cz - 0.012), (0.032, 0.024, 0.01), 0.006, "InteriorPlastic", segs=1)
        p.box((x, yy - 0.004, cz - 0.0175), (0.02, 0.006, 0.002), "ButtonGlow")


def deco(ck):
    from .. import deco as D
    p = Part("Deko")
    D.common(ck, p)
    D.duck(ck, p)
    D.pizza(ck, p)
    return p


SPEC.update({"details": details, "engine": engine, "deco": deco, "unsprung": unsprung, "cockpit_extra": cockpit_extra})
