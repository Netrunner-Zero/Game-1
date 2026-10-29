// Einstellungen (werden im localStorage gespeichert).
//
// interiorLight      Innenraumbeleuchtung 0..1 (0 = aus). Standard bewusst dunkel: 25 %.
// displayBrightness  Helligkeit von Displays und Instrumenten 0..1 (Standard 70 %).
// quality            'auto' | 'low' | 'medium' | 'high'
// exposure           Belichtung (ACES Filmic Tone Mapping), 0.5..1.6
// bloom              Leuchten um helle Flächen (nur Qualität Mittel/Hoch)
// showFps            Leistungsanzeige
// lodMode            'auto' | '0' | '1' | '2' (Detailstufe erzwingen, zum Testen)

const KEY = 'neonHaven.settings.v1';

export const DEFAULT_SETTINGS = Object.freeze({
  interiorLight: 0.25,
  displayBrightness: 0.7,
  quality: 'auto',
  exposure: 1.0,
  bloom: true,
  showFps: false,
  lodMode: 'auto',
});

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const data = JSON.parse(raw);
    return typeof data === 'object' && data ? data : {};
  } catch (e) {
    return {};
  }
}

export class Settings extends EventTarget {
  constructor() {
    super();
    this.values = { ...DEFAULT_SETTINGS, ...load() };
    // Werte absichern
    this.values.interiorLight = clamp01(Number(this.values.interiorLight));
    this.values.displayBrightness = clamp01(Number(this.values.displayBrightness));
    if (!['auto', 'low', 'medium', 'high'].includes(this.values.quality)) this.values.quality = 'auto';
  }

  get(key) {
    return this.values[key];
  }

  set(key, value) {
    if (this.values[key] === value) return;
    this.values[key] = value;
    this.save();
    this.dispatchEvent(new CustomEvent('change', { detail: { key, value } }));
  }

  reset() {
    this.values = { ...DEFAULT_SETTINGS };
    this.save();
    for (const key of Object.keys(DEFAULT_SETTINGS)) {
      this.dispatchEvent(new CustomEvent('change', { detail: { key, value: this.values[key] } }));
    }
  }

  save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(this.values));
    } catch (e) {
      /* privater Modus o. Ä. – Einstellungen gelten dann nur für diese Sitzung */
    }
  }

  // Qualität, die tatsächlich verwendet wird ('auto' wird anhand des Geräts aufgelöst)
  resolvedQuality() {
    const q = this.values.quality;
    if (q !== 'auto') return q;
    const touch = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
    const cores = navigator.hardwareConcurrency || 4;
    if (touch) return cores >= 8 ? 'medium' : 'low';
    return cores >= 6 ? 'high' : 'medium';
  }
}

function clamp01(v) {
  return Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0;
}

// Qualitätsstufen: Detailgrad, Schatten, Reflexionen
export const QUALITY = {
  low: {
    pixelRatio: 1.0, shadows: false, shadowSize: 0, envSize: 128, clearcoat: false, bloom: false,
    lodDistances: [7, 20], antialias: false, maxAnisotropy: 2,
  },
  medium: {
    pixelRatio: 1.5, shadows: true, shadowSize: 1024, envSize: 256, clearcoat: true, bloom: true,
    lodDistances: [12, 32], antialias: true, maxAnisotropy: 4,
  },
  high: {
    pixelRatio: 2.0, shadows: true, shadowSize: 2048, envSize: 512, clearcoat: true, bloom: true,
    lodDistances: [20, 50], antialias: true, maxAnisotropy: 8,
  },
};
