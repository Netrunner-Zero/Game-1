// Kameras für das Fahren: Verfolger (nah/weit), Motorhaube, Stoßstange, Cockpit.
//
// Verfolger: folgt dem Auto mit Verzögerung beim Gieren (beim Driften sieht man das Auto schräg),
// wird bei Tempo etwas weiter und breiter (Sichtfeld), schaut leicht voraus. Rechter Stick, Maus
// oder Finger: um das Auto schauen (kehrt nach kurzer Zeit zurück). B / Taste B: nach hinten schauen.
// Cockpit: Kopf bewegt sich mit Beschleunigung und Kurvenkräften, schaut leicht in die Kurve,
// freies Umschauen. Motorhaube/Stoßstange: fest am Aufbau (nicken und wanken mit).

import * as THREE from 'three';

export const CAMERAS = [
  { id: 'chase', label: 'Verfolger' },
  { id: 'far', label: 'Verfolger weit' },
  { id: 'hood', label: 'Motorhaube' },
  { id: 'bumper', label: 'Stoßstange' },
  { id: 'cockpit', label: 'Cockpit' },
];

const angDiff = (a, b) => {
  let d = a - b;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return d;
};
const clamp = THREE.MathUtils.clamp;

export class CameraRig {
  constructor(camera) {
    this.camera = camera;
    this.mode = 'chase';
    this.yaw = 0;
    this.orbit = { yaw: 0, pitch: 0, idle: 10 };
    this.targetY = 0;
    this.distExtra = 0;
    this.shake = 0;
    this.world = null;               // StaticWorld: Kamera nicht hinter Häuser stellen
    this.snapNext = true;
    this.head = new THREE.Vector3();
    this.lookBackK = 0;
    this._v = new THREE.Vector3();
    this._t = new THREE.Vector3();
    this._q = new THREE.Quaternion();
    this._q2 = new THREE.Quaternion();
    this._e = new THREE.Euler();
  }

  setMode(id) {
    if (!CAMERAS.some((c) => c.id === id)) id = 'chase';
    this.mode = id;
    this.orbit.yaw = 0;
    this.orbit.pitch = 0;
    this.snapNext = true;
  }

  next() {
    const i = CAMERAS.findIndex((c) => c.id === this.mode);
    this.setMode(CAMERAS[(i + 1) % CAMERAS.length].id);
    return this.label;
  }

  get label() { return (CAMERAS.find((c) => c.id === this.mode) || CAMERAS[0]).label; }
  get inside() { return this.mode === 'cockpit'; }
  get attached() { return this.mode === 'cockpit' || this.mode === 'hood' || this.mode === 'bumper'; }

  addShake(s) { this.shake = Math.min(1, this.shake + s); }
  snap() { this.snapNext = true; }

  _lookInput(dt, inp) {
    const o = this.orbit;
    const stick = Math.abs(inp.lookX) > 0.01 || Math.abs(inp.lookY) > 0.01;
    const mouse = inp.mouseX || inp.mouseY;
    if (stick) {
      o.yaw += -inp.lookX * 2.6 * dt;
      o.pitch += -inp.lookY * 1.6 * dt;
      o.idle = 0;
      o.fromStick = true;
    } else if (mouse) {
      o.yaw -= inp.mouseX * 0.0055;
      o.pitch -= inp.mouseY * 0.0042;
      o.idle = 0;
      o.fromStick = false;
    } else {
      o.idle += dt;
    }
    const lim = this.mode === 'cockpit' ? 2.1 : Math.PI;
    o.yaw = clamp(o.yaw, -lim, lim);
    o.pitch = clamp(o.pitch, this.mode === 'cockpit' ? -0.7 : -0.25, this.mode === 'cockpit' ? 0.55 : 0.9);
    // zurückdrehen: Stick sofort nach dem Loslassen, Maus/Finger nach einer Pause
    const wait = o.fromStick ? 0.15 : 1.6;
    if (o.idle > wait) {
      const k = 1 - Math.exp(-dt * 3.5);
      o.yaw += -o.yaw * k;
      o.pitch += -o.pitch * k;
    }
    this.lookBackK += ((inp.lookBack ? 1 : 0) - this.lookBackK) * (1 - Math.exp(-dt * 18));
  }

