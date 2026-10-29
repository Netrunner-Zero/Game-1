"""Auto-spezifische Texturen (werden in die GLB eingebettet):
Embleme, Schriftzüge, Nabendeckel, Bremssattel-Logo, Kennzeichen,
Startnummer, Displays (Standardbild – im Spiel live gezeichnet),
Easter-Egg-Texturen und der vorberechnete Kontaktschatten.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .textures import font, embed, fabric_check


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def center_text(d, xy, text, f, fill):
    bb = d.textbbox((0, 0), text, font=f)
    d.text((xy[0] - (bb[2] - bb[0]) / 2 - bb[0], xy[1] - (bb[3] - bb[1]) / 2 - bb[1]), text, font=f, fill=fill)


def emblem(mono, accent, size=512, ring=(225, 226, 230), field=(18, 18, 22)):
    """Rundes Emblem: Chromring, dunkles Feld, Monogramm."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    d.ellipse((6, 6, size - 6, size - 6), fill=ring + (255,))
    d.ellipse((30, 30, size - 30, size - 30), fill=(150, 152, 158, 255))
    d.ellipse((44, 44, size - 44, size - 44), fill=field + (255,))
    acc = _hex(accent)
    d.arc((70, 70, size - 70, size - 70), 200, 340, fill=acc + (255,), width=10)
    center_text(d, (c, c + 8), mono, font(int(size * 0.42), "serif"), ring + (255,))
    return img


def wordmark(text, w=1024, h=160, color=(232, 233, 238)):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(120, "cond")
    # Buchstaben gesperrt
    spaced = " ".join(list(text))
    center_text(d, (w / 2, h / 2), spaced, f, color + (255,))
    return img


def caliper_logo(text, w=512, h=128):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    center_text(d, (w / 2, h / 2), text, font(88, "cond"), (250, 250, 250, 255))
    return img


def plate(text, w=1040, h=220):
    img = Image.new("RGB", (w, h), (244, 245, 241))
    d = ImageDraw.Draw(img)
    d.rectangle((4, 4, w - 5, h - 5), outline=(20, 20, 24), width=8)
    d.rectangle((8, 8, 110, h - 9), fill=(28, 70, 190))
    center_text(d, (59, 70), "★", font(46, "sans"), (250, 210, 40))
    center_text(d, (59, 160), "NH", font(52), (255, 255, 255))
    center_text(d, (w / 2 + 55, h / 2 + 4), text, font(150, "cond"), (16, 16, 20))
    return img


def number(num, size=512):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, size - 6, size - 6), fill=(250, 250, 250, 255))
    d.ellipse((30, 30, size - 30, size - 30), outline=(12, 12, 16, 255), width=10)
    center_text(d, (size / 2, size / 2 + 6), num, font(270), (12, 12, 16))
    return img


