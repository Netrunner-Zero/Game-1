"""Prozedurale Texturen (numpy + Pillow).

Geteilte Texturen werden als Dateien nach models/textures/ geschrieben
und von allen Autos referenziert (einmal laden, im Browser gecacht).
Auto-spezifische Texturen (Logos, Displays, Kennzeichen …) werden in
die GLB eingebettet.

Normalmaps: Tangentenraum, +X rechts, +Y oben (glTF/OpenGL).
"""
import io
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"


def font(size, kind="cond"):
    files = {"cond": "DejaVuSansCondensed-Bold.ttf", "mono": "DejaVuSansMono-Bold.ttf",
             "sans": "DejaVuSans.ttf", "bold": "DejaVuSans-Bold.ttf", "serif": "DejaVuSerif-Bold.ttf",
             "light": "DejaVuSans-ExtraLight.ttf", "condlight": "DejaVuSansCondensed.ttf"}
    try:
        return ImageFont.truetype(FONT_DIR + files[kind], size)
    except OSError:
        return ImageFont.load_default(size=size)


def encode(img, fmt="PNG", quality=90):
    b = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(b, "JPEG", quality=quality, optimize=True, progressive=True)
    else:
        img.save(b, "PNG", optimize=True)
    return b.getvalue()


def rng(seed):
    return np.random.default_rng(seed)


# ----------------------------------------------------------------------
# Rausch-Bausteine (kachelbar)
# ----------------------------------------------------------------------

def tile_noise(size, cells, seed, octaves=4, persistence=0.5):
    """Kachelbares Value-Noise (bilinear, mehrere Oktaven), Wertebereich ~0..1."""
    r = rng(seed)
    out = np.zeros((size, size))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = cells * (2 ** o)
        g = r.random((c, c))
        ys = np.linspace(0, c, size, endpoint=False)
        y0 = np.floor(ys).astype(int)
        fy = ys - y0
        fy = fy * fy * (3 - 2 * fy)
        y1 = (y0 + 1) % c
        a = g[y0][:, y0] * (1 - fy)[None, :] + g[y0][:, y1] * fy[None, :]
        b = g[y1][:, y0] * (1 - fy)[None, :] + g[y1][:, y1] * fy[None, :]
        val = a * (1 - fy)[:, None] + b * fy[:, None]
        out += val * amp
        tot += amp
        amp *= persistence
    return out / tot


def worley(size, n_points, seed):
    """Kachelbares Zell-Rauschen: Abstand zum nächsten Punkt (0..1)."""
    r = rng(seed)
    pts = r.random((n_points, 2)) * size
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.full((size, size), 1e9, dtype=np.float32)
    for (px, py) in pts:
        dx = np.abs(xx - px)
        dx = np.minimum(dx, size - dx)
        dy = np.abs(yy - py)
        dy = np.minimum(dy, size - dy)
        d = np.minimum(d, dx * dx + dy * dy)
    d = np.sqrt(d)
    return d / d.max()


def height_to_normal(h, strength=2.0):
    """Höhenkarte -> Normalmap (kachelbar, glTF-Konvention)."""
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    nx = -dx * strength
    ny = dy * strength
    nz = np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / ln, ny / ln, nz / ln], -1)
    return Image.fromarray(((n * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8))


# ----------------------------------------------------------------------
# Geteilte Material-Texturen
# ----------------------------------------------------------------------

def flakes_normal(size=512, seed=1):
    """Metallic-Flakes: kleine Plättchen mit zufälliger Neigung unter dem Klarlack."""
    r = rng(seed)
    cell = 2
    c = size // cell
    tilt = r.random((c, c)) ** 1.5 * 0.55
    ang = r.random((c, c)) * 2 * math.pi
    on = r.random((c, c)) < 0.75
    nx = np.where(on, np.sin(tilt) * np.cos(ang), 0.0)
    ny = np.where(on, np.sin(tilt) * np.sin(ang), 0.0)
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    n = np.stack([nx, ny, nz], -1).repeat(cell, 0).repeat(cell, 1)
    return Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8))


