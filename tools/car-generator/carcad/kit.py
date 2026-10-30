"""Baukasten für Außendetails, den alle Autos benutzen.

Lampen, Einlässe, Lamellen, Spiegel, Griffe, Wischer, Embleme,
Splitter, Schweller, Diffusor-Finnen, Motorraum und Motoren.
Alle Funktionen arbeiten mit dem Baukontext ctx (eine LOD-Stufe) und
schreiben in benannte Teile (ctx.part(name)).
"""
import math

import numpy as np

from .mesh import Part, norm, frame, round_rect, round_poly, resample, rot_matrix, round_open, axis_angle
from .parts import (conform_part, lamp_local, place_lamp, grille_local, place_front, place_side, place_top,
                    place_flat, decal_local, tray, pillow, flat_shape, strip2d, rr_outline, densify, fill_shape,
                    seg_box)
from .interior import CabinGeo


def rshape(pts, r=0.012, n=3):
    """Polygon mit gerundeten Ecken (für Lampen-/Einlassumrisse)."""
    return round_poly(pts, r, n)


def mirror_uv(shape):
    return [(-u, v) for (u, v) in reversed(shape)]


# ----------------------------------------------------------------------
# Lampen und Öffnungen
# ----------------------------------------------------------------------

def lamp(ctx, spec, x, y, front=True, mirror=True, blend=0.55, part="Lights"):
    return place_lamp(ctx, spec, x, y, front=front, dst=ctx.part(part), mirror=mirror, normal_blend=blend)


def opening(ctx, outline, where, a, b, depth=0.06, style="honeycomb", frame_mat="Trim", mesh_mat="Mesh",
            cell=0.026, mirror=False, blend=0.5, part="Openings", frame_w=0.010, up_hint=(0, 1, 0), normal=None):
    """Lufteinlass/Grill in einer echten Öffnung.

    where: front (a=x, b=y), rear (a=x, b=y), side (a=z, b=y), top (a=x, b=z)."""
    P = np.array(outline)
    w = P[:, 0].max() - P[:, 0].min()
    h = P[:, 1].max() - P[:, 1].min()
    local = grille_local(w, h, style, depth=depth, frame_w=frame_w, frame_mat=frame_mat, mesh_mat=mesh_mat,
                         lod=ctx.lod, cell=cell, shape=outline)
    dst = ctx.part(part)
    cut = outline if ctx.lod == 0 else None
    if where in ("front", "rear"):
        return place_front(ctx, local, a, b, (w, h), dst, mirror=mirror, normal_blend=blend, rear=(where == "rear"),
                           cut=cut)
    if where == "side":
        return place_side(ctx, local, a, b, (w, h), dst, mirror=mirror, cut=cut, normal=normal)
    return place_top(ctx, local, a, b, (w, h), dst, mirror=mirror, up_hint=up_hint, cut=cut)


def louvres(ctx, x, z, w, l, n, angle=35.0, depth=0.05, mat="BlackGloss", frame_mat="Trim", part="Openings",
            mirror=False):
    """Lamellen in einer Öffnung auf der Oberseite (Motorhaube/Heckdeckel)."""
    outline = rr_outline(w, l, 0.02, 4)
    p = Part("louvres")
    if ctx.lod == 0:
        tray(p, outline, depth, "Mesh", "Mesh")
        for i in range(n):
            v = -l / 2 + l * (i + 0.5) / n
            seg_box(p, (0, v, -0.012), (w - 0.012, 0.010, l / n * 1.15), mat, rot=(math.radians(angle), 0, 0))
        # Rahmen
        outer = densify(outline, 0.015)
        cen = np.mean(np.array(outer), axis=0)
        inner = [(u - np.sign(u - cen[0]) * 0.008 * abs(u) / (w / 2), v - np.sign(v) * 0.008 * abs(v) / (l / 2))
                 for (u, v) in outer]
        for i in range(len(outer)):
            j = (i + 1) % len(outer)
            p.quad((*outer[i], 0.0025), (*outer[j], 0.0025), (*inner[j], 0.0025), (*inner[i], 0.0025), frame_mat,
                   outward=(0, 0, 1))
    else:
        flat_shape(p, outline, 0.0015, "Mesh")
        for i in range(n):
            v = -l / 2 + l * (i + 0.5) / n
            seg_box(p, (0, v, 0.003), (w - 0.012, 0.010, 0.003), mat)
    return place_top(ctx, p, x, z, (w, l), ctx.part(part), mirror=mirror, up_hint=(0, 0, 1),
                     cut=outline if ctx.lod == 0 else None)


# ----------------------------------------------------------------------
# Grundriss-Konturen: Splitter, Schweller
# ----------------------------------------------------------------------

def side_line(ctx, y, z0, z1, n=16):
    pts = []
    for z in np.linspace(z0, z1, n):
        h = ctx.hit_side(z, y, 1)
        if h is not None:
            pts.append((float(h[0][0]), float(z)))
    return pts


def plan_ring(ctx, y, z_from, front=True, n_side=8, n_arc=30, depth=0.55):
    """Kontur der Karosserie bei Höhe y (Draufsicht) um Front oder Heck: Liste (x, z),
    rechte Seite ab z_from, um das Ende herum, linke Seite zurück."""
    b = ctx.b
    sgn = 1.0 if front else -1.0
    zend = b.zf if front else b.zr
    zc = zend - sgn * depth
    side = side_line(ctx, y, z_from, zc, n_side)
    arc = []
    for k in range(n_arc + 1):
        a = math.pi * k / n_arc
        d = np.array([math.cos(a), 0.0, sgn * math.sin(a)])
        o = np.array([0.0, y, zc]) + d * 3.0
        h = ctx.rc.cast(o, -d, max_t=3.2)
        if h is not None:
            arc.append((float(h[0][0]), float(h[0][2])))
    left = [(-x, z) for (x, z) in reversed(side)]
    pts = side + arc + left
    # Duplikate entfernen
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 0.004:
            out.append(p)
    return out, zc


def offset_line(pts, d, ref):
    """Polylinie (x, z) um d nach außen versetzen (weg vom Referenzpunkt ref=(x, z))."""
    P = np.asarray(pts, dtype=float)
    n = len(P)
    out = []
    for i in range(n):
        a = P[max(i - 1, 0)]
        b = P[min(i + 1, n - 1)]
        t = b - a
        t /= max(np.linalg.norm(t), 1e-12)
        nn = np.array([t[1], -t[0]])
        if np.dot(nn, P[i] - np.asarray(ref)) < 0:
            nn = -nn
        out.append(tuple(P[i] + nn * d))
    return out


