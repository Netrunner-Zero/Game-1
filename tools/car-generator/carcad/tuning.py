"""Tuning-Teile: Spoiler, Folierungen, Auspuffanlagen, Unterbodenbeleuchtung.

Jede Variante ist ein eigener Knoten (Spoiler_1..3, Livery_1..3,
Exhaust_1..3, RollCage_1..2, EngineStage_N). Das Spiel blendet die
gewählte Variante ein und die anderen aus.
"""
import math

import numpy as np

from .mesh import Part, norm, round_rect, resample, rot_matrix
from .parts import Conformer, place_side, decal_local, exhaust_tip, conform_part
from .interior import CabinGeo


# ----------------------------------------------------------------------
# Spoiler
# ----------------------------------------------------------------------

def airfoil(chord, thick, n=10, camber=0.04):
    """Profil (z nach vorne, y nach oben), Vorderkante bei +chord/2."""
    top, bot = [], []
    for i in range(n + 1):
        x = i / n
        yt = 5 * thick * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1015 * x ** 4)
        yc = camber * chord * 4 * x * (1 - x)
        z = chord / 2 - x * chord
        top.append((z, yc + yt * chord))
        bot.append((z, yc - yt * chord))
    return top + list(reversed(bot[1:-1]))


def wing(part, center, span, chord, thick, angle_deg, mat, n_span=12, camber=0.05):
    prof = airfoil(chord, thick, 10, camber)
    a = math.radians(angle_deg)
    R = rot_matrix(a, 0, 0)
    secs = []
    for t in np.linspace(-1, 1, n_span):
        x = center[0] + t * span / 2
        taper = 1.0 - 0.04 * abs(t)
        secs.append([np.asarray(center) + np.array([t * span / 2, 0, 0]) + R @ np.array([0.0, y * taper, z * taper])
                     for (z, y) in prof])
    part.loft(secs, lambda k, j: mat, caps=(mat, mat), smooth=True)


def endplate(part, center, h, length, thick, mat, rake=0.0):
    pts = [(-length / 2, -h / 2), (length / 2, -h / 2 + 0.01), (length / 2 - 0.02, h / 2), (-length / 2 + 0.03 + rake, h / 2)]
    secs = []
    for dx in (-thick / 2, thick / 2):
        secs.append([np.asarray(center) + np.array([dx, y, z]) for (z, y) in pts])
    part.loft(secs, lambda k, j: mat, caps=(mat, mat), smooth=False)


def spoilers(ctx):
    sp = ctx.spec["spoiler"]
    b = ctx.b
    out = []
    zt = sp["z"]
    w = sp["w"]
    roof = sp.get("roof", False)
    if roof:
        cg = CabinGeo(b)
        y_at = lambda z: cg.roof(z)
    else:
        y_at = lambda z: b.top_y(z, 0.0)
    y = sp.get("y") or y_at(zt)
    lip_len, lip_rise = sp.get("lip", (0.22, 0.07))
    over = sp.get("over", 0.0)
    lod = ctx.lod

    # 1: Lippe / Ducktail – folgt der Oberfläche
    p = Part("Spoiler_1")
    zs = np.linspace(zt - over, zt + lip_len, 8)
    xs = np.linspace(-w, w, 14)
    top_rows, bot_rows = [], []
    for z in zs:
        t = (z - (zt - over)) / (lip_len + over)
        rise = lip_rise * (1 - t) ** 1.4
        trow, brow = [], []
        for x in xs:
            ys = y_at(z) if (roof or abs(x) < 0.5) else b.top_y(z, x)
            if not roof:
                ys = b.top_y(z, x * 0.98)
            elif z < zt:
                ys = y_at(zt)
            taper = 1 - (abs(x) / w) ** 6
            trow.append(np.array([x, ys + 0.004 + rise * taper, z]))
            brow.append(np.array([x, ys - 0.012, z]))
        top_rows.append(trow)
        bot_rows.append(brow)
    secs = []
    for i in range(len(zs)):
        secs.append(top_rows[i] + list(reversed(bot_rows[i])))
    p.loft(secs, lambda k, j: sp.get("lip_mat", "Paint"), caps=(sp.get("lip_mat", "Paint"), sp.get("lip_mat", "Paint")),
           smooth=True)
    out.append(p)

    # 2: GT-Flügel (Carbon) auf Stützen
    p = Part("Spoiler_2")
    h = sp.get("h2", 0.24)
    zc = zt + 0.07
    for sx in (-1, 1):
        xs_ = sx * w * 0.55
        base_y = y_at(zc + 0.05) if roof else b.top_y(zc + 0.05, xs_)
        prof = round_rect(0.014, 0.12, 0.005, 2)
        secs = [[np.array([xs_ + u, base_y - 0.01 + hh, zc + 0.05 + v - hh * 0.25]) for (u, v) in prof]
                for hh in np.linspace(0, h + 0.02, 5)]
        p.loft(secs, lambda k, j: "Carbon", caps=("Carbon", "Carbon"), smooth=True)
    wing(p, (0.0, y + h, zc - 0.02), 2 * w * 1.02, 0.30, 0.12, 9.0, "Carbon", n_span=14 if lod == 0 else 4)
    for sx in (-1, 1):
        endplate(p, (sx * (w * 1.02 + 0.006), y + h + 0.01, zc - 0.02), 0.17, 0.36, 0.012, "Carbon")
    out.append(p)

    # 3: Cyber-Flügel (Schwanenhals, Neon-Abrisskante)
    p = Part("Spoiler_3")
    h = sp.get("h3", 0.40)
    zc = zt + 0.02
    yw = y + h
    for sx in (-1, 1):
        xs_ = sx * w * 0.45
        base_y = y_at(zc + 0.18) if roof else b.top_y(zc + 0.18, xs_)
        path = []
        for t in np.linspace(0, 1, 9):
            zz = zc + 0.18 - 0.30 * t + 0.08 * math.sin(t * math.pi)
            yy = base_y - 0.01 + (yw + 0.03 - base_y) * (1 - (1 - t) ** 2)
            path.append(np.array([xs_, yy, zz]))
        p.sweep(path, round_rect(0.016, 0.07, 0.006, 2), "Trim", up=(1, 0, 0))
    wing(p, (0.0, yw, zc - 0.04), 2 * w * 1.08, 0.36, 0.11, 7.0, "Paint", n_span=16 if lod == 0 else 4)
    p.box((0.0, yw + 0.022, zc - 0.215), (2 * w * 1.04, 0.008, 0.012), "Accent", rot=(math.radians(7), 0, 0))
    for sx in (-1, 1):
        endplate(p, (sx * (w * 1.08 + 0.008), yw + 0.02, zc - 0.06), 0.24, 0.46, 0.012, "Trim", rake=0.06)
    out.append(p)
    return out


