# Game-1 – Neon Haven

Hier entsteht ein 3D-Autospiel in einer futuristischen Stadt (**Neon Haven**). Zurzeit gibt es:

- **das Spiel** (`game/`, in Arbeit): die Stadt Neon Haven und ein Testgelände, echte Fahrphysik, Steuerung per
  Touch, Tastatur und Xbox-Controller, fünf Kameras, Tageszeit – Regen und Verkehr folgen,
- **die Fahrzeug-Garage** (`garage/`): sechs detaillierte 3D-Autos zum Ansehen, Tunen und Testen,
- **Highway Dodge** (`index.html`): das ursprüngliche kleine 2D-Ausweichspiel (siehe unten).

## Spiel (Open World, in Arbeit)

- **Online (Branch `open-world`):** <https://raw.githack.com/Netrunner-Zero/Game-1/open-world/game/index.html>
- **Lokal:** `python3 -m http.server 8000` im Projektordner, dann `http://localhost:8000/game/`

**Neon Haven** (Karte `neon_haven`, ca. 900 × 900 m): Straßenraster mit Neon-Boulevard und Zentralboulevard
(2 × 3 Spuren, Mittelstreifen mit Bäumen), Avenuen und Gassen, 15 cm hohe Gehwege mit Bordstein, Zebrastreifen und
Ampeln an jeder Kreuzung (schalten wirklich), Laternen. Viertel: **Downtown** (Glastürme bis ~280 m mit Werbetafeln
und Neon-Kronen), **Neon-Markt** (Läden, Leuchtreklame), **Wohnviertel**, **Lichtpark**, **Altstadt** und **Hafen**
(Lagerhallen, Containerlager, Kräne, Kai). Rundherum eine Mauer mit Hochstraße und Skyline, im Süden Wasser.
Minikarte oben rechts (dreht sich mit, N zeigt nach Norden).

**Testgelände** (Karte `testgelaende`, im Menü unter „Welt“): 1,15 km lange Gerade (Bremspunkte bei 300/200/100 m),
Kreisbahn, Slalom und Ausweichtest (Pylonen fliegen weg), Tisch-Sprung, Kicker, Rüttel- und Wellenstrecke,
Crashwand mit Reifenstapeln und Containern. Tageszeit frei einstellbar (auch nachts).

| Was | Tastatur | Xbox-Controller | Touch |
|-----|----------|-----------------|-------|
| Gas / Bremse | W / S (Pfeile) | RT / LT | GAS / BREMSE rechts |
| Rückwärts | im Stand S halten | im Stand LT halten | im Stand BREMSE halten |
| Lenken | A / D | linker Stick | links wischen · Neigen · Tasten (Menü) |
| Handbremse | Leertaste | A | HANDBREMSE |
| Kamera (Verfolger, weit, Haube, Stoßstange, Cockpit) | C | Y | Kamera-Knopf |
| Umschauen / nach hinten | Maus ziehen / B | rechter Stick / B | Bild ziehen |
| Licht, Blinker, Warnblinker | L, Q/E, X | X, LB/RB, Steuerkreuz ↓ | Licht-Knopf |
| Zurücksetzen (2× = zum Start) | R | Ansicht-Taste | ⟲ |
| Menü (Auto, Fahrhilfen, Tageszeit, Grafik, Ton) | Esc | Menü-Taste | ☰ |

**Fahrphysik** (`src/physics/CarPhysics.js`): Reifen mit Schlupf und Schräglauf (Reibungsellipse, Lastabhängigkeit),
Federung mit Stabilisatoren (Gewichtsverlagerung entsteht von selbst), Drehmomentkurve, Automatik, Differenzial
(Front/Heck/Allrad), Bremskraftverteilung, Handbremse, Hangabtrieb, Sprünge. Fahrhilfen **Voll / Sport / Aus**
(ABS, ASR, ESP, Gegenlenk-Hilfe). Das Tuning aus der Garage wirkt: mehr Leistung, Käfig = mehr Gewicht,
Tieferlegung = tieferer Schwerpunkt. **Kollisionen** (`src/physics/collision.js`): gedrehte Rechtecke und Kreise mit
Stoß und Reibung, Hindernisse in einem Raster, auch bei 300 km/h kein Durchtunneln. **Ton** wird live erzeugt
(Motor nach Zylinderzahl, Elektro-Pfeifen, Reifen, Wind, Aufprall).

