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
    build_city(imgs)
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


# ----------------------------------------------------------------------
# Stadt: Gehweg, Gras, Fassaden, Ladenzeilen, Leuchtreklame, Werbetafeln, Wasser
# ----------------------------------------------------------------------

def pavers(size=512, seed=71, n=4):
    """Gehwegplatten (n × n je Kachel), Fugen dunkel und vertieft."""
    r = rng(seed)
    noise = tile_noise(size, 32, seed, octaves=3)
    cell = size // n
    col = np.zeros((size, size), np.float32)
    hgt = np.zeros((size, size), np.float32)
    for j in range(n):
        for i in range(n):
            tone = 0.47 + 0.08 * r.random()
            col[j * cell:(j + 1) * cell, i * cell:(i + 1) * cell] = tone
            hgt[j * cell:(j + 1) * cell, i * cell:(i + 1) * cell] = 1.0
    yy, xx = np.mgrid[0:size, 0:size]
    joint = ((xx % cell) < 3) | ((yy % cell) < 3)
    col[joint] = 0.22
    hgt[joint] = 0.0
    col = col * (0.88 + 0.24 * noise)
    rgb = np.stack([col * 1.0, col * 0.99, col * 0.96], -1)
    hb = np.asarray(Image.fromarray((hgt * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)), height_to_normal(hb + noise * 0.15, strength=2.5)


def grass(size=512, seed=81):
    n1 = tile_noise(size, 6, seed, octaves=5, persistence=0.6)
    n2 = tile_noise(size, 128, seed + 1, octaves=2, persistence=0.7)
    g = 0.5 * n1 + 0.5 * n2
    rgb = np.stack([0.09 + 0.08 * g, 0.20 + 0.14 * g, 0.06 + 0.05 * g], -1)
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)), height_to_normal(n2, strength=3.0)


def _windows(col_img, emi_img, cols, rows, frame, glass, lit_p, palette, r, inset=(0.12, 0.14, 0.12, 0.2), mullion=True):
    w, h = col_img.size
    cw, ch = w / cols, h / rows
    dc, de = ImageDraw.Draw(col_img), ImageDraw.Draw(emi_img)
    for j in range(rows):
        floor_lit = r.random() < 0.15        # ganze Etage hell (Büro)
        for i in range(cols):
            x0, y0 = i * cw + cw * inset[0], j * ch + ch * inset[1]
            x1, y1 = (i + 1) * cw - cw * inset[2], (j + 1) * ch - ch * inset[3]
            g = glass[0] + int(glass[1] * r.random())
            dc.rectangle([x0, y0, x1, y1], fill=(g, g + 5, g + 14))
            if mullion:
                dc.line([(x0 + x1) / 2, y0, (x0 + x1) / 2, y1], fill=frame, width=2)
            if floor_lit or r.random() < lit_p:
                c = palette[int(r.random() * len(palette))]
                k = 0.5 + 0.5 * r.random()
                de.rectangle([x0 + 1, y0 + 1, x1 - 1, y1 - 1], fill=tuple(int(v * k) for v in c))


def facade_glass(size=512, seed=91):
    """Glasfassade (Büroturm): 4 Achsen × 4 Etagen je Kachel."""
    r = rng(seed)
    col = Image.new("RGB", (size, size), (96, 104, 114))
    emi = Image.new("RGB", (size, size), (0, 0, 0))
    _windows(col, emi, 4, 4, (120, 128, 138), (34, 22), 0.45,
             [(200, 225, 255), (235, 240, 255), (170, 205, 255), (255, 236, 200)], r, inset=(0.04, 0.06, 0.04, 0.22))
    d = ImageDraw.Draw(col)
    for j in range(4):                         # Brüstungsbänder
        y = int((j + 1) * size / 4 - size / 4 * 0.2)
        d.rectangle([0, y, size, y + int(size / 4 * 0.2)], fill=(58, 64, 74))
    return col, emi