def plan_slab(part, inner, outer, y_top, thick, mat, edge=True):
    """Platte zwischen zwei Konturen (Splitter, Schwellerleiste) mit Außenkante."""
    n = len(inner)
    yb = y_top - thick
    for i in range(n - 1):
        i0, i1 = inner[i], inner[i + 1]
        o0, o1 = outer[i], outer[i + 1]
        part.quad((i0[0], y_top, i0[1]), (o0[0], y_top, o0[1]), (o1[0], y_top, o1[1]), (i1[0], y_top, i1[1]), mat,
                  outward=(0, 1, 0))
        part.quad((i0[0], yb, i0[1]), (o0[0], yb, o0[1]), (o1[0], yb, o1[1]), (i1[0], yb, i1[1]), mat,
                  outward=(0, -1, 0))
        if edge:
            on = np.array([o1[1] - o0[1], 0.0, -(o1[0] - o0[0])])
            mid_o = np.array([(o0[0] + o1[0]) / 2, 0, (o0[1] + o1[1]) / 2])
            mid_i = np.array([(i0[0] + i1[0]) / 2, 0, (i0[1] + i1[1]) / 2])
            if np.dot(on, mid_o - mid_i) < 0:
                on = -on
            part.quad((o0[0], y_top, o0[1]), (o1[0], y_top, o1[1]), (o1[0], yb, o1[1]), (o0[0], yb, o0[1]), mat,
                      outward=on)
    for (i_, o_) in ((inner[0], outer[0]), (inner[-1], outer[-1])):
        part.quad((i_[0], y_top, i_[1]), (o_[0], y_top, o_[1]), (o_[0], yb, o_[1]), (i_[0], yb, i_[1]), mat)


def splitter(ctx, y, z_from, out=0.045, inset=0.10, thick=0.016, mat="Carbon", front=True, part="Aero"):
    ring, zc = plan_ring(ctx, y + 0.012, z_from, front=front)
    if len(ring) < 4:
        return
    ref = (0.0, zc)
    outer = offset_line(ring, out, ref)
    inner = offset_line(ring, -inset, ref)
    plan_slab(ctx.part(part), inner, outer, y, thick, mat)


def side_skirt(ctx, y, z0, z1, out=0.03, thick=0.018, inset=0.06, mat="Carbon", part="Aero", fence=0.0):
    pts = side_line(ctx, y + 0.01, z0, z1, 18)
    if len(pts) < 2:
        return
    p = ctx.part(part)
    for sgn in (1, -1):
        line = [(sgn * x, z) for (x, z) in pts]
        outer = [(x + sgn * out, z) for (x, z) in line]
        inner = [(x - sgn * inset, z) for (x, z) in line]
        plan_slab(p, inner, outer, y, thick, mat)
        if fence > 0:
            # senkrechte Leiste an der Außenkante (Luftleitkante)
            for i in range(len(outer) - 1):
                a, b_ = outer[i], outer[i + 1]
                p.quad((a[0], y, a[1]), (b_[0], y, b_[1]), (b_[0], y + fence, b_[1]), (a[0], y + fence, a[1]), mat,
                       outward=(sgn, 0, 0))


def rear_panel(ctx, x, y, w, h, mat="Carbon", part="Aero", r=0.03, rear=True):
    """Aufgesetzte Blende (z. B. Diffusor-Einfassung) als dünne, der Form folgende Platte."""
    o = densify(rr_outline(w, h, r, 4), 0.015)
    loc = Part("panel")
    secs = [[np.array([u * s_, v * s_, wv]) for (u, v) in o] for (wv, s_) in ((-0.002, 1.0), (0.004, 0.996))]
    loc.loft(secs, lambda k, j: mat, caps=(None, None), smooth=True)
    inner = [(u * 0.996, v * 0.996) for (u, v) in rr_outline(w, h, r, 4)]
    fill_shape(loc, inner, lambda u, v, su, sv: 0.004, mat, outward=(0, 0, 1), max_du=0.025, max_dv=0.025)
    place_front(ctx, loc, x, y, (w, h), ctx.part(part), mirror=False, normal_blend=0.6, rear=rear)


def diffuser_fins(ctx, xs, z_back, length, y_bottom, height, mat="Carbon", part="Aero", thick=0.012):
    p = ctx.part(part)
    for x in xs:
        secs = []
        for t in np.linspace(0, 1, 6):
            z = z_back + length * t
            hh = height * (1 - t) ** 0.8 + 0.01
            secs.append([np.array([x + u, y_bottom + v, z]) for (u, v) in
                         ((-thick / 2, 0.0), (thick / 2, 0.0), (thick / 2, hh), (-thick / 2, hh))])
        p.loft(secs, lambda k, j: mat, caps=(mat, mat))


# ----------------------------------------------------------------------
# Spiegel, Griffe, Wischer, Embleme
# ----------------------------------------------------------------------

