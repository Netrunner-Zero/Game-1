#!/usr/bin/env python3
"""Karte mit dem Software-Renderer des Fahrzeug-Generators ansehen – inklusive Wiederholteilen
(Laternen, Ampeln, Bäume) und Ampel-Lampen, so wie das Spiel sie instanziert.

  python3 tools/world-generator/qa/render_map.py out.png world/neon_haven.glb --eye=x,y,z --target=x,y,z [--fov 60]
  optional: --car models/pulse.glb --car-at=x,z,yaw   (ein Auto zum Größenvergleich hineinstellen)
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "car-generator", "qa")))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
from render import Scene, Renderer  # noqa: E402
import worldgen  # noqa: E402,F401
from worldgen.maps import neon_haven  # noqa: E402,F401


def ground_fn(regions):
    def gh(x, z):
        h = 0.0
        for r in regions:
            if r["t"] != "rect":
                continue
            if abs(x - r["x"]) <= r["hx"] and abs(z - r["z"]) <= r["hz"]:
                h = max(h, r["h"])
        return h
    return gh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("glb")
    ap.add_argument("--eye", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--fov", type=float, default=60)
    ap.add_argument("--w", type=int, default=1000)
    ap.add_argument("--h", type=int, default=620)
    ap.add_argument("--car", default="")
    ap.add_argument("--car-at", default="")
    a = ap.parse_args()
    Scene.lod_level = None
    sc = Scene.load_glb(a.glb)
    meta = json.load(open(a.glb[:-4] + ".json", encoding="utf-8"))
    gh = ground_fn(meta.get("regions", []))
    eye = np.array([float(v) for v in a.eye.split(",")])
    tpl = {}
    rest = []
    for b in sc.batches:
        name = b["node"]
        key = next((k for k in ("Tpl_StreetLamp", "Tpl_Signal", "Tpl_Tree", "Prop_Cone") if name.startswith(k)), None)
        if key:
            tpl.setdefault(key, []).append(b)
        else:
            rest.append(b)
    sc.batches = rest
    for kind, d in meta.get("instances", {}).items():
        for it in d["items"]:
            x, z = it[0], it[1]
            if math.hypot(x - eye[0], z - eye[2]) > 160:
                continue
            yaw = it[2] if len(it) > 2 else 0.0
            s = it[3] if len(it) > 3 else 1.0
            c, sn = math.cos(yaw), math.sin(yaw)
            R = np.array([[c, 0, sn], [0, 1, 0], [-sn, 0, c]]) * s
            t = np.array([x, gh(x, z), z])
            for b in tpl.get(d["template"], []):
                sc.batches.append({"P": b["P"] @ R.T + t, "N": b["N"] @ R.T, "UV": b["UV"], "mat": b["mat"], "node": kind})
    # Ampel-Lampen als kleine Quadrate (rot/gelb/grün je nach Zeitpunkt 0)
    lamp_mats = [dict(sc.batches[0]["mat"], color=np.zeros(3, np.float32), emissive=np.array(c, np.float32), tex=None, emis_tex=None,
                      metallic=0.0, roughness=0.5, blend=False, mask=False, double=True)
                 for c in ((6, 0.2, 0.1), (5, 3, 0.2), (0.2, 5, 1.5))]
    S = meta.get("signals")
    if S:
        for (x, y, z, face, grp, off) in S["heads"]:
            if math.hypot(x - eye[0], z - eye[2]) > 160:
                continue
            C = S["cycle"]
            tg = ((off - grp * C / 2) % C)
            k = 2 if tg < S["green"] else 1 if tg < S["green"] + S["yellow"] else 0
            big = y > 4
            dy = 0.36 if big else 0.3
            fx, fz = math.sin(face) * (0.17 if big else 0.15), math.cos(face) * (0.17 if big else 0.15)
            yy = y + dy * (1 - k)
            rx, rz = math.cos(face), -math.sin(face)
            q = 0.12
            pts = [np.array([x + fx - rx * q, yy - q, z + fz - rz * q]), np.array([x + fx + rx * q, yy - q, z + fz + rz * q]),
                   np.array([x + fx + rx * q, yy + q, z + fz + rz * q]), np.array([x + fx - rx * q, yy + q, z + fz - rz * q])]
            n = np.array([math.sin(face), 0, math.cos(face)])
            P = np.array([[pts[0], pts[1], pts[2]], [pts[0], pts[2], pts[3]]])
            sc.batches.append({"P": P, "N": np.tile(n, (2, 3, 1)), "UV": np.zeros((2, 3, 2)), "mat": lamp_mats[k], "node": "lamp"})
    if a.car:
        cx, cz, cyaw = [float(v) for v in a.car_at.split(",")]
        Scene.lod_level = 1
        car = Scene.load_glb(a.car)
        c, sn = math.cos(cyaw), math.sin(cyaw)
        R = np.array([[c, 0, sn], [0, 1, 0], [-sn, 0, c]])
        t = np.array([cx, gh(cx, cz), cz])
        for b in car.batches:
            sc.batches.append({"P": b["P"] @ R.T + t, "N": b["N"] @ R.T, "UV": b["UV"], "mat": b["mat"], "node": "car"})
    r = Renderer(a.w, a.h, 1, env="studio")
    img = r.render(sc, eye, [float(v) for v in a.target.split(",")], fov=a.fov)
    img.save(a.out)
    print("gerendert:", a.out, sum(len(b["P"]) for b in sc.batches), "Dreiecke")


if __name__ == "__main__":
    main()
