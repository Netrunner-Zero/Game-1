// Anzeige beim Fahren: Tempo, Gang, Drehzahl, Fahrhilfen (ABS/ASR/ESP leuchten beim Eingreifen),
// kurze Meldungen („Kamera: Cockpit“). Reines DOM + ein kleines Canvas für den Drehzahlbogen.

export class Hud {
  constructor(root) {
    this.root = root;
    root.innerHTML = `
      <div class="cluster">
        <canvas class="rpm" width="320" height="120"></canvas>
        <div class="readout">
          <div class="spd"><b>0</b><span>km/h</span></div>
          <div class="gear">N</div>
        </div>
        <div class="lamps"><span data-l="abs">ABS</span><span data-l="tcs">ASR</span><span data-l="esc">ESP</span></div>
      </div>
      <div class="toast"></div>
      <canvas class="minimap hidden" width="240" height="240"></canvas>`;
    this.cv = root.querySelector('.rpm');
    this.ctx = this.cv.getContext('2d');
    this.spd = root.querySelector('.spd b');
    this.gear = root.querySelector('.gear');
    this.lamps = {};
    for (const el of root.querySelectorAll('.lamps span')) this.lamps[el.dataset.l] = el;
    this.toastEl = root.querySelector('.toast');
    this._toastT = 0;
    this._last = { spd: -1, gear: '', rpm: -1 };
    this.accent = '#00e5ff';
    this.mmCanvas = root.querySelector('.minimap');
    this.mmCtx = this.mmCanvas.getContext('2d');
    this.mm = null;
    this._mmT = 0;
    this._mmZoom = 0.7;
  }

  /** Minikarte der Welt (Bild + Maßstab aus der Karten-JSON) oder null. */
  setMinimap(src, info) {
    if (!src || !info) { this.mm = null; this.mmCanvas.classList.add('hidden'); return; }
    const img = new Image();
    img.src = src;
    this.mm = { img, info, ok: false };
    img.onload = () => { if (this.mm && this.mm.img === img) { this.mm.ok = true; this.mmCanvas.classList.remove('hidden'); } };
  }

  _drawMinimap(p) {
    const mm = this.mm;
    if (!mm || !mm.ok) return;
    const c = this.mmCtx, W = this.mmCanvas.width, R = W / 2 - 3;
    const s = mm.info.size / mm.info.span;
    // Bildpunkt: u = (span/2 − x)·s, v = (span/2 − z)·s (Norden oben, +X links wie aus dem Auto gesehen)
    const u = (mm.info.span / 2 - p.pos.x) * s, v = (mm.info.span / 2 - p.pos.z) * s;
    const want = 0.95 - Math.min(0.5, Math.abs(p.speed) / 70);       // bei Tempo weiter herauszoomen
    this._mmZoom += (want - this._mmZoom) * 0.08;
    c.clearRect(0, 0, W, W);
    c.save();
    c.beginPath(); c.arc(W / 2, W / 2, R, 0, Math.PI * 2); c.clip();
    c.fillStyle = '#0b0d12'; c.fillRect(0, 0, W, W);
    c.translate(W / 2, W / 2);
    c.rotate(p.yaw);                                                  // Fahrtrichtung zeigt nach oben
    c.scale(this._mmZoom, this._mmZoom);
    c.translate(-u, -v);
    c.drawImage(mm.img, 0, 0);
    c.restore();
    // Rand, Spieler-Pfeil, Norden
    c.lineWidth = 3; c.strokeStyle = 'rgba(255,255,255,0.18)';
    c.beginPath(); c.arc(W / 2, W / 2, R, 0, Math.PI * 2); c.stroke();
    c.fillStyle = this.accent;
    c.beginPath(); c.moveTo(W / 2, W / 2 - 13); c.lineTo(W / 2 + 9, W / 2 + 10); c.lineTo(W / 2, W / 2 + 5); c.lineTo(W / 2 - 9, W / 2 + 10);
    c.closePath(); c.fill();
    const nx = W / 2 + Math.sin(p.yaw) * (R - 14), ny = W / 2 - Math.cos(p.yaw) * (R - 14);
    c.fillStyle = 'rgba(0,0,0,0.6)'; c.beginPath(); c.arc(nx, ny, 12, 0, Math.PI * 2); c.fill();
    c.fillStyle = '#ff5a6a'; c.font = 'bold 17px sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillText('N', nx, ny + 1);
  }

  setAccent(c) { this.accent = c; this._last.rpm = -1; }

  toast(text, seconds = 1.6) {
    this.toastEl.textContent = text;
    this.toastEl.classList.add('on');
    this._toastT = seconds;
  }

  update(dt, p) {
    if (this._toastT > 0) {
      this._toastT -= dt;
      if (this._toastT <= 0) this.toastEl.classList.remove('on');
    }
    const spd = Math.round(Math.abs(p.speedKmh));
    if (spd !== this._last.spd) { this.spd.textContent = spd; this._last.spd = spd; }
    const g = p.gearLabel();
    if (g !== this._last.gear) { this.gear.textContent = g; this.gear.classList.toggle('rev', g === 'R'); this._last.gear = g; }
    this.lamps.abs.classList.toggle('on', p.absLamp > 0 && p.assist.abs);
    this.lamps.tcs.classList.toggle('on', p.tcsLamp > 0);
    this.lamps.esc.classList.toggle('on', p.escLamp > 0);
    const rpm = p.electric ? Math.min(1, Math.abs(p.speed) / p.vLimit) : Math.min(1.02, p.rpm / (p.redline * 1.08));
    if (Math.abs(rpm - this._last.rpm) > 0.004) { this._drawRpm(rpm, p); this._last.rpm = rpm; }
    this._mmT += dt;
    if (this._mmT > 1 / 30) { this._mmT = 0; this._drawMinimap(p); }
  }

  _drawRpm(f, p) {
    const c = this.ctx, w = this.cv.width, h = this.cv.height;
    c.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h * 1.55, r = h * 1.32;
    const a0 = -Math.PI / 2 - 0.62, a1 = -Math.PI / 2 + 0.62;
    const red = p.electric ? 0.92 : (p.redline * 0.94) / (p.redline * 1.08);
    c.lineCap = 'butt';
    const seg = 34;
    for (let i = 0; i < seg; i++) {
      const t0 = i / seg, t1 = (i + 0.72) / seg;
      const on = t0 < f;
      const hot = t0 >= red;
      c.beginPath();
      c.arc(cx, cy, r, a0 + (a1 - a0) * t0, a0 + (a1 - a0) * t1);
      c.lineWidth = hot ? 15 : 12;
      c.strokeStyle = on ? (hot ? '#ff2a3d' : t0 > red - 0.12 ? '#ffb020' : this.accent) : 'rgba(255,255,255,0.10)';
      c.stroke();
    }
  }
}