def cluster_digital(name, accent, vmax, w=1024, h=410):
    """Digitales Kombiinstrument (Standardbild)."""
    img = Image.new("RGB", (w, h), (4, 5, 8))
    d = ImageDraw.Draw(img)
    acc = _hex(accent)
    dim = tuple(int(c * 0.3) for c in acc)
    # Drehzahlbogen
    cx, cy, r = w / 2, h * 0.98, h * 0.9
    d.arc((cx - r, cy - r, cx + r, cy + r), 200, 340, fill=(30, 32, 40), width=22)
    d.arc((cx - r, cy - r, cx + r, cy + r), 200, 228, fill=acc, width=22)
    for k in range(9):
        a = math.radians(200 + 140 * k / 8)
        x0, y0 = cx + (r - 34) * math.cos(a), cy + (r - 34) * math.sin(a)
        center_text(d, (x0, y0 + 26), str(k), font(26, "mono"), (140, 145, 160))
    center_text(d, (cx, h * 0.5), "0", font(150, "cond"), (240, 242, 248))
    center_text(d, (cx, h * 0.72), "km/h", font(30, "sans"), (130, 136, 150))
    d.rounded_rectangle((cx - 40, h * 0.78, cx + 40, h * 0.93), radius=10, outline=acc, width=4)
    center_text(d, (cx, h * 0.855), "P", font(48, "cond"), acc)
    # Seitenfelder
    d.text((40, 40), name.upper(), font=font(30, "cond"), fill=(200, 204, 216))
    d.text((40, 84), "23:07   18°C", font=font(26, "mono"), fill=(120, 126, 140))
    d.text((w - 260, 40), "RANGE 412 km", font=font(26, "mono"), fill=(120, 126, 140))
    for i, lab in enumerate(("FUEL", "TEMP")):
        y = h - 110 + i * 46
        d.text((40, y), lab, font=font(22, "mono"), fill=(110, 116, 130))
        d.rectangle((130, y + 6, 330, y + 20), fill=(28, 30, 38))
        d.rectangle((130, y + 6, 130 + (150 if i == 0 else 110), y + 20), fill=acc if i == 0 else (90, 170, 255))
    d.text((w - 300, h - 110), "ODO 077 777 km", font=font(24, "mono"), fill=dim)
    d.text((w - 300, h - 70), "NH-OS 4.0", font=font(22, "mono"), fill=(80, 86, 100))
    return img


def cluster_analog(accent, vmax, rpm_max, w=1024, h=512):
    img = Image.new("RGB", (w, h), (8, 8, 10))
    d = ImageDraw.Draw(img)
    acc = _hex(accent)
    for cx, maxv, step, label, red in ((256, vmax, 20, "km/h", None),
                                       (768, rpm_max, 1 if rpm_max < 12 else 2, "x1000 U/min", rpm_max - 1.5)):
        cy, r = 256, 220
        d.ellipse((cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10), fill=(22, 22, 26), outline=(170, 172, 178), width=8)
        n = int(maxv / step)
        for i in range(n + 1):
            v = i * step
            t = v / maxv
            th = math.radians(225 - 270 * t)
            major = (i % 2 == 0) if step == 20 else True
            r0 = r - (34 if major else 18)
            col = (255, 70, 60) if (red is not None and v >= red) else (238, 236, 228)
            d.line((cx + r0 * math.cos(th), cy - r0 * math.sin(th), cx + (r - 6) * math.cos(th), cy - (r - 6) * math.sin(th)),
                   fill=col, width=7 if major else 3)
            if major:
                tr = r - 70
                center_text(d, (cx + tr * math.cos(th), cy - tr * math.sin(th)), str(int(v)),
                            font(30 if step == 20 else 40, "cond"), col)
        center_text(d, (cx, cy + 96), label, font(26, "sans"), (150, 150, 140))
    center_text(d, (512, 430), "077 777", font(30, "mono"), acc)
    return img


