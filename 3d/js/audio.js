// Ton: Motor, Fahrtwind, Abrollgeräusch, Crash, Vorbeifahrten.
// Alles wird mit der Web Audio API erzeugt, es gibt keine Sounddateien.
const GEARS = [0, 55, 95, 140, 185, 235, 400]; // km/h-Grenzen der Gänge

function distortionCurve(k) {
  const n = 1024, curve = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1;
    curve[i] = ((1 + k) * x) / (1 + k * Math.abs(x));
  }
  return curve;
}

export class GameAudio {
  constructor() {
    this.ctx = null;
    this.enabled = true;
    this.lastWhoosh = 0;
  }

  // Muss aus einer Nutzeraktion heraus aufgerufen werden (Autoplay-Regeln der Browser)
  init() {
    if (this.ctx) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    let ctx;
    try {
      ctx = new AC();
    } catch {
      return;
    }
    this.ctx = ctx;
    this.master = ctx.createGain();
    this.master.gain.value = this.enabled ? 0.75 : 0;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -12;
    comp.ratio.value = 4;
    this.master.connect(comp);
    comp.connect(ctx.destination);

    const len = ctx.sampleRate * 2;
    this.noise = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = this.noise.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;

    // Motor: drei Oszillatoren → Verzerrung → Tiefpass
    const shaper = ctx.createWaveShaper();
    shaper.curve = distortionCurve(5);
    this.engFilter = ctx.createBiquadFilter();
    this.engFilter.type = 'lowpass';
    this.engFilter.Q.value = 1.2;
    this.engine = ctx.createGain();
    this.engine.gain.value = 0;
    shaper.connect(this.engFilter);
    this.engFilter.connect(this.engine);
    this.engine.connect(this.master);
    this.oscs = [];
    for (const [type, mul, gain, detune] of [['sawtooth', 1, 0.45, 0], ['sawtooth', 0.5, 0.6, 7], ['square', 2, 0.08, -5]]) {
      const o = ctx.createOscillator();
      o.type = type;
      o.detune.value = detune;
      o.frequency.value = 60 * mul;
      const g = ctx.createGain();
      g.gain.value = gain;
      o.connect(g);
      g.connect(shaper);
      o.start();
      this.oscs.push({ o, mul });
    }

    // Rauschen für Fahrtwind, Abrollgeräusch und Schleifen an der Leitplanke
    const src = ctx.createBufferSource();
    src.buffer = this.noise;
    src.loop = true;
    src.start();
    const chain = (type, freq, q) => {
      const f = ctx.createBiquadFilter();
      f.type = type;
      f.frequency.value = freq;
      f.Q.value = q;
      const g = ctx.createGain();
      g.gain.value = 0;
      src.connect(f);
      f.connect(g);
      g.connect(this.master);
      return [f, g];
    };
    [this.windF, this.wind] = chain('bandpass', 800, 0.6);
    [this.roadF, this.road] = chain('lowpass', 260, 0.7);
    [this.scrapeF, this.scrape] = chain('bandpass', 2600, 3);
  }

  resume() {
    if (this.ctx && this.ctx.state !== 'running') this.ctx.resume().catch(() => {});
  }

  suspend() {
    if (this.ctx && this.ctx.state === 'running') this.ctx.suspend().catch(() => {});
  }

  setEnabled(on) {
    this.enabled = on;
    if (this.ctx) this.master.gain.setTargetAtTime(on ? 0.75 : 0, this.ctx.currentTime, 0.05);
  }

  // Laufende Geräusche an Tempo und Gaspedal anpassen
  update(kmh, throttle, active) {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    let g = 0;
    while (g < GEARS.length - 2 && kmh > GEARS[g + 1]) g++;
    const frac = Math.min(1, Math.max(0, (kmh - GEARS[g]) / (GEARS[g + 1] - GEARS[g])));
    const rpm = g === 0 ? 1000 + frac * 5600 : 2900 + frac * 3900;
    const f = (rpm / 60) * 3; // Zündfrequenz eines Sechszylinders
    for (const { o, mul } of this.oscs) o.frequency.setTargetAtTime(f * mul, t, 0.04);
    this.engFilter.frequency.setTargetAtTime(400 + throttle * 1600 + rpm * 0.12, t, 0.06);
    this.engine.gain.setTargetAtTime(active ? 0.08 + throttle * 0.08 : 0, t, 0.1);
    const sp = Math.min(1, kmh / 260);
    this.windF.frequency.setTargetAtTime(450 + kmh * 4, t, 0.1);
    this.wind.gain.setTargetAtTime(active ? sp * sp * 0.35 : 0, t, 0.15);
    this.road.gain.setTargetAtTime(active ? sp * 0.2 : 0, t, 0.15);
  }

