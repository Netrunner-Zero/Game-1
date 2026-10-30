"""Prozedurale Texturen für die Welt (kachelbar, numpy + Pillow).

Alle Texturen werden nach world/textures/ geschrieben und von allen Karten geteilt.
Kachelgrößen (Meter) stehen bei den Materialien (materials.py).
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from carcad.textures import tile_noise, height_to_normal, rng, encode


def _wrap_dots(draw_fn, size, pts, rad):
    """Punkte kachelbar zeichnen (am Rand auf der Gegenseite wiederholen)."""
    for (x, y), r in zip(pts, rad):
        for ox in (-size, 0, size):
            if not (-r <= x + ox <= size + r):
                continue
            for oy in (-size, 0, size):
                if not (-r <= y + oy <= size + r):
                    continue
                draw_fn(x + ox, y + oy, r)


def asphalt(size=1024, seed=31, tone=0.30, stones=46000):
    """Asphalt: Bitumen mit Gesteinskörnung. Liefert (Farbe, Normal, ORM)."""
    r = rng(seed)
    big = tile_noise(size, 4, seed, octaves=5, persistence=0.6)          # Flecken innerhalb der Kachel
    fine = tile_noise(size, 128, seed + 1, octaves=2, persistence=0.6)
    height = np.zeros((size, size), np.float32)
    col = np.zeros((size, size), np.float32)
    hi = Image.new("L", (size, size), 0)
    ci = Image.new("L", (size, size), 0)
    dh, dc = ImageDraw.Draw(hi), ImageDraw.Draw(ci)
    pts = r.random((stones, 2)) * size
    rad = r.choice([0.8, 1.0, 1.3, 1.7, 2.2, 2.8], stones, p=[0.28, 0.26, 0.2, 0.14, 0.08, 0.04])
    shade = r.random(stones)

    idx = {"i": 0}

    def dot(x, y, rr):
        i = idx["i"]
        s = shade[i]
        v = int(70 + 185 * s) if s > 0.35 else int(10 + 60 * s)
        dh.ellipse([x - rr, y - rr, x + rr, y + rr], fill=int(150 + 105 * min(1, rr / 2.8)))
        dc.ellipse([x - rr, y - rr, x + rr, y + rr], fill=v)

    for k in range(stones):
        idx["i"] = k
        _wrap_dots(dot, size, [pts[k]], [rad[k]])
    hs = np.asarray(hi.filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255.0
    cs = np.asarray(ci, np.float32) / 255.0
    mask = (np.asarray(hi, np.float32) > 0).astype(np.float32)
    height = hs * 0.9 + fine * 0.25
    # Farbe: Bitumen dunkel, Steine heller/dunkler, großflächige Aufhellung
    binder = tone * (0.78 + 0.35 * (big - 0.5)) + (fine - 0.5) * 0.04
    stone = 0.17 + 0.34 * cs
    c = binder * (1 - mask * 0.8) + stone * mask * 0.8
    c = np.clip(c, 0.03, 0.85)
    rgb = np.stack([c * 0.985, c * 0.99, c * 1.02], -1)
    color = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    normal = height_to_normal(height, strength=2.2)
    rough = 0.93 - 0.16 * mask * (0.5 + 0.5 * cs) + (big - 0.5) * 0.06
    ao = 1.0 - 0.22 * (1 - hs) * (1 - mask)
    orm = np.stack([ao, np.clip(rough, 0.6, 1.0), np.zeros_like(ao)], -1)
    orm = Image.fromarray((orm * 255).astype(np.uint8))
    return color, normal, orm


def concrete(size=512, seed=41, tone=0.58):
    r = rng(seed)
    n1 = tile_noise(size, 8, seed, octaves=5, persistence=0.55)
    n2 = tile_noise(size, 64, seed + 3, octaves=3, persistence=0.5)
    pores = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(pores)
    pts = r.random((2600, 2)) * size
    rad = r.random(2600) * 1.3 + 0.4
    _wrap_dots(lambda x, y, rr: d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=255), size, pts, rad)
    p = np.asarray(pores, np.float32) / 255.0
    c = tone * (0.86 + 0.24 * (n1 - 0.5) + 0.1 * (n2 - 0.5)) - p * 0.18
    rgb = np.stack([c * 1.0, c * 0.99, c * 0.965], -1)
    color = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    normal = height_to_normal(n2 * 0.6 - p * 0.8, strength=1.6)
    return color, normal


def dirt(size=512, seed=51):
    r = rng(seed)
    n1 = tile_noise(size, 6, seed, octaves=5, persistence=0.6)
    n2 = tile_noise(size, 96, seed + 1, octaves=2, persistence=0.6)
    pebbles = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(pebbles)
    pts = r.random((5000, 2)) * size
    rad = r.random(5000) * 1.6 + 0.5
    _wrap_dots(lambda x, y, rr: d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=int(80 + 175 * r.random())), size, pts, rad)
    p = np.asarray(pebbles, np.float32) / 255.0
    base = 0.24 + 0.12 * (n1 - 0.5) + 0.05 * (n2 - 0.5)
    c = base * (1 - p * 0.5) + p * 0.5 * 0.42
    rgb = np.stack([c * 1.05, c * 0.98, c * 0.86], -1)
    color = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    normal = height_to_normal(n2 * 0.4 + p * 0.9, strength=2.0)
    return color, normal


def curb(w=256, h=64):
    """Randstein rot/weiß: u läuft entlang des Randsteins (2 Streifen je Kachel)."""
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for i in range(2):
        d.rectangle([i * w // 2, 0, (i + 1) * w // 2, h], fill=(176, 26, 34) if i == 0 else (232, 232, 228))
    arr = np.asarray(img, np.float32) / 255.0
    n = tile_noise(w, 16, 7, octaves=3)[:h, :w] if h <= w else tile_noise(h, 16, 7)[:h, :w]
    arr *= (0.9 + 0.12 * n)[..., None]
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))


def facade(size=512, seed=61, cols=4, rows=4):
    """Hochhaus-Fassade (Fensterraster) + Leuchtfenster für die Nacht. Liefert (Farbe, Emission)."""
    r = rng(seed)
    cw, ch = size // cols, size // rows
    col = Image.new("RGB", (size, size), (52, 56, 64))
    emi = Image.new("RGB", (size, size), (0, 0, 0))
    dc, de = ImageDraw.Draw(col), ImageDraw.Draw(emi)
    warm = [(255, 196, 120), (255, 214, 150), (255, 170, 90)]
    cool = [(150, 210, 255), (190, 230, 255), (120, 170, 255)]
    neon = [(255, 60, 200), (0, 230, 255), (150, 90, 255)]
    for j in range(rows):
        for i in range(cols):
            x0, y0 = i * cw, j * ch
            # Fensterglas (dunkel, leicht bläulich), Rahmen = Fassadenfarbe
            g = int(18 + 14 * r.random())
            dc.rectangle([x0 + 8, y0 + 10, x0 + cw - 8, y0 + ch - 14], fill=(g, g + 6, g + 16))
            dc.line([x0 + cw // 2, y0 + 10, x0 + cw // 2, y0 + ch - 14], fill=(40, 44, 52), width=3)
            u = r.random()
            if u < 0.42:
                c = (warm if r.random() < 0.6 else cool)[r.integers(0, 3)]
                k = 0.45 + 0.55 * r.random()
                c = tuple(int(v * k) for v in c)
                de.rectangle([x0 + 9, y0 + 11, x0 + cw - 9, y0 + ch - 15], fill=c)
                # Vorhang/Jalousie: obere Hälfte dunkler
                if r.random() < 0.3:
                    de.rectangle([x0 + 9, y0 + 11, x0 + cw - 9, y0 + ch // 2], fill=tuple(v // 3 for v in c))
            elif u < 0.47:
                de.rectangle([x0 + 9, y0 + 11, x0 + cw - 9, y0 + ch - 15], fill=neon[r.integers(0, 3)])
    return col, emi


def checker(n=8, px=32):
    img = Image.new("RGB", (n * px, 2 * px))
    d = ImageDraw.Draw(img)
    for i in range(n):
        for j in range(2):
            d.rectangle([i * px, j * px, (i + 1) * px - 1, (j + 1) * px - 1],
                        fill=(235, 235, 235) if (i + j) % 2 == 0 else (16, 16, 18))
    return img


def neon_sign(text, w=1024, h=256, color=(255, 43, 214), seed=1):
    """Leuchtschrift (Emission) auf schwarz – für Tore und Werbetafeln."""
    from carcad.textures import font
    img = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(img)
    size = int(h * 0.62)
    f = font(size, "cond")
    tw = d.textlength(text, font=f)
    while tw > w * 0.92 and size > 10:
        size -= 4
        f = font(size, "cond")
        tw = d.textlength(text, font=f)
    x = (w - tw) / 2
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    dg = ImageDraw.Draw(glow)
    ty = (h - size) / 2 - size * 0.08
    dg.text((x, ty), text, font=f, fill=color)
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    d.text((x, ty), text, font=f, fill=tuple(min(255, int(c * 0.6 + 110)) for c in color))
    out = Image.blend(glow, img, 0.6)
    arr = np.maximum(np.asarray(out, np.float32), np.asarray(img, np.float32))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


SHARED = {
    "asphalt_c": ("asphalt_c.jpg", "JPEG"),
    "asphalt_n": ("asphalt_n.jpg", "JPEG"),
    "asphalt_orm": ("asphalt_orm.jpg", "JPEG"),
    "concrete_c": ("concrete_c.jpg", "JPEG"),
    "concrete_n": ("concrete_n.jpg", "JPEG"),
    "dirt_c": ("dirt_c.jpg", "JPEG"),
    "dirt_n": ("dirt_n.jpg", "JPEG"),
    "curb_c": ("curb_c.jpg", "JPEG"),
    "facade_c": ("facade_c.jpg", "JPEG"),
    "facade_e": ("facade_e.jpg", "JPEG"),
    "checker_c": ("checker_c.png", "PNG"),
    "sign_neon_e": ("sign_neon_e.jpg", "JPEG"),
}


def build_all(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    imgs = {}
    imgs["asphalt_c"], imgs["asphalt_n"], imgs["asphalt_orm"] = asphalt()
    imgs["concrete_c"], imgs["concrete_n"] = concrete()
    imgs["dirt_c"], imgs["dirt_n"] = dirt()
    imgs["curb_c"] = curb()
    imgs["facade_c"], imgs["facade_e"] = facade()
    imgs["checker_c"] = checker()
    imgs["sign_neon_e"] = neon_sign("NEON HAVEN  TESTGELÄNDE", color=(255, 43, 214))
    lib = {}
    for name, (fname, fmt) in SHARED.items():
        data = encode(imgs[name], fmt, quality=86)
        with open(os.path.join(out_dir, fname), "wb") as f:
            f.write(data)
        lib[name] = {"file": fname, "mime": "image/jpeg" if fmt == "JPEG" else "image/png", "external": True,
                     "bytes": len(data)}
    return lib


def load_lib(out_dir):
    lib = {}
    for name, (fname, fmt) in SHARED.items():
        p = os.path.join(out_dir, fname)
        if not os.path.exists(p):
            return None
        lib[name] = {"file": fname, "mime": "image/jpeg" if fmt == "JPEG" else "image/png", "external": True,
                     "bytes": os.path.getsize(p)}
    return lib