def facade_panel(size=512, seed=101):
    """Putz-/Plattenfassade mit kleinen Fenstern und Klimageräten (Neon-Markt). Grau, wird per Material eingefärbt."""
    r = rng(seed)
    n = tile_noise(size, 16, seed, octaves=4)
    base = (150 + 40 * (n - 0.5)).clip(0, 255).astype(np.uint8)
    col = Image.fromarray(np.stack([base, base, base], -1))
    emi = Image.new("RGB", (size, size), (0, 0, 0))
    _windows(col, emi, 4, 4, (60, 60, 64), (24, 18), 0.5,
             [(255, 190, 120), (255, 150, 80), (120, 200, 255), (255, 80, 200), (180, 255, 210)], r,
             inset=(0.2, 0.22, 0.2, 0.3))
    d = ImageDraw.Draw(col)
    for k in range(6):                         # Klimageräte, Rohre, Schmutzfahnen
        x = int(r.random() * size); y = int(r.random() * size)
        d.rectangle([x, y, x + 26, y + 18], fill=(88, 90, 92))
        d.line([x + 13, y + 18, x + 13, y + 60], fill=(70, 70, 72), width=2)
    arr = np.asarray(col, np.float32)
    streak = tile_noise(size, 24, seed + 5, octaves=2)
    arr *= (0.85 + 0.15 * streak)[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8)), emi


def facade_apart(size=512, seed=111):
    """Wohnhaus: 3 Achsen × 4 Etagen, Balkonbänder."""
    r = rng(seed)
    col = Image.new("RGB", (size, size), (168, 160, 150))
    emi = Image.new("RGB", (size, size), (0, 0, 0))
    _windows(col, emi, 3, 4, (210, 205, 198), (30, 16), 0.38,
             [(255, 200, 130), (255, 180, 110), (255, 220, 170), (200, 220, 255)], r, inset=(0.15, 0.12, 0.15, 0.32))
    d = ImageDraw.Draw(col)
    for j in range(4):                         # Balkone: Platte + Geländer
        y = int((j + 1) * size / 4 - size / 4 * 0.3)
        d.rectangle([0, y, size, y + 8], fill=(120, 116, 110))
        for x in range(0, size, 10):
            d.line([x, y - 26, x, y], fill=(70, 72, 76), width=1)
        d.line([0, y - 26, size, y - 26], fill=(70, 72, 76), width=2)
    return col, emi


