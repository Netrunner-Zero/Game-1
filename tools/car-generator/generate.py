#!/usr/bin/env python3
"""Erzeugt die Fahrzeugmodelle (GLB) und models/cars.json.

  python3 tools/car-generator/generate.py              # alle Autos
  python3 tools/car-generator/generate.py vektra ion   # nur diese
  python3 tools/car-generator/generate.py --tex        # geteilte Texturen neu erzeugen

Benötigt nur Python 3 mit numpy und Pillow.
"""
import importlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from carcad.textures import build_shared, SHARED        # noqa: E402
from carcad.build import build_car                      # noqa: E402
from carcad.cars import ORDER                           # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "..", "models"))


def shared_lib(regen):
    tex_dir = os.path.join(OUT, "textures")
    missing = [f for (f, _fn, _fmt) in SHARED.values() if not os.path.exists(os.path.join(tex_dir, f))]
    if regen or missing:
        print("Geteilte Texturen erzeugen …")
        return build_shared(tex_dir)
    lib = {}
    for name, (fname, _fn, fmt) in SHARED.items():
        lib[name] = {"file": fname, "mime": "image/jpeg" if fmt == "JPEG" else "image/png", "external": True,
                     "bytes": os.path.getsize(os.path.join(tex_dir, fname))}
    return lib


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    regen = "--tex" in sys.argv
    names = args or ORDER
    os.makedirs(OUT, exist_ok=True)
    shared = shared_lib(regen)
    meta_path = os.path.join(OUT, "cars.json")
    cars = {}
    if os.path.exists(meta_path):
        try:
            for c in json.load(open(meta_path, encoding="utf-8"))["cars"]:
                cars[c["id"]] = c
        except (ValueError, KeyError):
            cars = {}
    t0 = time.time()
    for n in names:
        spec = importlib.import_module("carcad.cars." + n).SPEC
        print("== %s ==" % spec["name"])
        cars[spec["id"]] = build_car(spec, OUT, shared)
    order = []
    for n in ORDER:
        try:
            cid = importlib.import_module("carcad.cars." + n).SPEC["id"]
        except ImportError:
            continue
        if cid in cars:
            order.append(cars[cid])
    tex_bytes = sum(v["bytes"] for v in shared.values())
    doc = {"version": 4, "generator": "tools/car-generator", "units": "Meter, +Y oben, +Z vorne, +X links",
           "sharedTextures": "textures/", "sharedTextureBytes": tex_bytes, "cars": order}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print("fertig in %.0fs -> %s" % (time.time() - t0, meta_path))


if __name__ == "__main__":
    main()
