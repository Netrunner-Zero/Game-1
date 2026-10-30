// Fahrgeräusche, komplett synthetisch (WebAudio, keine Audiodateien):
//  * Motor: Zündfrequenz aus Drehzahl und Zylinderzahl (V8 blubbert, V12 singt, Vierzylinder brummt),
//    Klangfarbe öffnet mit Gas und Drehzahl, Sportauspuff = lauter und rauer
//  * Elektro: Pfeifen der Motoren und Inverter, steigt mit dem Tempo
//  * Reifen quietschen beim Rutschen, Fahrtwind, dumpfer Schlag bei Aufprall
// Browser erlauben Ton erst nach einer Berührung/Taste: start() im Klick-Handler aufrufen.

const CYL = { vektra_gt: 8, brawler_77: 8, rhino_x: 8, pulse: 4, aurelion_s: 12, ion_spectre: 0 };

function noiseBuffer(ctx, seconds = 2) {
  const n = Math.floor(ctx.sampleRate * seconds);
  const b = ctx.createBuffer(1, n, ctx.sampleRate);
  const d = b.getChannelData(0);
  let last = 0;
  for (let i = 0; i < n; i++) {
    const w = Math.random() * 2 - 1;
    last = last * 0.6 + w * 0.4;          // leicht gefärbt (weniger Zischen)
    d[i] = last;
  }
  return b;
}

function softClip(k) {
  const n = 1024, c = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1;
    c[i] = Math.tanh(x * k) / Math.tanh(k);
  }
  return c;
}

export class CarAudio {
  constructor() {
    this.ctx = null;
    this.volume = 0.7;
    this.muted = false;
    this.cyl = 8;
    this.loud = 0;
    this.electric = false;
  }

  async start() {
    if (this.ctx) {
      if (this.ctx.state === 'suspended') { try { await this.ctx.resume(); } catch (e) { /* egal */ } }
      return;
    }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    const ctx = new AC();
    this.ctx = ctx;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -14; comp.ratio.value = 4;
    comp.connect(ctx.destination);
    this.master = ctx.createGain();
    this.master.gain.value = this.muted ? 0 : this.volume;
    this.master.connect(comp);
    const noise = noiseBuffer(ctx);
    const loopNoise = () => { const s = ctx.createBufferSource(); s.buffer = noise; s.loop = true; s.start(); return s; };

    // --- Verbrenner
    this.eng = ctx.createGain(); this.eng.gain.value = 0;
    this.lp = ctx.createBiquadFilter(); this.lp.type = 'lowpass'; this.lp.Q.value = 1.4; this.lp.frequency.value = 600;
    this.shaper = ctx.createWaveShaper(); this.shaper.curve = softClip(2.2); this.shaper.oversample = '2x';
    this.mix = ctx.createGain(); this.mix.gain.value = 0.5;
    this.o1 = ctx.createOscillator(); this.o1.type = 'sawtooth';
    this.o2 = ctx.createOscillator(); this.o2.type = 'square';
    this.o3 = ctx.createOscillator(); this.o3.type = 'triangle';
    const g1 = ctx.createGain(); g1.gain.value = 0.55;
    this.g2 = ctx.createGain(); this.g2.gain.value = 0.35;
    const g3 = ctx.createGain(); g3.gain.value = 0.25;
    this.o1.connect(g1).connect(this.mix);
    this.o2.connect(this.g2).connect(this.mix);
    this.o3.connect(g3).connect(this.mix);
    // Ansaug-/Auspuffrauschen im Takt
    this.breath = ctx.createBiquadFilter(); this.breath.type = 'bandpass'; this.breath.Q.value = 1.6;
    this.breathG = ctx.createGain(); this.breathG.gain.value = 0;
    loopNoise().connect(this.breath).connect(this.breathG).connect(this.mix);
    this.mix.connect(this.shaper).connect(this.lp).connect(this.eng).connect(this.master);
    // Blubbern (Amplitudenmodulation, z. B. V8-Leerlauf)
    this.lfo = ctx.createOscillator(); this.lfo.type = 'sine';
    this.lfoG = ctx.createGain(); this.lfoG.gain.value = 0;
    this.lfo.connect(this.lfoG).connect(this.eng.gain);
    for (const o of [this.o1, this.o2, this.o3, this.lfo]) o.start();

    // --- Elektro
    this.ev = ctx.createGain(); this.ev.gain.value = 0;
    this.e1 = ctx.createOscillator(); this.e1.type = 'sine';
    this.e2 = ctx.createOscillator(); this.e2.type = 'triangle';
    const eg2 = ctx.createGain(); eg2.gain.value = 0.3;
    this.e1.connect(this.ev); this.e2.connect(eg2).connect(this.ev);
    this.ev.connect(this.master);
    this.e1.start(); this.e2.start();

    // --- Reifen, Wind
    this.tire = ctx.createGain(); this.tire.gain.value = 0;
    const tb = ctx.createBiquadFilter(); tb.type = 'bandpass'; tb.frequency.value = 1150; tb.Q.value = 4;
    this.tireF = tb;
    loopNoise().connect(tb).connect(this.tire).connect(this.master);
    // Regen: breites Rauschen (oben gedämpft), leises Prasseln
    this.rainG = ctx.createGain(); this.rainG.gain.value = 0;
    const rl = ctx.createBiquadFilter(); rl.type = 'lowpass'; rl.frequency.value = 3200;
    const rh = ctx.createBiquadFilter(); rh.type = 'highpass'; rh.frequency.value = 420;
    loopNoise().connect(rh).connect(rl).connect(this.rainG).connect(this.master);
    this.wind = ctx.createGain(); this.wind.gain.value = 0;
    const wl = ctx.createBiquadFilter(); wl.type = 'lowpass'; wl.frequency.value = 520;
    loopNoise().connect(wl).connect(this.wind).connect(this.master);
    this.noise = noise;
  }

