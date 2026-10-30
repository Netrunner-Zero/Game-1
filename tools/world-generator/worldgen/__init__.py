"""Neon Haven – Welt-Generator (Karten als glTF + JSON).

Nutzt die Geometrie- und glTF-Bausteine des Fahrzeug-Generators (tools/car-generator/carcad).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAR_GEN = os.path.normpath(os.path.join(HERE, "..", "..", "car-generator"))
if CAR_GEN not in sys.path:
    sys.path.insert(0, CAR_GEN)
