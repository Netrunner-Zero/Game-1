# Game-1 – Highway Dodge

Zwei Autospiele für den Browser: eine schlichte 2D-Version und eine 3D-Version mit möglichst realistischer Grafik. Beide laufen am PC und auf dem Handy.

## Highway Dodge (2D)

Ein kleines 2D-Autospiel, geschrieben in reinem HTML, CSS und JavaScript (ohne Bibliotheken, ohne Bilddateien).

Du steuerst ein rotes Auto auf einer dreispurigen, vertikal scrollenden Straße und musst dem Gegenverkehr ausweichen. Mit der Zeit wird das Spiel immer schneller. Punkte gibt es für die gefahrene Strecke; der Highscore wird im `localStorage` des Browsers gespeichert.

| Gerät | Steuerung |
|-------|-----------|
| PC    | Pfeiltasten ← / → (alternativ A / D), Enter startet das Spiel |
| Handy | Auf die linke oder rechte Bildschirmhälfte tippen oder nach links/rechts wischen |

Das Spiel ist für das Hochformat auf dem Handy optimiert. Auf breiten Bildschirmen wird das Spielfeld mittig im Hochformat angezeigt. Das ganze Spiel steckt in `index.html`.

## Highway Dodge 3D

Ein Endlos-Rennspiel auf einer vierspurigen Autobahn, gebaut mit [Three.js](https://threejs.org) (wird per CDN geladen). Die Kamera fährt hinter dem Auto her.

- Verkehr aus Autos, SUVs, Transportern, Lkws und Bussen; die anderen Fahrer halten Abstand, überholen links und blinken vor dem Spurwechsel. Auf der Gegenfahrbahn kommt Gegenverkehr.
- Das Tempo steigt mit der Zeit. Punkte gibt es für die Strecke, Bonuspunkte für knappes Überholen (mehrere hintereinander geben einen Multiplikator). Der Highscore wird im `localStorage` gespeichert.
- Tag-Nacht-Wechsel: Nach gut einer Minute geht die Sonne unter, nachts leuchten Scheinwerfer, Rücklichter und Laternen.
- Grafik: weiche Schatten, Spiegelungen im Lack, Nebel in der Ferne, Wolken, Leuchteffekte (Bloom) und Fahrtwind. Fahrzeuge, Straße, Bäume und Texturen werden im Code erzeugt, es gibt keine Bild- oder Modelldateien.
- Ton: Motor mit Gangwechseln, Fahrtwind, Vorbeifahrgeräusche und Crash, alles mit der Web Audio API erzeugt.
- Die Grafikstufe (Niedrig/Mittel/Hoch) passt sich auf „Auto“ selbst an die Bildrate an und lässt sich im Menü auch von Hand wählen.

| Gerät | Steuerung |
|-------|-----------|
| PC    | ← / → lenken, ↑ Gas, ↓ Bremse (alternativ W A S D), P oder Esc: Pause |
| Handy | Linke/rechte Bildschirmhälfte halten zum Lenken, Gas und Bremse als Buttons unten. Alternativ im Menü „Neigen“ wählen und das Handy wie ein Lenkrad kippen. |

Das Auto fährt von selbst; Gas und Bremse sind optional. Geht das Spiel in den Hintergrund (Tab wechseln, App verlassen), pausiert es automatisch.

Die Dateien liegen im Ordner `3d/` (`index.html`, `style.css` und die Module in `3d/js/`).

## Spiele starten

Am einfachsten über GitHub Pages: Unter **Settings → Pages** den Branch auswählen, dann ist die 2D-Version unter `https://<name>.github.io/Game-1/` und die 3D-Version unter `https://<name>.github.io/Game-1/3d/` erreichbar. Die beiden Spiele verlinken sich gegenseitig.

Lokal:

- **2D:** `index.html` im Browser öffnen (Doppelklick genügt).
- **3D:** braucht einen kleinen Webserver, weil der Browser JavaScript-Module nicht direkt von der Festplatte lädt, und eine Internetverbindung für Three.js:
  ```bash
  python3 -m http.server 8000
  ```
  Danach `http://localhost:8000/3d/` aufrufen bzw. auf dem Handy im selben WLAN `http://<IP-des-Rechners>:8000/3d/`. Die Neigungssteuerung funktioniert auf dem Handy nur über HTTPS (z. B. GitHub Pages).
