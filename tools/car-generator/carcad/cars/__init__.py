"""Fahrzeugbeschreibungen. Jedes Modul liefert SPEC (dict)."""

ORDER = ["vektra", "brawler", "ion", "rhino", "pulse", "aurelion"]


def S(z, w, yb, yt, cr):
    """Karosserie-Station: Länge z, halbe Breite w, Unterkante yb, Schulter yt, Wölbung cr."""
    return {"z": z, "w": w, "yb": yb, "yt": yt, "cr": cr}


def C(z, wb, wt, y1, kind="roof"):
    """Kabinenstation. y1 > 0: absolute Höhe; y1 <= 0: so viel über der Haube.
    kind: ws (Frontscheibe), roof, glassroof, pillar (B-Säule), rear (Heckscheibe)."""
    return {"z": z, "wb": wb, "wt": wt, "y1": y1, "kind": kind}
