"""Baut ein Auto komplett (alle LOD-Stufen, Räder, Tuning-Teile) und schreibt die GLB.

Knotenstruktur (Namen sind die Schnittstelle zum Spiel, siehe models/README.md):

  <Auto>                       Wurzel, extras = Kenndaten
    Body                       Karosserie
      Body_L0 / _L1 / _L2      Detailstufen
    Cockpit
      Cockpit_L0               Innenraum + bewegliche Teile (Lenkrad, Nadeln, Pedale) + Deko
      Cockpit_L1               vereinfachter Innenraum
      Cockpit_L2               leer (Kabine geschlossen)
    Wheel_FL …                 Rad (Drehung um X = Rollen, um Y = Lenken)
      Tire_FL_L0/_L1, Brake_FL_L0, Rim_<n>_FL (Felgenwahl) -> _L0/_L1
    Caliper_FL …               Bremssattel (lenkt mit, dreht nicht)
    Spoiler_<n>, Livery_<n>, Exhaust_<n>, RollCage_<n>, EngineStage_<n>  Tuning
    Plate_Front / Plate_Rear, Underglow, ContactShadow
    Cam_Cockpit, Cam_Hood, Seat_Driver   Hilfspunkte

LOD-Regel: Ein Knoten mit Endung _L<k> ist sichtbar, wenn k = min(Stufe, höchste Stufe
seiner Geschwister-Gruppe). Gibt es nur _L0, ist er nur in Stufe 0 sichtbar.
"""
import copy
import math
import os
import time

import numpy as np

from .body import Body
from .mesh import Part, smooth_part
from .gltf import GLB
from .raycast import Raycaster
from .parts import Ctx, underbody, plate_holder_local, place_flat
from .interior import Cockpit
from . import wheels as WH
from . import tuning as TU
from . import cartex
from .materials import library
from .textures import embed

LODS = (0, 1, 2)
NO_SMOOTH = {"Glass", "LampGlass", "TailGlass", "SmokeGlass", "Plate", "Badge", "Wordmark", "Number", "Livery",
             "Display_Cluster", "Display_Center", "Display_Rear", "Sticker", "Secret", "Label", "Dice", "Gap"}


# ----------------------------------------------------------------------
# Karosserie je Detailstufe
# ----------------------------------------------------------------------

def resolve_cabin(spec, body):
    for c in spec["cabin"]:
        if c["y1"] <= 0:
            c["y1"] = body._y1abs(c)


def skin_material_fn(spec, body, lod):
    custom = spec.get("skin_mat")
    tt = spec.get("two_tone")
    zo0, zo1 = body.cabin_open_range()

    def fn(j, c):
        if custom is not None:
            m = custom(j, c, lod, body)
            if m is not False:          # None = Fläche ausschneiden, Name = Material
                return m
        if lod == 2 and body.j_cut_r <= j < body.j_cut_l and zo0 < c[2] < zo1:
            return "InteriorPlastic"    # geschlossene Kabine in großer Entfernung
        if tt:
            y_line = tt["y"] if "y" in tt else body.params_at(c[2])["yt"] - tt.get("below_belt", 0.08)
            if c[1] > y_line:
                return "Paint2"
        return "Paint"
    return fn


def build_lod(spec, lod):
    sp = copy.deepcopy(spec)
    body = Body(sp, lod)
    resolve_cabin(sp, body)
    mat_fn = skin_material_fn(sp, body, lod)
    skin = body.build_skin(mat_fn=mat_fn, open_cabin=(lod < 2))
    arches = body.wheel_arches(lip_mat=sp.get("arch_mat", "Paint"), liner_mat="Liner", flare=sp.get("flare"))
    glass = body.glasshouse(glass="Glass", roof=sp.get("roof_mat", "Paint2"), pillar=sp.get("pillar_mat", "Paint2"),
                            bpillar=sp.get("bpillar_mat", "BlackGloss"), seal="Seal",
                            belt="BeltTrim" if lod < 2 else None, glass_roof=sp.get("glass_roof_mat"))
    ctx = Ctx(sp, lod, body, Raycaster([skin]))
    if "details" in sp:
        sp["details"](ctx)
    if ctx.cuts:
        # zweiter Durchgang: Haut mit exakten Öffnungen für Lampen, Grills, Einlässe
        skin = body.build_skin(mat_fn=mat_fn, open_cabin=(lod < 2), cuts=ctx.cuts)
    main = Part("Body")
    main.merge(skin).merge(arches).merge(glass)
    if lod == 0:
        body.gap_lines(main, sp.get("gaps", {}))
    underbody(main, body)
    if "Body" in ctx.parts:
        main.merge(ctx.parts["Body"])
    ctx.parts["Body"] = main
    return sp, body, ctx


