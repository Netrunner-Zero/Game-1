"""Materialien der Welt (glTF-PBR, siehe carcad.gltf.GLB.add_material).

extras.group steuert das Verhalten im Spiel:
  street   Straßenlaternen (nachts an)
  windows  Fenster der Hochhäuser (nachts viele an)
  neon     Leuchtreklame, Neon-Kanten (immer an, nachts kräftiger)
extras.wet = true: wird bei Regen nass (dunkler, spiegelnd).
"""


def library():
    return {
        "Asphalt": {"color": [1, 1, 1], "map": ("asphalt_c", 7.0), "normal": ("asphalt_n", 7.0, 0.9),
                    "orm": ("asphalt_orm", 7.0), "metallic": 1.0, "roughness": 1.0,
                    "extras": {"surface": "asphalt", "wet": True}},
        "Dirt": {"color": [1, 1, 1], "map": ("dirt_c", 9.0), "normal": ("dirt_n", 9.0, 1.0), "roughness": 0.96,
                 "extras": {"surface": "dirt"}},
        "Concrete": {"color": [1, 1, 1], "map": ("concrete_c", 2.5), "normal": ("concrete_n", 2.5, 0.8),
                     "roughness": 0.86, "extras": {"wet": True}},
        "ConcreteDark": {"color": [0.55, 0.56, 0.58], "map": ("concrete_c", 3.0), "normal": ("concrete_n", 3.0, 0.8),
                         "roughness": 0.9},
        "Paint": {"color": "#e8e8e3", "roughness": 0.62, "extras": {"wet": True}},
        "PaintYellow": {"color": "#e0ad1f", "roughness": 0.62, "extras": {"wet": True}},
        "PaintRed": {"color": "#b8202b", "roughness": 0.62, "extras": {"wet": True}},
        "Curb": {"color": [1, 1, 1], "map": ("curb_c", 2.0), "roughness": 0.58, "extras": {"wet": True}},
        "Checker": {"color": [1, 1, 1], "map": ("checker_c", None), "roughness": 0.6, "extras": {"wet": True}},
        "Metal": {"color": "#8a9099", "metallic": 0.85, "roughness": 0.42},
        "DarkMetal": {"color": "#202329", "metallic": 0.7, "roughness": 0.45},
        "Rubber": {"color": "#141416", "roughness": 0.88},
        "LampHead": {"color": "#d8d8d0", "roughness": 0.3, "emissive": "#ffe2b8", "emissiveStrength": 6.0,
                     "extras": {"group": "street", "base": 6.0}},
        "NeonPink": {"color": "#26061f", "roughness": 0.4, "emissive": "#ff2bd6", "emissiveStrength": 5.0,
                     "extras": {"group": "neon", "base": 5.0}},
        "NeonCyan": {"color": "#03191d", "roughness": 0.4, "emissive": "#00e5ff", "emissiveStrength": 5.0,
                     "extras": {"group": "neon", "base": 5.0}},
        "NeonViolet": {"color": "#120a26", "roughness": 0.4, "emissive": "#7a5cff", "emissiveStrength": 5.0,
                       "extras": {"group": "neon", "base": 5.0}},
        "Sign": {"color": "#050506", "roughness": 0.35, "emissive": "#ffffff", "emissiveMap": ("sign_neon_e", None),
                 "emissiveStrength": 3.5, "extras": {"group": "neon", "base": 3.5}},
        "Facade": {"color": [1, 1, 1], "map": ("facade_c", 12.0), "metallic": 0.35, "roughness": 0.32,
                   "emissive": "#ffffff", "emissiveMap": ("facade_e", 12.0), "emissiveStrength": 2.2,
                   "extras": {"group": "windows", "base": 2.2}},
        "Roof": {"color": "#2b2e34", "roughness": 0.8},
        "ContainerRed": {"color": "#8a2a1e", "metallic": 0.55, "roughness": 0.55},
        "ContainerBlue": {"color": "#1f4a7a", "metallic": 0.55, "roughness": 0.55},
        "ContainerGrey": {"color": "#6d7176", "metallic": 0.55, "roughness": 0.55},
        "Cone": {"color": "#ff5a0a", "roughness": 0.5},
        "ConeBand": {"color": "#f2f2f2", "roughness": 0.25, "metallic": 0.2},
    }
