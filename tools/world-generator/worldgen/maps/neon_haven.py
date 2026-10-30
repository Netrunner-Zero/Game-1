"""Neon Haven – die Stadt (ca. 900 × 900 m, klein und dicht).

Straßenraster mit Boulevard (2 × 3 Spuren mit Mittelstreifen), Avenuen (2 × 2) und Straßen (2 × 1),
Gehwege 15 cm hoch mit Bordstein, Ampeln an allen Kreuzungen, Laternen, Bäume.
Viertel: Downtown (Glastürme mit Werbetafeln und Neon-Kronen), Neon-Markt (dichte Häuser mit
Leuchtreklame), Wohnviertel, Park, Hafen (Lagerhallen, Container, Kräne, Kai). Rundherum eine
Mauer, dahinter eine Hochstraße und die Skyline; im Süden Wasser.

Ausgabe: Grafik in 3 × 3 Kacheln (Sichtbarkeitsprüfung je Kachel), Wiederholteile (Laternen,
Ampeln, Bäume) als Vorlagen + Positionen (im Spiel instanziert), Spieldaten (Kollisionen,
Bordsteine, Ampeln, Spurgraph, Startplätze, Viertel) und eine Minikarte.
"""
import math

import numpy as np
from PIL import Image, ImageDraw

from carcad.mesh import Part
from .. import geom as G
from ..geom import Frame, P

NAME = "Neon Haven"
ID = "neon_haven"

ROAD = {
    "boulevard": {"lanes": 3, "lane": 3.4, "median": 5.0, "walk": 5.0},
    "avenue": {"lanes": 2, "lane": 3.4, "median": 0.0, "walk": 4.0},
    "street": {"lanes": 1, "lane": 3.8, "median": 0.0, "walk": 3.0},
}
# Straßenachsen: Nord-Süd (fest x) und Ost-West (fest z), mit Namen
# Himmelsrichtungen: +Z = Norden, −X = Osten (rechtshändig mit Y nach oben: von oben gesehen liegt +X links)
NS = [(-440.0, "avenue", "Ostring"), (-335.0, "street", "Glasgasse"), (-225.0, "avenue", "Chrom-Allee"),
      (-110.0, "street", "Kabelweg"), (0.0, "boulevard", "Neon-Boulevard"), (115.0, "street", "Pixelgasse"),
      (225.0, "avenue", "Synth-Allee"), (330.0, "street", "Laternengasse"), (440.0, "avenue", "Westring")]
EW = [(-440.0, "avenue", "Hafenstraße"), (-330.0, "street", "Kranweg"), (-220.0, "avenue", "Werftallee"),
      (-110.0, "street", "Schienenweg"), (0.0, "boulevard", "Zentralboulevard"), (110.0, "street", "Marktgasse"),
      (220.0, "avenue", "Turmallee"), (330.0, "street", "Parkweg"), (440.0, "avenue", "Nordring")]
CURB_H = 0.15
BEVEL = 0.28
CHUNKS = 3
HALF_CITY = 460.0


def half(t):
    r = ROAD[t]
    return r["lanes"] * r["lane"] + r["median"] / 2


def walk(t):
    return ROAD[t]["walk"]


EDGE = 440.0 + half("avenue") + walk("avenue")       # Außenkante Gehweg am Ring


def district(cx, cz):
    if cz < -330:
        return "harbor"
    if cx < -110 and cz > 110:
        return "residential"
    if -110 < cx < 115 and cz > 220:
        return "park"
    if math.hypot(cx, cz * 1.15) < 245:
        return "downtown"
    if cx > 115:
        return "market"
    return "mixed"


DISTRICT_NAMES = {"downtown": "Downtown", "market": "Neon-Markt", "residential": "Wohnviertel", "park": "Lichtpark",
                  "harbor": "Hafen", "mixed": "Altstadt"}


class Builder:
    def __init__(self, rnd):
        self.rnd = rnd
        self.chunks = {}
        self.colliders = []
        self.regions = []
        self.inst = {"streetlamp": [], "signal": [], "tree": []}
        self.signals = []
        self.props = []
        self.minimap = []           # (Art, Polygon/Rechteck) für die Minikarte
        self.lights = []

    def part(self, x, z, cat):
        cx = min(CHUNKS - 1, max(0, int((x + HALF_CITY) / (2 * HALF_CITY) * CHUNKS)))
        cz = min(CHUNKS - 1, max(0, int((z + HALF_CITY) / (2 * HALF_CITY) * CHUNKS)))
        key = (cx, cz, cat)
        if key not in self.chunks:
            self.chunks[key] = Part("%s_%d_%d" % (cat, cx, cz))
        return self.chunks[key]

    def box_col(self, x, z, hx, hz, yaw=0.0, top=10.0, kind="building", mu=0.35, e=0.1):
        self.colliders.append({"t": "box", "x": round(x, 2), "z": round(z, 2), "hx": round(hx, 2), "hz": round(hz, 2),
                               "yaw": round(yaw, 4), "top": round(top, 2), "kind": kind, "mu": mu, "e": e})

    def circ_col(self, x, z, r, top=4.0, kind="pole"):
        self.colliders.append({"t": "circle", "x": round(x, 2), "z": round(z, 2), "r": r, "top": top, "kind": kind,
                               "mu": 0.3, "e": 0.1})

    def raised(self, x0, z0, x1, z1, top_mat="Pavers", kind="walk"):
        """Erhöhte Fläche (Gehweg/Insel): Oberseite, Bordsteinkanten, Bodenhöhe mit Anrampung."""
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        pg = self.part(cx, cz, "Ground")
        G.quad_up(pg, x0, z0, x1, z1, CURB_H, top_mat)
        for (ax, az, bx, bz, ox, oz) in ((x0, z0, x1, z0, 0, -1), (x1, z0, x1, z1, 1, 0), (x1, z1, x0, z1, 0, 1), (x0, z1, x0, z0, -1, 0)):
            L = math.hypot(bx - ax, bz - az)
            pg.quad(P(ax, 0, az), P(bx, 0, bz), P(bx, CURB_H, bz), P(ax, CURB_H, az), "Curb", outward=P(ox, 0, oz),
                    uvs=[(0, 0), (L, 0), (L, CURB_H), (0, CURB_H)])
        self.regions.append({"t": "rect", "x": round(cx, 3), "z": round(cz, 3), "hx": round((x1 - x0) / 2, 3),
                             "hz": round((z1 - z0) / 2, 3), "h": CURB_H, "bevel": BEVEL})
        self.minimap.append((kind, (x0, z0, x1, z1)))


