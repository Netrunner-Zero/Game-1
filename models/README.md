# Fahrzeugmodelle (glTF 2.0)

Alle Dateien in diesem Ordner werden von `tools/car-generator` erzeugt – **nicht von Hand bearbeiten**,
sondern den Generator anpassen und neu bauen (siehe Haupt-README).

| Datei | Inhalt |
|-------|--------|
| `cars.json` | Liste aller Autos mit Daten fürs Spiel (Maße, Räder, Physik, Tuning-Namen, Kamera-Punkte …) |
| `*.glb` | ein Auto je Datei: Karosserie, Innenraum, Räder, alle Tuning-Teile, 3 Detailstufen |
| `textures/` | gemeinsame Texturen (Carbon, Leder-Normalen, Reifenprofil, Bremsscheibe …) |

Einheiten: Meter. Achsen: **+Y oben, +Z vorne, +X links** (Fahrerseite links). Der Ursprung liegt am Boden
in der Mitte zwischen den Achsen.

## Knoten

Die Szene hat genau einen Wurzelknoten (das Auto). Dessen direkte Kinder sind die Bauteile; das Spiel liest
alles über die `extras` der Knoten (in three.js: `object.userData`).

| Knoten | extras | Bedeutung |
|--------|--------|-----------|
| `Body` → `Body_L0/L1/L2` | `lod` | Karosserie, Glas, Lampen, Anbauteile |
| `Cockpit` → `Cockpit_L0/L1/L2` | `lod` | Innenraum (L2 ist leer) |
| `SteeringWheel` | `anim: "steering"` | dreht um die eigene Z-Achse |
| `Needle_Speed`, `Needle_RPM` | `anim: "needle"`, `gauge` | nur bei analogen Instrumenten |
| `Pedal_Brake`, `Pedal_Throttle` | `anim: "pedal"`, `pedal` | kippen um die X-Achse |
| `Wheel_FL/FR/RL/RR` | `wheel`, `steer`, `radius`, `drive` | Rad mit Reifen, Bremse und allen Felgen |
| `Rim_<n>_<Rad>` | `tune: "rim"`, `variant` | Felgendesign n (nur eines sichtbar) |
| `Caliper_FL/…` | `caliper`, `steer` | Bremssattel (dreht mit der Lenkung, nicht mit dem Rad) |
| `Spoiler_1..3` | `tune: "spoiler"`, `variant` | |
| `Livery_1..3` | `tune: "livery"`, `variant` | Folierung (Farbe über Material `Livery`) |
| `Exhaust_1..n` | `tune: "exhaust"`, `variant` | Auspuffanlage |
| `RollCage_1..2` | `tune: "cage"`, `variant` | Halb-/Vollkäfig |
| `EngineStage_1..3` | `tune: "engine"`, `stage` | sichtbare Motor-Stufen, **aufbauend** (Stufe 2 zeigt 1 und 2) |
| `Plate_Front/Rear` | `plate` | Kennzeichen |
| `Underglow` | `tune: "neon"` | Unterbodenbeleuchtung |
| `Axles` | `unsprung: true` | Starrachsen (Rhino X): bleiben beim Tieferlegen auf Radhöhe |
| `ContactShadow` | `shadow: true` | weicher Bodenschatten (AO) |
| `Cam_Cockpit`, `Cam_Hood`, `Seat_Driver` | `helper` | Kamera- und Sitzpunkte |

**Detailstufen:** Unter einem Elternknoten liegen Kinder mit `lod: 0, 1, 2`. Sichtbar ist das Kind mit
`lod == min(Stufe, höchste vorhandene Stufe)`. Hat eine Gruppe nur `lod: 0` (z. B. Bremssättel), ist sie nur in
Stufe 0 sichtbar.

## Materialien

Materialien mit gleichem Namen haben in allen Autos dieselbe Rolle:

| Material | Rolle |
|----------|-------|
| `Paint`, `Paint2` | Lack und Dach-/Zweitfarbe (`Paint2` fehlt bei Autos ohne lackiertes Dach) |
| `Rim`, `Caliper`, `Livery`, `Glass` | per Tuning eingefärbt bzw. getönt |
| `Accent`, `Underglow` | Leuchtakzente/Neon (`extras.group = "neon"`) |
| `Headlight`, `DRL`, `Taillight`, `Brakelight`, `Reverse`, `Indicator`, `IndicatorR` | Lichter (`extras.group = "lights"`, `extras.light` = Art, `IndicatorR` = rechte Blinker) |
| `InteriorAmbient`, `Starlight`, `DomeLight`, `Hologram` | Innenraumlicht (`extras.group = "interior"`) – Regler „Innenraumbeleuchtung“ |
| `Display_Cluster`, `Display_Center`, `Display_Rear` | Bildschirme (`extras.group = "display"`, `extras.canvas`) – werden zur Laufzeit live gezeichnet |

`extras.base` ist die Grundhelligkeit (emissive), `extras.active` die Helligkeit im eingeschalteten Zustand
(Bremslicht, Rückfahrlicht, Blinker).

In der Ferne (L1/L2) teilen sich dunkle Kleinteile ein Material, damit weniger Draw Calls entstehen;
Lichtmaterialien bleiben immer getrennt, damit Scheinwerfer und Rückleuchten auch weit weg funktionieren.
