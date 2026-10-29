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