# ----------------------------------------------------------------------
def build(rnd):
    B = Builder(rnd)
    base = Part("BaseAsphalt")
    G.quad_up(base, -EDGE - 2, -EDGE - 14, EDGE + 2, EDGE + 2, 0.0, "Asphalt")
    out = Part("Outskirts")
    water = Part("Water")

    xs = [r[0] for r in NS]
    zs = [r[0] for r in EW]

    # ------------------------------------------------------------ Blöcke (Gehweg + Bauland)
    blocks = []
    for i in range(len(NS) - 1):
        for j in range(len(EW) - 1):
            tw, te = NS[i][1], NS[i + 1][1]
            ts, tn = EW[j][1], EW[j + 1][1]
            x0, x1 = NS[i][0] + half(tw), NS[i + 1][0] - half(te)
            z0, z1 = EW[j][0] + half(ts), EW[j + 1][0] - half(tn)
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            dist = district(cx, cz)
            B.raised(x0, z0, x1, z1, "Grass" if dist == "park" else "Pavers", kind="park" if dist == "park" else "walk")
            inner = (x0 + walk(tw), z0 + walk(ts), x1 - walk(te), z1 - walk(tn))
            blocks.append({"i": i, "j": j, "curb": (x0, z0, x1, z1), "inner": inner, "district": dist,
                           "roads": {"w": NS[i], "e": NS[i + 1], "s": EW[j], "n": EW[j + 1]}})
    # äußere Gehwege am Ring (W, O, N) und Kai-Promenade (S)
    hw = half("avenue")
    B.raised(-EDGE, -440 + hw, -440 - hw, EDGE, kind="walk")
    B.raised(440 + hw, -440 + hw, EDGE, EDGE, kind="walk")
    B.raised(-440 + hw, 440 + hw, 440 - hw, EDGE, kind="walk")
    B.raised(-EDGE, -EDGE - 12, EDGE, -440 - hw, kind="walk")          # Kai
    # Mittelstreifen der Boulevards (zwischen den Kreuzungen)
    medW = ROAD["boulevard"]["median"] / 2
    for k in range(len(EW) - 1):
        z0 = EW[k][0] + half(EW[k][1]) + 6.0
        z1 = EW[k + 1][0] - half(EW[k + 1][1]) - 6.0
        B.raised(-medW + 0.3, z0, medW - 0.3, z1, "Grass", kind="median")
        for z in np.arange(z0 + 6, z1 - 3, 12.0):
            B.inst["tree"].append([0.0, round(float(z), 2), round(rnd.random() * 6.28, 3), round(0.85 + rnd.random() * 0.3, 3)])
    for k in range(len(NS) - 1):
        x0 = NS[k][0] + half(NS[k][1]) + 6.0
        x1 = NS[k + 1][0] - half(NS[k + 1][1]) - 6.0
        B.raised(x0, -medW + 0.3, x1, medW - 0.3, "Grass", kind="median")
        for x in np.arange(x0 + 6, x1 - 3, 12.0):
            B.inst["tree"].append([round(float(x), 2), 0.0, round(rnd.random() * 6.28, 3), round(0.85 + rnd.random() * 0.3, 3)])

    # ------------------------------------------------------------ Markierungen, Ampeln, Laternen
    y_m = 0.006
    nodes = []
    node_id = {}
    for a, (x, tx, _n) in enumerate(NS):
        for b, (z, tz, _m) in enumerate(EW):
            node_id[(a, b)] = len(nodes)
            nodes.append({"id": len(nodes), "x": x, "z": z, "ns": tx, "ew": tz, "signal": None})
    edges = []

    def lane_lines(p, ax, az, bx, bz, t):
        """Markierungen eines Abschnitts (a -> b) einer Straße vom Typ t."""
        r = ROAD[t]
        L = math.hypot(bx - ax, bz - az)
        dx, dz = (bx - ax) / L, (bz - az) / L
        lx, lz = dz, -dx                                      # links
        if t == "boulevard":
            for side in (-1, 1):
                for k in range(1, r["lanes"]):
                    off = side * (r["median"] / 2 + k * r["lane"])
                    G.dashed(p, ax + lx * off, az + lz * off, bx + lx * off, bz + lz * off, 0.13, y_m, "Paint", dash=4, gap=8)
        elif t == "avenue":
            for off in (-0.1, 0.1):
                G.strip(p, [(ax + lx * off, az + lz * off), (bx + lx * off, bz + lz * off)], 0.1, y_m, "PaintYellow")
            for side in (-1, 1):
                off = side * r["lane"]
                G.dashed(p, ax + lx * off, az + lz * off, bx + lx * off, bz + lz * off, 0.13, y_m, "Paint", dash=4, gap=8)
        else:
            G.dashed(p, ax, az, bx, bz, 0.12, y_m, "PaintYellow", dash=3, gap=5)

    def crossing(p, cx, cz, dx, dz, t_road, d_cross):
        """Zebrastreifen + Haltelinie vor der Kreuzung (cx, cz), Zufahrt in Richtung (dx, dz)."""
        r = ROAD[t_road]
        hw_ = half(t_road)
        lx, lz = dz, -dx
        back = d_cross + 1.0                                   # Abstand der Zebra-Vorderkante zur Kreuzungsmitte
        n = int(hw_ * 2 / 1.0)
        for k in range(n):
            off = -hw_ + 0.5 + k * 1.0
            if abs(off) < r["median"] / 2:
                continue
            p0 = (cx - dx * back + lx * off, cz - dz * back + lz * off)
            p1 = (cx - dx * (back + 3.2) + lx * off, cz - dz * (back + 3.2) + lz * off)
            G.strip(p, [p0, p1], 0.5, y_m, "Paint")
        # Haltelinie nur über die Spuren der Zufahrt (rechte Hälfte)
        s0 = r["median"] / 2
        a = (cx - dx * (back + 4.2) - lx * s0, cz - dz * (back + 4.2) - lz * s0)
        b = (cx - dx * (back + 4.2) - lx * hw_, cz - dz * (back + 4.2) - lz * hw_)
        G.strip(p, [a, b], 0.4, y_m, "Paint")
        return back + 4.2

    cyc = 32.0
    for a, (x, tx, _n) in enumerate(NS):
        for b, (z, tz, _m) in enumerate(EW):
            nid = node_id[(a, b)]
            # Zufahrten: aus welchen Richtungen kommen Straßen?
            approaches = []
            if b > 0:
                approaches.append((0.0, 1.0, tx, half(tz), "ns"))       # von Süden nach Norden
            if b < len(EW) - 1:
                approaches.append((0.0, -1.0, tx, half(tz), "ns"))
            if a > 0:
                approaches.append((1.0, 0.0, tz, half(tx), "ew"))       # von Westen nach Osten (+x)
            if a < len(NS) - 1:
                approaches.append((-1.0, 0.0, tz, half(tx), "ew"))
            corner = len(approaches) <= 2
            offset = ((a + b) * 4.0) % cyc
            if not corner:
                nodes[nid]["signal"] = offset
            p = B.part(x, z, "Markings")
            for (dx, dz, t_road, d_cross, grp) in approaches:
                stop = crossing(p, x, z, dx, dz, t_road, d_cross) if not corner else d_cross
                if corner:
                    continue
                # Ampelmast an der rechten Ecke der Zufahrt, Arm über die Fahrspuren
                rx, rz = -dz, dx                                       # rechts
                hw_ = half(t_road)
                px, pz = x - dx * (d_cross + 1.5) + rx * (hw_ + 0.8), z - dz * (d_cross + 1.5) + rz * (hw_ + 0.8)
                lx, lz = dz, -dx
                yaw = math.atan2(lx, lz)                                 # Arm (lokal +z) zeigt nach links über die Spuren
                B.inst["signal"].append([round(px, 2), round(pz, 2), round(yaw, 4)])
                # Signalkopf: am Armende, schaut den ankommenden Autos entgegen
                arm = 4.4                                               # wie in der Vorlage Tpl_Signal
                hx, hz = px + lx * arm, pz + lz * arm
                face = math.atan2(-dx, -dz)
                B.signals.append([round(hx, 2), 5.55, round(hz, 2), round(face, 4), 0 if grp == "ns" else 1, offset])
                # kleines Signal an der Ecke (für die erste Spur, auf Augenhöhe)
                B.signals.append([round(px - dx * 0.0 + lx * 0.25, 2), 3.1, round(pz + lz * 0.25, 2), round(face, 4),
                                  0 if grp == "ns" else 1, offset])
    # Abschnitte zwischen den Kreuzungen: Markierungen, Laternen, Kanten im Spurgraph
    for a, (x, t, _n) in enumerate(NS):
        for b in range(len(EW) - 1):
            z0 = EW[b][0] + half(EW[b][1]) + 9.0
            z1 = EW[b + 1][0] - half(EW[b + 1][1]) - 9.0
            p = B.part(x, (z0 + z1) / 2, "Markings")
            lane_lines(p, x, z0, x, z1, t)
            edges.append({"a": node_id[(a, b)], "b": node_id[(a, b + 1)], "type": t})
            hw_ = half(t)
            for side in (-1, 1):
                if (a == 0 and side < 0) or (a == len(NS) - 1 and side > 0):
                    pass
                for zz in np.arange(z0 + 6, z1 - 4, 30.0):
                    lx_ = x + side * (hw_ + 0.7)
                    yaw = math.atan2(-side, 0.0)
                    B.inst["streetlamp"].append([round(lx_, 2), round(float(zz), 2), round(yaw, 4)])
    for b, (z, t, _n) in enumerate(EW):
        for a in range(len(NS) - 1):
            x0 = NS[a][0] + half(NS[a][1]) + 9.0
            x1 = NS[a + 1][0] - half(NS[a + 1][1]) - 9.0
            p = B.part((x0 + x1) / 2, z, "Markings")
            lane_lines(p, x0, z, x1, z, t)
            edges.append({"a": node_id[(a, b)], "b": node_id[(a + 1, b)], "type": t})
            hw_ = half(t)
            for side in (-1, 1):
                for xx in np.arange(x0 + 21, x1 - 4, 30.0):
                    lz_ = z + side * (hw_ + 0.7)
                    yaw = math.atan2(0.0, -side)
                    B.inst["streetlamp"].append([round(float(xx), 2), round(lz_, 2), round(yaw, 4)])

    # ------------------------------------------------------------ Gebäude
    for blk in blocks:
        build_block(B, blk)

    # ------------------------------------------------------------ Hafen: Kai, Wasser, Kräne
    zq = -EDGE - 12
    water.quad(P(-2600, -1.2, zq), P(2600, -1.2, zq), P(2600, -1.2, -2600), P(-2600, -1.2, -2600), "Water", outward=G.UP,
               uvs=[(-2600, zq), (2600, zq), (2600, -2600), (-2600, -2600)], normals=[G.UP] * 4)
    out.quad(P(-EDGE - 2, -1.2, zq), P(EDGE + 2, -1.2, zq), P(EDGE + 2, CURB_H, zq), P(-EDGE - 2, CURB_H, zq), "ConcreteDark",
             outward=P(0, 0, -1))
    B.box_col(0, zq - 1.0, EDGE + 2, 1.0, 0, top=1.0, kind="quay")
    for x in np.arange(-EDGE + 6, EDGE - 4, 9.0):
        G.cylinder(B.part(float(x), zq, "Buildings"), float(x), zq + 0.6, CURB_H, 0.95, 0.22, "RoofGear", segs=8)
        B.circ_col(float(x), zq + 0.6, 0.24, top=1.0, kind="bollard")
    for k, x in enumerate((-300.0, -120.0, 90.0, 300.0)):
        crane(B, x, zq + 4.0, rnd)
    # Container-Schiffe in der Ferne (nur Kulisse)
    for (x, z, L) in ((-600.0, -900.0, 220.0), (500.0, -1200.0, 260.0)):
        f = Frame(x, z, 1.5708)
        G.box(out, f, 0, 4, 0, 32, 12, L, "ConcreteDark")
        for k in range(int(L / 14)):
            G.box(out, f, 0, 12, -L / 2 + 10 + k * 14, 26, 5 + (k % 3) * 2.6, 12, ("ContainerRed", "ContainerBlue", "ContainerGrey")[k % 3])

    # ------------------------------------------------------------ Mauer, Hochstraße, Umland, Skyline
    wall_h = 4.0
    for (x0, z0, x1, z1) in ((-EDGE - 1.2, zq, -EDGE, EDGE + 1.2), (EDGE, zq, EDGE + 1.2, EDGE + 1.2), (-EDGE - 1.2, EDGE, EDGE + 1.2, EDGE + 1.2)):
        f = Frame((x0 + x1) / 2, (z0 + z1) / 2, 0)
        G.box(out, f, 0, wall_h / 2, 0, x1 - x0, wall_h, z1 - z0, "Concrete")
        B.box_col((x0 + x1) / 2 + (-1.0 if x1 - x0 < 2 and x0 < 0 else 1.0 if x1 - x0 < 2 else 0),
                  (z0 + z1) / 2 + (1.0 if z1 - z0 < 2 else 0), (x1 - x0) / 2 + (1.0 if x1 - x0 < 2 else 0),
                  (z1 - z0) / 2 + (1.0 if z1 - z0 < 2 else 0), 0, top=wall_h, kind="wall")
    # Neonband oben auf der Mauer
    for (ax, az, bx, bz) in ((-EDGE - 0.6, zq, -EDGE - 0.6, EDGE + 0.6), (EDGE + 0.6, zq, EDGE + 0.6, EDGE + 0.6), (-EDGE - 0.6, EDGE + 0.6, EDGE + 0.6, EDGE + 0.6)):
        f = Frame((ax + bx) / 2, (az + bz) / 2, 0)
        G.box(out, f, 0, wall_h + 0.04, 0, max(0.12, abs(bx - ax)), 0.08, max(0.12, abs(bz - az)), "NeonCyan")
    for (x0, z0, x1, z1) in ((-2600, -EDGE - 12, -EDGE - 1.2, 2600), (EDGE + 1.2, -EDGE - 12, 2600, 2600), (-EDGE - 1.2, EDGE + 1.2, EDGE + 1.2, 2600)):
        G.quad_up(out, x0, z0, x1, z1, -0.02, "Dirt")
    highway(out, rnd)
    skyline(out, rnd)

    # ------------------------------------------------------------ Baustelle mit Pylonen (Neon-Markt)
    for k in range(9):
        B.props.append({"type": "cone", "x": round(225.0 + 1.6 + (k % 3) * 0.9, 2), "z": round(60.0 + k * 3.0, 2)})
    # Zonen (Viertel) als Rechtecke
    zones = []
    for blk in blocks:
        x0, z0, x1, z1 = blk["curb"]
        zones.append({"name": DISTRICT_NAMES[blk["district"]], "rect": [round(x0 - 8, 1), round(z0 - 8, 1), round(x1 + 8, 1), round(z1 + 8, 1)]})

    meta = {
        "id": ID, "name": NAME,
        "bounds": [-EDGE, -EDGE - 12, EDGE, EDGE],
        "spawn": [
            # Rechtsverkehr: in Fahrtrichtung rechts = (−dz, dx); +X ist „links“, wenn man nach +Z schaut
            {"x": -(2.5 + 1.7), "z": -170.0, "yaw": 0.0, "name": "Neon-Boulevard"},
            {"x": -150.0, "z": -440.0 + 1.7, "yaw": 1.5708, "name": "Hafen"},
            {"x": 225.0 - 1.7, "z": 40.0, "yaw": 0.0, "name": "Neon-Markt"},
            {"x": -335.0 - 1.9, "z": 250.0, "yaw": 0.0, "name": "Wohnviertel"},
            {"x": 50.0, "z": 330.0 - 1.9, "yaw": -1.5708, "name": "Lichtpark"},
        ],
        "env": {"ground": "Dirt", "fogNear": 180, "fogFar": 1500},
        "colliders": B.colliders, "regions": B.regions, "props": B.props, "zones": zones,
        "instances": {
            "streetlamp": {"template": "Tpl_StreetLamp", "collider": {"r": 0.2, "top": 8.5}, "head": [0.0, 8.35, 2.05],
                           "items": B.inst["streetlamp"]},
            "signal": {"template": "Tpl_Signal", "collider": {"r": 0.22, "top": 6.0}, "items": B.inst["signal"]},
            "tree": {"template": "Tpl_Tree", "collider": {"r": 0.3, "top": 5.0}, "items": B.inst["tree"]},
        },
        "signals": {"cycle": cyc, "green": 12.0, "yellow": 3.0, "allRed": 1.0, "heads": B.signals},
        "roads": {"types": ROAD, "nodes": nodes, "edges": edges,
                  "ns": [{"x": x, "type": t, "name": n} for (x, t, n) in NS],
                  "ew": [{"z": z, "type": t, "name": n} for (z, t, n) in EW]},
        "props_templates": {"cone": "Prop_Cone"},
    }
    templates = make_templates()
    nodes = [("BaseAsphalt", base, {"shadow": "receive"}), ("Water", water, {"shadow": "none"}),
             ("Outskirts", out, {"shadow": "none", "far": True})]
    shadow = {"Ground": "receive", "Markings": "receive", "Buildings": "both"}
    for (cx, cz, cat), part in sorted(B.chunks.items()):
        nodes.append(("%s_%d_%d" % (cat, cx, cz), part, {"shadow": shadow[cat], "chunk": [cx, cz]}))

    def post(out_dir):
        import os
        meta["minimap"] = minimap(B, os.path.join(out_dir, ID + "_map.png"))

    return {"nodes": nodes, "templates": templates, "meta": meta, "post": post}


