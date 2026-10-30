"""Software-Renderer für Kontrollbilder (ohne GPU).

Liest die erzeugten GLB-Dateien direkt (inkl. externer Texturen),
rastert mit Z-Buffer, perspektivisch korrekter Interpolation,
Near-Plane-Clipping (für Cockpit-Ansichten) und einfacher PBR-Näherung
(Lambert + Glanzlicht + Umgebungsreflexion mit Fresnel).

Nutzung:
  python3 qa/render.py out.png models/vektra_gt.glb --view front34 [--hide Spoiler_2,...]
"""
import argparse
import io
import json
import math
import os
import re
import struct
import sys

import numpy as np
from PIL import Image


# ----------------------------------------------------------------------
# GLB lesen
# ----------------------------------------------------------------------

def quat_to_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


DEFAULT_SET = {"Spoiler": 0, "Livery": 0, "Exhaust": 1, "Cage": 0, "Engine": 0, "Rim": 1, "Glow": 0}


class Scene:
    settings = None      # Tuning-Auswahl wie im Spiel (siehe DEFAULT_SET)
    lod_level = 0        # None = alle Knoten zeigen

    def __init__(self):
        self.batches = []   # dicts: P (n,3,3), N (n,3,3), UV (n,3,2), mat

    @staticmethod
    def load_glb(path, hide=(), show_only=None, extra_offset=None):
        data = open(path, "rb").read()
        magic, ver, total = struct.unpack_from("<III", data, 0)
        assert magic == 0x46546C67 and ver == 2 and total == len(data), "GLB-Header defekt"
        jl, jt = struct.unpack_from("<II", data, 12)
        js = json.loads(data[20:20 + jl])
        bl, bt = struct.unpack_from("<II", data, 20 + jl)
        binb = data[28 + jl:28 + jl + bl]
        base = os.path.dirname(path)
        images = {}

        def image(i):
            if i in images:
                return images[i]
            im = js["images"][i]
            if "uri" in im:
                raw = open(os.path.join(base, im["uri"]), "rb").read()
            else:
                bv = js["bufferViews"][im["bufferView"]]
                raw = binb[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
            img = Image.open(io.BytesIO(raw)).convert("RGBA")
            arr = np.asarray(img).astype(np.float32) / 255.0
            images[i] = arr
            return arr

        def acc(i):
            a = js["accessors"][i]
            bv = js["bufferViews"][a["bufferView"]]
            comp = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8, 5120: np.int8,
                    5122: np.int16}[a["componentType"]]
            ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
            off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
            stride = bv.get("byteStride")
            isz = np.dtype(comp).itemsize
            if stride and stride != ncomp * isz:
                raw = np.frombuffer(binb, dtype=comp, count=a["count"] * stride // isz, offset=off)
                arr = raw.reshape(a["count"], stride // isz)[:, :ncomp].reshape(-1)
            else:
                arr = np.frombuffer(binb, dtype=comp, count=a["count"] * ncomp, offset=off)
            if a.get("normalized"):
                arr = arr.astype(np.float32) / {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}[a["componentType"]]
            return arr.reshape(-1, ncomp) if ncomp > 1 else arr

        mats = []
        for m in js.get("materials", []):
            pbr = m.get("pbrMetallicRoughness", {})
            bc = pbr.get("baseColorFactor", [1, 1, 1, 1])
            ext = m.get("extensions", {})
            md = {"name": m.get("name", ""), "color": np.array(bc[:3], dtype=np.float32), "alpha": bc[3],
                  "metallic": pbr.get("metallicFactor", 1.0), "roughness": pbr.get("roughnessFactor", 1.0),
                  "emissive": np.array(m.get("emissiveFactor", [0, 0, 0]), dtype=np.float32)
                  * ext.get("KHR_materials_emissive_strength", {}).get("emissiveStrength", 1.0),
                  "blend": m.get("alphaMode") == "BLEND", "mask": m.get("alphaMode") == "MASK",
                  "double": m.get("doubleSided", False), "tex": None, "tex_scale": 1.0,
                  "emis_tex": None, "clearcoat": ext.get("KHR_materials_clearcoat", {}).get("clearcoatFactor", 0.0)}
            if "baseColorTexture" in pbr:
                ti = pbr["baseColorTexture"]
                md["tex"] = image(js["textures"][ti["index"]]["source"])
                tr = ti.get("extensions", {}).get("KHR_texture_transform", {})
                md["tex_scale"] = np.array(tr.get("scale", [1, 1]), dtype=np.float64)
            md["emis_scale"] = 1.0
            if "emissiveTexture" in m:
                md["emis_tex"] = image(js["textures"][m["emissiveTexture"]["index"]]["source"])
                tr = m["emissiveTexture"].get("extensions", {}).get("KHR_texture_transform", {})
                md["emis_scale"] = np.array(tr.get("scale", [1, 1]), dtype=np.float64)
            mats.append(md)

        scene = Scene()
        sel = dict(DEFAULT_SET)
        sel.update(Scene.settings or {})
        lod_level = Scene.lod_level

        def tuned_visible(name):
            m = re.match(r"^(Spoiler|Livery|Exhaust|RollCage|EngineStage)_(\d+)$", name)
            if m:
                key = {"RollCage": "Cage", "EngineStage": "Engine"}.get(m.group(1), m.group(1))
                n = int(m.group(2))
                return n <= sel[key] if key == "Engine" else n == sel[key]
            m = re.match(r"^Rim_(\d+)_(FL|FR|RL|RR)$", name)
            if m:
                return int(m.group(1)) == sel["Rim"]
            if name == "Underglow":
                return bool(sel["Glow"])
            return True

        def lod_visible(name, siblings):
            m = re.match(r"^(.*)_L(\d)$", name)
            if not m or lod_level is None:
                return True
            base, k = m.group(1), int(m.group(2))
            ks = [int(mm.group(2)) for mm in (re.match(r"^(.*)_L(\d)$", s) for s in siblings) if mm and mm.group(1) == base]
            kmax = max(ks)
            if kmax == 0:
                return lod_level == 0 and k == 0
            return k == min(lod_level, kmax)

        def walk(ni, M, t, hidden, siblings=()):
            node = js["nodes"][ni]
            name = node.get("name", "")
            if any(name == h or name.startswith(h) for h in hide):
                return
            if not tuned_visible(name) or not lod_visible(name, siblings):
                return
            R = quat_to_mat(node["rotation"]) if "rotation" in node else np.eye(3)
            S = np.diag(node.get("scale", [1, 1, 1]))
            Tn = np.array(node.get("translation", [0, 0, 0]), dtype=float)
            M2 = M @ R @ S
            t2 = M @ Tn + t
            if "mesh" in node:
                for pr in js["meshes"][node["mesh"]]["primitives"]:
                    P = acc(pr["attributes"]["POSITION"]).astype(np.float64)
                    Nn = acc(pr["attributes"]["NORMAL"]).astype(np.float64)
                    UV = acc(pr["attributes"]["TEXCOORD_0"]).astype(np.float64) if "TEXCOORD_0" in pr["attributes"] else np.zeros((len(P), 2))
                    I = acc(pr["indices"]).astype(np.int64) if "indices" in pr else np.arange(len(P))
                    Pw = P @ M2.T + t2
                    Ninv = np.linalg.inv(M2).T
                    Nw = Nn @ Ninv.T
                    Nw /= np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-9)
                    tri = I.reshape(-1, 3)
                    scene.batches.append({"P": Pw[tri], "N": Nw[tri], "UV": UV[tri], "mat": mats[pr["material"]],
                                          "node": name})
            kids = node.get("children", [])
            names = [js["nodes"][c].get("name", "") for c in kids]
            for c in kids:
                walk(c, M2, t2, hidden, names)

        for r in js["scenes"][js.get("scene", 0)]["nodes"]:
            walk(r, np.eye(3), np.zeros(3) if extra_offset is None else np.asarray(extra_offset), False)
        if show_only:
            scene.batches = [b for b in scene.batches if any(b["node"].startswith(s) for s in show_only)]
        scene.json = js
        return scene


# ----------------------------------------------------------------------
# Rasterizer
# ----------------------------------------------------------------------

def look_at(eye, target, up=(0, 1, 0)):
    eye = np.asarray(eye, dtype=float)
    f = np.asarray(target, dtype=float) - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    V = np.eye(4)
    V[0, :3], V[1, :3], V[2, :3] = r, u, -f
    V[:3, 3] = -V[:3, :3] @ eye
    return V


def env_color(d, mode="studio"):
    """Einfache Umgebung für Reflexionen: Studio mit Softboxen oben/seitlich."""
    y = d[..., 1]
    if mode == "night":
        base = np.stack([0.03 + 0.04 * np.clip(y, 0, 1), 0.035 + 0.04 * np.clip(y, 0, 1), 0.06 + 0.08 * np.clip(y, 0, 1)], -1)
        neon = np.clip(1 - np.abs(y - 0.15) * 8, 0, 1)[..., None] * np.array([0.9, 0.2, 0.8]) * (d[..., 0] > 0)[..., None]
        neon2 = np.clip(1 - np.abs(y - 0.25) * 8, 0, 1)[..., None] * np.array([0.1, 0.8, 1.0]) * (d[..., 0] <= 0)[..., None]
        return base + neon * 0.8 + neon2 * 0.8
    sky = np.stack([0.32 + 0.45 * np.clip(y, 0, 1), 0.34 + 0.47 * np.clip(y, 0, 1), 0.38 + 0.52 * np.clip(y, 0, 1)], -1)
    ground = np.stack([0.06 + 0 * y, 0.06 + 0 * y, 0.07 + 0 * y], -1)
    c = np.where((y > 0)[..., None], sky, ground)
    # Softbox-Streifen oben (lange Lichtkanten im Lack)
    strip = np.clip(1 - np.abs(d[..., 2]) * 3.2, 0, 1) * np.clip((y - 0.55) * 5, 0, 1)
    c = c + strip[..., None] * 2.2
    side = np.clip(1 - np.abs(y - 0.25) * 6, 0, 1) * np.clip(np.abs(d[..., 0]) * 1.6 - 0.9, 0, 1)
    c = c + side[..., None] * 1.0
    return c


class Renderer:
    def __init__(self, w=1200, h=760, ss=2, env="studio", bg=(0.11, 0.12, 0.15)):
        self.W, self.H, self.ss = w * ss, h * ss, ss
        self.env = env
        self.bg = np.array(bg, dtype=np.float32)

    def render(self, scene, eye, target, fov=35.0, near=0.02, light_dir=(0.45, 0.8, 0.35), exposure=1.0):
        W, H = self.W, self.H
        color = np.tile(self.bg, (H, W, 1)).astype(np.float32)
        # Hintergrundverlauf
        yy = np.linspace(1, 0, H)[:, None, None]
        color = color * (0.75 + 0.5 * yy)
        depth = np.full((H, W), np.inf, dtype=np.float32)
        V = look_at(eye, target)
        f = 1.0 / math.tan(math.radians(fov) / 2)
        aspect = W / H
        L = np.asarray(light_dir, dtype=float)
        L /= np.linalg.norm(L)
        eye = np.asarray(eye, dtype=float)
        opaque, trans = [], []
        for b in scene.batches:
            (trans if b["mat"]["blend"] else opaque).append(b)
        self._draw(opaque, V, f, aspect, near, color, depth, L, eye, blend=False)
        # transparente Flächen von hinten nach vorne
        tris = []
        for b in trans:
            P = b["P"]
            Pc = P @ V[:3, :3].T + V[:3, 3]
            d = Pc[:, :, 2].mean(axis=1)
            for i in range(len(P)):
                tris.append((d[i], b, i))
        tris.sort(key=lambda x: x[0])
        if tris:
            # gruppiert zeichnen (Reihenfolge beibehalten)
            for d, b, i in tris:
                sub = {"P": b["P"][i:i + 1], "N": b["N"][i:i + 1], "UV": b["UV"][i:i + 1], "mat": b["mat"]}
                self._draw([sub], V, f, aspect, near, color, depth, L, eye, blend=True)
        img = lin_to_srgb(self._tonemap(color * exposure))
        im = Image.fromarray((img * 255).astype(np.uint8))
        if self.ss > 1:
            im = im.resize((W // self.ss, H // self.ss), Image.LANCZOS)
        return im

    @staticmethod
    def _tonemap(c):
        # ACES-Näherung (Narkowicz)
        a, b, cc, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
        return np.clip((c * (a * c + b)) / (c * (cc * c + d) + e), 0, 1)

    def _draw(self, batches, V, f, aspect, near, color, depth, L, eye, blend):
        W, H = self.W, self.H
        for b in batches:
            mat = b["mat"]
            P = b["P"]
            if len(P) == 0:
                continue
            Pc = P @ V[:3, :3].T + V[:3, 3]           # Kameraraum (Blick entlang -z)
            Nw = b["N"]
            UV = b["UV"]
            for i in range(len(P)):
                pc = Pc[i]
                zc = -pc[:, 2]
                if np.all(zc < near):
                    continue
                if np.any(zc < near):
                    polys = clip_near(pc, Nw[i], UV[i], P[i], near)
                else:
                    polys = [(pc, Nw[i], UV[i], P[i])]
                for (pcs, ns, uvs, pws) in polys:
                    self._raster(pcs, ns, uvs, pws, mat, f, aspect, color, depth, L, eye, blend)

    def _raster(self, pc, ns, uvs, pws, mat, f, aspect, color, depth, L, eye, blend):
        W, H = self.W, self.H
        zc = -pc[:, 2]
        sx = (pc[:, 0] * f / aspect / zc * 0.5 + 0.5) * W
        sy = (0.5 - pc[:, 1] * f / zc * 0.5) * H
        # Rückseiten
        area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if abs(area) < 1e-9:
            return
        backface = area > 0  # (y nach unten) -> gegen den Uhrzeigersinn im Bild = Vorderseite hat area < 0
        if backface and not mat["double"]:
            return
        x0, x1 = int(max(0, math.floor(sx.min()))), int(min(W - 1, math.ceil(sx.max())))
        y0, y1 = int(max(0, math.floor(sy.min()))), int(min(H - 1, math.ceil(sy.max())))
        if x0 > x1 or y0 > y1:
            return
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = np.arange(y0, y1 + 1) + 0.5
        X, Y = np.meshgrid(xs, ys)
        w0 = (sx[1] - X) * (sy[2] - Y) - (sx[2] - X) * (sy[1] - Y)
        w1 = (sx[2] - X) * (sy[0] - Y) - (sx[0] - X) * (sy[2] - Y)
        w2 = (sx[0] - X) * (sy[1] - Y) - (sx[1] - X) * (sy[0] - Y)
        if area > 0:
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        else:
            inside = (w0 <= 0) & (w1 <= 0) & (w2 <= 0)
        if not inside.any():
            return
        w0, w1, w2 = w0 / area, w1 / area, w2 / area
        # perspektivisch korrekt
        iz = np.array([1 / zc[0], 1 / zc[1], 1 / zc[2]])
        denom = w0 * iz[0] + w1 * iz[1] + w2 * iz[2]
        zpix = 1.0 / denom
        b0, b1, b2 = w0 * iz[0] * zpix, w1 * iz[1] * zpix, w2 * iz[2] * zpix
        sub = depth[y0:y1 + 1, x0:x1 + 1]
        test = inside & (zpix < sub - 1e-5)
        if not test.any():
            return
        bb0, bb1, bb2 = b0[test], b1[test], b2[test]
        n = bb0[:, None] * ns[0] + bb1[:, None] * ns[1] + bb2[:, None] * ns[2]
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        pw = bb0[:, None] * pws[0] + bb1[:, None] * pws[1] + bb2[:, None] * pws[2]
        vdir = eye - pw
        vdir /= np.maximum(np.linalg.norm(vdir, axis=1, keepdims=True), 1e-9)
        if backface:
            n = -n
        flipmask = np.sum(n * vdir, axis=1) < 0
        n[flipmask] = -n[flipmask]
        base = mat["color"].astype(np.float32)
        alpha = np.full(len(bb0), mat["alpha"], dtype=np.float32)
        albedo = np.tile(base, (len(bb0), 1))
        if mat["tex"] is not None:
            uv = bb0[:, None] * uvs[0] + bb1[:, None] * uvs[1] + bb2[:, None] * uvs[2]
            uv = uv * mat["tex_scale"]
            tex = mat["tex"]
            th, tw = tex.shape[0], tex.shape[1]
            tu = (np.mod(uv[:, 0], 1.0) * tw).astype(int).clip(0, tw - 1)
            tv = (np.mod(uv[:, 1], 1.0) * th).astype(int).clip(0, th - 1)
            texel = tex[tv, tu]
            albedo = albedo * srgb_to_lin(texel[:, :3])
            alpha = alpha * texel[:, 3]
        if mat["mask"]:
            keep = alpha >= 0.5
            if not keep.any():
                return
            idx = np.where(test)
            test2 = np.zeros_like(test)
            test2[idx[0][keep], idx[1][keep]] = True
            test = test2
            n, pw, vdir, albedo, alpha = n[keep], pw[keep], vdir[keep], albedo[keep], alpha[keep]
            bb0, bb1, bb2 = bb0[keep], bb1[keep], bb2[keep]
        emis = np.tile(mat["emissive"], (len(n), 1))
        if mat["emis_tex"] is not None:
            uv = bb0[:, None] * uvs[0] + bb1[:, None] * uvs[1] + bb2[:, None] * uvs[2]
            uv = uv * mat["emis_scale"]
            tex = mat["emis_tex"]
            th, tw = tex.shape[0], tex.shape[1]
            tu = (np.mod(uv[:, 0], 1.0) * tw).astype(int).clip(0, tw - 1)
            tv = (np.mod(uv[:, 1], 1.0) * th).astype(int).clip(0, th - 1)
            emis = emis * srgb_to_lin(tex[tv, tu][:, :3])
        met = mat["metallic"]
        rough = max(mat["roughness"], 0.04)
        ndl = np.clip(n @ L, 0, 1)
        hemi = 0.5 + 0.5 * n[:, 1]
        diffuse = albedo * (1 - met) * (ndl[:, None] * 1.6 + (0.18 + 0.32 * hemi)[:, None])
        # Reflexion
        r = 2 * np.sum(n * vdir, axis=1, keepdims=True) * n - vdir
        envc = env_color(r, self.env)
        rough_blur = np.clip(rough * 1.6, 0, 1)
        envc = envc * (1 - rough_blur) + 0.35 * rough_blur
        cosv = np.clip(np.sum(n * vdir, axis=1), 0, 1)
        F0 = 0.04 * (1 - met) + albedo * met
        F = F0 + (1 - F0) * ((1 - cosv) ** 5)[:, None]
        spec_env = envc * F * (1 - 0.6 * rough)
        h = L[None, :] + vdir
        h /= np.maximum(np.linalg.norm(h, axis=1, keepdims=True), 1e-9)
        shin = 2.0 / max(rough ** 4, 1e-4)
        spec = (np.clip(np.sum(n * h, axis=1), 0, 1) ** min(shin, 4000.0)) * (shin + 2) / 8 * ndl
        spec_c = spec[:, None] * F * 0.9
        cc = mat["clearcoat"]
        if cc > 0:
            Fc = 0.04 + 0.96 * (1 - cosv) ** 5
            spec_env = spec_env + envc * Fc[:, None] * cc * 0.8
        out = diffuse + spec_env + spec_c + emis
        Ys, Xs = np.where(test)
        Ys = Ys + int(math.floor(ys[0] - 0.5))
        Xs = Xs + int(math.floor(xs[0] - 0.5))
        if blend:
            a = alpha[:, None]
            color[Ys, Xs] = color[Ys, Xs] * (1 - a) + out * a + spec_env * (1 - a) * 0.0
        else:
            color[Ys, Xs] = out
            depth[Ys, Xs] = zpix[test]


def clip_near(pc, ns, uvs, pws, near):
    """Sutherland-Hodgman gegen die Near-Plane; liefert Dreiecke."""
    verts = [(pc[i], ns[i], uvs[i], pws[i]) for i in range(3)]
    out = []
    for i in range(3):
        a, b = verts[i], verts[(i + 1) % 3]
        za, zb = -a[0][2], -b[0][2]
        ina, inb = za >= near, zb >= near
        if ina:
            out.append(a)
        if ina != inb:
            t = (near - za) / (zb - za)
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(4)))
    res = []
    for i in range(1, len(out) - 1):
        tri = [out[0], out[i], out[i + 1]]
        res.append((np.array([v[0] for v in tri]), np.array([v[1] for v in tri]),
                    np.array([v[2] for v in tri]), np.array([v[3] for v in tri])))
    return res


VIEWS = {
    # hl = halbe Länge, H = Höhe
    "front34": lambda hl, H: ((hl * 1.55 + 1.2, H * 0.75 + 0.55, hl * 1.9 + 1.4), (0, H * 0.42, 0.15), 30),
    "rear34": lambda hl, H: ((-hl * 1.55 - 1.2, H * 0.8 + 0.6, -hl * 1.9 - 1.4), (0, H * 0.42, -0.15), 30),
    "side": lambda hl, H: ((hl * 2.6 + 2.4, H * 0.5, 0.0), (0, H * 0.45, 0.0), 28),
    "front": lambda hl, H: ((0.0, H * 0.62 + 0.1, hl * 2.4 + 2.2), (0, H * 0.45, 0.0), 28),
    "rear": lambda hl, H: ((0.0, H * 0.7 + 0.15, -hl * 2.4 - 2.2), (0, H * 0.45, 0.0), 28),
    "top": lambda hl, H: ((0.001, hl * 3.2 + 2.0, 0.0), (0, 0, 0.0), 36),
    "low": lambda hl, H: ((hl * 0.9 + 0.8, 0.28, hl * 1.0 + 0.9), (0, H * 0.3, 0.0), 38),
    "wheel": lambda hl, H: ((hl * 0.45 + 1.4, 0.45, hl * 0.62 + 0.25), (0.7, 0.35, hl * 0.6), 30),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("glb")
    ap.add_argument("--view", default="front34")
    ap.add_argument("--hide", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--eye", default="")
    ap.add_argument("--target", default="")
    ap.add_argument("--fov", type=float, default=0)
    ap.add_argument("--w", type=int, default=1100)
    ap.add_argument("--h", type=int, default=700)
    ap.add_argument("--ss", type=int, default=2)
    ap.add_argument("--env", default="studio")
    ap.add_argument("--exposure", type=float, default=1.0)
    ap.add_argument("--lod", type=int, default=0, help="Detailstufe 0..2, -1 = alle Knoten")
    ap.add_argument("--set", default="", help="Tuning, z. B. Spoiler=2,Rim=3,Exhaust=2,Cage=1,Engine=3,Glow=1")
    a = ap.parse_args()
    Scene.lod_level = None if a.lod < 0 else a.lod
    Scene.settings = {k: int(v) for k, v in (kv.split("=") for kv in a.set.split(",") if kv)}
    hide = [h for h in a.hide.split(",") if h]
    only = [h for h in a.only.split(",") if h] or None
    sc = Scene.load_glb(a.glb, hide=hide, show_only=only)
    allP = np.concatenate([b["P"].reshape(-1, 3) for b in sc.batches])
    L = (allP[:, 2].max() - allP[:, 2].min()) / 2
    Hh = allP[:, 1].max()
    if a.eye:
        eye = [float(x) for x in a.eye.split(",")]
        tgt = [float(x) for x in a.target.split(",")]
        fov = a.fov or 60
    else:
        eye, tgt, fov = VIEWS[a.view](L, Hh)
        if a.fov:
            fov = a.fov
    r = Renderer(a.w, a.h, a.ss, env=a.env)
    img = r.render(sc, eye, tgt, fov=fov, exposure=a.exposure)
    img.save(a.out)
    print("gerendert:", a.out, sum(len(b["P"]) for b in sc.batches), "Dreiecke")


if __name__ == "__main__":
    main()