def side_mirror(ctx, z, y, reach=0.20, rise=0.05, length=0.19, h=0.09, depth=0.12, body_mat="Paint",
                cap_mat=None, stalk_mat="Trim", indicator=True, part="Mirrors", stalk_w=0.05):
    """Außenspiegel (links gebaut, rechts gespiegelt). Fuß auf der Tür bei (z, y)."""
    hit = ctx.hit_side(z, y, 1)
    if hit is None:
        return
    base = hit[0]
    lod = ctx.lod
    p = Part("mirror")
    segs = 5 if lod == 0 else 2
    x0 = base[0] + reach - length * 0.15
    c = np.array([x0, base[1] + rise, base[2] - 0.02])
    # Gehäuse: Querschnitte (z, y) entlang x; vorne rund, hinten flach (Glas)
    secs = []
    nx = 9 if lod == 0 else 4
    for t in np.linspace(0.0, 1.0, nx):
        s = math.sin(min(t, 1.0) * math.pi * 0.5) ** 0.6
        e = 1.0 - (max(0.0, t - 0.82) / 0.18) ** 2 * 0.85
        hh = h * (0.62 + 0.38 * s) * e
        dd = depth * (0.55 + 0.45 * s) * (0.75 + 0.25 * e)
        prof = []
        for k in range(16 if lod == 0 else 8):
            a = 2 * math.pi * k / (16 if lod == 0 else 8)
            yy = math.sin(a) * hh / 2
            zz = math.cos(a)
            zz = (zz * dd * 0.5) if zz > 0 else (zz * 0.08 * dd)      # vorne rund, hinten fast flach
            prof.append(np.array([c[0] + t * length, c[1] + yy, c[2] + zz]))
        secs.append(prof)
    p.loft(secs, lambda k, j: (cap_mat or body_mat) if (cap_mat and (j < 4 or j > 12)) else body_mat,
           caps=(body_mat, body_mat), smooth=True)
    # Spiegelglas (hinten)
    gz = c[2] - 0.08 * depth * 0.5 - 0.004
    p.tex_quad((c[0] + length * 0.52, c[1], gz), (1, 0, 0), (0, 1, 0), length * 0.78, h * 0.72, "Mirror")
    # Rahmen ums Glas
    p.rbox((c[0] + length * 0.52, c[1], gz + 0.004), (length * 0.84, h * 0.80, 0.008), 0.012, "Trim", segs=2)
    if indicator and lod == 0:
        p.box((c[0] + length * 0.6, c[1] - h * 0.36, c[2] + depth * 0.18), (length * 0.55, 0.008, 0.03), "Indicator",
              rot=(math.radians(-25), 0, 0))
    # Fuß/Stiel: vom Türblech zum Gehäuse
    st = []
    for t in np.linspace(0, 1, 5):
        pt = base * (1 - t) + np.array([c[0] + length * 0.12, c[1] - h * 0.15, c[2] + 0.01]) * t
        ww = stalk_w * (1.4 - 0.6 * t)
        th = 0.022 * (1.3 - 0.5 * t)
        st.append([pt + np.array([0, v, u]) for (u, v) in round_rect(ww, th, min(ww, th) * 0.45, 2)])
    p.loft(st, lambda k, j: stalk_mat, caps=(None, stalk_mat), smooth=True)
    dst = ctx.part(part)
    dst.merge(p)
    dst.merge(p.mirrored_x())
    if lod == 0:
        ctx.meta.setdefault("mirrors", []).append([round(float(v), 3) for v in c])


def flush_handle(ctx, z, y, w=0.13, h=0.026, mat="BlackGloss", part="Trim"):
    loc = Part("handle")
    o = rr_outline(w, h, h * 0.48, 4)
    secs = [[np.array([u * s, v * s, wv]) for (u, v) in o] for (wv, s) in ((0.0, 1.0), (0.003, 0.97), (0.004, 0.9))]
    loc.loft(secs, lambda k, j: mat, caps=(None, mat), smooth=True)
    place_side(ctx, loc, z, y, (w, h), ctx.part(part), mirror=True)


def pull_handle(ctx, z, y, w=0.16, h=0.03, mat="Chrome", part="Trim"):
    """Bügelgriff (klassisch): Mulde + Griff."""
    loc = Part("handle")
    o = rr_outline(w + 0.03, h + 0.03, 0.02, 4)
    flat_shape(loc, o, 0.0012, "Trim")
    loc.rbox((0, 0, 0.012), (w, h * 0.6, 0.016), h * 0.28, mat, segs=3)
    place_side(ctx, loc, z, y, (w + 0.03, h + 0.03), ctx.part(part), mirror=True)


def wiper(ctx, x0, x1, dz=0.06, part="Trim", pivots=None):
    """Scheibenwischer auf der Frontscheibe (liegt am unteren Rand)."""
    b = ctx.b
    cg = CabinGeo(b)
    cab = sorted(ctx.spec["cabin"], key=lambda c: -c["z"])
    zws = cab[0]["z"]
    p = ctx.part(part)
    pts = []
    for t in np.linspace(0, 1, 10):
        x = x0 + (x1 - x0) * t
        z = zws - dz - 0.03 * t
        y = cg.glass_y(z, x)
        pts.append(np.array([x, y + 0.012, z]))
    p.sweep(pts, round_rect(0.016, 0.012, 0.004, 1), "Wiper", up=(0, 1, 0))
    for pv in (pivots or [x0]):
        z = zws + 0.01
        y = b.top_y(z, pv) + 0.01
        p.lathe([(0.0, 0.0), (0.0, 0.016), (0.014, 0.013), (0.02, 0.0)], 10, "Wiper", center=(pv, y, z), axis="y",
                inside=(0.006, 0.0))


def emblem(ctx, pos, normal, d=0.075, part="Badges", mat="Badge"):
    loc = Part("emblem")
    if ctx.lod == 0:
        loc.lathe([(0.0, d / 2 + 0.003), (0.004, d / 2 + 0.002), (0.0055, d / 2 - 0.002), (0.0055, d / 2 - 0.004)], 32,
                  "Chrome", center=(0, 0, 0), axis="z", inside=(0.0, d / 4))
    loc.tex_quad((0, 0, 0.0052), (1, 0, 0), (0, 1, 0), d, d, mat)
    place_flat(ctx, loc, pos, normal, (d, d), ctx.part(part), lift=0.001)


def wordmark(ctx, x, y, w, h, rear=True, part="Badges", blend=0.6):
    loc = decal_local(w, h, "Wordmark", wv=0.0022)
    place_front(ctx, loc, x, y, (w, h), ctx.part(part), mirror=False, normal_blend=blend, rear=rear)


def side_badge(ctx, z, y, w, h, mat="Wordmark", part="Badges"):
    """Schriftzug an beiden Seiten (nicht gespiegelt lesbar)."""
    for side in (1, -1):
        hit = ctx.hit_side(z, y, side)
        if hit is None:
            continue
        loc = decal_local(w, h, mat, wv=0.0022)
        from .parts import conform_part as _cp
        _cp(ctx, loc, hit[0], hit[1], (w, h), dst=ctx.part(part), mirror=False)


# ----------------------------------------------------------------------
# Motorraum und Motoren
# ----------------------------------------------------------------------

def bay_box(part, x, y0, y1, z0, z1, mat="EngineBlack"):
    """Offene Motorraum-Wanne (Innenflächen sichtbar)."""
    # Boden
    part.quad((x, y0, z0), (-x, y0, z0), (-x, y0, z1), (x, y0, z1), mat, outward=(0, 1, 0))
    for sx in (1, -1):
        part.quad((sx * x, y0, z0), (sx * x, y0, z1), (sx * x, y1, z1), (sx * x, y1, z0), mat, outward=(-sx, 0, 0))
    part.quad((x, y0, z0), (-x, y0, z0), (-x, y1, z0), (x, y1, z0), mat, outward=(0, 0, 1 if z1 > z0 else -1))
    part.quad((x, y0, z1), (-x, y0, z1), (-x, y1, z1), (x, y1, z1), mat, outward=(0, 0, -1 if z1 > z0 else 1))