  setCar(meta, tuning = {}) {
    this.cyl = CYL[meta.id] !== undefined ? CYL[meta.id] : 8;
    this.electric = !!(meta.physics && meta.physics.electric) || this.cyl === 0;
    const ex = meta.tuning && meta.tuning.exhaust && meta.tuning.exhaust[(tuning.exhaust || 1) - 1];
    this.loud = ex && ex.loudness ? ex.loudness : 0;
    this.redline = (meta.physics && meta.physics.redlineRpm) || 7000;
    this.idle = (meta.physics && meta.physics.idleRpm) || 850;
  }

  setVolume(v) {
    this.volume = v;
    if (this.master) this.master.gain.setTargetAtTime(this.muted ? 0 : v, this.ctx.currentTime, 0.05);
  }

  setMuted(m) {
    this.muted = m;
    this.setVolume(this.volume);
  }

  update(dt, p, inp) {
    const ctx = this.ctx;
    if (!ctx || ctx.state !== 'running') return;
    const t = ctx.currentTime, k = 0.035;
    const thr = p.gear < 0 ? (inp.brake || 0) : (inp.throttle || 0);
    const speed = Math.abs(p.speed);
    if (this.electric) {
      this.eng.gain.setTargetAtTime(0, t, 0.05);
      const f = 140 + speed * 11;
      this.e1.frequency.setTargetAtTime(f, t, k);
      this.e2.frequency.setTargetAtTime(f * 2.02, t, k);
      this.ev.gain.setTargetAtTime(0.025 + 0.06 * thr + Math.min(0.05, speed * 0.0008), t, 0.06);
    } else {
      this.ev.gain.setTargetAtTime(0, t, 0.05);
      const rpm = Math.max(this.idle * 0.9, p.rpm);
      const f = rpm / 60 * this.cyl / 2;
      const rf = Math.min(1, rpm / this.redline);
      this.o1.frequency.setTargetAtTime(f, t, k);
      this.o2.frequency.setTargetAtTime(f * 0.5, t, k);
      this.o3.frequency.setTargetAtTime(f * 2, t, k);
      this.breath.frequency.setTargetAtTime(f * 1.5, t, k);
      this.breathG.gain.setTargetAtTime(0.15 + thr * 0.45, t, k);
      this.lfo.frequency.setTargetAtTime(f * (this.cyl === 8 ? 0.25 : 0.5), t, k);
      const burble = this.cyl === 8 ? 0.35 : this.cyl === 4 ? 0.15 : 0.08;
      const base = 0.07 + thr * 0.16 + rf * 0.05 + this.loud * 0.012;
      this.eng.gain.setTargetAtTime(base, t, 0.04);
      this.lfoG.gain.setTargetAtTime(base * burble * (1 - rf * 0.7), t, 0.05);
      this.g2.gain.setTargetAtTime(this.cyl === 8 ? 0.45 : 0.3, t, 0.1);
      this.lp.frequency.setTargetAtTime(260 + rf * 1900 + thr * 1500 + this.loud * 160, t, k);
    }
    // Reifen: Schlupf/Schräglauf über dem Haftmaximum
    let slide = 0;
    for (const w of p.wheels) {
      if (!w.contact) continue;
      const sx = Math.abs(w.slip) / (p.kappaPeak * 1.6);
      const sy = Math.abs(w.slipAngle) / (p.alphaPeak * 1.25);
      slide = Math.max(slide, Math.hypot(sx, sy) - 0.85);
    }
    const sq = Math.min(1, Math.max(0, slide) * 1.2) * Math.min(1, speed / 4);
    // nasse Straße: Zischen der Reifen statt Quietschen
    const hiss = (this.wet || 0) * Math.min(1, speed / 25);
    this.tire.gain.setTargetAtTime(Math.max(sq * 0.22 * (1 - 0.6 * (this.wet || 0)), hiss * 0.07), t, 0.05);
    this.tireF.frequency.setTargetAtTime(hiss > sq ? 520 + speed * 6 : 900 + Math.min(speed, 40) * 12, t, 0.1);
    const ws = Math.min(1, speed / 70);
    this.wind.gain.setTargetAtTime(ws * ws * 0.22, t, 0.2);
  }

