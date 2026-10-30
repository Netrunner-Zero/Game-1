"""Geometrie-Bausteine für Karten (Boden, Linien, Leitwände, Rampen, Masten, Gebäude).

Konvention wie im Spiel: +Y oben; Drehung yaw wie bei den Autos – die lokale +Z-Achse zeigt in
Welt-Richtung (sin yaw, cos yaw), die lokale +X-Achse in (cos yaw, −sin yaw).
UVs in Metern (die Materialien kacheln über KHR_texture_transform).
"""
import math

import numpy as np

UP = np.array([0.0, 1.0, 0.0])


def P(x, y, z):
    return np.array([x, y, z], dtype=float)


class Frame:
    """Lokales Koordinatensystem in der Ebene (Mitte cx, cz, Drehung yaw)."""

    def __init__(self, cx=0.0, cz=0.0, yaw=0.0):
        self.cx, self.cz, self.yaw = cx, cz, yaw
        self.c, self.s = math.cos(yaw), math.sin(yaw)

    def w(self, lx, y, lz):
        return P(self.cx + lx * self.c + lz * self.s, y, self.cz - lx * self.s + lz * self.c)


def quad_up(part, x0, z0, x1, z1, y, mat, uv=None):
    """Waagerechtes Rechteck (achsparallel), Normale nach oben, UV = Weltmeter."""
    a, b, c, d = P(x0, y, z0), P(x1, y, z0), P(x1, y, z1), P(x0, y, z1)
    if uv is None:
        uv = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    part.quad(a, b, c, d, mat, uvs=uv, outward=UP, normals=[UP] * 4)


def rect_up(part, f, hx, hz, y, mat, uv=None):
    """Waagerechtes, gedrehtes Rechteck im Frame f."""
    a, b, c, d = f.w(-hx, y, -hz), f.w(hx, y, -hz), f.w(hx, y, hz), f.w(-hx, y, hz)
    if uv is None:
        uv = [(a[0], a[2]), (b[0], b[2]), (c[0], c[2]), (d[0], d[2])]
    part.quad(a, b, c, d, mat, uvs=uv, outward=UP, normals=[UP] * 4)


def strip(part, pts, width, y, mat, closed=False, u0=0.0, v_scale=1.0):
    """Band entlang einer Linie (Markierungen, Randsteine). UV: u = Meter entlang, v = Meter quer."""
    pts = [np.array([p[0], p[1]], dtype=float) for p in pts]
    n = len(pts)
    if closed:
        pts = pts + [pts[0]]
        n += 1
    left = []
    for i in range(n):
        if i == 0 and not closed:
            d = pts[1] - pts[0]
        elif i == n - 1 and not closed:
            d = pts[-1] - pts[-2]
        else:
            d0 = pts[i] - pts[i - 1] if i > 0 else pts[-1] - pts[-2]
            d1 = pts[(i + 1) % n] - pts[i] if i < n - 1 else pts[1] - pts[0]
            d = d0 / max(1e-9, np.linalg.norm(d0)) + d1 / max(1e-9, np.linalg.norm(d1))
        d = d / max(1e-9, np.linalg.norm(d))
        left.append(np.array([d[1], -d[0]]))
    u = u0
    hw = width / 2
    for i in range(n - 1):
        a, b = pts[i], pts[i + 1]
        la, lb = left[i], left[i + 1]
        seg = float(np.linalg.norm(b - a))
        q0, q1, q2, q3 = a - la * hw, b - lb * hw, b + lb * hw, a + la * hw
        p0, p1, p2, p3 = P(q0[0], y, q0[1]), P(q1[0], y, q1[1]), P(q2[0], y, q2[1]), P(q3[0], y, q3[1])
        part.quad(p0, p1, p2, p3, mat, uvs=[(u, 0), (u + seg, 0), (u + seg, width * v_scale), (u, width * v_scale)],
                  outward=UP, normals=[UP] * 4)
        u += seg
    return u


def arc_points(cx, cz, r, a0, a1, step=1.0):
    n = max(2, int(abs(a1 - a0) * r / step) + 1)
    return [(cx + r * math.sin(a0 + (a1 - a0) * i / (n - 1)), cz + r * math.cos(a0 + (a1 - a0) * i / (n - 1))) for i in range(n)]


def ring(part, cx, cz, r, width, y, mat, step=1.0):
    pts = arc_points(cx, cz, r, 0, 2 * math.pi, step)[:-1]
    strip(part, pts, width, y, mat, closed=True)