# ----------------------------------------------------------------------
# Folierungen
# ----------------------------------------------------------------------

def liveries(ctx):
    b = ctx.b
    sp = ctx.spec
    cab = sorted(sp["cabin"], key=lambda c: -c["z"])
    cg = CabinGeo(b)
    wf, wr = sp["wheels"]["front"], sp["wheels"]["rear"]
    z0 = wr["z"] + wr["R"] + 0.14
    z1 = wf["z"] - wf["R"] - 0.14
    out = []
    # 1: Doppelte Rennstreifen
    l1 = Part("Livery_1")
    zo0, zo1 = b.cabin_open_range()
    for x0, x1 in ((0.07, 0.17), (-0.17, -0.07)):
        for (za, zb) in ((zo1 + 0.03, b.zf - 0.06), (b.zr + 0.06, zo0 - 0.03)):
            if zb - za < 0.05:
                continue
            # Unterbrechungen (z. B. über Hutzen/Lüftungsschlitzen)
            pieces = [(za, zb)]
            for (s0, s1) in sp.get("livery_skip_z", []):
                nxt = []
                for (a_, b_) in pieces:
                    if s1 <= a_ or s0 >= b_:
                        nxt.append((a_, b_))
                        continue
                    if s0 > a_:
                        nxt.append((a_, s0))
                    if s1 < b_:
                        nxt.append((s1, b_))
                pieces = nxt
            xm = (x0 + x1) / 2
            for (a_, b_) in pieces:
                if b_ - a_ < 0.04:
                    continue
                n_ = max(4, int((b_ - a_) / 0.04))
                samples = [(z, b.j_at_x_top(z, xm)) for z in np.linspace(a_, b_, n_)]
                b.strip(l1, samples, abs(x1 - x0), "Livery", offset=0.0025)
        # Dach
        roofs = [c for c in cab if c["kind"] in ("roof", "glassroof", "pillar")]
        if roofs and not any(c["kind"] == "glassroof" for c in cab):
            zr0 = max(c["z"] for c in roofs) + 0.02
            zr1 = min(c["z"] for c in roofs) - 0.02
            zz = np.linspace(zr1, zr0, 12)
            for k in range(len(zz) - 1):
                ya = cg.glass_y(zz[k], (x0 + x1) / 2) + 0.004
                yb_ = cg.glass_y(zz[k + 1], (x0 + x1) / 2) + 0.004
                l1.quad((x0, ya, zz[k]), (x1, ya, zz[k]), (x1, yb_, zz[k + 1]), (x0, yb_, zz[k + 1]), "Livery",
                        outward=(0, 1, 0))
    out.append(l1)
    # 2: Seitenblitz
    l2 = Part("Livery_2")
    for side in (1, -1):
        n = 7
        pts = []
        for i in range(n + 1):
            z = z1 - (z1 - z0) * i / n
            lo = b.params_at(z)["yb"] + 0.12
            hi = b.params_at(z)["yt"] - 0.1
            pts.append((z, lo + 0.02 if i % 2 == 0 else hi - 0.02))
        for i in range(n):
            (za, ya), (zb, yb_) = pts[i], pts[i + 1]
            path = [(za + (zb - za) * t, ya + (yb_ - ya) * t) for t in np.linspace(0, 1, 5)]
            samples = [(z, b.j_at_height(z, y, side)) for (z, y) in path]
            b.strip(l2, samples, 0.045, "Livery", offset=0.0025)
    out.append(l2)
    # 3: Startnummer + Linie
    l3 = Part("Livery_3")
    zc = (z0 + z1) / 2 + 0.05
    yc = (b.params_at(zc)["yb"] + b.params_at(zc)["yt"]) / 2 + 0.02
    d = min(0.32, (b.params_at(zc)["yt"] - b.params_at(zc)["yb"]) * 0.62)
    place_side(ctx, decal_local(d, d, "Number", wv=0.0025), zc, yc, (d, d), l3, mirror=True)
    for side in (1, -1):
        samples = [(z, b.j_at_height(z, b.params_at(z)["yt"] - 0.07, side)) for z in np.linspace(z0, z1, 20)]
        b.strip(l3, samples, 0.014, "Livery", offset=0.0025)
    out.append(l3)
    return out