  setScrape(level) {
    if (this.ctx) this.scrape.gain.setTargetAtTime(level * 0.35, this.ctx.currentTime, 0.03);
  }

  crash() {
    if (!this.ctx) return;
    const ctx = this.ctx, t = ctx.currentTime;
    const burst = (dur, from, to, vol, type) => {
      const s = ctx.createBufferSource();
      s.buffer = this.noise;
      const f = ctx.createBiquadFilter();
      f.type = type;
      f.frequency.setValueAtTime(from, t);
      f.frequency.exponentialRampToValueAtTime(to, t + dur);
      const g = ctx.createGain();
      g.gain.setValueAtTime(vol, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + dur);
      s.connect(f);
      f.connect(g);
      g.connect(this.master);
      s.start(t, Math.random());
      s.stop(t + dur + 0.05);
    };
    burst(1.4, 5000, 200, 0.9, 'lowpass');
    burst(0.5, 6000, 3000, 0.35, 'highpass'); // splitterndes Glas
    const o = ctx.createOscillator();
    o.type = 'sine';
    o.frequency.setValueAtTime(110, t);
    o.frequency.exponentialRampToValueAtTime(30, t + 0.45);
    const og = ctx.createGain();
    og.gain.setValueAtTime(1, t);
    og.gain.exponentialRampToValueAtTime(0.001, t + 0.6);
    o.connect(og);
    og.connect(this.master);
    o.start(t);
    o.stop(t + 0.65);
    for (let i = 0; i < 5; i++) {
      // schepperndes Blech
      const m = ctx.createOscillator();
      m.type = 'square';
      m.frequency.value = 180 + Math.random() * 900;
      const mf = ctx.createBiquadFilter();
      mf.type = 'bandpass';
      mf.frequency.value = 900 + Math.random() * 1500;
      mf.Q.value = 4;
      const mg = ctx.createGain();
      const t0 = t + i * 0.05 + Math.random() * 0.05;
      mg.gain.setValueAtTime(0.0001, t);
      mg.gain.setValueAtTime(0.25, t0);
      mg.gain.exponentialRampToValueAtTime(0.001, t0 + 0.25);
      m.connect(mf);
      mf.connect(mg);
      mg.connect(this.master);
      m.start(t0);
      m.stop(t0 + 0.3);
    }
    this.engine.gain.setTargetAtTime(0, t, 0.2);
  }

  // Rauschen beim Vorbeifahren, links/rechts im Stereobild
  whoosh(pan, vol, heavy) {
    if (!this.ctx) return;
    const ctx = this.ctx, t = ctx.currentTime;
    if (t - this.lastWhoosh < 0.08) return;
    this.lastWhoosh = t;
    const s = ctx.createBufferSource();
    s.buffer = this.noise;
    const f = ctx.createBiquadFilter();
    f.type = 'bandpass';
    f.Q.value = 0.9;
    const base = heavy ? 220 : 380;
    f.frequency.setValueAtTime(base, t);
    f.frequency.exponentialRampToValueAtTime(base * 3.2, t + 0.16);
    f.frequency.exponentialRampToValueAtTime(base * 0.7, t + 0.55);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(Math.max(0.02, 0.5 * vol * (heavy ? 1.4 : 1)), t + 0.12);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.6);
    s.connect(f);
    f.connect(g);
    let out = g;
    if (ctx.createStereoPanner) {
      const p = ctx.createStereoPanner();
      p.pan.value = Math.max(-1, Math.min(1, pan * 0.8));
      g.connect(p);
      out = p;
    }
    out.connect(this.master);
    s.start(t, Math.random());
    s.stop(t + 0.65);
  }

  nearMiss(combo) {
    if (!this.ctx) return;
    const ctx = this.ctx, t = ctx.currentTime;
    const pitch = 1 + Math.min(combo - 1, 4) * 0.06;
    [[0, 880], [0.07, 1320]].forEach(([delay, freq]) => {
      const o = ctx.createOscillator();
      o.type = 'triangle';
      o.frequency.value = freq * pitch;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, t + delay);
      g.gain.exponentialRampToValueAtTime(0.18, t + delay + 0.02);
      g.gain.exponentialRampToValueAtTime(0.001, t + delay + 0.25);
      o.connect(g);
      g.connect(this.master);
      o.start(t + delay);
      o.stop(t + delay + 0.3);
    });
  }
}