def v_engine(part, c, length, cyl_per_bank, bank_angle=90.0, bore=0.09, cover_mat="EngineRed",
             block_mat="EngineMetal", plenum_mat="EngineBlack", lod=0, plenum_h=0.10, label=True):
    """V-Motor, Kurbelwelle entlang z. c = Mitte der Kurbelwelle (Unterkante Köpfe)."""
    c = np.asarray(c, dtype=float)
    half = math.radians(bank_angle / 2)
    L = length
    # Block (Kurbelgehäuse)
    part.rbox(c + np.array([0, -0.06, 0]), (0.34, 0.16, L), 0.03, block_mat, segs=2)
    for sx in (1, -1):
        d = np.array([sx * math.sin(half), math.cos(half), 0.0])
        Mb = rot_matrix(0, 0, -sx * half)
        head_c = c + d * 0.20
        part.rbox(head_c, (0.17, 0.12, L * 0.98), 0.025, block_mat, M=Mb, segs=2)
        cov_c = c + d * 0.285
        part.rbox(cov_c, (0.16, 0.05, L * 0.94), 0.022, cover_mat, M=Mb, segs=3)
        if lod == 0:
            # Rippen auf dem Ventildeckel
            for k in range(cyl_per_bank):
                zz = -L * 0.42 + L * 0.84 * (k + 0.5) / cyl_per_bank
                part.rbox(cov_c + d * 0.027 + np.array([0, 0, zz]), (0.11, 0.008, 0.012), 0.003, "Aluminum", M=Mb,
                          segs=1)
                # Zündspulen
                part.rbox(cov_c + d * 0.04 + np.array([sx * -0.035 * math.cos(half), 0.0, zz]), (0.025, 0.03, 0.025),
                          0.006, "EngineBlack", M=Mb, segs=1)
            # Krümmer an der Außenseite
            for k in range(cyl_per_bank):
                zz = -L * 0.42 + L * 0.84 * (k + 0.5) / cyl_per_bank
                a = c + d * 0.17 + np.array([sx * 0.10, -0.04, zz])
                b_ = a + np.array([sx * 0.07, -0.18, 0.0])
                part.tube([a, a + np.array([sx * 0.06, -0.03, 0]), b_], 0.019, "Titanium", segs=8)
    # Ansaugbrücke in der Mitte des V
    top = c + np.array([0, 0.24, 0])
    part.rbox(top, (0.22, plenum_h, L * 0.9), 0.035, plenum_mat, segs=3)
    if lod == 0:
        for k in range(cyl_per_bank):
            zz = -L * 0.42 + L * 0.84 * (k + 0.5) / cyl_per_bank
            for sx in (1, -1):
                a = top + np.array([sx * 0.06, -0.01, zz])
                b_ = c + np.array([sx * 0.15, 0.17, zz])
                part.tube([a, b_], 0.022, plenum_mat, segs=8)
        if label:
            part.tex_quad(top + np.array([0, plenum_h / 2 + 0.002, 0]), (-1, 0, 0), (0, 0, 1), 0.16, 0.025, "Wordmark")
    return top + np.array([0, plenum_h / 2, 0])


def turbo(part, c, axis=(1, 0, 0), r=0.07, mat_hot="Titanium", mat_cold="Aluminum", lod=0):
    """Abgasturbolader: Schnecke (heiß) + Verdichter (kalt) auf gemeinsamer Achse."""
    c = np.asarray(c, dtype=float)
    ax = norm(axis)
    M = np.column_stack(frame(ax, (0, 1, 0)))
    segs = 20 if lod == 0 else 8
    tmp = Part("turbo")
    tmp.lathe([(-0.05, 0.0), (-0.05, r * 0.7), (-0.03, r), (0.0, r * 0.95), (0.005, r * 0.5), (0.005, 0.0)], segs,
              mat_hot, center=(0, 0, 0), axis="z", inside=(-0.02, r * 0.4))
    tmp.lathe([(0.005, 0.0), (0.005, r * 0.55), (0.03, r * 0.95), (0.06, r * 0.9), (0.075, r * 0.5), (0.075, 0.0)], segs,
              mat_cold, center=(0, 0, 0), axis="z", inside=(0.04, r * 0.4))
    tmp.lathe([(0.075, r * 0.42), (0.11, r * 0.4), (0.11, r * 0.34)], segs, mat_cold, center=(0, 0, 0), axis="z",
              inside=(0.09, r * 0.2))
    part.merge(tmp.transformed(M, c))


def roof_scoop(ctx, z0, z1, w=0.24, h=0.10, mat="Carbon", part="Scoop"):
    """Dachhutze (Ansaugschnorchel) auf der Dachmitte: vorne offen, läuft nach hinten flach aus."""
    cg = CabinGeo(ctx.b)
    p = ctx.part(part)
    secs = []
    zs = np.linspace(z0, z1, 12 if ctx.lod == 0 else 5)
    for i, z in enumerate(zs):
        t = i / (len(zs) - 1)
        hh = h * (1 - t ** 1.6) + 0.004
        ww = w * (1 - 0.35 * t)
        y0 = cg.roof(z)
        prof = round_open([(ww / 2 + 0.02, y0 - 0.004), (ww / 2, y0 + hh * 0.8), (0.0, y0 + hh),
                           (-ww / 2, y0 + hh * 0.8), (-ww / 2 - 0.02, y0 - 0.004)], [0, 0.03, 0.05, 0.03, 0], 3)
        secs.append([np.array([x, y, z]) for (x, y) in prof])
    p.loft(secs, lambda k, j: mat, closed=False, smooth=True,
           hint_fn=lambda k: np.array([0.0, cg.roof(zs[k]) - 0.3, zs[k]]))
    # Öffnung vorne (dunkel) + Gitter
    s0 = secs[0]
    c0 = sum(s0) / len(s0)
    for j in range(len(s0) - 1):
        p.tri(c0, s0[j], s0[j + 1], "Mesh", outward=(0, 0, 1 if z0 > z1 else -1))
    if ctx.lod == 0:
        rim = Part("rim")
        prof = [q + np.array([0, 0, 0.004 if z0 > z1 else -0.004]) for q in s0]
        rim.sweep(prof, round_rect(0.012, 0.012, 0.005, 1), "Trim", up=(0, 0, 1), closed_profile=True, caps=False)
        p.merge(rim)