# ----------------------------------------------------------------------
def split_lots(rect, rnd, n_target, min_side=14.0, alley_p=0.4):
    lots = [rect]
    tries = 0
    while len(lots) < n_target and tries < 40:
        tries += 1
        lots.sort(key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
        x0, z0, x1, z1 = lots[-1]
        w, d = x1 - x0, z1 - z0
        along_x = w >= d
        size = w if along_x else d
        if size < 2 * min_side:
            break
        alley = (3.5 + rnd.random() * 2.5) if rnd.random() < alley_p else 0.0
        cut = (0.35 + rnd.random() * 0.3) * size
        lots.pop()
        if along_x:
            lots += [(x0, z0, x0 + cut - alley / 2, z1), (x0 + cut + alley / 2, z0, x1, z1)]
        else:
            lots += [(x0, z0, x1, z0 + cut - alley / 2), (x0, z0 + cut + alley / 2, x1, z1)]
    return lots


def walls(part, x0, z0, x1, z1, y0, y1, mat, u0=0.0, v0=0.0):
    """Vier Außenwände eines achsparallelen Quaders (Fassaden-UVs: u entlang, v = Höhe)."""
    u = u0
    for (ax, az, bx, bz, ox, oz) in ((x0, z0, x1, z0, 0, -1), (x1, z0, x1, z1, 1, 0), (x1, z1, x0, z1, 0, 1), (x0, z1, x0, z0, -1, 0)):
        L = math.hypot(bx - ax, bz - az)
        part.quad(P(ax, y0, az), P(bx, y0, bz), P(bx, y1, bz), P(ax, y1, az), mat, outward=P(ox, 0, oz),
                  uvs=[(u, v0 + y0), (u + L, v0 + y0), (u + L, v0 + y1), (u, v0 + y1)])
        u += L


def roof(part, x0, z0, x1, z1, y, mat="Roof"):
    part.quad(P(x0, y, z0), P(x1, y, z0), P(x1, y, z1), P(x0, y, z1), mat, outward=G.UP, normals=[G.UP] * 4)


def neon_rim(part, x0, z0, x1, z1, y, mat, t=0.25):
    for (ax, az, bx, bz) in ((x0, z0, x1, z0), (x1, z0, x1, z1), (x1, z1, x0, z1), (x0, z1, x0, z0)):
        f = Frame((ax + bx) / 2, (az + bz) / 2, 0)
        G.box(part, f, 0, y + t / 2, 0, max(t, abs(bx - ax)), t, max(t, abs(bz - az)), mat)


SIGN_H = [(c * 0.5, r * 0.125, 0.5, 0.125) for r in range(4) for c in range(2)]     # u0, v0, du, dv
SIGN_V = [(k * 0.125, 0.5, 0.125, 0.5) for k in range(8)]
BILL = [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)]