Tests ohne Browser:

```bash
node tests/physics.test.mjs      # 0–100, Vmax, Bremsweg, Querbeschleunigung, Rückwärts, Handbremse, Stabilität
node tests/collision.test.mjs    # Mauer mit 300 km/h, Wand streifen, Pfosten, Auto gegen Auto
node tests/world.test.mjs        # Testgelände abfahren: Gerade, Sprung, Wellen, Crashwand, Kreisbahn
node tests/city.test.mjs         # Stadt: Startplätze, Bordsteine, Ampelzyklus, Boulevard-Fahrt, Häuser
node tests/smoke/run.mjs         # ganzes Spiel mit Ersatz-three.js: Laden, Fahren, Kameras, Menü, Autowechsel, Nacht, Touch
```

Die Karten erzeugt `tools/world-generator` (Python, wie die Autos): `python3 tools/world-generator/generate.py`
schreibt `world/<karte>.glb` (Grafik in Kacheln) und `world/<karte>.json` (Kollisionen, Gehwege/Rampen, Laternen,
Ampeln und Bäume als Positionen für Instancing, Ampelphasen, Spurgraph für den Verkehr, Startplätze, Viertel,
Minikarte). Ansehen ohne Browser: `python3 tools/world-generator/qa/render_map.py bild.png world/neon_haven.glb
--eye=-4.2,1.5,-150 --target=-4.2,3.5,-110`.

## Garage öffnen

- **Online (Branch `fahrzeuge-v4`):**
  <https://raw.githack.com/Netrunner-Zero/Game-1/fahrzeuge-v4/garage/index.html>
  (nach dem Zusammenführen in `main` entsprechend `…/main/garage/index.html`)
- **Lokal:** im Projektordner `python3 -m http.server 8000` starten und `http://localhost:8000/garage/` öffnen.
  Die Garage braucht einen Webserver (wegen der Modelldateien) und lädt three.js aus dem Netz.

Läuft auf dem Handy (Hoch- und Querformat) und am PC.

### Bedienung

| Was | Wie |
|-----|-----|
| Auto drehen / zoomen | ziehen bzw. zwei Finger / Mausrad |
| Kamera | Knopf oben: **Außen → Cockpit → Haube**; im Cockpit ziehen zum Umschauen |
| Auto wählen | Leiste mit den sechs Autos |
| Tunen | Feld „Tuning“ (auf dem Handy oben rechts aufklappen): Lack, Felgen, Aero, Motor, Innen |
| Testen | unten: Lenkung, Gas, Bremse, Licht, Blinker ◀ ▶, Drehteller |
| Tag / Nacht | ☾ / ☀ |
| Einstellungen | ⚙ |

## Die Fahrzeuge

| Auto | Klasse | Antrieb | Leistung | Gewicht | Besonderheiten |
|------|--------|---------|----------|---------|----------------|
| **Vektra GT** | Supersportwagen | Heck, V8 | 470 kW | 1.380 kg | Mittelmotor sichtbar unter der Heckscheibe, Rennschalen, Carbon |
| **Brawler 77** | Muscle Car | Heck, V8 | 450 kW | 1.650 kg | Chromgrill mit vier Rundscheinwerfern, Kompressor, Sidepipes, Retro-Cockpit |
| **Ion Spectre** | Elektro-Hypercar | Allrad, elektrisch | 1.100 kW | 1.850 kg | Glaskanzel, Lichtbänder, Kameraspiegel, Yoke-Lenkrad |
| **Rhino X** | Geländewagen | Allrad, V8 | 330 kW | 2.400 kg | Starrachsen, Reserverad, Schnorchel, Seilwinde, Hochauspuff |
| **Pulse** | Hot Hatch | Front, Turbo | 235 kW | 1.250 kg | Lichtband vorne und hinten, Rallye-Paket, Karostoff-Sitze |
| **Aurelion S** | Luxuslimousine | Heck, V12 | 450 kW | 2.350 kg | Chromgrill, Kühlerfigur, Zweifarblack, Sternenhimmel, Fond mit Champagner |