def carbon(size=512, tows=8):
    """2x2-Köper-Carbon: Farbtextur + Normalmap."""
    t = size // tows
    yy, xx = np.mgrid[0:size, 0:size]
    ci, cj = yy // t, xx // t
    fy, fx = (yy % t) / t, (xx % t) / t
    horiz = (((ci + cj) // 2) % 2) == 0
    across = np.where(horiz, fy, fx)
    bulge = np.sin(across * math.pi)
    streak_h = tile_noise(size, 64, 7, octaves=2)
    streak = np.where(horiz, np.roll(streak_h, 0, 1), streak_h.T)
    # Fasern entlang der Faserrichtung
    fib = np.where(horiz, np.sin(yy * 2.1) * 0.5 + 0.5, np.sin(xx * 2.1) * 0.5 + 0.5)
    base = 0.014 + 0.055 * bulge * (0.7 + 0.3 * fib) + 0.016 * streak
    sheen = np.where(horiz, 1.0, 0.75)
    v = base * sheen
    rgb = np.stack([v * 0.96, v * 0.98, v * 1.05], -1)
    col = Image.fromarray((np.clip(rgb, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))
    h = bulge * 0.6 + fib * 0.08
    nrm = height_to_normal(h, strength=3.0)
    return col, nrm


def leather_normal(size=512, seed=3):
    w = worley(size, 900, seed)
    g = 1 - np.clip(w * 3.2, 0, 1)
    fine = tile_noise(size, 32, seed + 1, octaves=3)
    h = g * 0.8 + fine * 0.25
    return height_to_normal(h, strength=2.4)


def micro_normal(size=256, seed=5, strength=1.2, cells=32):
    h = tile_noise(size, cells, seed, octaves=4, persistence=0.6)
    return height_to_normal(h, strength=strength)


def brushed(size=512, seed=9):
    r = rng(seed)
    line = r.random(size)
    line = np.convolve(np.concatenate([line, line[:8]]), np.ones(8) / 8, "valid")[:size]
    v = 0.72 + 0.12 * line[:, None] * np.ones((1, size))
    noise = tile_noise(size, 16, seed + 1, octaves=2) * 0.05
    v = v + noise
    rgb = np.stack([v, v * 1.005, v * 1.02], -1)
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def wood(w=1024, h=512, seed=11, tone=(0.20, 0.10, 0.045), dark=(0.075, 0.032, 0.014)):
    """Edelholz-Furnier (Längsmaserung mit Wellen), kachelbar in Längsrichtung."""
    r = rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    warp = tile_noise(max(w, h), 6, seed, octaves=3)[:h, :w] * 40
    warp2 = tile_noise(max(w, h), 24, seed + 3, octaves=2)[:h, :w] * 6
    rings = np.sin((yy + warp + warp2) * 0.21) * 0.5 + 0.5
    rings = rings ** 2.2
    pores = (tile_noise(max(w, h), 128, seed + 5, octaves=1)[:h, :w] > 0.72) * 0.12
    t = np.clip(rings * 0.75 + pores, 0, 1)[..., None]
    a = np.array(tone)[None, None, :]
    d = np.array(dark)[None, None, :]
    rgb = a * (1 - t) + d * t
    rgb = rgb * (0.9 + 0.2 * tile_noise(max(w, h), 4, seed + 7, octaves=2)[:h, :w, None])
    return Image.fromarray((np.clip(rgb, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))


def tread_normal(w=512, h=256, kind="sport"):
    """Profil: Längsrillen + Lamellen. u = Umfang, v = Breite."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    hgt = np.ones((h, w), dtype=np.float32)
    if kind == "sport":
        for gy in (0.24, 0.5, 0.76):
            hgt -= np.exp(-((yy / h - gy) ** 2) / (2 * 0.012 ** 2)) * 0.9
        sip = (np.sin((xx / w * 24 + (yy / h) * 3) * math.pi) > 0.92).astype(np.float32)
        band = ((yy / h > 0.08) & (yy / h < 0.92)).astype(np.float32)
        hgt -= sip * band * 0.35
    else:  # Allterrain: Blöcke
        bx = (xx / w * 12) % 1.0
        by = (yy / h * 4) % 1.0
        stagger = ((np.floor(yy / h * 4) % 2) * 0.5)
        bx2 = (xx / w * 12 + stagger) % 1.0
        block = ((bx2 > 0.12) & (bx2 < 0.88) & (by > 0.1) & (by < 0.9)).astype(np.float32)
        hgt = 0.2 + block * 0.8
    img = Image.fromarray((np.clip(hgt, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    hh = np.asarray(img).astype(np.float32) / 255.0
    return height_to_normal(hh, strength=6.0)


def sidewall(text, w=2048, h=128):
    """Reifenflanke: dunkler Gummi, Beschriftung leicht heller (u = Umfang, v = radial)."""
    img = Image.new("RGB", (w, h), (11, 11, 12))
    d = ImageDraw.Draw(img)
    f1 = font(58, "cond")
    f2 = font(30, "cond")
    for k in range(2):
        x0 = k * w // 2
        d.text((x0 + 70, 14), text[0], font=f1, fill=(46, 46, 48))
        d.text((x0 + 72, 80), text[1], font=f2, fill=(36, 36, 38))
    # feine Rillen am Felgenhorn und an der Lauffläche
    for yv in (6, 10, h - 12, h - 8):
        d.line((0, yv, w, yv), fill=(20, 20, 21), width=2)
    return img


def disc_texture(size=512, slots=True, drilled=True):
    """Bremsscheibe (polare UVs): Reibfläche mit Riefen, Bohrungen, Schlitzen, Topf."""
    img = Image.new("RGB", (size, size), (70, 70, 74))
    d = ImageDraw.Draw(img)
    c = size / 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    rr = np.hypot(xx - c, yy - c) / c
    arr = np.asarray(img).astype(np.float32)
    rings = (np.sin(rr * 260) * 0.5 + 0.5) * 10
    arr[..., :] += rings[..., None] - 5
    hat = rr < 0.42
    arr[hat] = [44, 45, 48]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    if drilled:
        for ring_r, n, off in ((0.62, 18, 0.0), (0.76, 18, 0.5), (0.9, 18, 0.0)):
            for k in range(n):
                a = (k + off) / n * 2 * math.pi
                x, y = c + math.cos(a) * ring_r * c, c + math.sin(a) * ring_r * c
                rd = size * 0.012
                d.ellipse((x - rd, y - rd, x + rd, y + rd), fill=(14, 14, 15))
    if slots:
        for k in range(6):
            a0 = k / 6 * 2 * math.pi + 0.2
            pts = []
            for t in np.linspace(0, 1, 8):
                rad = (0.55 + 0.4 * t) * c
                a = a0 + t * 0.5
                pts.append((c + math.cos(a) * rad, c + math.sin(a) * rad))
            d.line(pts, fill=(22, 22, 24), width=max(2, size // 160))
    # Topf-Schrauben
    for k in range(5):
        a = k / 5 * 2 * math.pi
        x, y = c + math.cos(a) * 0.3 * c, c + math.sin(a) * 0.3 * c
        rd = size * 0.025
        d.ellipse((x - rd, y - rd, x + rd, y + rd), fill=(150, 150, 155))
    return img


def stitch(w=64, h=16):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x in range(0, w, 16):
        d.rounded_rectangle((x + 2, 5, x + 11, 10), radius=3, fill=(255, 255, 255, 255))
    return img


def speaker(size=256):
    img = Image.new("RGB", (size, size), (60, 62, 66))
    d = ImageDraw.Draw(img)
    step = size // 16
    for j in range(16):
        for i in range(16):
            ox = (step // 2) if j % 2 else 0
            x, y = i * step + ox, j * step + step // 2
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(8, 8, 9))
    return img


def starlight(size=1024, seed=21):
    """Sternenhimmel (Emission) – dimmbar über die Innenraumbeleuchtung."""
    r = rng(seed)
    arr = np.zeros((size, size, 3), dtype=np.float32)
    n = 900
    xs = r.integers(0, size, n)
    ys = r.integers(0, size, n)
    br = r.random(n) ** 3
    for x, y, b in zip(xs, ys, br):
        rad = 1 if b < 0.6 else 2
        v = 0.35 + 0.65 * b
        tint = np.array([1.0, 0.97, 0.9]) if r.random() < 0.8 else np.array([0.85, 0.9, 1.0])
        arr[max(0, y - rad):y + rad + 1, max(0, x - rad):x + rad + 1] = np.maximum(
            arr[max(0, y - rad):y + rad + 1, max(0, x - rad):x + rad + 1], v * tint)
    img = Image.fromarray((arr * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    return img


def fabric_check(size=512, base=(38, 40, 44), line=(182, 255, 0), seed=13):
    """Karostoff für Sportsitze (Linienfarbe je Auto)."""
    yy, xx = np.mgrid[0:size, 0:size]
    a = np.array(base, dtype=np.float32)[None, None, :] / 255
    b = np.array(line, dtype=np.float32)[None, None, :] / 255
    c = np.array((20, 21, 24), dtype=np.float32)[None, None, :] / 255
    cell = size // 8
    gx = (xx % cell) < cell * 0.5
    gy = (yy % cell) < cell * 0.5
    mix = (gx.astype(np.float32) + gy.astype(np.float32)) / 2
    col = a * (1 - mix[..., None]) + c * mix[..., None]
    thin = ((xx % cell) == cell // 4) | ((yy % cell) == cell // 4)
    col = np.where(thin[..., None], b * 0.85, col)
    weave = (np.sin(xx * 1.6) * np.sin(yy * 1.6)) * 0.03
    col = col + weave[..., None]
    return Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8))


SHARED = {
    # name: (datei, erzeuger, format)
    "flakes_n": ("flakes_n.png", lambda: flakes_normal(), "PNG"),
    "carbon_c": ("carbon_c.jpg", lambda: carbon()[0], "JPEG"),
    "carbon_n": ("carbon_n.jpg", lambda: carbon()[1], "JPEG"),
    "leather_n": ("leather_n.jpg", lambda: leather_normal(), "JPEG"),
    "alcantara_n": ("alcantara_n.jpg", lambda: micro_normal(256, 5, 1.6, 48), "JPEG"),
    "plastic_n": ("plastic_n.jpg", lambda: micro_normal(256, 6, 0.8, 32), "JPEG"),
    "cladding_n": ("cladding_n.jpg", lambda: micro_normal(256, 7, 2.2, 24), "JPEG"),
    "carpet_n": ("carpet_n.jpg", lambda: micro_normal(256, 8, 3.0, 96), "JPEG"),
    "brushed_c": ("brushed_c.jpg", lambda: brushed(), "JPEG"),
    "wood_walnut": ("wood_walnut.jpg", lambda: wood(), "JPEG"),
    "wood_ash": ("wood_ash.jpg", lambda: wood(seed=17, tone=(0.55, 0.45, 0.33), dark=(0.33, 0.25, 0.16)), "JPEG"),
    "tread_sport_n": ("tread_sport_n.jpg", lambda: tread_normal(kind="sport"), "JPEG"),
    "tread_at_n": ("tread_at_n.jpg", lambda: tread_normal(kind="at"), "JPEG"),
    "sidewall_c": ("sidewall_c.png", lambda: sidewall(("NEON HAVEN  PROGRIP", "SPORT  Z-RATED  TUBELESS  RADIAL  MAX LOAD 725 KG")), "PNG"),
    "disc_c": ("disc_c.jpg", lambda: disc_texture(), "JPEG"),
    "stitch_a": ("stitch_a.png", lambda: stitch(), "PNG"),
    "speaker_c": ("speaker_c.png", lambda: speaker(), "PNG"),
    "starlight_e": ("starlight_e.png", lambda: starlight(), "PNG"),
}


def build_shared(out_dir):
    """Schreibt die geteilten Texturen und liefert die Texturbibliothek."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    lib = {}
    for name, (fname, fn, fmt) in SHARED.items():
        img = fn()
        data = encode(img, fmt, quality=88)
        with open(os.path.join(out_dir, fname), "wb") as f:
            f.write(data)
        lib[name] = {"file": fname, "mime": "image/jpeg" if fmt == "JPEG" else "image/png", "external": True,
                     "bytes": len(data)}
    return lib


def embed(img, fmt="PNG", quality=90):
    data = encode(img, fmt, quality)
    return {"data": data, "mime": "image/jpeg" if fmt == "JPEG" else "image/png", "external": False,
            "bytes": len(data)}