def facade_ware(size=512, seed=121):
    """Lagerhalle: Trapezblech (senkrechte Sicken), oben ein Fensterband."""
    xx = np.arange(size)
    prof = (np.sin(xx / size * 2 * math.pi * 24) > 0.2).astype(np.float32)
    h = np.tile(prof, (size, 1))
    n = tile_noise(size, 8, seed, octaves=4)
    c = 0.62 * (0.8 + 0.2 * h) * (0.85 + 0.3 * (n - 0.5))
    rgb = np.stack([c, c, c * 1.02], -1)
    col = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    emi = Image.new("RGB", (size, size), (0, 0, 0))
    d, de = ImageDraw.Draw(col), ImageDraw.Draw(emi)
    d.rectangle([0, 30, size, 74], fill=(40, 46, 54))
    for x in range(0, size, 64):
        d.line([x, 30, x, 74], fill=(90, 92, 96), width=3)
        if (x // 64) % 3 == 0:
            de.rectangle([x + 3, 32, x + 61, 72], fill=(150, 170, 190))
    return col, emi, height_to_normal(h * 0.8 + n * 0.1, strength=3.0)


def shopfront(w=1024, h=512, seed=131):
    """Ladenzeile Erdgeschoss: 2 Läden je Kachel (8 m × 4,2 m) mit beleuchteten Schaufenstern."""
    r = rng(seed)
    col = Image.new("RGB", (w, h), (36, 36, 40))
    emi = Image.new("RGB", (w, h), (0, 0, 0))
    dc, de = ImageDraw.Draw(col), ImageDraw.Draw(emi)
    tints = [(255, 214, 160), (190, 230, 255), (255, 170, 220), (200, 255, 210), (255, 240, 200)]
    for k in range(2):
        x0 = k * w // 2
        # Schildband oben (dunkel), Rahmen, Schaufenster, Tür
        dc.rectangle([x0, 0, x0 + w // 2, int(h * 0.2)], fill=(24, 24, 28))
        dc.rectangle([x0 + 10, int(h * 0.24), x0 + w // 2 - 10, h - 6], fill=(70, 72, 78))
        t = tints[int(r.random() * len(tints))]
        dc.rectangle([x0 + 22, int(h * 0.28), x0 + int(w * 0.33), h - 30], fill=(40, 44, 50))
        de.rectangle([x0 + 22, int(h * 0.28), x0 + int(w * 0.33), h - 30], fill=t)
        # Regale/Silhouetten im Schaufenster
        for s in range(5):
            yy = int(h * 0.38) + s * 34
            de.line([x0 + 30, yy, x0 + int(w * 0.32), yy], fill=tuple(int(v * 0.55) for v in t), width=5)
        dc.rectangle([x0 + int(w * 0.36), int(h * 0.3), x0 + w // 2 - 22, h - 6], fill=(30, 30, 34))
        de.rectangle([x0 + int(w * 0.37), int(h * 0.32), x0 + w // 2 - 24, h - 8], fill=tuple(int(v * 0.6) for v in t))
    return col, emi


NEON = [(255, 43, 214), (0, 229, 255), (122, 92, 255), (255, 138, 0), (57, 255, 20), (255, 225, 77), (255, 31, 61),
        (240, 240, 255)]
SIGNS_H = ["RAMEN", "HOTEL NOVA", "ARCADE", "SPÄTI 24/7", "NETRUNNER", "SYNTH BAR", "KLINIK", "PIXEL KINO"]
SIGNS_V = ["NEON", "BAR", "HOTEL", "SUSHI", "TECH", "CLUB", "ZERO", "OPEN"]


def _glow_text(img, box, text, color, vertical=False, seed=0):
    from carcad.textures import font
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGB", (w, h) if not vertical else (h, w), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    lw, lh = layer.size
    size = int(lh * 0.62)
    f = font(size, "cond")
    tw = d.textlength(text, font=f)
    while tw > lw * 0.86 and size > 8:
        size -= 2
        f = font(size, "cond")
        tw = d.textlength(text, font=f)
    ty = (lh - size) / 2 - size * 0.1
    glow = Image.new("RGB", layer.size, (0, 0, 0))
    ImageDraw.Draw(glow).text(((lw - tw) / 2, ty), text, font=f, fill=color)
    glow = glow.filter(ImageFilter.GaussianBlur(max(3, lh // 14)))
    d.text(((lw - tw) / 2, ty), text, font=f, fill=tuple(min(255, int(c * 0.55 + 120)) for c in color))
    # Rahmen aus Neonröhre
    d.rectangle([4, 4, lw - 5, lh - 5], outline=color, width=3)
    out = np.maximum(np.asarray(glow, np.float32) * 1.3, np.asarray(layer, np.float32))
    out = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    if vertical:
        out = out.rotate(90, expand=True)
    img.paste(out, (x0, y0))


def signs_atlas(size=1024):
    """Leuchtreklame: oben 8 waagerechte Schilder (2 × 4 Zellen à 512 × 128),
    unten 8 senkrechte (8 Zellen à 128 × 512)."""
    img = Image.new("RGB", (size, size), (0, 0, 0))
    for i, t in enumerate(SIGNS_H):
        c, rr = i % 2, i // 2
        _glow_text(img, (c * 512, rr * 128, c * 512 + 512, rr * 128 + 128), t, NEON[i % len(NEON)])
    for j, t in enumerate(SIGNS_V):
        _glow_text(img, (j * 128, 512, j * 128 + 128, 1024), t, NEON[(j + 3) % len(NEON)], vertical=True)
    return img


def billboards(size=1024, seed=141):
    """Vier große Werbetafeln (je 512 × 512) für Hochhäuser."""
    from carcad.textures import font
    r = rng(seed)
    img = Image.new("RGB", (size, size), (0, 0, 0))
    ads = [("NEON COLA", "TRINK DAS LICHT", (255, 43, 214), (40, 0, 60)),
           ("KAI CORP", "DIE ZUKUNFT GEHÖRT UNS", (0, 229, 255), (0, 30, 50)),
           ("SYNTH-X", "IMPLANTATE · JETZT 0% ZINS", (122, 92, 255), (20, 0, 40)),
           ("VEKTRA GT", "470 KW · FAHR DIE NACHT", (255, 138, 0), (50, 10, 0))]
    for k, (title, sub, c, bg) in enumerate(ads):
        x0, y0 = (k % 2) * 512, (k // 2) * 512
        cell = Image.new("RGB", (512, 512), bg)
        d = ImageDraw.Draw(cell)
        yy = np.linspace(0, 1, 512)[:, None]
        grad = (np.array(bg)[None, None, :] * (1 - yy[..., None]) + np.array(c)[None, None, :] * 0.35 * yy[..., None])
        cell = Image.fromarray(np.clip(np.repeat(grad, 512, axis=1), 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(cell)
        for s in range(14):                    # Formen
            cx, cy, rad = r.random() * 512, r.random() * 300, 20 + r.random() * 90
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=c, width=3)
        fs = 92
        f = font(fs, "cond")
        tw = d.textlength(title, font=f)
        while tw > 470 and fs > 20:
            fs -= 4
            f = font(fs, "cond")
            tw = d.textlength(title, font=f)
        d.text(((512 - tw) / 2, 300), title, font=f, fill=(255, 255, 255))
        f2 = font(30, "cond")
        tw = d.textlength(sub, font=f2)
        d.text(((512 - tw) / 2, 410), sub, font=f2, fill=c)
        d.rectangle([6, 6, 505, 505], outline=c, width=6)
        img.paste(cell, (x0, y0))
    return img


def water_normal(size=512, seed=151):
    n = tile_noise(size, 12, seed, octaves=5, persistence=0.55)
    return height_to_normal(n, strength=6.0)


CITY_SHARED = {
    "pavers_c": ("pavers_c.jpg", "JPEG"), "pavers_n": ("pavers_n.jpg", "JPEG"),
    "grass_c": ("grass_c.jpg", "JPEG"), "grass_n": ("grass_n.jpg", "JPEG"),
    "fac_glass_c": ("fac_glass_c.jpg", "JPEG"), "fac_glass_e": ("fac_glass_e.jpg", "JPEG"),
    "fac_panel_c": ("fac_panel_c.jpg", "JPEG"), "fac_panel_e": ("fac_panel_e.jpg", "JPEG"),
    "fac_apart_c": ("fac_apart_c.jpg", "JPEG"), "fac_apart_e": ("fac_apart_e.jpg", "JPEG"),
    "fac_ware_c": ("fac_ware_c.jpg", "JPEG"), "fac_ware_e": ("fac_ware_e.jpg", "JPEG"), "fac_ware_n": ("fac_ware_n.jpg", "JPEG"),
    "shop_c": ("shop_c.jpg", "JPEG"), "shop_e": ("shop_e.jpg", "JPEG"),
    "signs_e": ("signs_e.jpg", "JPEG"), "billboards_e": ("billboards_e.jpg", "JPEG"),
    "water_n": ("water_n.jpg", "JPEG"),
}
SHARED.update(CITY_SHARED)


def build_city(imgs):
    imgs["pavers_c"], imgs["pavers_n"] = pavers()
    imgs["grass_c"], imgs["grass_n"] = grass()
    imgs["fac_glass_c"], imgs["fac_glass_e"] = facade_glass()
    imgs["fac_panel_c"], imgs["fac_panel_e"] = facade_panel()
    imgs["fac_apart_c"], imgs["fac_apart_e"] = facade_apart()
    imgs["fac_ware_c"], imgs["fac_ware_e"], imgs["fac_ware_n"] = facade_ware()
    imgs["shop_c"], imgs["shop_e"] = shopfront()
    imgs["signs_e"] = signs_atlas()
    imgs["billboards_e"] = billboards()
    imgs["water_n"] = water_normal()
