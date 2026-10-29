"""Mehrere Ansichten parallel rendern und zu einem Kontrollbogen zusammensetzen.

  python3 qa/sheet.py out.png models/vektra_gt.glb front34 side "eye=1.6,0.9,4.6;target=0.1,0.4,1.8;fov=34" \
          [--cols 2] [--w 900] [--h 560] [--set Spoiler=2] [--lod 0] [--env night]
"""
import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as RD  # noqa: E402


def job(args):
    glb, view, w, h, settings, lod, env, hide, exposure = args
    RD.Scene.settings = settings
    RD.Scene.lod_level = lod
    sc = RD.Scene.load_glb(glb, hide=hide)
    allP = np.concatenate([b["P"].reshape(-1, 3) for b in sc.batches])
    L = (allP[:, 2].max() - allP[:, 2].min()) / 2
    Hh = allP[:, 1].max()
    if "=" in view:
        d = dict(kv.split("=") for kv in view.split(";"))
        eye = [float(x) for x in d["eye"].split(",")]
        tgt = [float(x) for x in d["target"].split(",")]
        fov = float(d.get("fov", 40))
        near = float(d.get("near", 0.02))
    else:
        eye, tgt, fov = RD.VIEWS[view](L, Hh)
        near = 0.02
    r = RD.Renderer(w, h, 2, env=env)
    return r.render(sc, eye, tgt, fov=fov, near=near, exposure=exposure)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("glb")
    ap.add_argument("views", nargs="+")
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--w", type=int, default=900)
    ap.add_argument("--h", type=int, default=560)
    ap.add_argument("--set", default="")
    ap.add_argument("--lod", type=int, default=0)
    ap.add_argument("--env", default="studio")
    ap.add_argument("--hide", default="")
    ap.add_argument("--exposure", type=float, default=1.0)
    a = ap.parse_args()
    settings = {k: int(v) for k, v in (kv.split("=") for kv in a.set.split(",") if kv)}
    hide = [h for h in a.hide.split(",") if h]
    lod = None if a.lod < 0 else a.lod
    jobs = [(a.glb, v, a.w, a.h, settings, lod, a.env, hide, a.exposure) for v in a.views]
    with Pool(min(len(jobs), os.cpu_count() or 2)) as pool:
        ims = pool.map(job, jobs)
    cols = min(a.cols, len(ims))
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGB", (cols * a.w, rows * a.h))
    for k, im in enumerate(ims):
        out.paste(im, ((k % cols) * a.w, (k // cols) * a.h))
    out.save(a.out)
    print("Kontrollbogen:", a.out)


if __name__ == "__main__":
    main()