# ----------------------------------------------------------------------
# Auspuffanlagen
# ----------------------------------------------------------------------

def exhausts(ctx):
    """ctx.spec['exhaust'] = {'y': .., 'variants': [ [ (x, r, style, mat), ... ], ... ], 'side_pipes': idx}"""
    ex = ctx.spec["exhaust"]
    out = []
    for vi, layout in enumerate(ex["variants"]):
        p = Part("Exhaust_%d" % (vi + 1))
        for item in layout:
            if item[0] == "side":
                # Sidepipes vor dem Hinterrad, Mündung zeigt zur Seite
                _, z, y, r, mat = item
                for sx in (1, -1):
                    hit = ctx.hit_side(z, y, sx)
                    if hit is None:
                        continue
                    P = hit[0] + np.array([sx * 0.025, 0, 0])
                    M = rot_matrix(0, -sx * math.pi / 2, 0)    # Rohr zeigt nach innen, Mündung nach außen
                    exhaust_tip(p, P, r, 0.06, "round", mat, lod=ctx.lod, M=M)
                    outs = ctx.meta.setdefault("exhaust_out", {}).setdefault(vi + 1, [])
                    outs.append([round(float(v), 3) for v in P] + [float(sx), 0.0, 0.0])
                    p.tube([P + np.array([-sx * 0.02, 0, 0.0]), P + np.array([-sx * 0.02, -0.03, 0.35])], r * 0.9, mat,
                           segs=14)
                continue
            x, r, style, mat = item[:4]
            y = ex.get("y", 0.3) if len(item) < 5 else item[4]
            hit = ctx.hit_rear(x, y)
            if hit is None:
                continue
            P = hit[0] + np.array([0, 0, -ex.get("protrude", 0.018)])
            exhaust_tip(p, P, r, 0.08, style, mat, lod=ctx.lod)
            outs = ctx.meta.setdefault("exhaust_out", {}).setdefault(vi + 1, [])
            outs.append([round(float(v), 3) for v in P] + [0.0, 0.0, -1.0])
            # dunkle Aussparung im Stoßfänger
            loc = Part("cut")
            if style == "square":
                o = round_rect(r * 3.1, r * 1.8, r * 0.4, 4)
            else:
                k = 1.45 if style == "oval" else 1.0
                o = [(r * 1.22 * k * math.cos(a), r * 1.22 * (0.8 if style == "oval" else 1.0) * math.sin(a))
                     for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
            c = np.array([0.0, 0.0, 0.0012])
            pts = [np.array([u, v, 0.0012]) for (u, v) in o]
            for i in range(len(pts)):
                loc.tri(c, pts[i], pts[(i + 1) % len(pts)], "ExhaustInner", outward=(0, 0, 1))
            conform_part(ctx, loc, hit[0], hit[1], (r * 3.2, r * 2.6), dst=p, mirror=False)
        out.append(p)
    return out


# ----------------------------------------------------------------------
# Unterbodenbeleuchtung
# ----------------------------------------------------------------------

def underglow(ctx):
    b = ctx.b
    sp = ctx.spec
    p = Part("Underglow")
    zf_, zr_ = sp["wheels"]["front"]["z"], sp["wheels"]["rear"]["z"]
    ybmin = min(s["yb"] for s in sp["body"])
    wmin = min(b.params_at(z)["w"] for z in np.linspace(zr_, zf_, 9))
    y = ybmin - 0.02
    p.rbox((0, y, (zf_ + zr_) / 2), (wmin * 1.6, 0.01, (zf_ - zr_) * 0.9), 0.004, "Underglow", segs=1)
    return p