# ----------------------------------------------------------------------
# Klassische Teile: Stoßstangen, Seitenleuchten, Hutzen, Kompressor
# ----------------------------------------------------------------------

def bumper(ctx, y, z_from, h=0.09, out=0.05, thick=0.07, front=True, mat="Chrome", part="Bumpers", depth=0.5):
    """Stoßstange als Profil entlang der Grundriss-Kontur (rund um Front oder Heck)."""
    ring, zc = plan_ring(ctx, y, z_from, front=front, n_side=6, n_arc=36, depth=depth)
    if len(ring) < 4:
        return
    ref = (0.0, zc)
    path2 = offset_line(ring, out - thick / 2, ref)
    path = [np.array([x, y, z]) for (x, z) in path2]
    prof = round_rect(thick, h, min(thick, h) * 0.42, 3)
    p = ctx.part(part)
    tmp = Part("bumper")
    tmp.sweep(path, [(u, v) for (u, v) in prof], mat, up=(0, 1, 0), caps=True, smooth=True)
    p.merge(tmp)
    # Gummileiste (Prallstreifen) mittig
    if ctx.lod == 0:
        path_r = [np.array([x, y, z]) for (x, z) in offset_line(ring, out + 0.004, ref)]
        tmp2 = Part("strip")
        tmp2.sweep(path_r, round_rect(0.012, h * 0.28, 0.005, 1), "Rubber", up=(0, 1, 0), caps=True, smooth=True)
        p.merge(tmp2)


def side_lamp(ctx, z, y, w, h, mat="Indicator", lens="LampGlass", part="Lights", kind="marker"):
    """Kleine Seitenleuchte (Seitenmarkierung/Blinker) – beide Seiten."""
    spec = {"w": w, "h": h, "r": min(w, h) * 0.3, "depth": 0.02, "dome": 0.003, "lens": lens, "kind": kind,
            "elements": [("panel", rr_outline(w * 0.8, h * 0.6, min(w, h) * 0.2, 2), mat)]}
    from .parts import lamp_local as _ll
    local = _ll(spec, ctx.lod)
    outline = rr_outline(w, h, min(w, h) * 0.3, 4)
    place_side(ctx, local, z, y, (w, h), ctx.part(part), mirror=True, cut=outline if ctx.lod == 0 else None)