Jedes Auto hat einen eigenen Innenraum mit drehendem Lenkrad, Pedalen, live gezeichneten Instrumenten und
Bildschirmen (Tempo, Drehzahl, Gang, Navigation) sowie versteckte Easter Eggs.

### Tuning (alle Autos)

- **Lack:** Farbe, Lackart (Glanz, Metallic, Perleffekt, Satin, Matt, Chrom), Dach-/Zweitfarbe, 3 Folierungen in jeder Farbe
- **Felgen:** 3 Designs je Auto, Felgen- und Bremssattelfarbe, Tieferlegung
- **Aero:** 3 Spoiler, Scheibentönung, Neon-Unterbodenbeleuchtung
- **Motor:** 3 sichtbare Motorstufen (z. B. Hutzen, Turbos, Schnorchel, Zusatzscheinwerfer), 3 Auspuffanlagen,
  Halb- oder Vollkäfig
- **Innen:** Farbe der Ambientebeleuchtung
- **Werkszustand:** setzt das Tuning des Autos zurück

Das Tuning wird je Auto im Browser gespeichert (`localStorage`, Schlüssel `neonHaven.tuning.v1`).

## Einstellungen

| Einstellung | Standard | Wirkung |
|-------------|----------|---------|
| Innenraumbeleuchtung | 25 % | Ambiente, Sternenhimmel, Innenlicht – 0 % = komplett aus |
| Displays & Instrumente | 70 % | Helligkeit aller Bildschirme und Instrumente, unabhängig vom Innenlicht |
| Belichtung | 1,00 | Gesamthelligkeit (ACES-Filmic-Tonemapping, nichts überstrahlt – auch nachts nicht) |
| Grafikqualität | Automatisch | Niedrig / Mittel / Hoch: Auflösung, Schatten, Spiegelungen, Klarlack, Detailstufen-Abstände |
| Detailstufe (LOD) | Automatisch | zum Testen erzwingen: volle Details, Mittel oder Fern |
| Leuchteffekt (Bloom) | an | Glühen heller Lichter (nur Mittel/Hoch) |
| Leistungsanzeige | aus | FPS, Dreiecke, Draw Calls, aktuelle Detailstufe |

Alle Einstellungen werden gespeichert (`neonHaven.settings.v1`). **Leistungstest:** im Einstellungsfenster stellt
der Knopf „Leistungstest (12 Autos)“ zwölf Autos in verschiedene Entfernungen, fährt 8 Sekunden mit der Kamera
herum und zeigt FPS, langsamstes Bild, Dreiecke und Draw Calls.

## Leistung

Jedes Auto gibt es in drei Detailstufen. Gewechselt wird nach Entfernung zur Kamera (mit etwas Spielraum gegen
Flackern):

| Qualität | volle Details bis | mittlere Details bis | danach |
|----------|-------------------|----------------------|--------|
| Niedrig (Handys) | 7 m | 20 m | Fern |
| Mittel | 12 m | 32 m | Fern |
| Hoch | 20 m | 50 m | Fern |

Budget je Auto (Standard-Tuning, inklusive Innenraum; gemessen mit `tools/car-generator/qa/check.py`):