def dashed(part, x0, z0, x1, z1, width, y, mat, dash=6.0, gap=6.0):
    L = math.hypot(x1 - x0, z1 - z0)
    dx, dz = (x1 - x0) / L, (z1 - z0) / L
    s = 0.0
    while s < L:
        e = min(L, s + dash)
        strip(part, [(x0 + dx * s, z0 + dz * s), (x0 + dx * e, z0 + dz * e)], width, y, mat)
        s = e + gap


def extrude(part, profile, a, b, mat, y0=0.0, caps=True):
    """Profil (quer, hoch) entlang der Strecke a→b (Punkte x, z) ziehen – z. B. Betonleitwand."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    d = b - a
    L = float(np.linalg.norm(d))
    t = d / L
    lat = np.array([t[1], -t[0]])                       # links von der Fahrtrichtung
    def pt(base, q):
        return P(base[0] + lat[0] * q[0], y0 + q[1], base[1] + lat[1] * q[0])
    cen = (a + b) / 2
    hint = P(cen[0], y0 + 0.3 * max(q[1] for q in profile), cen[1])
    for i in range(len(profile) - 1):
        q0, q1 = profile[i], profile[i + 1]
        part.quad(pt(a, q0), pt(b, q0), pt(b, q1), pt(a, q1), mat, hint=hint)
    if caps:
        for base, sgn in ((a, -1), (b, 1)):
            ring_pts = [pt(base, q) for q in profile]
            c = sum(ring_pts) / len(ring_pts)
            out = P(t[0] * sgn, 0, t[1] * sgn)
            for i in range(len(ring_pts) - 1):
                part.tri(c, ring_pts[i], ring_pts[i + 1], mat, outward=out)


def cylinder(part, cx, cz, y0, y1, r, mat, segs=12, top=True, r_top=None):
    r_top = r if r_top is None else r_top
    ring0 = [P(cx + r * math.cos(2 * math.pi * i / segs), y0, cz + r * math.sin(2 * math.pi * i / segs)) for i in range(segs)]
    ring1 = [P(cx + r_top * math.cos(2 * math.pi * i / segs), y1, cz + r_top * math.sin(2 * math.pi * i / segs)) for i in range(segs)]
    circ = 2 * math.pi * r
    for i in range(segs):
        j = (i + 1) % segs
        ang = 2 * math.pi * (i + 0.5) / segs
        out = P(math.cos(ang), (r - r_top) / max(1e-6, y1 - y0), math.sin(ang))
        na = P(math.cos(2 * math.pi * i / segs), 0, math.sin(2 * math.pi * i / segs))
        nb = P(math.cos(2 * math.pi * j / segs), 0, math.sin(2 * math.pi * j / segs))
        u0, u1 = circ * i / segs, circ * (i + 1) / segs
        part.quad(ring0[i], ring0[j], ring1[j], ring1[i], mat, outward=out, normals=[na, nb, nb, na],
                  uvs=[(u0, y0), (u1, y0), (u1, y1), (u0, y1)])
    if top and r_top > 1e-4:
        c = P(cx, y1, cz)
        for i in range(segs):
            part.tri(c, ring1[i], ring1[(i + 1) % segs], mat, outward=UP)


def box(part, f, lx, ly, lz, sx, sy, sz, mat):
    """Quader im Frame f: Mitte (lx, ly, lz) lokal, Größe sx (quer), sy (hoch), sz (längs)."""
    hx, hz = sx / 2, sz / 2
    pts = [f.w(lx - hx, ly - sy / 2, lz - hz), f.w(lx + hx, ly - sy / 2, lz - hz), f.w(lx + hx, ly - sy / 2, lz + hz),
           f.w(lx - hx, ly - sy / 2, lz + hz)]
    pts += [p + P(0, sy, 0) for p in pts]
    part.hexa(pts, mat)


def ramp(part, f, hw, prof, top_mat, side_mat):
    """Rampe/Tisch: prof = [(lz, h), …] entlang der lokalen z-Achse, Breite 2·hw."""
    for (z0, h0), (z1, h1) in zip(prof[:-1], prof[1:]):
        a, b, c, d = f.w(-hw, h0, z0), f.w(hw, h0, z0), f.w(hw, h1, z1), f.w(-hw, h1, z1)
        n = np.cross(c - b, a - b)
        if n[1] < 0:
            n = -n
        n = n / np.linalg.norm(n)
        part.quad(a, b, c, d, top_mat, outward=n, normals=[n] * 4,
                  uvs=[(a[0], a[2]), (b[0], b[2]), (c[0], c[2]), (d[0], d[2])])
        for sx in (-hw, hw):
            out = f.w(sx * 2, 0, 0) - f.w(0, 0, 0)
            pts = [f.w(sx, 0, z0), f.w(sx, 0, z1), f.w(sx, h1, z1), f.w(sx, h0, z0)]
            if h0 < 1e-6 and h1 < 1e-6:
                continue
            if h0 < 1e-6:
                part.tri(pts[0], pts[1], pts[2], side_mat, outward=out)
            elif h1 < 1e-6:
                part.tri(pts[0], pts[1], pts[3], side_mat, outward=out)
            else:
                part.quad(*pts, side_mat, outward=out)
    # senkrechte Stirnflächen, wo die Rampe nicht bei 0 beginnt/endet
    for (lz, h), sgn in ((prof[0], -1), (prof[-1], 1)):
        if h > 1e-6:
            out = f.w(0, 0, sgn) - f.w(0, 0, 0)
            part.quad(f.w(-hw, 0, lz), f.w(hw, 0, lz), f.w(hw, h, lz), f.w(-hw, h, lz), side_mat, outward=out)


def ramp_height(prof, lz):
    if lz < prof[0][0] or lz > prof[-1][0]:
        return 0.0
    for (z0, h0), (z1, h1) in zip(prof[:-1], prof[1:]):
        if z0 <= lz <= z1:
            return h0 + (h1 - h0) * (lz - z0) / max(1e-9, z1 - z0)
    return 0.0


def wave_surface(part, f, hw, hl, amp, length, top_mat, side_mat, step=0.25):
    """Wellenstrecke: h = amp · ½(1 − cos(2π (lz + hl) / length)) für |lz| ≤ hl."""
    n = int(2 * hl / step)
    zs = [-hl + 2 * hl * i / n for i in range(n + 1)]
    hs = [amp * 0.5 * (1 - math.cos(2 * math.pi * (z + hl) / length)) for z in zs]
    for i in range(n):
        z0, z1, h0, h1 = zs[i], zs[i + 1], hs[i], hs[i + 1]
        a, b, c, d = f.w(-hw, h0, z0), f.w(hw, h0, z0), f.w(hw, h1, z1), f.w(-hw, h1, z1)
        slope0 = amp * 0.5 * 2 * math.pi / length * math.sin(2 * math.pi * (z0 + hl) / length)
        slope1 = amp * 0.5 * 2 * math.pi / length * math.sin(2 * math.pi * (z1 + hl) / length)
        def nrm(sl):
            v = f.w(0, 1, -sl) - f.w(0, 0, 0)
            return v / np.linalg.norm(v)
        n0, n1 = nrm(slope0), nrm(slope1)
        part.quad(a, b, c, d, top_mat, outward=UP, normals=[n0, n0, n1, n1],
                  uvs=[(a[0], a[2]), (b[0], b[2]), (c[0], c[2]), (d[0], d[2])])
        for sx in (-hw, hw):
            if h0 < 0.004 and h1 < 0.004:
                continue
            out = f.w(sx * 2, 0, 0) - f.w(0, 0, 0)
            part.quad(f.w(sx, 0, z0), f.w(sx, 0, z1), f.w(sx, h1, z1), f.w(sx, h0, z0), side_mat, outward=out)
    return hs


def building(part, cx, cz, w, d, h, yaw, mat, roof_mat, u_off=0.0, v_off=0.0):
    """Hochhaus-Quader mit Fassaden-UVs (u entlang der Wand, v = Höhe), Dach separat."""
    f = Frame(cx, cz, yaw)
    hw, hd = w / 2, d / 2
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    u = u_off
    for i in range(4):
        x0, z0 = corners[i]
        x1, z1 = corners[(i + 1) % 4]
        L = math.hypot(x1 - x0, z1 - z0)
        a, b = f.w(x0, 0, z0), f.w(x1, 0, z1)
        out = (a + b) / 2 - f.w(0, 0, 0)
        out[1] = 0
        part.quad(a, b, b + P(0, h, 0), a + P(0, h, 0), mat, outward=out,
                  uvs=[(u, v_off), (u + L, v_off), (u + L, v_off + h), (u, v_off + h)])
        u += L
    top = [f.w(x, h, z) for (x, z) in corners]
    part.quad(top[0], top[1], top[2], top[3], roof_mat, outward=UP)