def center_display(name, accent, user="Zero", w=1024, h=640):
    img = Image.new("RGB", (w, h), (5, 6, 12))
    d = ImageDraw.Draw(img)
    acc = _hex(accent)
    dim = tuple(int(c * 0.35) for c in acc)
    for i in range(0, w, 64):
        d.line((i, 90, i - 220, h), fill=(18, 22, 34), width=2)
    for j in range(110, h, 56):
        d.line((0, j, 640, j + 30), fill=(18, 22, 34), width=2)
    pts = [(80, 600), (180, 470), (330, 430), (420, 300), (560, 260), (610, 140)]
    d.line(pts, fill=acc, width=10, joint="curve")
    d.ellipse((598, 128, 622, 152), fill=(255, 255, 255))
    d.polygon([(70, 590), (95, 560), (100, 610)], fill=(255, 255, 255))
    d.rectangle((0, 0, w, 86), fill=(10, 12, 20))
    d.text((28, 22), "NEON HAVEN OS", font=font(38), fill=acc)
    d.text((w - 210, 26), "23:07  18°C", font=font(32, "mono"), fill=(220, 224, 236))
    d.rectangle((660, 110, w - 24, h - 24), fill=(12, 14, 24), outline=dim, width=3)
    d.text((690, 135), "Hallo %s!" % user, font=font(44), fill=(240, 242, 250))
    d.text((690, 195), name, font=font(30, "sans"), fill=(150, 156, 176))
    d.text((690, 270), "JETZT LÄUFT", font=font(22, "sans"), fill=dim)
    d.text((690, 300), "Midnight Overdrive", font=font(30), fill=(235, 238, 246))
    d.text((690, 340), "The Synth Rats", font=font(26, "sans"), fill=(150, 156, 176))
    d.rectangle((690, 395, w - 54, 403), fill=(40, 44, 60))
    d.rectangle((690, 395, 870, 403), fill=acc)
    d.text((690, 450), "Ziel: Neon Pier", font=font(28, "sans"), fill=(200, 204, 220))
    d.text((690, 490), "4,2 km · 6 min", font=font(28, "mono"), fill=acc)
    d.text((690, 560), "Tipp: Hupe 3x drücken …", font=font(22, "sans"), fill=(90, 96, 115))
    return img


def retro_display(accent, w=512, h=170):
    img = Image.new("RGB", (w, h), (20, 12, 4))
    d = ImageDraw.Draw(img)
    d.text((24, 16), "FM 77.7", font=font(64, "mono"), fill=(255, 150, 40))
    d.text((24, 100), "MIXTAPE '77 - SIDE A", font=font(30, "mono"), fill=(200, 110, 30))
    return img


def rear_display(accent, w=1024, h=640):
    img = Image.new("RGB", (w, h), (6, 6, 10))
    d = ImageDraw.Draw(img)
    acc = _hex(accent)
    for y in range(h):
        t = y / h
        d.line((0, y, w, y), fill=(int(20 + 40 * t), int(14 + 20 * t), int(40 + 60 * (1 - t))))
    d.ellipse((620, 120, 900, 400), fill=(255, 190, 120))
    for k in range(12):
        x = 40 + k * 82
        hh = 120 + (k * 37) % 180
        d.rectangle((x, h - hh, x + 60, h), fill=(12, 10, 22))
        for wy in range(h - hh + 12, h - 10, 22):
            if (wy + k) % 3:
                d.rectangle((x + 10, wy, x + 18, wy + 8), fill=acc)
    d.rectangle((0, h - 70, w, h), fill=(0, 0, 0))
    d.text((30, h - 56), "▶  NEON HAVEN – DOKUMENTATION   12:04 / 48:00", font=font(28, "mono"), fill=(220, 220, 230))
    return img


def sticker(size=512):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, size - 8, size - 8), fill=(14, 14, 22, 255), outline=(255, 43, 214, 255), width=18)
    d.ellipse((60, 60, size - 60, size - 60), outline=(0, 229, 255, 255), width=6)
    center_text(d, (size / 2, 170), "NEON HAVEN", font(58), (240, 240, 250))
    center_text(d, (size / 2, 256), "RACING", font(78), (0, 229, 255))
    center_text(d, (size / 2, 336), "CLUB", font(58), (240, 240, 250))
    center_text(d, (size / 2, 412), "EST. 2077", font(30, "mono"), (255, 43, 214))
    return img


def label(lines, bg=(30, 30, 36), fg=(240, 240, 245), size=(512, 256)):
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    n = len(lines)
    for i, (txt, fs) in enumerate(lines):
        center_text(d, (size[0] / 2, size[1] * (i + 0.5) / n), txt, font(fs), fg)
    return img


def dice(size=128):
    img = Image.new("RGB", (size, size), (245, 245, 240))
    d = ImageDraw.Draw(img)
    for (x, y) in ((32, 32), (96, 32), (64, 64), (32, 96), (96, 96)):
        d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=(200, 20, 60))
    return img