def wall_sign(part, p0, p1, y0, y1, normal, cell, mat="Signs"):
    """Flaches Schild vor einer Wand (p0 -> p1 von außen gesehen links -> rechts)."""
    u0, v0, du, dv = cell
    n = np.array([normal[0], 0, normal[1]])
    a, b = P(p0[0], y0, p0[1]) + n * 0.08, P(p1[0], y0, p1[1]) + n * 0.08
    part.quad(a, b, b + P(0, y1 - y0, 0), a + P(0, y1 - y0, 0), mat, outward=n,
              uvs=[(u0, v0 + dv), (u0 + du, v0 + dv), (u0 + du, v0), (u0, v0)])


def street_faces(blk):
    """Straßenseiten des Blocks: (Seite, Achse a->b von außen gesehen links->rechts, Normale)."""
    x0, z0, x1, z1 = blk["inner"]
    return {"s": ((x1, z0), (x0, z0), (0, -1)), "n": ((x0, z1), (x1, z1), (0, 1)),
            "w": ((x0, z0), (x0, z1), (-1, 0)), "e": ((x1, z1), (x1, z0), (1, 0))}


def build_block(B, blk):
    rnd = B.rnd
    dist = blk["district"]
    x0, z0, x1, z1 = blk["inner"]
    if dist == "park":
        park(B, blk)
        return
    n_target = {"downtown": 1 + int(rnd.random() * 2), "market": 4 + int(rnd.random() * 3), "residential": 2 + int(rnd.random() * 3),
                "harbor": 2 + int(rnd.random() * 2), "mixed": 3 + int(rnd.random() * 2)}[dist]
    lots = split_lots((x0, z0, x1, z1), rnd, n_target, min_side=16.0 if dist != "market" else 11.0,
                      alley_p={"market": 0.5, "harbor": 0.7}.get(dist, 0.3))
    for k, (a0, b0, a1, b1) in enumerate(lots):
        inset = 0.3
        a0, b0, a1, b1 = a0 + inset, b0 + inset, a1 - inset, b1 - inset
        if a1 - a0 < 6 or b1 - b0 < 6:
            continue
        cx, cz = (a0 + a1) / 2, (b0 + b1) / 2
        p = B.part(cx, cz, "Buildings")
        if dist == "harbor" and k == 0 and (a1 - a0) * (b1 - b0) > 1800:
            container_yard(B, (a0, b0, a1, b1))
            continue
        if dist == "downtown":
            h = tower(B, p, (a0, b0, a1, b1), rnd, blk)
        elif dist == "market":
            h = midrise(B, p, (a0, b0, a1, b1), rnd, "FacPanel", 12 + rnd.random() * 34, signs=True, blk=blk)
        elif dist == "residential":
            h = midrise(B, p, (a0, b0, a1, b1), rnd, "FacApart", 18 + rnd.random() * 36, signs=rnd.random() < 0.4,
                        shop=rnd.random() < 0.6, blk=blk)
        elif dist == "harbor":
            h = warehouse(B, p, (a0, b0, a1, b1), rnd)
        else:
            mat = ("FacPanel", "FacApart", "FacGlass")[int(rnd.random() * 3)]
            h = midrise(B, p, (a0, b0, a1, b1), rnd, mat, 20 + rnd.random() * 50, signs=rnd.random() < 0.5, blk=blk)
        B.box_col(cx, cz, (a1 - a0) / 2, (b1 - b0) / 2, 0.0, top=h, kind="building")
        B.minimap.append((dist, (a0, b0, a1, b1)))
    # Bäume am Gehweg im Wohnviertel
    if dist == "residential":
        cx0, cz0, cx1, cz1 = blk["curb"]
        for side in ("s", "n"):
            z = cz0 + 1.6 if side == "s" else cz1 - 1.6
            for x in np.arange(cx0 + 8, cx1 - 6, 15.0):
                B.inst["tree"].append([round(float(x), 2), round(z, 2), round(rnd.random() * 6.28, 3), round(0.8 + rnd.random() * 0.35, 3)])


