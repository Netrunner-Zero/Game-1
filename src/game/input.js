// Eingabe für das Fahren: Tastatur, Xbox-Controller (Gamepad API, Standard-Belegung) und Touch.
//
// update(dt, speedKmh) liefert jedes Bild geglättete Werte:
//   throttle 0..1, brake 0..1, steer −1..1 (+ = rechts), handbrake 0..1,
//   lookX/lookY (Umschauen, −1..1), lookBack (Blick nach hinten), source ('keyboard'|'gamepad'|'touch')
// Einmalige Aktionen kommen als Ereignis 'action' mit detail = Name:
//   camera, lights, indicatorLeft, indicatorRight, hazard, horn, reset, pause
//
// Xbox-Controller: RT Gas, LT Bremse/Rückwärts, linker Stick lenken, A Handbremse, B nach hinten schauen,
//   Y Kamera, X Licht, LB/RB Blinker, Steuerkreuz unten Warnblinker, Ansicht-Taste Auto zurücksetzen,
//   Menü-Taste Pause, rechter Stick umschauen, linker Stick drücken Hupe.

const KEYMAP = {
  KeyW: 'throttle', ArrowUp: 'throttle',
  KeyS: 'brake', ArrowDown: 'brake',
  KeyA: 'left', ArrowLeft: 'left',
  KeyD: 'right', ArrowRight: 'right',
  Space: 'handbrake',
  KeyB: 'lookBack',
};
const KEY_ACTIONS = {
  KeyC: 'camera', KeyV: 'camera', KeyL: 'lights', KeyQ: 'indicatorLeft', KeyE: 'indicatorRight',
  KeyX: 'hazard', KeyH: 'horn', KeyR: 'reset', Escape: 'pause', KeyP: 'pause', KeyM: 'map',
};
const PAD_ACTIONS = { 3: 'camera', 2: 'lights', 4: 'indicatorLeft', 5: 'indicatorRight', 13: 'hazard', 8: 'reset',
  9: 'pause', 10: 'horn', 14: 'indicatorLeft', 15: 'indicatorRight', 12: 'map' };

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const approach = (v, target, rate, dt) => v + clamp(target - v, -rate * dt, rate * dt);

/** Totzone mit weichem Übergang und leichter Kurve (feines Lenken um die Mitte). */
export function stickCurve(x, dead = 0.1, expo = 1.35) {
  const a = Math.abs(x);
  if (a <= dead) return 0;
  const n = Math.min(1, (a - dead) / (1 - dead));
  return Math.sign(x) * Math.pow(n, expo);
}

/** Digitale Lenkung (Tasten, Touch-Knöpfe): Einlenkgeschwindigkeit sinkt mit dem Tempo. */
export function digitalSteer(cur, target, speedKmh, dt) {
  const v = Math.abs(speedKmh);
  const rateIn = 3.4 / (1 + v / 90);             // Einlenken: schnell im Stand, ruhiger bei Tempo
  const rateOut = 5.5;                           // Zurückstellen
  const back = target === 0 || Math.sign(target) !== Math.sign(cur);
  const limit = 1 / (1 + Math.pow(v / 160, 2) * 0.6);   // Tasten-Vollausschlag bei Tempo begrenzen
  return approach(cur, target * limit, back ? rateOut : rateIn, dt);
}

export class Input extends EventTarget {
  constructor(opts = {}) {
    super();
    this.keys = new Set();
    this.out = { throttle: 0, brake: 0, steer: 0, handbrake: 0, lookX: 0, lookY: 0, lookBack: false, source: 'keyboard' };
    this.touch = { steer: 0, steerActive: false, left: false, right: false, gas: false, brake: false, hand: false };
    this.steerMode = opts.steerMode || 'swipe';          // Touch: 'swipe' | 'tilt' | 'buttons'
    this.sensitivity = opts.sensitivity || 1;
    this.padPrev = [];
    this.padIndex = -1;
    this.mouseLook = { x: 0, y: 0 };
    this.tilt = 0;
    this.tiltOk = false;
    this.enabled = true;
    this._kSteer = 0;
    this._tSteer = 0;
    this._thr = 0;
    this._brk = 0;
    this.lastSource = 'keyboard';
    this._bindKeyboard();
    window.addEventListener('gamepadconnected', (e) => { this.padIndex = e.gamepad.index; this._emitInfo('gamepad'); });
    window.addEventListener('gamepaddisconnected', (e) => { if (this.padIndex === e.gamepad.index) this.padIndex = -1; });
  }

  _emit(name) { this.dispatchEvent(new CustomEvent('action', { detail: name })); }
  _emitInfo(src) { this.dispatchEvent(new CustomEvent('source', { detail: src })); }