  /** Regenstärke 0..1. */
  setRain(r) {
    if (!this.ctx || !this.rainG) return;
    if (Math.abs((this._rain || 0) - r) < 0.01) return;
    this._rain = r;
    this.rainG.gain.setTargetAtTime(r * 0.16, this.ctx.currentTime, 0.4);
  }

  /** Aufprall (0..1). */
  impact(s) {
    const ctx = this.ctx;
    if (!ctx || ctx.state !== 'running') return;
    const src = ctx.createBufferSource();
    src.buffer = this.noise;
    const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 180 + s * 900;
    const g = ctx.createGain();
    const t = ctx.currentTime;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.25 + s * 0.9, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.18 + s * 0.45);
    src.connect(f).connect(g).connect(this.master);
    src.start(t, Math.random() * 1.5);
    src.stop(t + 0.8);
  }

  /** Hupe eines anderen Autos (tiefer/höher je Auto, leiser mit Abstand). */
  honk(dist = 10, pitch = 1) {
    this.horn(0.35 + Math.random() * 0.4, Math.max(0.15, 1 - dist / 40), pitch);
  }

  /** Hupe (zwei Töne, kurz). */
  horn(seconds = 0.45, vol = 1, pitch = 1) {
    const ctx = this.ctx;
    if (!ctx || ctx.state !== 'running') return;
    const t = ctx.currentTime;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.16 * vol, t + 0.02);
    g.gain.setValueAtTime(0.16 * vol, t + seconds);
    g.gain.exponentialRampToValueAtTime(0.0001, t + seconds + 0.08);
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2200;
    g.connect(lp).connect(this.master);
    for (const f of [415 * pitch, 523 * pitch]) {
      const o = ctx.createOscillator(); o.type = 'square'; o.frequency.value = f;
      o.connect(g); o.start(t); o.stop(t + seconds + 0.1);
    }
  }

  suspend() { if (this.ctx && this.ctx.state === 'running') this.ctx.suspend(); }
  resume() { if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume(); }
}
