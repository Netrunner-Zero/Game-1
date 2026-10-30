"""GLB-Writer.

- indizierte Meshes (Vertex-Deduplizierung, uint16/uint32)
- Materialien aus einer kompakten Beschreibung (siehe materials.py)
- Texturen extern (geteilt, models/textures/…) oder eingebettet
- Knoten mit Namen, Transformation, Kindern und extras
"""
import json
import struct

import numpy as np

REPEAT, CLAMP = 10497, 33071


def hex_to_linear(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def col(v):
    if isinstance(v, str):
        return hex_to_linear(v)
    return [float(x) for x in v]


class GLB:
    def __init__(self, generator="Neon Haven carcad"):
        self.json = {"asset": {"version": "2.0", "generator": generator},
                     "scenes": [{"nodes": []}], "scene": 0, "nodes": [], "meshes": [],
                     "materials": [], "accessors": [], "bufferViews": [], "buffers": [],
                     "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": REPEAT, "wrapT": REPEAT},
                                  {"magFilter": 9729, "minFilter": 9987, "wrapS": CLAMP, "wrapT": CLAMP}]}
        self.bin = bytearray()
        self.mat_index = {}
        self.mesh_cache = {}
        self.ext_used = set()
        self.tex_cache = {}
        self.image_cache = {}
        self.texlib = None
        self.stats = {"triangles": 0, "vertices": 0}

    # ------------------------------------------------------------------
    def _align(self):
        while len(self.bin) % 4:
            self.bin.append(0)

    def _view(self, data, target=None, stride=None):
        self._align()
        off = len(self.bin)
        self.bin.extend(data)
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            v["target"] = target
        if stride:
            v["byteStride"] = stride
        self.json["bufferViews"].append(v)
        return len(self.json["bufferViews"]) - 1

    # ------------------------------------------------------------------
    # Texturen
    # ------------------------------------------------------------------
    def _image(self, name):
        if name in self.image_cache:
            return self.image_cache[name]
        t = self.texlib[name]
        img = {"name": name}
        if t.get("external"):
            img["uri"] = "textures/" + t["file"]
            img["mimeType"] = t["mime"]
        else:
            img["bufferView"] = self._view(t["data"])
            img["mimeType"] = t["mime"]
        self.json.setdefault("images", []).append(img)
        idx = len(self.json["images"]) - 1
        self.image_cache[name] = idx
        return idx

    def _texture(self, name, clamp=False):
        key = (name, clamp)
        if key in self.tex_cache:
            return self.tex_cache[key]
        src = self._image(name)
        self.json.setdefault("textures", []).append({"sampler": 1 if clamp else 0, "source": src})
        idx = len(self.json["textures"]) - 1
        self.tex_cache[key] = idx
        return idx

    def _texinfo(self, ref, extra=None):
        """ref = (name, tile_m) oder (name, None) für 0..1-UVs (Decals)."""
        name, tile = ref[0], ref[1]
        info = {"index": self._texture(name, clamp=tile is None)}
        if tile:
            # Kachelgröße in Metern: Zahl (quadratisch) oder (Breite, Höhe)
            tu, tv = (tile, tile) if not isinstance(tile, (tuple, list)) else tile
            info["extensions"] = {"KHR_texture_transform": {"scale": [1.0 / tu, 1.0 / tv]}}
            self.ext_used.add("KHR_texture_transform")
        if extra:
            info.update(extra)
        return info

    # ------------------------------------------------------------------
    # Materialien
    # ------------------------------------------------------------------
    def add_material(self, name, s):
        m = {"name": name}
        pbr = {"baseColorFactor": col(s.get("color", [1, 1, 1])) + [float(s.get("alpha", 1.0))],
               "metallicFactor": float(s.get("metallic", 0.0)),
               "roughnessFactor": float(s.get("roughness", 0.5))}
        if "map" in s:
            pbr["baseColorTexture"] = self._texinfo(s["map"])
        if "orm" in s:
            pbr["metallicRoughnessTexture"] = self._texinfo(s["orm"])
        m["pbrMetallicRoughness"] = pbr
        if "normal" in s:
            ref = s["normal"]
            m["normalTexture"] = self._texinfo(ref[:2], {"scale": float(ref[2]) if len(ref) > 2 else 1.0})
        if "emissive" in s:
            m["emissiveFactor"] = col(s["emissive"])
            if "emissiveMap" in s:
                m["emissiveTexture"] = self._texinfo(s["emissiveMap"])
            st = s.get("emissiveStrength", 1.0)
            if st != 1.0:
                m.setdefault("extensions", {})["KHR_materials_emissive_strength"] = {"emissiveStrength": float(st)}
        if s.get("alphaMode"):
            m["alphaMode"] = s["alphaMode"]
            if s["alphaMode"] == "MASK":
                m["alphaCutoff"] = float(s.get("alphaCutoff", 0.5))
        if s.get("doubleSided"):
            m["doubleSided"] = True
        ext = m.setdefault("extensions", {})
        if "clearcoat" in s:
            f, r = s["clearcoat"]
            cc = {"clearcoatFactor": float(f), "clearcoatRoughnessFactor": float(r)}
            ext["KHR_materials_clearcoat"] = cc
        if "sheen" in s:
            c, r = s["sheen"]
            ext["KHR_materials_sheen"] = {"sheenColorFactor": col(c), "sheenRoughnessFactor": float(r)}
        if "iridescence" in s:
            f, ior, t0, t1 = s["iridescence"]
            ext["KHR_materials_iridescence"] = {"iridescenceFactor": float(f), "iridescenceIor": float(ior),
                                                "iridescenceThicknessMinimum": float(t0),
                                                "iridescenceThicknessMaximum": float(t1)}
        if "anisotropy" in s:
            st, rot = s["anisotropy"]
            ext["KHR_materials_anisotropy"] = {"anisotropyStrength": float(st), "anisotropyRotation": float(rot)}
        if "ior" in s:
            ext["KHR_materials_ior"] = {"ior": float(s["ior"])}
        if "specular" in s:
            ext["KHR_materials_specular"] = {"specularFactor": float(s["specular"])}
        if "transmission" in s:
            ext["KHR_materials_transmission"] = {"transmissionFactor": float(s["transmission"])}
        if s.get("unlit"):
            ext["KHR_materials_unlit"] = {}
        if not ext:
            m.pop("extensions")
        for e in m.get("extensions", {}):
            self.ext_used.add(e)
        if "extras" in s:
            m["extras"] = s["extras"]
        self.mat_index[name] = len(self.json["materials"])
        self.json["materials"].append(m)

    # ------------------------------------------------------------------
    # Meshes
    # ------------------------------------------------------------------
    def add_mesh(self, part):
        key = id(part)
        if key in self.mesh_cache:
            return self.mesh_cache[key]
        prims = []
        for mat in sorted(part.tris):
            tris = part.tris[mat]
            if not tris:
                continue
            if mat not in self.mat_index:
                raise KeyError("Material fehlt: %s (Teil %s)" % (mat, part.name))
            n = len(tris)
            P = np.empty((n * 3, 3), dtype=np.float64)
            N = np.empty((n * 3, 3), dtype=np.float64)
            U = np.empty((n * 3, 2), dtype=np.float64)
            for i, (a, b, c, ns, uv) in enumerate(tris):
                P[3 * i], P[3 * i + 1], P[3 * i + 2] = a, b, c
                N[3 * i], N[3 * i + 1], N[3 * i + 2] = ns[0], ns[1], ns[2]
                U[3 * i], U[3 * i + 1], U[3 * i + 2] = uv[0], uv[1], uv[2]
            ln = np.linalg.norm(N, axis=1, keepdims=True)
            N = N / np.maximum(ln, 1e-9)
            # Deduplizieren
            key_arr = np.hstack([np.round(P * 1e5), np.round(N * 127.0), np.round(U * 1e4)]).astype(np.int64)
            _, first, inv = np.unique(key_arr, axis=0, return_index=True, return_inverse=True)
            inv = inv.reshape(-1)
            Pu = P[first].astype(np.float32)
            Nu = N[first].astype(np.float32)
            Uu = U[first].astype(np.float32)
            idx = inv.astype(np.uint32)
            # degenerierte Dreiecke nach Dedup entfernen
            tri_idx = idx.reshape(-1, 3)
            ok = (tri_idx[:, 0] != tri_idx[:, 1]) & (tri_idx[:, 1] != tri_idx[:, 2]) & (tri_idx[:, 0] != tri_idx[:, 2])
            tri_idx = tri_idx[ok]
            if len(tri_idx) == 0:
                continue
            idx = tri_idx.reshape(-1)
            nv = len(Pu)
            pv = self._view(Pu.tobytes(), 34962)
            # Normalen als 8-Bit (KHR_mesh_quantization): 4 statt 12 Byte je Punkt
            Nq = np.zeros((nv, 4), dtype=np.int8)
            Nq[:, :3] = np.clip(np.round(Nu * 127.0), -127, 127).astype(np.int8)
            nvw = self._view(Nq.tobytes(), 34962, stride=4)
            self.ext_used.add("KHR_mesh_quantization")
            uvw = self._view(Uu.tobytes(), 34962)
            if nv < 65536:
                ib = idx.astype(np.uint16).tobytes()
                ctype = 5123
            else:
                ib = idx.astype(np.uint32).tobytes()
                ctype = 5125
            iv = self._view(ib, 34963)
            acc = self.json["accessors"]
            acc.append({"bufferView": pv, "componentType": 5126, "count": nv, "type": "VEC3",
                        "min": [float(x) for x in Pu.min(axis=0)], "max": [float(x) for x in Pu.max(axis=0)]})
            pa = len(acc) - 1
            acc.append({"bufferView": nvw, "componentType": 5120, "normalized": True, "count": nv, "type": "VEC3"})
            na = len(acc) - 1
            acc.append({"bufferView": uvw, "componentType": 5126, "count": nv, "type": "VEC2"})
            ua = len(acc) - 1
            acc.append({"bufferView": iv, "componentType": ctype, "count": len(idx), "type": "SCALAR"})
            ia = len(acc) - 1
            prims.append({"attributes": {"POSITION": pa, "NORMAL": na, "TEXCOORD_0": ua},
                          "indices": ia, "material": self.mat_index[mat], "mode": 4})
            self.stats["triangles"] += len(idx) // 3
            self.stats["vertices"] += nv
        if not prims:
            self.mesh_cache[key] = None
            return None
        self.json["meshes"].append({"name": part.name, "primitives": prims})
        mi = len(self.json["meshes"]) - 1
        self.mesh_cache[key] = mi
        return mi

    def add_node(self, name, mesh=None, translation=None, rotation=None, scale=None, children=None, extras=None):
        n = {"name": name}
        if mesh is not None:
            mi = self.add_mesh(mesh)
            if mi is not None:
                n["mesh"] = mi
        if translation is not None and any(abs(x) > 1e-9 for x in translation):
            n["translation"] = [float(x) for x in translation]
        if rotation is not None:
            n["rotation"] = [float(x) for x in rotation]
        if scale is not None:
            n["scale"] = [float(x) for x in scale]
        if children:
            n["children"] = list(children)
        if extras:
            n["extras"] = extras
        self.json["nodes"].append(n)
        return len(self.json["nodes"]) - 1

    def write(self, path, roots):
        self.json["scenes"][0]["nodes"] = list(roots)
        self._align()
        self.json["buffers"] = [{"byteLength": len(self.bin)}]
        if self.ext_used:
            self.json["extensionsUsed"] = sorted(self.ext_used)
        if "KHR_mesh_quantization" in self.ext_used:
            self.json["extensionsRequired"] = ["KHR_mesh_quantization"]
        if not self.json.get("textures"):
            self.json.pop("samplers", None)
        js = json.dumps(self.json, separators=(",", ":")).encode("utf-8")
        while len(js) % 4:
            js += b" "
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, "wb") as f:
            f.write(struct.pack("<III", 0x46546C67, 2, total))
            f.write(struct.pack("<II", len(js), 0x4E4F534A))
            f.write(js)
            f.write(struct.pack("<II", len(self.bin), 0x004E4942))
            f.write(bytes(self.bin))
        return total