  _bindKeyboard() {
    window.addEventListener('keydown', (e) => {
      if (e.target && /INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
      if (e.code in KEYMAP || e.code in KEY_ACTIONS) e.preventDefault();
      if (!this.enabled && e.code !== 'Escape' && e.code !== 'KeyP') return;
      if (!e.repeat && KEY_ACTIONS[e.code]) this._emit(KEY_ACTIONS[e.code]);
      if (KEYMAP[e.code]) { this.keys.add(KEYMAP[e.code]); this._setSource('keyboard'); }
    });
    window.addEventListener('keyup', (e) => { if (KEYMAP[e.code]) this.keys.delete(KEYMAP[e.code]); });
    window.addEventListener('blur', () => this.keys.clear());
  }

  _setSource(s) {
    if (this.lastSource !== s) { this.lastSource = s; this._emitInfo(s); }
  }

  // ------------------------------------------------------------------
  // Touch-Bedienelemente anbinden: { steerZone, knob, left, right, gas, brake, hand, lookZone }
  bindTouch(el) {
    this.touchEl = el;
    const range = () => clamp(Math.min(window.innerWidth, window.innerHeight) * 0.16, 44, 110);
    // Wischlenkung: Finger irgendwo im linken Bereich aufsetzen und seitlich ziehen
    let steerId = null, x0 = 0;
    const zone = el.steerZone;
    zone.addEventListener('pointerdown', (e) => {
      if (this.steerMode !== 'swipe' || steerId !== null) return;
      steerId = e.pointerId; x0 = e.clientX;
      zone.setPointerCapture(e.pointerId);
      this.touch.steerActive = true;
      el.knob.style.left = e.clientX + 'px';
      el.knob.style.top = e.clientY + 'px';
      el.knob.classList.add('on');
      this._setSource('touch');
    });
    zone.addEventListener('pointermove', (e) => {
      if (e.pointerId !== steerId) return;
      const r = range();
      let dx = e.clientX - x0;
      // Startpunkt wandert mit, wenn man über den Anschlag hinauszieht (kein „Festkleben“ am Rand)
      if (Math.abs(dx) > r) { x0 += dx - Math.sign(dx) * r; dx = Math.sign(dx) * r; }
      this.touch.steer = clamp(dx / r, -1, 1);
      el.knob.style.setProperty('--dx', (this.touch.steer * r) + 'px');
    });
    const endSteer = (e) => {
      if (e.pointerId !== steerId) return;
      steerId = null;
      this.touch.steerActive = false;
      this.touch.steer = 0;
      el.knob.classList.remove('on');
      el.knob.style.setProperty('--dx', '0px');
    };
    zone.addEventListener('pointerup', endSteer);
    zone.addEventListener('pointercancel', endSteer);

    const hold = (node, key) => {
      if (!node) return;
      const set = (on) => (e) => {
        e.preventDefault();
        this.touch[key] = on;
        node.classList.toggle('on', on);
        if (on) { this._setSource('touch'); if (navigator.vibrate) try { navigator.vibrate(8); } catch (err) { /* egal */ } }
      };
      node.addEventListener('pointerdown', (e) => { node.setPointerCapture(e.pointerId); set(true)(e); });
      node.addEventListener('pointerup', set(false));
      node.addEventListener('pointercancel', set(false));
      node.addEventListener('contextmenu', (e) => e.preventDefault());
    };
    hold(el.gas, 'gas');
    hold(el.brake, 'brake');
    hold(el.hand, 'hand');
    hold(el.left, 'left');
    hold(el.right, 'right');
  }

  // Neigungslenkung (Handy wie ein Lenkrad kippen). Auf iOS braucht es eine Erlaubnis.
  async enableTilt() {
    try {
      if (typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
        const r = await DeviceMotionEvent.requestPermission();
        if (r !== 'granted') return false;
      }
    } catch (e) { return false; }
    if (!this._tiltBound) {
      this._tiltBound = true;
      window.addEventListener('devicemotion', (e) => {
        const g = e.accelerationIncludingGravity;
        if (!g || g.x === null) return;
        const ang = ((screen.orientation && screen.orientation.angle) || window.orientation || 0) * Math.PI / 180;
        // Richtung „rechts“ auf dem Bildschirm in Gerätekoordinaten: (cos θ, −sin θ)
        const gs = g.x * Math.cos(ang) - g.y * Math.sin(ang);
        const a = Math.asin(clamp(gs / 9.81, -1, 1));             // Kippwinkel (rad), rechts runter < 0
        this.tilt = -a;
        this.tiltOk = true;
      });
    }
    return true;
  }

  // Umschauen mit der Maus / einem Finger (Ziehen über dem Bild)
  addLook(dx, dy) {
    this.mouseLook.x += dx;
    this.mouseLook.y += dy;
  }

  // ------------------------------------------------------------------
  _readPad() {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    let pad = this.padIndex >= 0 ? pads[this.padIndex] : null;
    if (!pad) for (const p of pads) if (p && p.connected) { pad = p; this.padIndex = p.index; break; }
    if (!pad) return null;
    this.pad = pad;
    const b = (i) => (pad.buttons[i] ? pad.buttons[i].value || (pad.buttons[i].pressed ? 1 : 0) : 0);
    // Tasten-Ereignisse (steigende Flanke)
    for (const [i, name] of Object.entries(PAD_ACTIONS)) {
      const now = b(Number(i)) > 0.5;
      if (now && !this.padPrev[i]) {
        if (this.enabled || name === 'pause') this._emit(name);
      }
      this.padPrev[i] = now;
    }
    const ax = (i) => (pad.axes[i] !== undefined ? pad.axes[i] : 0);
    const r = {
      throttle: b(7), brake: b(6), steer: stickCurve(ax(0), 0.1, 1.35), handbrake: b(0),
      lookX: stickCurve(ax(2), 0.15, 1.2), lookY: stickCurve(ax(3), 0.15, 1.2), lookBack: b(1) > 0.5,
    };
    const active = r.throttle > 0.05 || r.brake > 0.05 || Math.abs(r.steer) > 0.05 || r.handbrake > 0.5 ||
      Math.abs(r.lookX) > 0.1 || Math.abs(r.lookY) > 0.1 || r.lookBack;
    if (active) this._setSource('gamepad');
    return r;
  }

  /** Vibration am Controller (z. B. bei Aufprall); stark/schwach 0..1. */
  rumble(strong, weak, ms = 120) {
    const pad = this.pad;
    if (pad && pad.vibrationActuator && pad.vibrationActuator.playEffect) {
      try {
        pad.vibrationActuator.playEffect('dual-rumble', { duration: ms, strongMagnitude: clamp(strong, 0, 1), weakMagnitude: clamp(weak, 0, 1) });
      } catch (e) { /* nicht unterstützt */ }
    } else if (this.lastSource === 'touch' && navigator.vibrate && strong > 0.25) {
      try { navigator.vibrate(Math.round(ms * strong)); } catch (e) { /* egal */ }
    }
  }

  update(dt, speedKmh = 0) {
    const o = this.out;
    const pad = this._readPad();
    const k = this.keys;
    const t = this.touch;
    // Tastatur
    const kThr = k.has('throttle') ? 1 : 0, kBrk = k.has('brake') ? 1 : 0;
    const kTarget = (k.has('right') ? 1 : 0) - (k.has('left') ? 1 : 0);
    this._kSteer = digitalSteer(this._kSteer, kTarget, speedKmh, dt);
    // Touch
    let tSteer = 0;
    if (this.steerMode === 'swipe') tSteer = t.steer;
    else if (this.steerMode === 'tilt') {
      const max = 0.42;                              // ~24° Kippen = voller Einschlag
      const a = this.tilt;
      tSteer = Math.abs(a) < 0.035 ? 0 : clamp((a - Math.sign(a) * 0.035) / max, -1, 1);
    } else {
      this._tSteer = digitalSteer(this._tSteer, (t.right ? 1 : 0) - (t.left ? 1 : 0), speedKmh, dt);
      tSteer = this._tSteer;
    }
    // Pedale: Tasten und Touch weich anfahren (kurzes Tippen = wenig Gas)
    this._thr = approach(this._thr, Math.max(kThr, t.gas ? 1 : 0), Math.max(kThr, t.gas ? 1 : 0) > this._thr ? 3.5 : 7, dt);
    this._brk = approach(this._brk, Math.max(kBrk, t.brake ? 1 : 0), Math.max(kBrk, t.brake ? 1 : 0) > this._brk ? 6 : 9, dt);

    let steer = this._kSteer + tSteer * this.sensitivity;
    let throttle = this._thr, brake = this._brk;
    let handbrake = k.has('handbrake') || t.hand ? 1 : 0;
    let lookX = 0, lookY = 0, lookBack = k.has('lookBack');
    if (pad) {
      steer += pad.steer * this.sensitivity;
      throttle = Math.max(throttle, pad.throttle);
      brake = Math.max(brake, pad.brake);
      handbrake = Math.max(handbrake, pad.handbrake);
      lookX = pad.lookX; lookY = pad.lookY;
      lookBack = lookBack || pad.lookBack;
    }
    if (!this.enabled) { throttle = 0; brake = 0; handbrake = 0; steer = 0; }
    o.steer = clamp(steer, -1, 1);
    o.throttle = clamp(throttle, 0, 1);
    o.brake = clamp(brake, 0, 1);
    o.handbrake = handbrake;
    o.lookX = lookX; o.lookY = lookY;
    o.lookBack = lookBack;
    o.mouseX = this.mouseLook.x; o.mouseY = this.mouseLook.y;
    this.mouseLook.x = 0; this.mouseLook.y = 0;
    o.source = this.lastSource;
    return o;
  }
}
