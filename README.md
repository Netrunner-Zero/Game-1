# Game-1 – Highway Dodge

Ein kleines 2D-Autospiel für den Browser, geschrieben in reinem HTML, CSS und JavaScript (ohne Bibliotheken, ohne Bilddateien).

Du steuerst ein rotes Auto auf einer dreispurigen, vertikal scrollenden Straße und musst dem Gegenverkehr ausweichen. Mit der Zeit wird das Spiel immer schneller. Punkte gibt es für die gefahrene Strecke; der Highscore wird im `localStorage` des Browsers gespeichert.

## Steuerung

| Gerät | Steuerung |
|-------|-----------|
| PC    | Pfeiltasten ← / → (alternativ A / D), Enter startet das Spiel |
| Handy | Auf die linke oder rechte Bildschirmhälfte tippen oder nach links/rechts wischen |

Das Spiel ist für das Hochformat auf dem Handy optimiert. Auf breiten Bildschirmen wird das Spielfeld mittig im Hochformat angezeigt.

## Spiel starten

Das ganze Spiel steckt in der Datei `index.html`.

- **Direkt:** `index.html` im Browser öffnen (Doppelklick genügt).
- **Über einen lokalen Server** (z. B. zum Testen auf dem Handy im selben WLAN):
  ```bash
  python3 -m http.server 8000
  ```
  Danach `http://localhost:8000` aufrufen bzw. auf dem Handy `http://<IP-des-Rechners>:8000`.
