#!/usr/bin/env python3
"""Erzeugt die Spielwelt-Karten (GLB + JSON) nach world/.

  python3 tools/world-generator/generate.py               # alle Karten
  python3 tools/world-generator/generate.py testgelaende  # nur diese
  python3 tools/world-generator/generate.py --tex         # Texturen neu erzeugen

Benötigt Python 3 mit numpy und Pillow (wie der Fahrzeug-Generator).
"""
import importlib
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import worldgen  # noqa: E402,F401  (setzt den Pfad zum Fahrzeug-Generator)
from carcad.gltf import GLB  # noqa: E402
from worldgen import textures as T  # noqa: E402
from worldgen.materials import library  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "..", "world"))
MAPS = ["testgelaende"]

# Schatten je Knoten: Boden empfängt nur, Bauten werfen und empfangen, Skyline gar nicht
NODE_EXTRAS = {
    "Ground": {"shadow": "receive"},
    "Markings": {"shadow": "receive"},
    "Structures": {"shadow": "both"},
    "Lamps": {"shadow": "none"},
    "Skyline": {"shadow": "none", "far": True},
}


def build_map(name, texlib):
    mod = importlib.import_module("worldgen.maps." + name)
    t0 = time.time()
    rnd = random.Random(1234)
    parts, cone, meta = mod.build(rnd)
    g = GLB(generator="Neon Haven worldgen")
    g.texlib = texlib
    mats = library()
    used = set()
    for p in list(parts.values()) + [cone]:
        used |= set(p.tris.keys())
    for m in sorted(used):
        g.add_material(m, mats[m])
    kids = []
    tri = {}
    for key, part in parts.items():
        if not part.tris:
            continue
        kids.append(g.add_node(key, mesh=part, extras=NODE_EXTRAS.get(key, {})))
        tri[key] = part.count()
    kids.append(g.add_node("Prop_Cone", mesh=cone, extras={"template": "cone"}))
    root = g.add_node(meta["id"], children=kids)
    path = os.path.join(OUT, meta["id"] + ".glb")
    size = g.write(path, [root])
    meta = dict(meta)
    meta["file"] = meta["id"] + ".glb"
    meta["triangles"] = tri
    meta["fileBytes"] = size
    meta["version"] = 1
    meta["units"] = "Meter, +Y oben; yaw: lokale +Z zeigt nach (sin yaw, cos yaw)"
    with open(os.path.join(OUT, meta["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    print("  %s: %.2f MB, %d Dreiecke, %d Materialien, %d Kollisionskörper, %d Pylonen (%.1fs)" % (
        meta["file"], size / 1e6, sum(tri.values()), len(used), len(meta["colliders"]), len(meta["props"]),
        time.time() - t0))
    return meta


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    os.makedirs(OUT, exist_ok=True)
    tex_dir = os.path.join(OUT, "textures")
    texlib = None if "--tex" in sys.argv else T.load_lib(tex_dir)
    if texlib is None:
        print("Texturen erzeugen …")
        texlib = T.build_all(tex_dir)
    index = []
    for n in args or MAPS:
        print("== %s ==" % n)
        m = build_map(n, texlib)
        index.append({"id": m["id"], "name": m["name"], "file": m["id"] + ".json"})
    if not args:
        with open(os.path.join(OUT, "maps.json"), "w", encoding="utf-8") as f:
            json.dump({"maps": index}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
