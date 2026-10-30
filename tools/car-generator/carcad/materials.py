"""Materialbibliothek (PBR, glTF-Erweiterungen).

Jedes Material ist ein kompaktes dict (siehe gltf.GLB.add_material).
Kachelgrößen von Texturen stehen in Metern (die UVs der Geometrie
sind in Metern), Decals nutzen None (UV 0..1).

extras.group sagt dem Spiel, welche Materialien auf welche Regler
reagieren:
  interior  Innenraumbeleuchtung (Ambiente, Deckenlicht, Sternenhimmel)
  display   Displays, Instrumente, beleuchtete Tasten
  lights    Fahrzeuglichter (Scheinwerfer, Rück-, Brems-, Blinklicht)
  neon      Neon-Akzente und Unterboden
extras.tune nennt die Tuning-Option, die das Material verändert.
"""


def _grp(group, base, **kw):
    e = {"group": group, "base": base}
    e.update(kw)
    return e


def paint_spec(color):
    return {"color": color, "metallic": 0.55, "roughness": 0.34, "clearcoat": (1.0, 0.03),
            "normal": ("flakes_n", 0.06, 0.18), "extras": {"tune": "paint"}}


TRIM_STYLES = {
    "carbon": {"color": [1, 1, 1], "map": ("carbon_c", 0.08), "normal": ("carbon_n", 0.08, 0.45),
               "metallic": 0.2, "roughness": 0.32, "clearcoat": (1.0, 0.02)},
    "wood_walnut": {"color": [1, 1, 1], "map": ("wood_walnut", 0.55), "metallic": 0.0, "roughness": 0.35,
                    "clearcoat": (1.0, 0.015)},
    "wood_ash": {"color": [1, 1, 1], "map": ("wood_ash", 0.55), "metallic": 0.0, "roughness": 0.4,
                 "clearcoat": (1.0, 0.02)},
    "aluminum": {"color": [0.92, 0.92, 0.94], "map": ("brushed_c", 0.25), "metallic": 1.0, "roughness": 0.32,
                 "anisotropy": (0.7, 0.0)},
    "pianoblack": {"color": "#050506", "metallic": 0.0, "roughness": 0.06, "clearcoat": (1.0, 0.01)},
    "honeycomb": {"color": "#1c1d21", "metallic": 0.4, "roughness": 0.35, "normal": ("cladding_n", 0.04, 1.0)},
}


