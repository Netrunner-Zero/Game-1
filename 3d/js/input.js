// Steuerung: Tastatur, Touch (linke/rechte Hälfte halten), Pedale und Neigungssensor
const KEYMAP = {
  ArrowLeft: 'left', KeyA: 'left',
  ArrowRight: 'right', KeyD: 'right',
  ArrowUp: 'gas', KeyW: 'gas',
  ArrowDown: 'brake', KeyS: 'brake',
};

const approach = (a, b, d) => (a < b ? Math.min(a + d, b) : Math.max(a - d, b));

export class Input {
  constructor({ surface, gasBtn, brakeBtn, onPause }) {
    this.keys = new Set();
    this.mode = 'touch';         // 'touch' | 'tilt'
    this.steer = 0;              // -1 (links) … 1 (rechts), geglättet
    this.pointers = new Map();   // aktive Finger auf der Spielfläche
    this.order = 0;
    this.gasHeld = false;
    this.brakeHeld = false;
    this.tiltRaw = 0;
    this.tiltZero = 0;
    this.tiltSeen = false;

    window.addEventListener('keydown', e => {
      const k = KEYMAP[e.code];
      if (k) {
        this.keys.add(k);
        e.preventDefault();
      } else if (e.code === 'KeyP' || e.code === 'Escape') {
        onPause();
      }
    });
    window.addEventListener('keyup', e => {
      const k = KEYMAP[e.code];
      if (k) this.keys.delete(k);
    });
    window.addEventListener('blur', () => this.keys.clear());

    surface.addEventListener('pointerdown', e => {
      this.pointers.set(e.pointerId, { x: e.clientX, order: ++this.order });
      try {
        surface.setPointerCapture(e.pointerId);
      } catch { /* ältere Browser */ }
      e.preventDefault();
    });
    surface.addEventListener('pointermove', e => {
      const p = this.pointers.get(e.pointerId);
      if (p) p.x = e.clientX;
    });
    const release = e => this.pointers.delete(e.pointerId);
    surface.addEventListener('pointerup', release);
    surface.addEventListener('pointercancel', release);
    surface.addEventListener('lostpointercapture', release);
    surface.addEventListener('contextmenu', e => e.preventDefault());

    const hold = (btn, set) => {
      btn.addEventListener('pointerdown', e => {
        set(true);
        btn.classList.add('active');
        try {
          btn.setPointerCapture(e.pointerId);
        } catch { /* ältere Browser */ }
        e.preventDefault();
        e.stopPropagation();
      });
      const off = () => {
        set(false);
        btn.classList.remove('active');
      };
      btn.addEventListener('pointerup', off);
      btn.addEventListener('pointercancel', off);
      btn.addEventListener('lostpointercapture', off);
      btn.addEventListener('contextmenu', e => e.preventDefault());
    };
    hold(gasBtn, v => (this.gasHeld = v));
    hold(brakeBtn, v => (this.brakeHeld = v));

    window.addEventListener('deviceorientation', e => this.onTilt(e));
  }

  onTilt(e) {
    if (e.gamma == null || e.beta == null) return;
    const angle = (screen.orientation && screen.orientation.angle) ?? window.orientation ?? 0;
    // Im Hochformat neigt man um gamma, im Querformat um beta
    if (angle === 90) this.tiltRaw = e.beta;
    else if (angle === -90 || angle === 270) this.tiltRaw = -e.beta;
    else if (angle === 180) this.tiltRaw = -e.gamma;
    else this.tiltRaw = e.gamma;
    this.tiltSeen = true;
  }

  // Aktuelle Haltung als Geradeaus-Stellung übernehmen
  calibrate() {
    this.tiltZero = this.tiltSeen ? this.tiltRaw : 0;
  }

  // iPhone/iPad verlangen eine Erlaubnis, die nur nach einem Tippen abgefragt werden darf
  async requestTilt() {
    const DOE = window.DeviceOrientationEvent;
    if (!DOE) return false;
    if (typeof DOE.requestPermission === 'function') {
      try {
        return (await DOE.requestPermission()) === 'granted';
      } catch {
        return false;
      }
    }
    return true;
  }

  get gas() {
    return this.keys.has('gas') || this.gasHeld;
  }

  get brake() {
    return this.keys.has('brake') || this.brakeHeld;
  }

  reset() {
    this.pointers.clear();
    this.keys.clear();
    this.gasHeld = this.brakeHeld = false;
    this.steer = 0;
  }

  update(dt) {
    let digital = 0;
    if (this.keys.has('left')) digital -= 1;
    if (this.keys.has('right')) digital += 1;
    if (this.mode === 'touch' && this.pointers.size) {
      // Der zuletzt aufgesetzte Finger gewinnt
      let last = null;
      for (const p of this.pointers.values()) if (!last || p.order > last.order) last = p;
      digital = last.x < window.innerWidth / 2 ? -1 : 1;
    }
    if (this.mode === 'tilt' && this.tiltSeen && digital === 0) {
      let t = this.tiltRaw - this.tiltZero;
      t = Math.sign(t) * Math.max(0, Math.abs(t) - 1.5); // kleine Totzone
      const target = Math.max(-1, Math.min(1, t / 20));
      this.steer += (target - this.steer) * Math.min(1, dt * 12);
      return;
    }
    const rate = digital === 0 ? 8 : Math.sign(digital) !== Math.sign(this.steer) ? 9 : 5;
    this.steer = approach(this.steer, digital, rate * dt);
  }
}