  update(dt, car, p, inp, aspect) {
    const cam = this.camera;
    const meta = car.meta;
    this._lookInput(dt, inp);
    const portrait = aspect < 1;
    const kmh = Math.abs(p.speedKmh);
    let fov, near;
    const shakeOff = this._v.set(0, 0, 0);
    if (this.shake > 0.001) {
      const s = this.shake * this.shake;
      shakeOff.set((Math.random() - 0.5) * s * 0.25, (Math.random() - 0.5) * s * 0.18, (Math.random() - 0.5) * s * 0.25);
      this.shake *= Math.exp(-dt * 7);
    }

    if (this.mode === 'chase' || this.mode === 'far') {
      const far = this.mode === 'far';
      const L = meta.dimensions.length, H = meta.dimensions.height;
      // Blickrichtung: Fahrzeugrichtung, bei Tempo etwas zur Bewegungsrichtung (Driften sichtbar)
      let hd = p.yaw;
      const sp = Math.hypot(p.vel.x, p.vel.z);
      if (sp > 4 && p.speed > 0) {
        const vh = Math.atan2(p.vel.x, p.vel.z);
        hd = p.yaw + angDiff(vh, p.yaw) * 0.4 * clamp((sp - 4) / 10, 0, 1);
      }
      if (this.snapNext) {
        this.yaw = hd; this.targetY = p.pos.y; this.distExtra = 0;
      }
      this.yaw += angDiff(hd, this.yaw) * (1 - Math.exp(-dt * (far ? 3.2 : 4.2)));
      // Abstand: bei Beschleunigung etwas zurückfallen, beim Bremsen aufschließen
      const want = clamp(p.accLong, -12, 12) * 0.035 + Math.min(kmh, 300) * 0.0045;
      this.distExtra += (want - this.distExtra) * (1 - Math.exp(-dt * 2.5));
      const dist = (far ? 1.75 : 1.22) * L + 0.4 + this.distExtra;
      const height = (far ? 1.35 : 0.95) * H + 0.45;
      this.targetY += (p.pos.y - this.targetY) * (1 - Math.exp(-dt * (this.snapNext ? 100 : 9)));
      const yawC = this.yaw + this.orbit.yaw + this.lookBackK * Math.PI;
      const sy = Math.sin(yawC), cy = Math.cos(yawC);
      const tx = p.pos.x, tz = p.pos.z, ty = this.targetY + H * 0.32;
      const el = Math.sin(this.orbit.pitch) * dist;
      let d = dist * Math.cos(this.orbit.pitch);
      let cx = tx - sy * d, cz = tz - cy * d;
      let cyH = ty + height - H * 0.32 + el;
      // nicht in Häuser/Mauern stellen
      if (this.world) {
        const f = this.world.raycast(tx, tz, cx, cz, cyH - 0.5);
        if (f < 1) {
          d = Math.max(1.4, d * f - 0.4);
          cx = tx - sy * d; cz = tz - cy * d;
        }
      }
      cyH = Math.max(cyH, (p.wheels[0].groundY || 0) + 0.35);
      cam.position.set(cx, cyH, cz).add(shakeOff);
      // leicht vorausschauen
      const ahead = this.lookBackK > 0.5 ? 0 : 1.5 + Math.min(kmh, 200) * 0.012;
      this._t.set(tx + Math.sin(this.yaw) * ahead, ty + 0.15, tz + Math.cos(this.yaw) * ahead);
      cam.up.set(0, 1, 0);
      cam.lookAt(this._t);
      fov = (portrait ? 72 : 60) + clamp(kmh / 260, 0, 1) * 9;
      near = 0.1;
    } else {
      // am Auto befestigte Kameras
      const pos = this._t;
      let followPitchRoll = 1;
      if (this.mode === 'cockpit') {
        if (!car.helperWorld('Cam_Cockpit', pos)) car.object.getWorldPosition(pos).add(new THREE.Vector3(0, 1.1, 0));
        followPitchRoll = 0.55;
        // Kopf: Fliehkräfte und Beschleunigung (gedämpft)
        const hx = clamp(-p.accLat * 0.0028, -0.045, 0.045);
        const hz = clamp(-p.accLong * 0.0022, -0.04, 0.04);
        const k = 1 - Math.exp(-dt * 8);
        this.head.x += (hx - this.head.x) * k;
        this.head.z += (hz - this.head.z) * k;
        const s = Math.sin(p.yaw), c = Math.cos(p.yaw);
        pos.x += this.head.x * c + this.head.z * s;
        pos.z += -this.head.x * s + this.head.z * c;
        fov = portrait ? 78 : 68;
        near = 0.02;
      } else if (this.mode === 'hood') {
        if (!car.helperWorld('Cam_Hood', pos)) car.object.getWorldPosition(pos).add(new THREE.Vector3(0, 1.2, 0.5));
        fov = portrait ? 76 : 64;
        near = 0.05;
      } else {
        const b = meta.bounds || { min: [0, 0.2, 0], max: [0, 1, meta.dimensions.length / 2] };
        pos.set(0, clamp(b.min[1] + 0.32, 0.38, 0.75), b.max[2] + 0.06);
        car.bodyInner.updateWorldMatrix(true, false);
        car.bodyInner.localToWorld(pos);
        fov = portrait ? 80 : 68;
        near = 0.05;
      }
      cam.position.copy(pos).addScaledVector(shakeOff, 0.4);
      // Ausrichtung: Gieren des Autos, Nicken/Wanken des Aufbaus (im Cockpit gedämpft wie ein Kopf)
      let lookYaw = this.orbit.yaw + this.lookBackK * Math.PI;
      if (this.mode === 'cockpit') lookYaw += -car.state.steer * 0.1 * (1 - this.lookBackK);
      this._e.set(p.pitch * followPitchRoll, p.yaw, p.roll * followPitchRoll, 'YXZ');
      this._q.setFromEuler(this._e);
      // Kamera blickt entlang +Z des Autos (deshalb π um die Hochachse), dazu freies Umschauen
      this._e.set(this.orbit.pitch + (this.mode === 'cockpit' ? -0.06 : -0.02), Math.PI + lookYaw, 0, 'YXZ');
      this._q2.setFromEuler(this._e);
      cam.quaternion.copy(this._q).multiply(this._q2);
    }
    if (Math.abs(cam.fov - fov) > 0.01 || cam.near !== near) {
      cam.fov += (fov - cam.fov) * (this.snapNext ? 1 : 1 - Math.exp(-dt * 4));
      cam.near = near;
      cam.updateProjectionMatrix();
    }
    this.snapNext = false;
  }
}