def merged_body(ctx, name):
    out = Part(name)
    for nm, prt in ctx.parts.items():
        if nm != "Body":
            mats = set(prt.tris) - NO_SMOOTH
            smooth_part(prt, 38.0, mats=mats)
        out.merge(prt)
    return out


def default_plates(ctx):
    """Kennzeichen vorne/hinten (flach, bündig zur Karosserie)."""
    pp = ctx.spec.get("plate_pos", {})
    out = []
    for name, front in (("Plate_Front", True), ("Plate_Rear", False)):
        y = pp.get("front" if front else "rear")
        p = Part(name)
        if y is not None:
            hit = ctx.hit_front(0.0, y) if front else ctx.hit_rear(0.0, y)
            if hit is not None:
                axis = np.array([0, 0, 1.0 if front else -1.0])
                n = hit[1] * 0.25 + axis * 0.75
                tilt = pp.get("tilt_front" if front else "tilt_rear")
                if tilt is not None:
                    n = np.array([0.0, math.sin(math.radians(tilt)), axis[2] * math.cos(math.radians(tilt))])
                # *_out: Kennzeichen sitzt vor der Haut (z. B. auf einem dicken Stoßfänger)
                lift = 0.004 + pp.get("front_out" if front else "rear_out", 0.0)
                place_flat(ctx, plate_holder_local(ctx.lod), hit[0], n, (0.54, 0.13), p, lift=lift)
        out.append(p)
    return out


# ----------------------------------------------------------------------
# Räder
# ----------------------------------------------------------------------

def wheel_parts(spec, axle, side, lod):
    wd = spec["wheels"][axle]
    R, W = wd["R"], wd["W"]
    Rr = R * spec.get("rim_ratio", 0.68)
    out = {"tire": WH.tire(R, W, Rr, side, lod, spec.get("tire", "sport"))}
    out["rims"] = [WH.rim(R, W, Rr, side, d, lod, nuts=spec.get("nuts", 5)) for d in spec["rims"]]
    for rp in out["rims"]:
        smooth_part(rp, 40.0, mats={"Rim", "RimDark"})
    if lod == 0:
        d0 = spec["rims"][0]
        size = spec.get("caliper_size", 1.0) * (1.0 if axle == "front" else 0.85)
        out["brake"] = WH.brake_disc(R, W, Rr, side, d0, 0)
        out["caliper"] = WH.caliper(R, W, Rr, side, d0, 0, angle_deg=spec.get("caliper_angle", 125.0), size=size)
    return out


def wheel_x(spec, body, axle):
    wd = spec["wheels"][axle]
    return body.params_at(wd["z"])["w"] + wd.get("out", spec.get("wheel_out", -0.012)) - wd["W"] / 2


# ----------------------------------------------------------------------
# Auto bauen
# ----------------------------------------------------------------------