def hood_bulge(ctx, z0, z1, w, h, mat="Paint", part="BodyAdd", x=0.0, ramp_u=0.22, ramp_v=0.14):
    """Aufgesetzte Wölbung (Power-Dome) auf der Motorhaube."""
    L = abs(z1 - z0)
    outline = rr_outline(w, L, min(w, L) * 0.25, 6)

    def sm(t):
        t = min(max(t, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    def wfn(u, v, su, sv):
        return -0.002 + (h + 0.002) * sm(min(su, 1 - su) / ramp_u) * sm(min(sv, 1 - sv) / ramp_v)

    loc = Part("bulge")
    fill_shape(loc, outline, wfn, mat, outward=(0, 0, 1), max_du=0.03, max_dv=0.03, smooth=True)
    place_top(ctx, loc, x, (z0 + z1) / 2, (w, L), ctx.part(part), mirror=False, up_hint=(0, 0, 1))


def hood_scoop(ctx, z_back, z_front, w, h, mat="Paint", inner="Mesh", part="BodyAdd", x=0.0, open_front=True):
    """Lufthutze auf der Haube. Öffnung vorne (Ram-Air) oder hinten (Cowl Induction)."""
    L = abs(z_front - z_back)
    lod = ctx.lod
    loc = Part("scoop")
    n = 10 if lod == 0 else 4
    secs = []
    for i in range(n + 1):
        t = i / n                                   # 0 = Öffnung, 1 = auslaufendes Ende
        v = (L / 2 - t * L) if open_front else (-L / 2 + t * L)
        hh = h * (1 - t ** 2) + 0.002
        ww = w * (1 - 0.25 * t)
        prof = round_open([(ww / 2 + 0.012, -0.003), (ww / 2, hh * 0.85), (0.0, hh), (-ww / 2, hh * 0.85),
                           (-ww / 2 - 0.012, -0.003)], [0, 0.02, 0.04, 0.02, 0], 3)
        secs.append([np.array([u, v, wv]) for (u, wv) in prof])
    loc.loft(secs, lambda k, j: mat, closed=False, smooth=True, hint_fn=lambda k: np.array([0.0, 0.0, -0.5]))
    # Öffnung (dunkel, leicht nach innen versetzt)
    s0 = secs[0]
    c0 = sum(s0) / len(s0)
    off = np.array([0, -0.004 if open_front else 0.004, 0])
    for j in range(len(s0) - 1):
        loc.tri(c0 + off, s0[j] + off, s0[j + 1] + off, inner, outward=(0, 1 if open_front else -1, 0))
    place_top(ctx, loc, x, (z_front + z_back) / 2, (w, L), ctx.part(part), mirror=False, up_hint=(0, 0, 1))


def blower(part, c, length=0.36, width=0.30, height=0.20, lod=0, hat=True):
    """Kompressor (Roots-Gebläse) mit Riementrieb und Einspritz-Hut; c = Mitte Unterkante."""
    c = np.asarray(c, dtype=float)
    part.rbox(c + np.array([0, height * 0.45, 0]), (width, height * 0.9, length), 0.035, "Aluminum", segs=3)
    if lod == 0:
        for k in range(7):                          # Kühlrippen
            zz = -length * 0.42 + length * 0.84 * k / 6
            part.box(c + np.array([0, height * 0.45, zz]), (width + 0.012, height * 0.7, 0.008), "Aluminum")
        # Riemenscheiben + Riemen vorne
        for (yy, r) in ((height * 0.6, 0.07), (-0.08, 0.09)):
            part.lathe([(0.0, 0.0), (0.0, r), (0.03, r), (0.03, 0.0)], 20, "Chrome",
                       center=(c[0], c[1] + yy, c[2] + length / 2 + 0.01), axis="z", inside=(0.015, r * 0.5))
        part.box(c + np.array([0.0, height * 0.26 - 0.04, length / 2 + 0.025]), (0.10, 0.36, 0.02), "Rubber")
    # Ansaug-Platte (Butterfly) oben
    part.rbox(c + np.array([0, height + 0.02, 0]), (width * 0.7, 0.04, length * 0.7), 0.01, "EngineBlack", segs=2)
    if hat:
        part.rbox(c + np.array([0, height + 0.07, 0.02]), (width * 0.62, 0.06, length * 0.62), 0.02, "Chrome", segs=3)


def shotgun_scoops(part, c, spread=0.09, length=0.30, r=0.055, mat="Chrome", lod=0):
    """Zwei runde 'Shotgun'-Hutzen (Rohre nach vorne offen) auf dem Kompressor."""
    c = np.asarray(c, dtype=float)
    segs = 24 if lod == 0 else 10
    for sx in (-1, 1):
        cc = c + np.array([sx * spread, 0, 0])
        part.lathe([(-length / 2, r * 0.9), (length * 0.2, r), (length / 2, r * 1.06), (length / 2 + 0.004, r * 0.92),
                    (length * 0.3, r * 0.88), (-length / 2, r * 0.82)], segs, mat, center=tuple(cc), axis="z",
                   inside=(0.0, r * 0.95))
        part.lathe([(length * 0.25, 0.0), (length * 0.25, r * 0.86)], segs, "Mesh", center=tuple(cc), axis="z",
                   inside=(length * 0.25 - 0.02, 0.0))


# ----------------------------------------------------------------------
# Zukunftsteile: Kameraspiegel, Haifischflosse, Canards, E-Antrieb
# ----------------------------------------------------------------------

def camera_mirror(ctx, z, y, reach=0.11, part="Mirrors", body_mat="BlackGloss"):
    """Kamera statt Außenspiegel: schlanker Arm mit stromlinienförmiger Kamerakapsel."""
    hit = ctx.hit_side(z, y, 1)
    if hit is None:
        return
    base = hit[0]
    p = Part("cam")
    c = base + np.array([reach, 0.05, -0.03])
    p.sphere(c, 0.032, body_mat, segs=16, rings=10, scale=(0.9, 0.75, 2.0))
    p.lathe([(0.0, 0.0), (0.0, 0.011), (-0.004, 0.009), (-0.005, 0.0)], 14, "DisplayGlass",
            center=(c[0], c[1], c[2] - 0.062), axis="z", inside=(-0.002, 0.004))
    p.lathe([(-0.0045, 0.0), (-0.0045, 0.004)], 10, "Accent", center=(c[0], c[1], c[2] - 0.0625), axis="z",
            inside=(-0.003, 0.0))
    st = []
    for t in np.linspace(0, 1, 5):
        pt = base * (1 - t) + (c + np.array([-0.02, -0.01, 0.01])) * t
        ww = 0.05 * (1.2 - 0.6 * t)
        st.append([pt + np.array([0, v, u]) for (u, v) in round_rect(ww, 0.012, 0.005, 2)])
    p.loft(st, lambda k, j: body_mat, caps=(None, body_mat), smooth=True)
    dst = ctx.part(part)
    dst.merge(p)
    dst.merge(p.mirrored_x())


def center_fin(ctx, z0, z1, h_max, thick=0.014, mat="Paint", edge="Accent", part="BodyAdd"):
    """Haifischflosse auf der Mittellinie (von der Heckscheibe bis zum Heck)."""
    cg = CabinGeo(ctx.b)
    b = ctx.b
    zs_cab = cg.zs
    p = ctx.part(part)
    secs = []
    n = 16 if ctx.lod == 0 else 5
    zs = np.linspace(z0, z1, n)
    tops = []
    for i, z in enumerate(zs):
        t = i / (n - 1)
        if zs_cab[0] <= z <= zs_cab[-1]:
            y0 = cg.roof(z)
        else:
            y0 = b.top_y(z, 0.0)
        h = h_max * min(1.0, t / 0.75) ** 0.7 * (1.0 if t < 0.85 else max(0.15, 1 - (t - 0.85) / 0.15 * 0.85))
        prof = [(thick / 2, y0 - 0.01), (thick / 2, y0 + h * 0.9), (thick * 0.25, y0 + h), (-thick * 0.25, y0 + h),
                (-thick / 2, y0 + h * 0.9), (-thick / 2, y0 - 0.01)]
        secs.append([np.array([x, y, z]) for (x, y) in prof])
        tops.append(np.array([0.0, y0 + h + 0.002, z]))
    p.loft(secs, lambda k, j: mat, closed=True, smooth=True, caps=(mat, mat))
    if edge and ctx.lod == 0:
        p.tube(tops[2:-1], 0.0035, edge, segs=6)


def canards(ctx, x, y, z_hint=None, size=0.14, mat="Carbon", part="Aero"):
    """Kleine Leitflügel an den vorderen Stoßfänger-Ecken (beide Seiten)."""
    hit = ctx.rc.cast((x + 1.5, y, ctx.b.zf - 0.35), (-1, 0, -0.25), 3.0)
    if hit is None:
        hit = ctx.hit_front(x, y)
    if hit is None:
        return
    P = hit[0]
    p = Part("canard")
    for k, (dy, s_) in enumerate(((0.0, 1.0), (0.065, 0.8))):
        o = np.array([P[0], P[1] + dy, P[2]])
        pts = [o + np.array([-0.01, 0, 0.01]), o + np.array([size * 0.55 * s_, 0.035 * s_, -0.04]),
               o + np.array([size * 0.6 * s_, 0.045 * s_, -0.11 * s_]), o + np.array([-0.01, 0.0, -0.13 * s_])]
        top = [q + np.array([0, 0.006, 0]) for q in pts]
        p.hexa(pts + top, mat)
    dst = ctx.part(part)
    dst.merge(p)
    dst.merge(p.mirrored_x())


def e_drive(part, c, lod=0, glow="Accent", width=1.1):
    """Elektro-Antrieb an der Hinterachse: zwei Motoren, Inverter, HV-Leitungen, Kühlleitungen."""
    c = np.asarray(c, dtype=float)
    segs = 24 if lod == 0 else 10
    for sx in (1, -1):
        mc = c + np.array([sx * 0.22, 0.0, 0.0])
        part.lathe([(-0.16, 0.0), (-0.16, 0.12), (-0.14, 0.135), (0.14, 0.135), (0.16, 0.12), (0.16, 0.0)], segs,
                   "EngineMetal", center=tuple(mc), axis="x", inside=(0.0, 0.06))
        if lod == 0:
            for k in range(7):                       # Kühlrippen
                xx = -0.12 + 0.24 * k / 6
                part.lathe([(xx - 0.006, 0.135), (xx - 0.006, 0.15), (xx + 0.006, 0.15), (xx + 0.006, 0.135)], segs,
                           "EngineBlack", center=tuple(mc), axis="x", inside=(xx, 0.14))
            part.lathe([(sx * 0.165, 0.0), (sx * 0.165, 0.09), (sx * 0.175, 0.07), (sx * 0.175, 0.0)], segs, "Copper",
                       center=tuple(mc), axis="x", inside=(sx * 0.17, 0.03))
        # Antriebswelle zum Rad
        part.tube([mc + np.array([sx * 0.16, 0, 0]), mc + np.array([sx * (width / 2 - 0.22), 0, 0])], 0.03, "EngineBlack",
                  segs=10)
    inv = c + np.array([0.0, 0.2, 0.05])
    part.rbox(inv, (0.42, 0.10, 0.34), 0.03, "EngineBlack", segs=2)
    part.rbox(inv + np.array([0, 0.052, 0]), (0.30, 0.008, 0.22), 0.01, "Carbon", segs=1)
    if lod == 0:
        part.tex_quad(inv + np.array([0, 0.057, 0.0]), (-1, 0, 0), (0, 0, 1), 0.16, 0.025, "Wordmark")
        for sx in (1, -1):                           # Hochvolt-Leitungen (orange)
            a = inv + np.array([sx * 0.12, 0.0, 0.17])
            part.tube([a, a + np.array([0, -0.05, 0.12]), c + np.array([sx * 0.22, 0.10, 0.25])], 0.016, "HVOrange",
                      segs=8)
        # Kühlleitungen mit Leuchtstreifen
        for sx in (1, -1):
            pts = [c + np.array([sx * 0.38, 0.05, -0.2]), c + np.array([sx * 0.42, 0.18, 0.1]),
                   c + np.array([sx * 0.30, 0.24, 0.35])]
            part.tube(pts, 0.012, glow, segs=8)


# ----------------------------------------------------------------------
# Geländewagen-Teile
# ----------------------------------------------------------------------

def spare_wheel(ctx, center, R=0.40, W=0.26, rim_design=None, part="Spare"):
    """Reserverad an der Hecktür (Achse entlang z), mit Halter."""
    from . import wheels as WH
    lod = min(ctx.lod, 1)
    rd = rim_design or {"style": "beadlock", "n": 6}
    Rr = R * 0.62
    t = WH.tire(R, W, Rr, 1, lod, "at")
    r = WH.rim(R, W, Rr, 1, rd, lod)
    M = rot_matrix(0, -math.pi / 2, 0)            # Radachse x -> -z (Außenseite zeigt nach hinten)
    p = ctx.part(part)
    c = np.asarray(center, dtype=float)
    p.merge(t.transformed(M, c))
    p.merge(r.transformed(M, c))
    p.rbox(c + np.array([0, 0, W / 2 + 0.03]), (0.30, 0.10, 0.06), 0.015, "Trim", segs=1)


def roof_rails(ctx, z0, z1, x, h=0.06, cross=(), mat="Trim", part="Roof"):
    cg = CabinGeo(ctx.b)
    p = ctx.part(part)
    for sx in (1, -1):
        path = [np.array([sx * x, cg.glass_y(z, x) + h, z]) for z in np.linspace(z0, z1, 10)]
        p.tube(path, 0.016, mat, segs=10, caps=True)
        for z in (z0, (z0 + z1) / 2, z1):            # Füße
            y = cg.glass_y(z, x)
            p.rbox((sx * x, y + h / 2, z), (0.04, h, 0.07), 0.012, mat, segs=1)
    for z in cross:
        y = max(cg.glass_y(z, x), cg.roof(z)) + h + 0.012
        p.tube([np.array([x, y, z]), np.array([-x, y, z])], 0.014, "Aluminum", segs=10)


def snorkel(part, fender_pt, top_pt, r=0.045, mat="Trim"):
    """Ansaugschnorchel vom Kotflügel an der A-Säule hinauf, Kopf zeigt nach vorne."""
    a = np.asarray(fender_pt, dtype=float)
    b = np.asarray(top_pt, dtype=float)
    mid = a + (b - a) * 0.5 + np.array([np.sign(a[0]) * 0.03, 0, 0.04])
    part.tube([a, a + np.array([0, 0.06, -0.04]), mid, b], r, mat, segs=14)
    part.rbox(a + np.array([0, 0.012, 0.0]), (0.12, 0.024, 0.14), 0.01, mat, segs=1)
    head = b + np.array([0, 0.03, 0.05])
    part.rbox(head, (r * 2.6, r * 2.4, 0.16), r * 0.8, mat, segs=3)
    part.rbox(head + np.array([0, 0, 0.08]), (r * 2.2, r * 1.9, 0.01), 0.01, "Mesh", segs=1)


def bull_bar(ctx, y, out=0.12, w=0.70, mat="Trim", part="BullBar"):
    """Frontbügel mit Seilwinde."""
    p = ctx.part(part)
    hit = ctx.hit_front(0.0, y)
    if hit is None:
        return
    z = hit[0][2] + out
    for sx in (1, -1):
        p.tube([np.array([sx * w * 0.45, y - 0.18, z - 0.06]), np.array([sx * w * 0.45, y + 0.20, z]),
                np.array([sx * w * 0.25, y + 0.32, z + 0.01])], 0.025, mat, segs=12)
    p.tube([np.array([-w * 0.25, y + 0.32, z + 0.01]), np.array([w * 0.25, y + 0.32, z + 0.01])], 0.025, mat, segs=12)
    p.tube([np.array([-w * 0.5, y + 0.02, z]), np.array([w * 0.5, y + 0.02, z])], 0.022, mat, segs=12)
    # Seilwinde
    p.lathe([(-0.16, 0.0), (-0.16, 0.06), (0.16, 0.06), (0.16, 0.0)], 18, "EngineBlack",
            center=(0.0, y - 0.10, z - 0.05), axis="x", inside=(0.0, 0.03))
    p.lathe([(-0.12, 0.062), (0.12, 0.062)], 18, "Wiper", center=(0.0, y - 0.10, z - 0.05), axis="x",
            inside=(0.0, 0.04))
    p.rbox((0.0, y - 0.10, z + 0.02), (0.10, 0.05, 0.04), 0.01, "EngineRed", segs=1)


def light_bar(ctx, z, w=1.2, h=0.07, part="Roof", y_off=0.06):
    """LED-Lichtleiste auf der Dachvorderkante."""
    cg = CabinGeo(ctx.b)
    y = cg.roof(z) + y_off
    p = ctx.part(part)
    p.rbox((0.0, y, z), (w, h, 0.08), 0.02, "Trim", segs=2)
    p.rbox((0.0, y, z + 0.041), (w - 0.04, h - 0.025, 0.004), 0.01, "LampGlass", segs=1)
    n = 10
    for k in range(n):
        x = -w / 2 + 0.06 + (w - 0.12) * k / (n - 1)
        p.lathe([(0.0, 0.0), (0.0, 0.016)], 10, "Headlight", center=(x, y, z + 0.035), axis="z", inside=(-0.01, 0.0))
    for sx in (1, -1):
        p.box((sx * w * 0.42, y - h / 2 - 0.03, z - 0.01), (0.03, 0.06, 0.03), "Trim")


# ----------------------------------------------------------------------
# Linien auf Front-/Heckflächen, aufgesetzte Lüftungsschlitze
# ----------------------------------------------------------------------

def face_line(ctx, pts, rear=True, width=0.0045, mat="Gap", part="Trim", lift=0.0015, step=0.02):
    """Fuge/Zierlinie auf der Front- oder Heckfläche. pts = [(x, y), ...] als Polylinie;
    jeder Punkt wird von vorne bzw. hinten auf die Haut projiziert."""
    dense = []
    for a, b_ in zip(pts[:-1], pts[1:]):
        L = math.hypot(b_[0] - a[0], b_[1] - a[1])
        k = max(1, int(math.ceil(L / step)))
        for i in range(k):
            t = i / k
            dense.append((a[0] + (b_[0] - a[0]) * t, a[1] + (b_[1] - a[1]) * t))
    dense.append(tuple(pts[-1]))
    P, N = [], []
    for (x, y) in dense:
        h = ctx.hit_rear(x, y) if rear else ctx.hit_front(x, y)
        if h is None:
            continue
        P.append(h[0] + h[1] * lift)
        N.append(h[1])
    p = ctx.part(part)
    for i in range(len(P) - 1):
        d = P[i + 1] - P[i]
        if np.linalg.norm(d) < 1e-6:
            continue
        t = norm(d)
        s0 = norm(np.cross(N[i], t)) * width / 2
        s1 = norm(np.cross(N[i + 1], t)) * width / 2
        p.quad(P[i] - s0, P[i] + s0, P[i + 1] + s1, P[i + 1] - s1, mat, normals=[N[i], N[i], N[i + 1], N[i + 1]],
               outward=N[i] + N[i + 1])


def raised_vent_local(w, l, n, lod=0, frame_mat="BlackGloss", slat_mat="BlackGloss", angle=10.0):
    """Aufgesetzter Lüftungsschlitz (liegt auf dem Blech, braucht kein Loch in der Haut)."""
    p = Part("vent")
    o = rr_outline(w, l, min(w, l) * 0.18, 4)
    od = densify(o, 0.012)
    secs = [[np.array([u * s_, v * s_, wv]) for (u, v) in od] for (wv, s_) in ((-0.003, 1.0), (0.007, 0.985),
                                                                              (0.009, 0.94))]
    p.loft(secs, lambda k, j: frame_mat, caps=(None, None), smooth=True)
    inner = [(u * 0.94, v * 0.94) for (u, v) in o]
    flat_shape(p, inner, 0.004, "Mesh")
    if lod == 0:
        for i in range(n):
            v = -l * 0.47 + l * 0.94 * (i + 0.5) / n
            seg_box(p, (0, v, 0.0065), (w * 0.9, l * 0.94 / n * 0.92, 0.004), slat_mat, rot=(math.radians(angle), 0, 0))
    return p


def side_strip(ctx, y_fn, z0, z1, width=0.02, mat="Chrome", part="Trim", offset=0.002, n=None):
    """Leiste/Zierlinie auf beiden Flanken, folgt der Oberfläche. y_fn: Höhe (Zahl oder Funktion von z)."""
    b = ctx.b
    p = ctx.part(part)
    n = n or max(8, int(abs(z1 - z0) / 0.04))
    zs = np.linspace(z0, z1, n)
    for side in (1, -1):
        samples = []
        for z in zs:
            y = y_fn(z) if callable(y_fn) else y_fn
            samples.append((z, b.j_at_height(z, y, side)))
        b.strip(p, samples, width, mat, offset=offset)


def hood_ornament(part, base, lod=0, mat="Chrome"):
    """Stehende Kühlerfigur: gebogene, nach hinten geschwungene Klinge auf einem runden Sockel."""
    c = np.asarray(base, dtype=float)
    segs = 20 if lod == 0 else 8
    part.lathe([(0.0, 0.026), (0.004, 0.026), (0.012, 0.02), (0.016, 0.012), (0.016, 0.0)], segs, mat,
               center=tuple(c), axis="y", inside=(0.006, 0.01))
    n_s = 14 if lod == 0 else 6
    secs = []
    for i in range(n_s + 1):
        t = i / n_s
        P = c + np.array([0.0, 0.014 + 0.095 * t, -0.075 * t ** 1.7])
        T = np.array([0.0, 0.095, -0.075 * 1.7 * max(t, 1e-3) ** 0.7])
        T = T / np.linalg.norm(T)
        N = np.array([0.0, -T[2], T[1]])                 # in der y-z-Ebene senkrecht zur Bahn
        if N[2] > 0:
            N = -N                                        # Vorderkante zeigt nach vorne (+z) -> N nach hinten
        a = 0.0045 * (1 - t) + 0.0012
        bb = 0.024 * (1 - t) ** 0.8 + 0.002
        sec = []
        for k in range(12):
            th = 2 * math.pi * k / 12
            sec.append(P + np.array([a * math.cos(th), 0.0, 0.0]) + N * (bb * math.sin(th) - bb * 0.35))
        secs.append(sec)
    part.loft(secs, lambda k, j: mat, caps=(mat, mat), smooth=True)