def secret():
    return label([("Wenn du das liest,", 34), ("schaust du nicht", 34), ("auf die Straße :)", 34)],
                 bg=(225, 222, 214), fg=(40, 40, 48))


def contact_shadow(body, wheels, res=0.02, margin=0.45):
    """Weicher Kontaktschatten (Alpha), von oben auf den Boden projiziert."""
    xs_all = np.abs(body.S[:, :, 0]).max()
    zmin, zmax = body.zr - margin, body.zf + margin
    xmax = xs_all + margin
    W = int(2 * xmax / res)
    H = int((zmax - zmin) / res)
    occ = np.zeros((H, W), dtype=np.float32)
    # Karosserie-Umriss (Unterkante), Höhe über Grund -> Unschärfe
    for k in range(body.K):
        z = body.zs[k]
        sec = body.S[k]
        low = sec[sec[:, 1] < body.params_at(z)["yt"]]
        if len(low) == 0:
            continue
        w = np.abs(low[:, 0]).max() - 0.02
        row = int((zmax - z) / res)
        c0 = int((xmax - w) / res)
        c1 = int((xmax + w) / res)
        if 0 <= row < H:
            occ[row, max(c0, 0):min(c1, W)] = 0.85
    img = Image.fromarray((occ * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
    a = np.asarray(img).astype(np.float32) / 255
    # Reifen-Aufstandsflächen dunkler
    spots = np.zeros_like(a)
    for (x, z, wdt) in wheels:
        r0 = int((zmax - z) / res)
        c0 = int((xmax + x) / res)
        hw = int(wdt / 2 / res)
        hl = int(0.12 / res)
        spots[max(r0 - hl, 0):r0 + hl, max(c0 - hw, 0):c0 + hw] = 1.0
    sp = Image.fromarray((spots * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    s_arr = np.asarray(sp).astype(np.float32) / 255
    alpha = np.clip(a * 0.72 + s_arr * 0.5, 0, 0.92)
    out = np.zeros((H, W, 4), dtype=np.uint8)
    out[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA"), (xmax, zmin, zmax)


def build_car_textures(car, vmax, rpm_max):
    pal = car["palette"]
    acc = pal["accent"]
    tex = {
        "Badge": embed(emblem(car["brand"]["mono"], acc, ring=car["brand"].get("ring", (225, 226, 230)))),
        "Wordmark": embed(wordmark(car["brand"]["word"])),
        "CenterCap": embed(emblem(car["brand"]["mono"], acc, size=256)),
        "CaliperLogo": embed(caliper_logo(car["brand"].get("caliper", car["brand"]["word"]))),
        "Plate": embed(plate(car["plate"]), "PNG"),
        "Number": embed(number(car["number"])),
        "Display_Center": embed(center_display(car["name"], acc), "JPEG", 90),
        "Sticker": embed(sticker()),
        "Secret": embed(secret(), "JPEG", 90),
        "Label": embed(label(car.get("deco_label", [("NEON", 80)])), "JPEG", 90),
        "Dice": embed(dice()),
    }
    if car["interior"].get("cluster", {}).get("type") == "analog":
        tex["Display_Cluster"] = embed(cluster_analog(acc, vmax, rpm_max), "JPEG", 90)
    else:
        tex["Display_Cluster"] = embed(cluster_digital(car["name"], acc, vmax), "JPEG", 90)
    if car["interior"].get("center", {}).get("type") == "retro":
        tex["Display_Center"] = embed(retro_display(acc), "JPEG", 90)
    if car["interior"].get("rear_screens"):
        tex["Display_Rear"] = embed(rear_display(acc), "JPEG", 88)
    if pal.get("insert") == "fabric":
        tex["fabric_check"] = embed(fabric_check(line=_hex(pal.get("fabric_line", "#b6ff00"))), "JPEG", 90)
    return tex