def library(p):
    """p: Palette des Autos (siehe cars/*.py)."""
    acc = p["accent"]
    belt = {"chrome": {"color": [0.9, 0.9, 0.92], "metallic": 1.0, "roughness": 0.05},
            "black": {"color": "#060607", "metallic": 0.1, "roughness": 0.18, "clearcoat": (1.0, 0.03)}}[p.get("belt", "black")]
    insert = p.get("insert", "alcantara")
    if insert == "alcantara":
        insert_spec = {"color": p.get("insert_color", "#26272b"), "roughness": 0.92,
                       "normal": ("alcantara_n", 0.05, 0.6), "sheen": ([0.32, 0.32, 0.34], 0.7)}
    elif insert == "fabric":
        insert_spec = {"color": [1, 1, 1], "map": (p.get("fabric_tex", "fabric_check"), 0.14), "roughness": 0.9,
                       "sheen": ([0.25, 0.25, 0.25], 0.8)}
    else:
        insert_spec = {"color": p.get("insert_color", p["seat"]), "roughness": 0.48,
                       "normal": ("leather_n", 0.09, 0.7), "sheen": ([0.12, 0.12, 0.12], 0.5)}
    trim = dict(TRIM_STYLES[p.get("trim", "carbon")])
    trim2 = dict(TRIM_STYLES[p.get("trim2", "pianoblack")])
    tire_tread = "tread_at_n" if p.get("tire") == "at" else "tread_sport_n"

    M = {
        # ---------------- Karosserie ----------------
        "Paint": paint_spec(p["paint"]),
        "Paint2": dict(paint_spec(p.get("paint2", p["paint"])), extras={"tune": "paint2"}),
        "Livery": {"color": "#f2f2f2", "metallic": 0.1, "roughness": 0.28, "clearcoat": (1.0, 0.04),
                   "extras": {"tune": "liveryColor"}},
        "Number": {"color": [1, 1, 1], "map": ("Number", None), "alphaMode": "MASK", "roughness": 0.3,
                   "clearcoat": (1.0, 0.04)},
        "BlackGloss": {"color": "#050506", "metallic": 0.0, "roughness": 0.08, "clearcoat": (1.0, 0.02)},
        "Trim": {"color": "#0c0c0d", "roughness": 0.6, "normal": ("plastic_n", 0.05, 0.45)},
        "Cladding": {"color": "#151618", "roughness": 0.72, "normal": ("cladding_n", 0.07, 0.9)},
        "Chrome": {"color": [0.92, 0.92, 0.94], "metallic": 1.0, "roughness": 0.04},
        "DarkChrome": {"color": [0.32, 0.33, 0.36], "metallic": 1.0, "roughness": 0.08},
        "Aluminum": dict(TRIM_STYLES["aluminum"]),
        "Titanium": {"color": [0.55, 0.53, 0.5], "metallic": 1.0, "roughness": 0.22,
                     "iridescence": (1.0, 1.9, 280.0, 620.0)},
        "Carbon": dict(TRIM_STYLES["carbon"]),
        "Glass": {"color": "#0b0f15", "alpha": 0.42, "metallic": 0.0, "roughness": 0.02, "ior": 1.52,
                  "alphaMode": "BLEND", "doubleSided": True, "extras": {"tune": "tint"}},
        "GlassFrit": {"color": "#040405", "roughness": 0.35},
        "LampGlass": {"color": [0.92, 0.94, 0.97], "alpha": 0.16, "roughness": 0.02, "ior": 1.5,
                      "alphaMode": "BLEND", "clearcoat": (1.0, 0.0)},
        "TailGlass": {"color": [0.42, 0.0, 0.01], "alpha": 0.62, "roughness": 0.04, "alphaMode": "BLEND",
                      "clearcoat": (1.0, 0.0)},
        "SmokeGlass": {"color": [0.03, 0.03, 0.035], "alpha": 0.72, "roughness": 0.03, "alphaMode": "BLEND",
                       "clearcoat": (1.0, 0.0)},
        "Reflector": {"color": [0.85, 0.86, 0.88], "metallic": 1.0, "roughness": 0.16},
        "LampHousing": {"color": "#0b0b0d", "roughness": 0.45},
        "Headlight": {"color": [1, 1, 1], "emissive": [0.95, 0.97, 1.0], "emissiveStrength": 5.0,
                      "roughness": 0.2, "extras": _grp("lights", 5.0, light="head", tune="lightColor")},
        "DRL": {"color": [1, 1, 1], "emissive": [0.92, 0.96, 1.0], "emissiveStrength": 4.0, "roughness": 0.25,
                "extras": _grp("lights", 4.0, light="drl", tune="lightColor")},
        "Taillight": {"color": [0.6, 0.0, 0.02], "emissive": [1.0, 0.02, 0.04], "emissiveStrength": 2.5,
                      "roughness": 0.3, "extras": _grp("lights", 2.5, light="tail")},
        "Brakelight": {"color": [0.5, 0.0, 0.02], "emissive": [1.0, 0.02, 0.03], "emissiveStrength": 0.6,
                       "roughness": 0.3, "extras": _grp("lights", 0.6, light="brake", active=6.0)},
        "Reverse": {"color": [0.85, 0.85, 0.88], "emissive": [1.0, 1.0, 1.0], "emissiveStrength": 0.0,
                    "roughness": 0.3, "extras": _grp("lights", 0.0, light="reverse", active=4.0)},
        "Indicator": {"color": [0.7, 0.32, 0.0], "emissive": [1.0, 0.45, 0.0], "emissiveStrength": 0.0,
                      "roughness": 0.3, "extras": _grp("lights", 0.0, light="indicator", active=5.0)},
        "Accent": {"color": acc, "emissive": acc, "emissiveStrength": 4.0, "roughness": 0.3,
                   "extras": _grp("neon", 4.0, tune="neon")},
        "Underglow": {"color": acc, "emissive": acc, "emissiveStrength": 3.0, "roughness": 0.5, "doubleSided": True,
                      "extras": _grp("neon", 3.0, tune="neon")},
        "Mirror": {"color": [0.78, 0.8, 0.83], "metallic": 1.0, "roughness": 0.02},
        "Seal": {"color": "#050506", "roughness": 0.78},
        "BeltTrim": belt,
        "Gap": {"color": "#020203", "roughness": 0.95},
        "Liner": {"color": "#0f0f11", "roughness": 0.85, "normal": ("cladding_n", 0.06, 0.8)},
        "Underbody": {"color": "#0b0b0c", "roughness": 0.9},
        "Grille": dict({"chrome": {"color": [0.9, 0.9, 0.92], "metallic": 1.0, "roughness": 0.05},
                        "black": {"color": "#08080a", "roughness": 0.35, "clearcoat": (1.0, 0.06)},
                        "dark": {"color": "#121316", "metallic": 0.6, "roughness": 0.3}}[p.get("grille", "black")]),
        "Mesh": {"color": "#0a0a0c", "metallic": 0.3, "roughness": 0.4},
        "ExhaustInner": {"color": "#050505", "roughness": 0.9},
        "Badge": {"color": [1, 1, 1], "map": ("Badge", None), "alphaMode": "MASK", "metallic": 0.9,
                  "roughness": 0.15},
        "Wordmark": {"color": [1, 1, 1], "map": ("Wordmark", None), "alphaMode": "MASK", "metallic": 0.95,
                     "roughness": 0.12},
        "Plate": {"color": [1, 1, 1], "map": ("Plate", None), "roughness": 0.35, "extras": {"tune": "plate"}},
        "Wiper": {"color": "#08080a", "roughness": 0.55},
        "Rubber": {"color": "#0a0a0b", "roughness": 0.85},
        "ContactShadow": {"color": [0, 0, 0], "map": ("Shadow", None), "alphaMode": "BLEND", "unlit": True,
                          "extras": {"shadow": True}},
        # ---------------- Räder ----------------
        "Tire": {"color": "#141415", "roughness": 0.86, "normal": (tire_tread, 0.25, 0.7)},
        "Groove": {"color": "#050506", "roughness": 0.95},
        "Sidewall": {"color": [1, 1, 1], "map": ("sidewall_c", 1.0), "roughness": 0.84},
        "Rim": {"color": p.get("rim", "#a3a9b2"), "metallic": 0.9, "roughness": 0.24, "clearcoat": (1.0, 0.05),
                "extras": {"tune": "rimColor"}},
        "RimDark": {"color": "#0d0d0f", "metallic": 0.5, "roughness": 0.45},
        "RimLip": {"color": [0.86, 0.87, 0.9], "metallic": 1.0, "roughness": 0.1},
        "LugNut": {"color": [0.85, 0.86, 0.88], "metallic": 1.0, "roughness": 0.15},
        "CenterCap": {"color": [1, 1, 1], "map": ("CenterCap", None), "metallic": 0.6, "roughness": 0.2},
        "BrakeDisc": {"color": [1, 1, 1], "map": ("disc_c", None), "metallic": 0.85, "roughness": 0.42},
        "BrakeHat": {"color": "#1a1b1e", "metallic": 0.6, "roughness": 0.4},
        "Caliper": {"color": p.get("caliper", "#c8102e"), "metallic": 0.15, "roughness": 0.3,
                    "clearcoat": (1.0, 0.06), "extras": {"tune": "caliper"}},
        "CaliperLogo": {"color": [1, 1, 1], "map": ("CaliperLogo", None), "alphaMode": "MASK", "roughness": 0.3},
        # ---------------- Innenraum ----------------
        "Seat": {"color": p["seat"], "roughness": 0.5, "normal": ("leather_n", 0.1, 0.7),
                 "sheen": ([0.12, 0.12, 0.12], 0.5), "extras": {"tune": "seat"}},
        "SeatInsert": insert_spec,
        "Stitch": {"color": p.get("stitch", "#8a8a8f"), "map": ("stitch_a", 0.024), "alphaMode": "MASK",
                   "roughness": 0.7},
        "Dash": {"color": p.get("dash", "#141416"), "roughness": 0.68, "normal": ("leather_n", 0.18, 0.35)},
        "Interior": {"color": p.get("door", p.get("dash", "#141416")), "roughness": 0.62,
                     "normal": ("leather_n", 0.12, 0.4)},
        "InteriorTrim": trim,
        "InteriorTrim2": trim2,
        "InteriorPlastic": {"color": "#0f0f11", "roughness": 0.58, "normal": ("plastic_n", 0.05, 0.4)},
        "Headliner": {"color": p.get("headliner", "#1b1b1e"), "roughness": 0.95, "normal": ("alcantara_n", 0.06, 0.5),
                      "sheen": ([0.2, 0.2, 0.21], 0.8)},
        "Carpet": {"color": p.get("carpet", "#0d0d0e"), "roughness": 1.0, "normal": ("carpet_n", 0.12, 1.0)},
        "FloorMat": {"color": "#070708", "roughness": 0.95, "normal": ("carpet_n", 0.08, 0.6)},
        "SteeringLeather": {"color": p.get("wheel_leather", "#0d0d0e"), "roughness": 0.55,
                            "normal": ("leather_n", 0.05, 0.6)},
        "SteeringGrip": dict(insert_spec) if p.get("wheel_grip") == "insert" else
        {"color": p.get("wheel_leather", "#0d0d0e"), "roughness": 0.55, "normal": ("leather_n", 0.05, 0.6)},
        "Pedal": {"color": [0.85, 0.86, 0.88], "metallic": 1.0, "roughness": 0.3, "anisotropy": (0.5, 0.0)},
        "PedalRubber": {"color": "#0b0b0c", "roughness": 0.9},
        "Speaker": {"color": [1, 1, 1], "map": ("speaker_c", 0.06), "metallic": 0.6, "roughness": 0.4},
        "Belt": {"color": "#16161a", "roughness": 0.9, "normal": ("carpet_n", 0.03, 0.4)},
        "BeltMetal": {"color": [0.8, 0.8, 0.82], "metallic": 1.0, "roughness": 0.2},
        "DisplayGlass": {"color": "#020203", "roughness": 0.06, "clearcoat": (1.0, 0.0)},
        "Display_Cluster": {"color": [1, 1, 1], "map": ("Display_Cluster", None), "emissive": [1, 1, 1],
                            "emissiveMap": ("Display_Cluster", None), "emissiveStrength": 1.0, "roughness": 0.15,
                            "extras": _grp("display", 1.0, canvas="cluster")},
        "Display_Center": {"color": [1, 1, 1], "map": ("Display_Center", None), "emissive": [1, 1, 1],
                           "emissiveMap": ("Display_Center", None), "emissiveStrength": 1.0, "roughness": 0.12,
                           "extras": _grp("display", 1.0, canvas="center")},
        "Display_Rear": {"color": [1, 1, 1], "map": ("Display_Rear", None), "emissive": [1, 1, 1],
                         "emissiveMap": ("Display_Rear", None), "emissiveStrength": 1.0, "roughness": 0.12,
                         "extras": _grp("display", 1.0, canvas="rear")},
        "Needle": {"color": [1.0, 0.25, 0.05], "emissive": [1.0, 0.22, 0.04], "emissiveStrength": 1.2,
                   "roughness": 0.4, "extras": _grp("display", 1.2)},
        "ButtonGlow": {"color": [0.9, 0.9, 0.9], "emissive": [0.9, 0.95, 1.0], "emissiveStrength": 0.6,
                       "roughness": 0.4, "extras": _grp("display", 0.6)},
        "StartButton": {"color": [0.6, 0.02, 0.03], "emissive": [1.0, 0.05, 0.05], "emissiveStrength": 0.5,
                        "roughness": 0.3, "clearcoat": (1.0, 0.02), "extras": _grp("display", 0.5)},
        "InteriorAmbient": {"color": p.get("ambient", acc), "emissive": p.get("ambient", acc),
                            "emissiveStrength": 1.2, "roughness": 0.4,
                            "extras": _grp("interior", 1.2, tune="ambient")},
        "DomeLight": {"color": [0.95, 0.92, 0.85], "emissive": [1.0, 0.92, 0.78], "emissiveStrength": 0.8,
                      "roughness": 0.4, "extras": _grp("interior", 0.8)},
        "Starlight": {"color": "#08080b", "roughness": 0.95, "emissive": [1, 1, 1], "emissiveMap": ("starlight_e", 0.7),
                      "emissiveStrength": 1.5, "extras": _grp("interior", 1.5)},
        "MarkerRed": {"color": p.get("marker", "#c8102e"), "roughness": 0.5},
        "Cage": {"color": p.get("cage", "#18191c"), "metallic": 0.35, "roughness": 0.32, "clearcoat": (1.0, 0.08),
                 "extras": {"tune": "cageColor"}},
        # ---------------- Motor ----------------
        "EngineMetal": {"color": "#3a3c40", "metallic": 0.85, "roughness": 0.42},
        "EngineBlack": {"color": "#101012", "metallic": 0.3, "roughness": 0.5},
        "EngineRed": {"color": "#a8121c", "metallic": 0.2, "roughness": 0.35, "clearcoat": (1.0, 0.05)},
        "Hose": {"color": "#0a0a0b", "roughness": 0.7},
        "Copper": {"color": [0.95, 0.55, 0.36], "metallic": 1.0, "roughness": 0.28},
        "HVOrange": {"color": "#ff6a00", "roughness": 0.55},
        # ---------------- Deko ----------------
        "DecoWhite": {"color": "#e8e9ec", "roughness": 0.25, "clearcoat": (1.0, 0.04)},
        "Visor": {"color": "#030305", "metallic": 0.6, "roughness": 0.04},
        "Hologram": {"color": acc, "alpha": 0.5, "emissive": acc, "emissiveStrength": 2.0, "alphaMode": "BLEND",
                     "roughness": 0.3, "extras": _grp("interior", 2.0)},
        "DuckYellow": {"color": "#f2b705", "roughness": 0.35},
        "DuckBeak": {"color": "#e8530e", "roughness": 0.4},
        "Cardboard": {"color": "#6b4a2a", "roughness": 0.95},
        "Dice": {"color": [1, 1, 1], "map": ("Dice", None), "roughness": 0.95},
        "Label": {"color": [1, 1, 1], "map": ("Label", None), "roughness": 0.6},
        "Sticker": {"color": [1, 1, 1], "map": ("Sticker", None), "alphaMode": "MASK", "roughness": 0.5},
        "Secret": {"color": [1, 1, 1], "map": ("Secret", None), "roughness": 0.9},
        "Bottle": {"color": "#0b2a12", "alpha": 0.85, "roughness": 0.05, "alphaMode": "BLEND", "ior": 1.5},
        "Crystal": {"color": [0.95, 0.97, 1.0], "alpha": 0.25, "roughness": 0.02, "alphaMode": "BLEND",
                    "ior": 1.5},
        "Gold": {"color": [1.0, 0.78, 0.34], "metallic": 1.0, "roughness": 0.18},
    }
    if p.get("extra_mats"):
        M.update(p["extra_mats"])
    return M