def build_car(spec, out_dir, shared_tex, log=print):
    t0 = time.time()
    name = spec["id"]
    lods = {}
    for lod in LODS:
        lods[lod] = build_lod(spec, lod)
    sp0, body0, ctx0 = lods[0]
    bodies = {lod: merged_body(lods[lod][2], "Body_L%d" % lod) for lod in LODS}
    log("  Karosserie: " + ", ".join("L%d %d" % (k, bodies[k].count()) for k in LODS) +
        " Dreiecke (%.0fs)" % (time.time() - t0))

    # ---------------- Innenraum ----------------
    ck = Cockpit(ctx0).build()
    deco = sp0["deco"](ck) if "deco" in sp0 else None
    smooth_part(ck.part, 40.0, mats=set(ck.part.tris) - NO_SMOOTH)
    for nn, (prt, _t, _q) in ck.nodes.items():
        smooth_part(prt, 40.0, mats=set(prt.tris) - NO_SMOOTH)
    if deco is not None:
        smooth_part(deco, 45.0, mats=set(deco.tris) - NO_SMOOTH)
    interior_l1 = ck.lod1(lods[1][1])
    cages = [ck.cage(1), ck.cage(2)]
    for c in cages:
        smooth_part(c, 40.0, mats={"Cage"})
    log("  Innenraum: %d Dreiecke (%.0fs)" % (ck.part.count() + sum(p[0].count() for p in ck.nodes.values()),
                                          time.time() - t0))

    # ---------------- Tuning ----------------
    spoilers = {lod: TU.spoilers(lods[lod][2]) for lod in (0, 1)}
    liveries = {lod: TU.liveries(lods[lod][2]) for lod in LODS}
    exhausts = {lod: TU.exhausts(lods[lod][2]) for lod in (0, 1)}
    engine = {lod: sp0["engine"](lods[lod][2]) for lod in (0, 1)} if "engine" in sp0 else {0: {}, 1: {}}
    plates = {lod: (sp0["plates"] if "plates" in sp0 else default_plates)(lods[lod][2]) for lod in LODS}
    # ungefederte Teile (Starrachsen): bleiben beim Tieferlegen auf Radhöhe
    unsprung = {lod: sp0["unsprung"](lods[lod][2]) for lod in (0, 1)} if "unsprung" in sp0 else None
    if unsprung:
        for prt in unsprung.values():
            smooth_part(prt, 40.0, mats=set(prt.tris) - NO_SMOOTH)
    glow = TU.underglow(ctx0)
    for dct in (spoilers, exhausts):
        for lst in dct.values():
            for prt in lst:
                smooth_part(prt, 38.0, mats=set(prt.tris) - NO_SMOOTH)
    for dct in engine.values():
        for prt in dct.values():
            smooth_part(prt, 38.0, mats=set(prt.tris) - NO_SMOOTH)
    log("  Tuning-Teile fertig (%.0fs)" % (time.time() - t0))

    # ---------------- Texturen ----------------
    st = spec["stats"]
    vmax = spec.get("gauge_vmax") or (400 if st["topSpeedKmh"] > 330 else 340 if st["topSpeedKmh"] > 280
                                      else 280 if st["topSpeedKmh"] > 240 else 260)
    rpm_max = spec.get("rpm_max", 9)
    car_tex = cartex.build_car_textures(spec, vmax, rpm_max)
    wheel_xz = []
    for axle in ("front", "rear"):
        wd = spec["wheels"][axle]
        for side in (1, -1):
            wheel_xz.append((side * wheel_x(spec, body0, axle), wd["z"], wd["W"]))
    shadow_img, (sx_max, sz0, sz1) = cartex.contact_shadow(body0, wheel_xz)
    car_tex["Shadow"] = embed(shadow_img, "PNG")
    shadow = Part("ContactShadow")
    shadow.tex_quad((0, 0.006, (sz0 + sz1) / 2), (-1, 0, 0), (0, 0, 1), 2 * sx_max, sz1 - sz0, "ContactShadow")

    # ---------------- GLB ----------------
    g = GLB()
    g.texlib = dict(shared_tex)
    g.texlib.update(car_tex)
    mats = library(spec["palette"])
    all_parts = []

    def mesh_node(nm, part, **kw):
        n = g.add_node(nm, None, **kw)
        g.json["nodes"][n]["_part"] = part
        all_parts.append(part)
        return n

    def group(nm, kids, **kw):
        return g.add_node(nm, children=kids, **kw)

    nodes = []
    # Karosserie
    nodes.append(group("Body", [mesh_node("Body_L%d" % k, bodies[k], extras={"lod": k}) for k in LODS]))
    # Cockpit
    ck_kids = [mesh_node("Interior", ck.part)]
    if deco is not None:
        ck_kids.append(mesh_node("Deko", deco, extras={"deco": True}))
    anim = {"SteeringWheel": {"anim": "steering"}, "Needle_Speed": {"anim": "needle", "gauge": "speed"},
            "Needle_RPM": {"anim": "needle", "gauge": "rpm"}, "Pedal_Brake": {"anim": "pedal", "pedal": "brake"},
            "Pedal_Throttle": {"anim": "pedal", "pedal": "throttle"}}
    for nname, (prt, tr, q) in ck.nodes.items():
        ck_kids.append(mesh_node(nname, prt, translation=tr, rotation=q, extras=anim.get(nname)))
    nodes.append(group("Cockpit", [group("Cockpit_L0", ck_kids, extras={"lod": 0}),
                                   mesh_node("Cockpit_L1", interior_l1, extras={"lod": 1}),
                                   g.add_node("Cockpit_L2", extras={"lod": 2})]))
    # Räder
    wheel_info = []
    cache = {}
    for axle, tag in (("front", "F"), ("rear", "R")):
        wd = spec["wheels"][axle]
        for side, lr in ((1, "L"), (-1, "R")):
            key = (axle, side)
            if key not in cache:
                cache[key] = {lod: wheel_parts(spec, axle, side, lod) for lod in (0, 1)}
            wp = cache[key]
            pos = tag + lr
            x = side * wheel_x(spec, body0, axle)
            kids = [group("Tire_" + pos, [mesh_node("Tire_%s_L%d" % (pos, lod), wp[lod]["tire"], extras={"lod": lod})
                                           for lod in (0, 1)]),
                    group("Brake_" + pos, [mesh_node("Brake_%s_L0" % pos, wp[0]["brake"], extras={"lod": 0})])]
            for ri in range(len(spec["rims"])):
                rk = [mesh_node("Rim_%d_%s_L%d" % (ri + 1, pos, lod), wp[lod]["rims"][ri], extras={"lod": lod})
                      for lod in (0, 1)]
                kids.append(group("Rim_%d_%s" % (ri + 1, pos), rk, extras={"tune": "rim", "variant": ri + 1}))
            nodes.append(group("Wheel_" + pos, kids, translation=(x, wd["R"], wd["z"]),
                               extras={"wheel": pos, "steer": axle == "front", "radius": wd["R"],
                                       "drive": st["drive"] == "AWD" or ((st["drive"] == "FWD") == (axle == "front"))}))
            nodes.append(group("Caliper_" + pos, [mesh_node("Caliper_%s_L0" % pos, wp[0]["caliper"], extras={"lod": 0})],
                               translation=(x, wd["R"], wd["z"]), extras={"caliper": pos, "steer": axle == "front"}))
            dr = st["drive"]
            wheel_info.append({"node": "Wheel_" + pos, "caliper": "Caliper_" + pos,
                               "position": [round(x, 4), round(wd["R"], 4), wd["z"]],
                               "radius": wd["R"], "width": wd["W"], "steer": axle == "front",
                               "drive": dr == "AWD" or ((dr == "FWD") == (axle == "front"))})
    # Tuning-Knoten
    for i in range(len(spoilers[0])):
        nm = spoilers[0][i].name
        nodes.append(group(nm, [mesh_node("%s_L%d" % (nm, k), spoilers[k][i], extras={"lod": k}) for k in (0, 1)],
                           extras={"tune": "spoiler", "variant": i + 1}))
    for i in range(len(liveries[0])):
        nm = liveries[0][i].name
        nodes.append(group(nm, [mesh_node("%s_L%d" % (nm, k), liveries[k][i], extras={"lod": k}) for k in LODS],
                           extras={"tune": "livery", "variant": i + 1}))
    for i in range(len(exhausts[0])):
        nm = exhausts[0][i].name
        nodes.append(group(nm, [mesh_node("%s_L%d" % (nm, k), exhausts[k][i], extras={"lod": k}) for k in (0, 1)],
                           extras={"tune": "exhaust", "variant": i + 1}))
    for i, c in enumerate(cages):
        nodes.append(group(c.name, [mesh_node(c.name + "_L0", c, extras={"lod": 0})],
                           extras={"tune": "cage", "variant": i + 1}))
    for nm in sorted(engine[0]):
        kids = [mesh_node("%s_L0" % nm, engine[0][nm], extras={"lod": 0})]
        if nm in engine[1] and engine[1][nm].count():
            kids.append(mesh_node("%s_L1" % nm, engine[1][nm], extras={"lod": 1}))
        nodes.append(group(nm, kids, extras={"tune": "engine", "stage": int(nm.split("_")[-1])}))
    for i, pn in enumerate(("Plate_Front", "Plate_Rear")):
        nodes.append(group(pn, [mesh_node("%s_L%d" % (pn, k), plates[k][i], extras={"lod": k}) for k in LODS],
                           extras={"plate": "front" if i == 0 else "rear"}))
    if unsprung:
        nodes.append(group("Axles", [mesh_node("Axles_L%d" % k, unsprung[k], extras={"lod": k}) for k in (0, 1)],
                           extras={"unsprung": True}))
    nodes.append(mesh_node("Underglow", glow, extras={"tune": "neon"}))
    nodes.append(mesh_node("ContactShadow", shadow, extras={"shadow": True}))
    # Hilfspunkte
    zws = ck.zws
    helpers = {"Cam_Cockpit": ck.eye,
               "Cam_Hood": spec.get("cam_hood", (0.0, body0.top_y(zws + 0.25) + 0.26, zws + 0.12)),
               "Seat_Driver": (ck.seat_x, ck.floor + 0.25, ck.hz)}
    helpers.update(ctx0.helpers)
    for hn, pos in helpers.items():
        nodes.append(g.add_node(hn, translation=pos, extras={"helper": hn}))

    # Materialien (nur benutzte)
    used = set()
    for prt in all_parts:
        used |= set(k for k, v in prt.tris.items() if v)
    missing = sorted(m for m in used if m not in mats)
    if missing:
        raise KeyError("Material(ien) fehlen: %s" % missing)
    for m in sorted(used):
        g.add_material(m, mats[m])
    for nd in g.json["nodes"]:
        prt = nd.pop("_part", None)
        if prt is not None:
            mi = g.add_mesh(prt)
            if mi is not None:
                nd["mesh"] = mi
    extras = {"id": name, "name": spec["name"], "stats": st}
    root = g.add_node(spec["node"], children=nodes, extras=extras)
    path = os.path.join(out_dir, name + ".glb")
    size = g.write(path, [root])
    log("  %s: %.2f MB, %d Dreiecke gesamt, %d Materialien (%.0fs)" % (
        os.path.basename(path), size / 1e6, g.stats["triangles"], len(used), time.time() - t0))

    # ---------------- Kennzahlen ----------------
    def wheel_tris(lod):
        w = cache[("front", 1)][lod]
        n = w["tire"].count() + w["rims"][0].count()
        if lod == 0:
            n += w["brake"].count() + w["caliper"].count()
        return n

    tri = {}
    for k in LODS:
        n = bodies[k].count() + 4 * wheel_tris(min(k, 1)) + plates[k][0].count() + plates[k][1].count()
        if k == 0:
            n += ck.part.count() + sum(p[0].count() for p in ck.nodes.values()) + (deco.count() if deco else 0)
        elif k == 1:
            n += interior_l1.count()
        tri["L%d" % k] = n
    cab_top = float(body0.cab_S[:, :, 1].max())
    meta = {
        "id": name, "name": spec["name"], "file": name + ".glb", "description": spec["desc"],
        "class": spec.get("class", ""), "brand": spec["brand"]["word"],
        "defaultPaint": spec["palette"]["paint"], "defaultAccent": spec["palette"]["accent"],
        "defaultRim": spec["palette"].get("rim"), "defaultCaliper": spec["palette"].get("caliper"),
        "dimensions": {"length": round(body0.zf - body0.zr, 3),
                       "width": round(2 * float(np.abs(body0.S[:, :, 0]).max()), 3),
                       "height": round(cab_top, 3)},
        "wheelbase": round(spec["wheels"]["front"]["z"] - spec["wheels"]["rear"]["z"], 3),
        "wheels": wheel_info, "stats": st, "physics": spec.get("physics", {}),
        "tuning": spec.get("tuning", {}), "plate": spec["plate"],
        "gauges": {"speedMaxKmh": vmax, "rpmMaxThousand": rpm_max, "sweepDeg": 270,
                   "cluster": spec["interior"].get("cluster", {}).get("type", "digital"),
                   "center": spec["interior"].get("center", {}).get("type", "dash"),
                   "rearScreens": bool(spec["interior"].get("rear_screens"))},
        "cockpit": {"eye": [round(float(v), 3) for v in ck.eye],
                    "steeringWheel": [round(float(v), 3) for v in ck.anchors["wheel"]],
                    "steeringRatioDeg": spec.get("steer_wheel_deg", 450)},
        "lights": ctx0.meta.get("lights", {}),
        "exhaustOutlets": ctx0.meta.get("exhaust_out", {}),
        "maxLoweringCm": spec.get("max_lowering_cm", 4),
        "defaultTuning": spec.get("default_tuning", {}),
        "rims": [d.get("label", d["style"]) for d in spec["rims"]],
        "spoilers": spec.get("spoiler_labels", ["Lippe", "GT-Flügel", "Cyber-Flügel"]),
        "liveries": spec.get("livery_labels", ["Rennstreifen", "Seitenblitz", "Startnummer"]),
        "triangles": tri, "fileBytes": size,
    }
    return meta