def midrise(B, p, r, rnd, mat, h, signs=False, shop=True, blk=None):
    a0, b0, a1, b1 = r
    h = round(h / 3.0) * 3.0 + 4.2
    if shop:
        walls(p, a0, b0, a1, b1, 0.0, 4.2, "Shop", u0=rnd.random() * 16)
        walls(p, a0, b0, a1, b1, 4.2, h, mat, u0=rnd.random() * 40, v0=-4.2)
        # Vordach über den Läden
        for (ax, az, bx, bz, ox, oz) in ((a0, b0, a1, b0, 0, -1), (a1, b0, a1, b1, 1, 0), (a1, b1, a0, b1, 0, 1), (a0, b1, a0, b0, -1, 0)):
            q0, q1 = P(ax, 4.2, az), P(bx, 4.2, bz)
            o = P(ox, 0, oz) * 1.2
            p.quad(q0, q1, q1 + o, q0 + o, "RoofGear", outward=G.UP)
            p.quad(q0 + o, q1 + o, q1 + o + P(0, 0.25, 0), q0 + o + P(0, 0.25, 0), "RoofGear", outward=P(ox, 0, oz))
    else:
        walls(p, a0, b0, a1, b1, 0.0, h, mat, u0=rnd.random() * 40)
    roof(p, a0, b0, a1, b1, h)
    rooftop(p, r, h, rnd)
    if signs and blk is not None:
        # Leuchtreklame über den Läden an den Straßenseiten + senkrechte Schilder an Ecken
        faces = street_faces(blk)
        for side, (pa, pb, nrm) in faces.items():
            # nur wenn diese Gebäudeseite an der Blockkante liegt
            on = {"s": abs(b0 - blk["inner"][1]) < 1.0, "n": abs(b1 - blk["inner"][3]) < 1.0,
                  "w": abs(a0 - blk["inner"][0]) < 1.0, "e": abs(a1 - blk["inner"][2]) < 1.0}[side]
            if not on or rnd.random() < 0.25:
                continue
            if side in ("s", "n"):
                xa, xb = (a1, a0) if side == "s" else (a0, a1)
                zz = b0 if side == "s" else b1
                L = abs(a1 - a0)
                w = min(6.0, L * 0.6)
                c = (xa + xb) / 2
                d = 1 if xb > xa else -1
                wall_sign(p, (c - d * w / 2, zz), (c + d * w / 2, zz), 5.0, 5.0 + w / 4, nrm, SIGN_H[int(rnd.random() * 8)])
            else:
                za, zb = (b0, b1) if side == "w" else (b1, b0)
                xx = a0 if side == "w" else a1
                L = abs(b1 - b0)
                w = min(6.0, L * 0.6)
                c = (za + zb) / 2
                d = 1 if zb > za else -1
                wall_sign(p, (xx, c - d * w / 2), (xx, c + d * w / 2), 5.0, 5.0 + w / 4, nrm, SIGN_H[int(rnd.random() * 8)])
            if h > 14 and rnd.random() < 0.6:
                blade_sign(p, pa if rnd.random() < 0.5 else pb, nrm, (a0, b0, a1, b1), h, rnd)
    if h > 30 and rnd.random() < 0.35:
        neon_rim(p, a0, b0, a1, b1, h, ("NeonPink", "NeonCyan", "NeonViolet")[int(rnd.random() * 3)], t=0.18)
    return h