| Auto | Detailstufe 0 (nah) | Detailstufe 1 | Detailstufe 2 (fern) | Datei |
|------|---------------------|---------------|----------------------|-------|
| Vektra GT | 116 k Dreiecke · 143 Draw Calls | 24 k · 50 | 15 k · 24 | 6,4 MB |
| Brawler 77 | 115 k · 136 | 20 k · 46 | 10 k · 23 | 6,0 MB |
| Ion Spectre | 106 k · 134 | 21 k · 47 | 12 k · 22 | 5,9 MB |
| Rhino X | 131 k · 147 | 25 k · 59 | 13 k · 26 | 6,9 MB |
| Pulse | 118 k · 141 | 21 k · 50 | 13 k · 27 | 6,2 MB |
| Aurelion S | 120 k · 134 | 19 k · 48 | 11 k · 24 | 6,1 MB |

Geometrien und Texturen werden zwischen Autos desselben Modells geteilt; jedes Auto hat nur eigene Materialien
(für das Tuning).

## Fahrzeuge im eigenen Code verwenden

```js
import { VehicleLibrary } from './src/vehicles/VehicleLibrary.js';
import { defaultTuning } from './src/vehicles/Vehicle.js';

const lib = new VehicleLibrary('models/', renderer);
await lib.init();                                  // liest models/cars.json
const car = await lib.create('pulse');             // Vehicle-Objekt
scene.add(car.object);
car.applyTuning({ ...defaultTuning(car.meta), paint: '#ff2bd6', spoiler: 2, engine: 3 });
car.state.speedKmh = 80; car.state.steer = 0.3;    // Räder, Lenkrad, Instrumente folgen
car.update(dt, time);                              // jedes Bild
car.updateLOD(camera, [12, 32]);                   // Detailstufe nach Entfernung
```

`cars.json` enthält für jedes Auto Maße, Radpositionen, Fahrphysik-Werte (Masse, Leistung, Gänge, Federung …),
die Namen aller Tuning-Stufen und die Kamerapunkte. Aufbau der Modelldateien: siehe `models/README.md`.

## Fahrzeuge neu erzeugen

Die Autos werden nicht modelliert, sondern von einem Python-Programm berechnet (`tools/car-generator`).
Benötigt Python 3.9+ mit `numpy` und `Pillow`.

```bash
python3 tools/car-generator/generate.py            # alle Autos (dauert ein paar Minuten)
python3 tools/car-generator/generate.py pulse      # nur ein Auto
python3 tools/car-generator/generate.py --tex      # gemeinsame Texturen neu erzeugen
```

Jedes Auto ist eine Beschreibung in `tools/car-generator/carcad/cars/<name>.py` (Karosserie-Querschnitte,
Glashaus, Räder, Lampen, Anbauteile, Innenraum, Tuning, Easter Eggs).

Prüfen ohne Browser:

```bash
python3 tools/car-generator/qa/check.py                      # Aufbau + Leistungsbudget aller Autos
python3 tools/car-generator/qa/sheet.py out.png models/pulse.glb front34 rear34 side --set Engine=3
```

## Highway Dodge (2D)

Ein kleines 2D-Autospiel, geschrieben in reinem HTML, CSS und JavaScript (ohne Bibliotheken, ohne Bilddateien).

Du steuerst ein rotes Auto auf einer dreispurigen, vertikal scrollenden Straße und musst dem Gegenverkehr ausweichen. Mit der Zeit wird das Spiel immer schneller. Punkte gibt es für die gefahrene Strecke; der Highscore wird im `localStorage` des Browsers gespeichert.

| Gerät | Steuerung |
|-------|-----------|
| PC    | Pfeiltasten ← / → (alternativ A / D), Enter startet das Spiel |
| Handy | Auf die linke oder rechte Bildschirmhälfte tippen oder nach links/rechts wischen |

Das Spiel steckt komplett in `index.html`: direkt im Browser öffnen oder über `python3 -m http.server 8000`
(dann `http://localhost:8000`, auf dem Handy `http://<IP-des-Rechners>:8000`).
