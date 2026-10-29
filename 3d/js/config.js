// Gemeinsame Konstanten. Einheiten: Meter, Sekunden, m/s.
// Koordinaten: Der Spieler fährt in Richtung -z, +x ist rechts.

export const KMH = 1 / 3.6;

// Eigene Fahrbahn: 4 Spuren, Spur 0 ist die linke Überholspur
export const LANE_X = [-5.4, -1.8, 1.8, 5.4];
// Gegenfahrbahn hinter der Mittelschutzwand
export const ONCOMING_X = [-11.8, -15.4, -19.0, -22.6];

export const ROAD = {
  left: -27.8,        // Asphaltkante links (inkl. Gegenfahrbahn und Bankett)
  right: 10.6,        // Asphaltkante rechts (inkl. Standstreifen und Bankett)
  median: -8.6,       // Betonschutzwand in der Mitte
  railRight: 10.25,   // Leitplanke rechts
  railLeft: -27.45,   // Leitplanke links (Gegenfahrbahn)
};

// Seitlicher Bewegungsraum des Spielers (Standstreifen ist befahrbar)
export const PLAYER_BOUNDS = { min: -7.35, max: 9.2 };

export const Z_NEAR = 60;     // so weit reicht die Kulisse hinter den Spieler
export const Z_FAR = -980;    // so weit reicht die Kulisse nach vorn
export const SPAWN_AHEAD = 620;

export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const smoothstep = (a, b, x) => {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};
export const rand = (a, b) => a + Math.random() * (b - a);
export const pick = arr => arr[Math.floor(Math.random() * arr.length)];