def blade_sign(p, corner, nrm, r, h, rnd):
    """Senkrechtes Schild, steht an einer Gebäudeecke quer zur Fassade (von beiden Seiten lesbar)."""
    a0, b0, a1, b1 = r
    cx = min(max(corner[0], a0), a1)
    cz = min(max(corner[1], b0), b1)
    nx, nz = nrm
    # Schild ragt in Richtung der Normalen aus der Wand, liegt also in der Ebene (Normale, oben)
    tx, tz = -nz, nx
    cx += tx * (1.0 if (cx - (a0 + a1) / 2) * tx + (cz - (b0 + b1) / 2) * tz < 0 else -1.0) * 1.5
    y0 = 6.0
    y1 = min(h - 1.0, y0 + 7.0)
    cell = SIGN_V[int(rnd.random() * 8)]
    u0, v0, du, dv = cell
    o0 = P(cx, 0, cz)
    o1 = P(cx + nx * 1.4, 0, cz + nz * 1.4)
    side = P(tx, 0, tz)
    for s in (1, -1):
        off = side * 0.07 * s
        a, b = o0 + off, o1 + off
        uv = [(u0, v0 + dv), (u0 + du, v0 + dv), (u0 + du, v0), (u0, v0)]
        if s < 0:
            a, b = b, a
        p.quad(a + P(0, y0, 0), b + P(0, y0, 0), b + P(0, y1, 0), a + P(0, y1, 0), "Signs", outward=side * s,
               uvs=[(u0, v0), (u0, v0 + dv), (u0 + du, v0 + dv), (u0 + du, v0)])
    f = Frame((o0[0] + o1[0]) / 2, (o0[2] + o1[2]) / 2, math.atan2(nx, nz))
    G.box(p, f, 0, y1 + 0.1, 0, 0.16, 0.2, 1.45, "RoofGear")


def tower(B, p, r, rnd, blk):
    """Hochhaus: Sockel mit Läden, Turm (eingerückt), oft Stufe, Krone mit Neon, Werbetafel."""
    a0, b0, a1, b1 = r
    pod = 9.0 + rnd.random() * 9.0
    walls(p, a0, b0, a1, b1, 0.0, 4.2, "Shop", u0=rnd.random() * 16)
    walls(p, a0, b0, a1, b1, 4.2, pod, "FacPanel", v0=-4.2)
    roof(p, a0, b0, a1, b1, pod)
    ins = 3.0 + rnd.random() * 5.0
    t0, u0_, t1, u1_ = a0 + ins, b0 + ins, a1 - ins, b1 - ins
    if t1 - t0 < 12 or u1_ - u0_ < 12:
        t0, u0_, t1, u1_ = a0 + 1.5, b0 + 1.5, a1 - 1.5, b1 - 1.5
    h = 90.0 + (rnd.random() ** 1.3) * 190.0
    step = rnd.random() < 0.55
    h1 = h * (0.62 + rnd.random() * 0.15) if step else h
    walls(p, t0, u0_, t1, u1_, pod, h1, "FacGlass", u0=rnd.random() * 48, v0=-pod)
    roof(p, t0, u0_, t1, u1_, h1)
    top_r = (t0, u0_, t1, u1_)
    if step:
        s = 2.5 + rnd.random() * 3.0
        q = (t0 + s, u0_ + s, t1 - s, u1_ - s)
        walls(p, *q, h1, h, "FacGlass", u0=rnd.random() * 48, v0=-pod)
        roof(p, *q, h)
        neon_rim(p, t0, u0_, t1, u1_, h1, "NeonCyan", t=0.3)
        top_r = q
    m = ("NeonPink", "NeonCyan", "NeonViolet")[int(rnd.random() * 3)]
    neon_rim(p, *top_r, h, m, t=0.4)
    # senkrechte Neonkanten an den Ecken des oberen Teils
    for (cx, cz) in ((top_r[0], top_r[1]), (top_r[2], top_r[1]), (top_r[2], top_r[3]), (top_r[0], top_r[3])):
        f = Frame(cx, cz, 0)
        G.box(p, f, 0, h - 18, 0, 0.35, 36, 0.35, m)
    if h > 200:
        f = Frame((top_r[0] + top_r[2]) / 2, (top_r[1] + top_r[3]) / 2, 0)
        G.box(p, f, 0, h + 16, 0, 1.2, 32, 1.2, "RoofGear")
        G.box(p, f, 0, h + 32.5, 0, 0.5, 1.0, 0.5, "NeonPink")
    rooftop(p, top_r, h, rnd, small=True)
    # Werbetafel an einer Straßenseite des Turms
    if rnd.random() < 0.6:
        faces = [("s", (top_r[2], top_r[1]), (top_r[0], top_r[1]), (0, -1)), ("n", (top_r[0], top_r[3]), (top_r[2], top_r[3]), (0, 1)),
                 ("w", (top_r[0], top_r[1]), (top_r[0], top_r[3]), (-1, 0)), ("e", (top_r[2], top_r[3]), (top_r[2], top_r[1]), (1, 0))]
        side, pa, pb, nrm = faces[int(rnd.random() * 4)]
        L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        w = min(22.0, L * 0.8)
        cx, cz = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
        dx, dz = (pb[0] - pa[0]) / L, (pb[1] - pa[1]) / L
        y0 = pod + 8 + rnd.random() * max(1.0, h1 - pod - w - 12)
        u0, v0 = BILL[int(rnd.random() * 4)]
        n = np.array([nrm[0], 0, nrm[1]])
        a = P(cx - dx * w / 2, y0, cz - dz * w / 2) + n * 0.35
        b = P(cx + dx * w / 2, y0, cz + dz * w / 2) + n * 0.35
        p.quad(a, b, b + P(0, w, 0), a + P(0, w, 0), "Billboard", outward=n,
               uvs=[(u0, v0 + 0.5), (u0 + 0.5, v0 + 0.5), (u0 + 0.5, v0), (u0, v0)])
        f = Frame(cx + nrm[0] * 0.18, cz + nrm[1] * 0.18, math.atan2(dx, dz))
        G.box(p, f, 0, y0 + w / 2, 0, 0.3, w + 0.6, w + 0.6, "RoofGear")
    return h


