#!/usr/bin/env python3
"""Vereinfachte Verkehrs-Autos („Proxys“) aus den fertigen Modellen erzeugen.

Für den Stadtverkehr werden Dutzende Autos gleichzeitig gezeichnet – dafür sind die echten Modelle zu
schwer. Dieses Skript nimmt die Detailstufe L2 jedes Autos, vereinfacht sie durch Zusammenfassen von
Punkten in einem Raster (zwei Stufen: nah und fern) und speichert alles als kompakte Binärdatei:

  models/traffic.bin   Positionen (float32), Normalen (int8), Farben (uint8), Merkmale (uint8), Indizes
  models/traffic.json  Inhaltsverzeichnis (Offsets, Anzahl, Maße)

Merkmale je Punkt (Bits): 1 Lack (wird je Auto eingefärbt), 2/4 Licht (1 Front, 2 Heck, 3 Blinker),
8 Glas, 16 Metall/Chrom. Das Spiel zeichnet je Auto-Typ und Stufe ein InstancedMesh.

  python3 tools/car-generator/traffic_proxies.py
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "qa"))
from render import Scene  # noqa: E402

MODELS = os.path.normpath(os.path.join(HERE, "..", "..", "models"))
CELLS = (0.04, 0.095)          # Rastergröße (m): nah, fern

LIGHT = {"Headlight": 1, "DRL": 1, "Taillight": 2, "Brakelight": 2, "Indicator": 3, "IndicatorR": 3}
METAL = ("Chrome", "Rim", "Aluminum", "Mirror", "Badge", "Exhaust")
SKIP = ("ContactShadow", "Underglow", "Accent", "Display", "Interior", "Starlight", "DomeLight", "Hologram", "Seal", "Plate")


def flags_for(name):
    f = 0
    if name in ("Paint", "Paint2"):
        f |= 1
    if name in LIGHT:
        f |= LIGHT[name] << 1
    if name == "Glass":
        f |= 8
    if any(name.startswith(m) for m in METAL):
        f |= 16
    return f


def cluster(P, cell):
    """Punktwolke + Dreiecke (je 3 Punkte) per Raster vereinfachen. Liefert (Punkte, Indizes)."""
    q = np.floor(P / cell).astype(np.int64)
    uniq, inv = np.unique(q, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    newP = np.zeros((len(uniq), 3))
    np.add.at(newP, inv, P)
    newP /= np.bincount(inv, minlength=len(uniq))[:, None]
    T = inv.reshape(-1, 3)
    ok = (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])
    T = T[ok]
    if len(T) == 0:
        return newP[:0], T
    srt = np.sort(T, axis=1)
    _, first = np.unique(srt, axis=0, return_index=True)
    T = T[np.sort(first)]
    used = np.unique(T)
    remap = -np.ones(len(newP), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return newP[used], remap[T]


def vertex_normals(P, T):
    n = np.zeros_like(P)
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    for k in range(3):
        np.add.at(n, T[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-12)


def build(meta):
    Scene.lod_level = 2
    sc = Scene.load_glb(os.path.join(MODELS, meta["file"]))
    groups = {}
    for b in sc.batches:
        m = b["mat"]
        name = m["name"]
        if any(name.startswith(s) for s in SKIP) or (m["blend"] and name != "Glass"):
            continue
        groups.setdefault(name, []).append(b)
    out = []
    for cell in CELLS:
        Ps, Ns, Cs, Fs, Is = [], [], [], [], []
        base = 0
        for name, bs in groups.items():
            m = bs[0]["mat"]
            P = np.concatenate([b["P"].reshape(-1, 3) for b in bs])
            V, T = cluster(P, cell)
            if len(T) == 0:
                continue
            N = vertex_normals(V, T)
            col = np.array(m["color"], dtype=np.float64)
            if m["tex"] is not None:
                col = col * np.power(m["tex"][..., :3].reshape(-1, 3).mean(0), 2.2)
            if name == "Glass":
                col = np.array([0.03, 0.04, 0.05])
            emis = np.array(m["emissive"])
            if emis.max() > 0.5 and name not in LIGHT:
                col = np.clip(col + emis * 0.2, 0, 1)
            srgb = np.power(np.clip(col, 0, 1), 1 / 2.2)
            Ps.append(V)
            Ns.append(N)
            Cs.append(np.tile((srgb * 255).round().astype(np.uint8), (len(V), 1)))
            Fs.append(np.full(len(V), flags_for(name), dtype=np.uint8))
            Is.append(T + base)
            base += len(V)
        out.append((np.concatenate(Ps).astype(np.float32), np.concatenate(Ns), np.concatenate(Cs), np.concatenate(Fs),
                    np.concatenate(Is)))
    return out


def main():
    cars = json.load(open(os.path.join(MODELS, "cars.json"), encoding="utf-8"))["cars"]
    blob = bytearray()
    index = {"version": 1, "cells": CELLS, "cars": []}

    def put(arr):
        while len(blob) % 4:
            blob.append(0)
        off = len(blob)
        blob.extend(arr.tobytes())
        return off

    for meta in cars:
        lods = []
        for (P, N, C, F, T) in build(meta):
            nq = np.clip(np.round(N * 127), -127, 127).astype(np.int8)
            idx = T.astype(np.uint16 if len(P) < 65536 else np.uint32)
            lods.append({"vertices": int(len(P)), "triangles": int(len(T)),
                         "position": put(P.reshape(-1)), "normal": put(nq.reshape(-1)), "color": put(C.reshape(-1)),
                         "flags": put(F), "index": put(idx.reshape(-1)), "index32": bool(idx.dtype == np.uint32)})
        index["cars"].append({"id": meta["id"], "lods": lods})
        print("  %-12s nah %5d / fern %5d Dreiecke" % (meta["id"], lods[0]["triangles"], lods[1]["triangles"]))
    with open(os.path.join(MODELS, "traffic.bin"), "wb") as f:
        f.write(bytes(blob))
    index["bytes"] = len(blob)
    with open(os.path.join(MODELS, "traffic.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1)
    print("traffic.bin: %.2f MB" % (len(blob) / 1e6))


if __name__ == "__main__":
    main()
