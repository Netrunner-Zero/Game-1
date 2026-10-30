"""Prüft alle Autos aus models/cars.json gegen die Knoten-/Material-Konventionen,
die das Spiel (src/vehicles/Vehicle.js) erwartet, und misst das Leistungsbudget.

  python3 tools/car-generator/qa/check.py            # alle Autos
  python3 tools/car-generator/qa/check.py pulse      # ein Auto

Ausgabe: Fehler/Warnungen je Auto + Tabelle mit Dreiecken und Draw Calls je Detailstufe
(Standard-Tuning, so wie die Garage das Auto zeigt).
"""
import json
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MODELS = os.path.join(ROOT, "models")

DEFAULT_TUNING = {"spoiler": 0, "livery": 0, "exhaust": 1, "cage": 0, "engine": 0, "rim": 1, "neon": False}
LIGHT_KINDS = ("head", "tail", "brake", "indicator", "reverse")


def read_glb_json(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError("keine glTF-2.0-Binärdatei")
    clen, ctype = struct.unpack_from("<II", data, 12)
    if ctype != 0x4E4F534A:
        raise ValueError("erster Block ist kein JSON")
    js = json.loads(data[20:20 + clen].decode("utf-8"))
    return js, len(data)


def check_car(meta):
    path = os.path.join(MODELS, meta["file"])
    js, size = read_glb_json(path)
    nodes = js["nodes"]
    errors, warns = [], []
    ex = lambda n: n.get("extras", {}) or {}

    # Eltern-Zuordnung
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    roots = js["scenes"][js.get("scene", 0)]["nodes"]
    if len(roots) != 1:
        errors.append("Szene hat %d Wurzelknoten (erwartet 1 – carRoot)" % len(roots))
    car_root = roots[0]
    top = nodes[car_root].get("children", [])

    by_name = {n.get("name", ""): i for i, n in enumerate(nodes)}
    wheels = [i for i, n in enumerate(nodes) if "wheel" in ex(n)]
    calipers = [i for i, n in enumerate(nodes) if "caliper" in ex(n)]
    if len(wheels) != 4:
        errors.append("%d Räder statt 4" % len(wheels))
    if len(calipers) != 4:
        errors.append("%d Bremssättel statt 4" % len(calipers))
    for i in wheels + calipers:
        if parent.get(i) != car_root:
            errors.append("Rad/Sattel %s hängt nicht direkt am Auto (Tieferlegung!)" % nodes[i].get("name"))

    tune = {}
    for i, n in enumerate(nodes):
        t = ex(n).get("tune")
        if t:
            tune.setdefault(t, []).append(i)
    def variants(kind, key="variant"):
        return sorted({ex(nodes[i]).get(key) for i in tune.get(kind, [])})
    n_rims = len(meta.get("rims", []))
    exp = {"spoiler": [1, 2, 3], "livery": [1, 2, 3], "cage": [1, 2],
           "exhaust": list(range(1, len(meta["tuning"]["exhaust"]) + 1)),
           "rim": list(range(1, n_rims + 1))}
    for k, want in exp.items():
        got = variants(k)
        if got != want:
            errors.append("Tuning %s: Varianten %s, erwartet %s" % (k, got, want))
    stages = variants("engine", "stage")
    if stages != list(range(1, len(meta["tuning"]["engine"]))):
        errors.append("Motorstufen %s passen nicht zu %d Einträgen" % (stages, len(meta["tuning"]["engine"])))
    if len(tune.get("rim", [])) != 4 * n_rims:
        errors.append("%d Felgenknoten statt %d" % (len(tune.get("rim", [])), 4 * n_rims))
    if len(tune.get("neon", [])) != 1:
        errors.append("Unterbodenbeleuchtung fehlt")

    helpers = {ex(n).get("helper") for n in nodes if ex(n).get("helper")}
    for h in ("Cam_Cockpit", "Cam_Hood", "Seat_Driver"):
        if h not in helpers:
            errors.append("Hilfspunkt %s fehlt" % h)
    anims = [ex(n).get("anim") for n in nodes if ex(n).get("anim")]
    if anims.count("steering") != 1:
        errors.append("Lenkrad-Knoten fehlt")
    if anims.count("pedal") != 2:
        warns.append("%d Pedale" % anims.count("pedal"))
    if meta.get("gauges", {}).get("cluster") == "analog" and anims.count("needle") != 2:
        errors.append("analoge Instrumente ohne 2 Zeiger")
    if sum(1 for n in nodes if ex(n).get("shadow")) != 1:
        errors.append("Kontaktschatten fehlt")
    plates = {ex(n).get("plate") for n in nodes if ex(n).get("plate")}
    if plates != {"front", "rear"}:
        warns.append("Kennzeichen: %s" % sorted(plates))

    # LOD-Gruppen: Kinder mit lod 0..k, keine Lücken
    groups = {}
    for i, n in enumerate(nodes):
        if "lod" in ex(n) and i in parent:
            groups.setdefault(parent[i], []).append(ex(n)["lod"])
    for p, ks in groups.items():
        if sorted(ks) != list(range(max(ks) + 1)):
            errors.append("LOD-Gruppe %s hat Stufen %s" % (nodes[p].get("name"), sorted(ks)))

    # Materialien
    mats = js.get("materials", [])
    names = {m.get("name") for m in mats}
    for m in ("Paint", "Glass", "Rim", "Caliper", "Tire"):
        if m not in names:
            errors.append("Material %s fehlt" % m)
    if "Paint2" not in names:
        warns.append("kein Paint2 (Dach/Zweifarbig wird in der Garage ausgeblendet)")
    lights = {(m.get("extras") or {}).get("light") for m in mats if (m.get("extras") or {}).get("group") == "lights"}
    for k in LIGHT_KINDS:
        if k not in lights:
            errors.append("Lichtmaterial '%s' fehlt" % k)
    canvases = {(m.get("extras") or {}).get("canvas") for m in mats if (m.get("extras") or {}).get("canvas")}
    want_c = {"cluster", "center"} | ({"rear"} if meta.get("gauges", {}).get("rearScreens") else set())
    if not want_c <= canvases:
        errors.append("Display-Flächen %s, erwartet %s" % (sorted(canvases), sorted(want_c)))
    groups_m = {(m.get("extras") or {}).get("group") for m in mats}
    for g in ("interior", "display", "lights"):
        if g not in groups_m:
            errors.append("keine Materialien der Gruppe '%s' (Regler würden nichts tun)" % g)

    # Sichtbarkeit wie in der Garage (Standard-Tuning) und Budget je Detailstufe
    T = dict(DEFAULT_TUNING)
    T.update(meta.get("defaultTuning") or {})

    def tuned_visible(n):
        e = ex(n)
        t = e.get("tune")
        if t == "rim":
            return e.get("variant") == T["rim"]
        if t in ("spoiler", "livery", "exhaust", "cage"):
            return e.get("variant") == T[t]
        if t == "engine":
            return e.get("stage", 99) <= T["engine"]
        if t == "neon":
            return bool(T["neon"])
        return True

    stats = {}
    for level in (0, 1, 2):
        tris = calls = 0

        def walk(i, visible=True):
            nonlocal tris, calls
            n = nodes[i]
            if not tuned_visible(n):
                return
            e = ex(n)
            if "lod" in e and i in parent:
                ks = groups[parent[i]]
                mk = max(ks)
                ok = (level == 0) if mk == 0 else e["lod"] == min(level, mk)
                if not ok:
                    return
            if "mesh" in n:
                for pr in js["meshes"][n["mesh"]]["primitives"]:
                    acc = js["accessors"][pr["indices"]] if "indices" in pr else js["accessors"][pr["attributes"]["POSITION"]]
                    tris += acc["count"] // 3
                    calls += 1
            for c in n.get("children", []):
                walk(c)
        walk(car_root)
        stats[level] = (tris, calls)
    img_bytes = sum(js["bufferViews"][im["bufferView"]]["byteLength"] for im in js.get("images", []) if "bufferView" in im)
    return errors, warns, stats, size, img_bytes, len(mats)


def main():
    doc = json.load(open(os.path.join(MODELS, "cars.json"), encoding="utf-8"))
    want = sys.argv[1:]
    cars = [c for c in doc["cars"] if not want or any(w in c["id"] for w in want)]
    rows = []
    bad = 0
    for meta in cars:
        errors, warns, stats, size, img, nmat = check_car(meta)
        status = "OK" if not errors else "FEHLER"
        bad += bool(errors)
        print("== %s (%s): %s" % (meta["name"], meta["file"], status))
        for e in errors:
            print("   ✗", e)
        for w in warns:
            print("   !", w)
        rows.append((meta["name"], stats, size, img, nmat))
    print()
    print("%-13s %8s %6s %8s %6s %8s %6s %8s %8s %4s" % ("Auto", "L0 Dr.", "Calls", "L1 Dr.", "Calls", "L2 Dr.", "Calls",
                                                       "Datei", "Texturen", "Mat"))
    for name, st, size, img, nmat in rows:
        print("%-13s %8d %6d %8d %6d %8d %6d %7.2fM %7.2fM %4d" % (
            name, st[0][0], st[0][1], st[1][0], st[1][1], st[2][0], st[2][1], size / 1e6, img / 1e6, nmat))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