def warehouse(B, p, r, rnd):
    a0, b0, a1, b1 = r
    h = 9.0 + rnd.random() * 7.0
    walls(p, a0, b0, a1, b1, 0.0, h, "FacWare", u0=rnd.random() * 16)
    roof(p, a0, b0, a1, b1, h)
    # Rolltore (dunkle Flächen) an den Längsseiten
    L = a1 - a0
    for k in range(int(L // 14)):
        x = a0 + 7 + k * 14
        for (z, nz) in ((b0, -1), (b1, 1)):
            q0, q1 = P(x - 2.5, 0.0, z + nz * 0.05), P(x + 2.5, 0.0, z + nz * 0.05)
            if nz < 0:
                q0, q1 = q1, q0
            p.quad(q0, q1, q1 + P(0, 5.0, 0), q0 + P(0, 5.0, 0), "RoofGear", outward=P(0, 0, nz))
    rooftop(p, r, h, rnd, small=True)
    return h


def container_yard(B, r):
    rnd = B.rnd
    a0, b0, a1, b1 = r
    mats = ("ContainerRed", "ContainerBlue", "ContainerGrey")
    x = a0 + 2
    while x + 2.5 < a1 - 2:
        z = b0 + 2
        while z + 12.3 < b1 - 2:
            if rnd.random() < 0.8:
                n = 1 + int(rnd.random() * 3)
                p = B.part(x, z, "Buildings")
                f = Frame(x + 1.22, z + 6.1, 0)
                for k in range(n):
                    G.box(p, f, 0, 1.3 + k * 2.6, 0, 2.44, 2.58, 12.2, mats[int(rnd.random() * 3)])
                B.box_col(x + 1.22, z + 6.1, 1.22, 6.1, 0, top=2.6 * n, kind="container")
                B.minimap.append(("container", (x, z, x + 2.44, z + 12.2)))
            z += 14.5
        x += 3.4 if rnd.random() < 0.75 else 9.0


def crane(B, x, z, rnd):
    """Containerkran (Portal) am Kai – Kulisse mit Kollision an den Beinen."""
    p = B.part(x, z, "Buildings")
    f = Frame(x, z, 0)
    for sx in (-9.0, 9.0):
        for sz in (-4.0, 4.0):
            G.box(p, f, sx, 16, sz, 1.2, 32, 1.2, "ContainerRed")
            B.circ_col(x + sx, z + sz, 0.9, top=32, kind="crane")
    G.box(p, f, 0, 32.5, 0, 20, 2.0, 10, "ContainerRed")
    G.box(p, f, 0, 34.5, -18, 3, 2.2, 60, "ContainerRed")
    G.box(p, f, 0, 30, 6, 6, 3, 4, "RoofGear")
    G.box(p, f, 0, 36.0, -46, 0.6, 0.4, 0.6, "NeonPink")


def rooftop(p, r, h, rnd, small=False):
    a0, b0, a1, b1 = r
    n = 1 + int(rnd.random() * (2 if small else 4))
    for k in range(n):
        w, d = 2 + rnd.random() * 4, 2 + rnd.random() * 4
        cx = a0 + w / 2 + 1 + rnd.random() * max(0.1, a1 - a0 - w - 2)
        cz = b0 + d / 2 + 1 + rnd.random() * max(0.1, b1 - b0 - d - 2)
        if cx + w / 2 > a1 or cz + d / 2 > b1:
            continue
        f = Frame(cx, cz, 0)
        if rnd.random() < 0.3 and not small:
            G.cylinder(p, cx, cz, h, h + 4.0, min(w, d) / 2, "RoofGear", segs=10)
        else:
            G.box(p, f, 0, h + 0.9, 0, w, 1.8, d, "RoofGear")


def park(B, blk):
    rnd = B.rnd
    x0, z0, x1, z1 = blk["curb"]
    p = B.part((x0 + x1) / 2, (z0 + z1) / 2, "Ground")
    # Wege (Kreuz + Diagonale) aus Platten auf dem Rasen
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    for pts in (((x0, cz), (x1, cz)), ((cx, z0), (cx, z1)), ((x0 + 3, z0 + 3), (x1 - 3, z1 - 3))):
        G.strip(p, list(pts), 3.0, CURB_H + 0.008, "Pavers")
    # Bäume (nicht auf den Wegen)
    for k in range(int((x1 - x0) * (z1 - z0) / 160)):
        x = x0 + 3 + rnd.random() * (x1 - x0 - 6)
        z = z0 + 3 + rnd.random() * (z1 - z0 - 6)
        if abs(x - cx) < 3.5 or abs(z - cz) < 3.5 or abs((x - x0) - (z - z0) * (x1 - x0) / (z1 - z0)) < 4:
            continue
        B.inst["tree"].append([round(x, 2), round(z, 2), round(rnd.random() * 6.28, 3), round(0.8 + rnd.random() * 0.6, 3)])
    # Holo-Säule in der Mitte
    pb = B.part(cx, cz, "Buildings")
    G.cylinder(pb, cx, cz, CURB_H, 0.9, 1.6, "Concrete", segs=16)
    G.cylinder(pb, cx, cz, 0.9, 7.5, 0.35, "NeonCyan", segs=10)
    B.circ_col(cx, cz, 1.65, top=7.5, kind="monument")


def highway(out, rnd):
    """Hochstraße außerhalb der Mauer (W, N, O) – Kulisse."""
    R = EDGE + 70
    y = 13.0
    for (ax, az, bx, bz) in ((-R, -EDGE - 12, -R, R), (-R, R, R, R), (R, R, R, -EDGE - 12)):
        L = math.hypot(bx - ax, bz - az)
        dx, dz = (bx - ax) / L, (bz - az) / L
        f = Frame((ax + bx) / 2, (az + bz) / 2, math.atan2(dx, dz))
        G.box(out, f, 0, y, 0, 26, 1.6, L + 26, "ConcreteDark")
        for sx in (-12.6, 12.6):
            G.box(out, f, sx, y + 1.3, 0, 0.4, 1.0, L + 26, "Concrete")
            G.box(out, f, sx, y + 1.85, 0, 0.12, 0.1, L + 26, "NeonPink" if sx < 0 else "NeonCyan")
        for k in range(int(L // 40) + 1):
            G.box(out, f, 0, y / 2, -L / 2 + k * 40, 4, y, 2.5, "Concrete")


def skyline(out, rnd):
    for i in range(240):
        ang = rnd.random() * 2 * math.pi
        r_ = 650 + rnd.random() ** 0.8 * 950
        x, z = r_ * math.sin(ang), r_ * math.cos(ang)
        if z < -EDGE - 60 and r_ < 900:          # über dem Wasser erst weiter weg
            continue
        h = 40 + rnd.random() ** 1.5 * 300
        w, d = 24 + rnd.random() * 40, 24 + rnd.random() * 40
        G.building(out, x, z, w, d, h, rnd.random() * math.pi, "FacGlass" if rnd.random() < 0.6 else "Facade", "Roof",
                   u_off=rnd.random() * 48, v_off=rnd.random() * 48)
        if h > 160 and rnd.random() < 0.6:
            f = Frame(x, z, 0)
            G.box(out, f, 0, h + 1.5, 0, w * 0.7, 3.0, d * 0.7, ("NeonPink", "NeonCyan", "NeonViolet")[int(rnd.random() * 3)])


# ----------------------------------------------------------------------
def make_templates():
    """Vorlagen für Wiederholteile (im Spiel als InstancedMesh)."""
    lamp = Part("Tpl_StreetLamp")
    G.cylinder(lamp, 0, 0, 0.0, 0.5, 0.2, "Concrete", segs=8)
    G.cylinder(lamp, 0, 0, 0.5, 8.3, 0.1, "Metal", segs=8, r_top=0.075)
    f = Frame(0, 0, 0)
    G.box(lamp, f, 0, 8.3, 1.0, 0.1, 0.1, 2.2, "Metal")
    G.box(lamp, f, 0, 8.32, 2.05, 0.36, 0.12, 0.85, "Metal")
    G.box(lamp, f, 0, 8.24, 2.05, 0.28, 0.04, 0.7, "LampHead")
    sig = Part("Tpl_Signal")
    G.cylinder(sig, 0, 0, 0.0, 6.0, 0.12, "SignalBody", segs=8)
    G.box(sig, f, 0, 5.8, 2.3, 0.12, 0.14, 4.6, "SignalBody")
    G.box(sig, f, 0, 5.55, 4.4, 0.42, 1.15, 0.32, "SignalBody")        # Kopf am Armende
    G.box(sig, f, 0, 3.1, 0.25, 0.36, 1.0, 0.28, "SignalBody")         # kleiner Kopf am Mast
    tree = Part("Tpl_Tree")
    G.cylinder(tree, 0, 0, 0.0, 2.6, 0.17, "Bark", segs=7, r_top=0.12)
    # Krone: drei gestapelte, flache „Kugeln“ aus Kegelstümpfen
    for (y0, y1, rb, rt) in ((2.2, 3.6, 1.9, 2.3), (3.6, 5.0, 2.3, 1.5), (5.0, 5.9, 1.5, 0.2)):
        G.cylinder(tree, 0, 0, y0, y1, rb, "Leaves", segs=9, r_top=rt, top=y1 > 5.5)
    cone = Part("Prop_Cone")
    G.box(cone, f, 0, 0.015, 0, 0.38, 0.03, 0.38, "Rubber")
    G.cylinder(cone, 0, 0, 0.03, 0.34, 0.15, "Cone", segs=14, top=False, r_top=0.095)
    G.cylinder(cone, 0, 0, 0.34, 0.47, 0.095, "ConeBand", segs=14, top=False, r_top=0.062)
    G.cylinder(cone, 0, 0, 0.47, 0.70, 0.062, "Cone", segs=14, top=True, r_top=0.022)
    return {"Tpl_StreetLamp": lamp, "Tpl_Signal": sig, "Tpl_Tree": tree, "Prop_Cone": cone}


# ----------------------------------------------------------------------
MAP_COLORS = {"walk": (58, 62, 72), "median": (40, 70, 44), "park": (34, 84, 48), "downtown": (92, 104, 134),
              "market": (120, 70, 128), "residential": (96, 104, 88), "harbor": (86, 86, 92), "mixed": (90, 92, 110),
              "container": (150, 70, 50)}


def minimap(B, path, size=1024, span=1024.0):
    img = Image.new("RGB", (size, size), (12, 14, 20))
    d = ImageDraw.Draw(img)
    s = size / span

    # Norden (+z) oben, Osten (−x) rechts – so liegt „links vom Auto“ auch links auf der Karte
    def rect(x0, z0, x1, z1, fill, grow=0):
        u0, u1 = (span / 2 - x1) * s, (span / 2 - x0) * s
        v0, v1 = (span / 2 - z1) * s, (span / 2 - z0) * s
        d.rectangle([u0 - grow, v0 - grow, u1 + grow, v1 + grow], fill=fill)

    rect(-span / 2, -span / 2, span / 2, -EDGE - 12, (10, 34, 56))         # Wasser
    rect(-EDGE, -EDGE - 12, EDGE, EDGE, (36, 38, 46))                      # Straßen
    order = ["walk", "median", "park", "harbor", "mixed", "residential", "market", "downtown", "container"]
    for kind in order:
        for (k, (x0, z0, x1, z1)) in B.minimap:
            if k == kind:
                rect(x0, z0, x1, z1, MAP_COLORS[k])
    for (x0, z0, x1, z1) in ((-EDGE - 1.2, -EDGE - 12, -EDGE, EDGE + 1.2), (EDGE, -EDGE - 12, EDGE + 1.2, EDGE + 1.2),
                             (-EDGE - 1.2, EDGE, EDGE + 1.2, EDGE + 1.2)):
        rect(x0, z0, x1, z1, (0, 200, 230), grow=1)
    img.save(path, optimize=True)
    # Bildpunkt (u, v) = ((span/2 − x)·s, (span/2 − z)·s)
    return {"file": ID + "_map.png", "span": span, "size": size}
