// Fahrphysik eines Autos – „realistisch, aber gut fahrbar“.
//
// Ohne Grafik-Abhängigkeiten (läuft auch in Node für Tests). Modell:
//  * Starrkörper mit Gieren (Fahrebene) sowie Heben, Nicken und Wanken (Federung)
//  * vier Räder mit Feder, Dämpfer und Stabilisator; Radlasten ergeben sich aus der Federung,
//    dadurch entsteht die Gewichtsverlagerung beim Bremsen, Beschleunigen und Kurvenfahren von selbst
//  * Reifen: Schräglauf und Schlupf (vereinfachte Pacejka-Kurve), Reibungsellipse, Lastabhängigkeit
//  * Antrieb: Drehmomentkurve, Gangschaltung (Automatik), Differential (Front/Heck/Allrad),
//    Motorbremse, Drehzahlbegrenzer, Bremsen mit Bremskraftverteilung, Handbremse
//  * Fahrhilfen: ABS, Antriebsschlupfregelung, Stabilitätskontrolle, geschwindigkeitsabhängige Lenkung
//
// Koordinaten wie in den Modellen: +Y oben, +Z vorne, +X links. Gieren ψ dreht um +Y
// (positiv = nach links). Nicken θ positiv = Nase runter, Wanken φ positiv = linke Seite hoch.
// Lenkeingabe steer: +1 = rechts (wie in der Garage).

const G = 9.81;
const AIR = 1.2;
const TIRE_MU = 1.15;   // die grip-Werte in cars.json sind relativ (1.0 = guter Straßenreifen)

// Reifenkurve: steigt bis zum Spitzenschlupf (s = 1) und fällt danach sanft ab (Gleiten behält Grip)
function tireCurve(s, C) {
  const B = Math.tan(Math.PI / (2 * C));            // Maximum genau bei s = 1
  return Math.sin(C * Math.atan(B * s));
}

const ASSISTS = {
  full: { abs: true, tcs: 1.0, esc: 1.0, steerAssist: 1.0 },
  sport: { abs: true, tcs: 0.5, esc: 0.35, steerAssist: 0.6 },
  off: { abs: false, tcs: 0.0, esc: 0.0, steerAssist: 0.25 },
};

export class CarPhysics {
  /**
   * @param {object} meta Eintrag aus cars.json (physics, wheels, stats, dimensions)
   * @param {object} [opts] { assists: 'full'|'sport'|'off', tuning: {engineStage, ...} }
   */
  constructor(meta, opts = {}) {
    const p = meta.physics || {};
    this.meta = meta;
    this.mass = p.massKg || meta.stats.massKg || 1400;
    this.hcg = p.cogHeight || 0.5;
    this.wf = p.weightFront || 0.5;
    this.cd = p.dragCd || 0.32;
    this.area = p.frontalArea || 2.2;
    this.electric = !!p.electric;
    this.idle = this.electric ? 0 : (p.idleRpm || 800);
    this.redline = p.redlineRpm || 7000;
    this.gears = p.gears && p.gears.length ? p.gears.slice() : [3.2, 2.1, 1.5, 1.15, 0.92, 0.76];
    this.finalDrive = p.finalDrive || 3.7;
    this.brakeForce = p.brakeForce || 1.0;
    this.brakeBias = p.brakeBias || 0.6;
    this.steerLock = (p.steerLockDeg || 33) * Math.PI / 180;
    this.vLimit = (p.speedLimiterKmh || meta.stats.topSpeedKmh || 320) / 3.6;
    const tire = p.tire || {};
    this.grip = (tire.grip || 1.0) * TIRE_MU;
    this.kappaPeak = tire.slipPeak || 0.1;
    this.alphaPeak = 0.135;                        // ~7,7° Schräglauf bis zum Haftmaximum
    this.rearGrip = tire.rearGripFactor || 1.0;
    this.diffLockFront = p.frontDiffLock || 0.0;
    this.torqueSteer = p.torqueSteer || 0.0;
    const su = p.suspension || {};
    this.setPower(p.powerKw || meta.stats.powerKw, p.torqueNm || 500);

    // Räder relativ zum Schwerpunkt (CoG liegt zwischen den Achsen gemäß Gewichtsverteilung)
    const ws = meta.wheels;
    const zf = Math.max(...ws.map((w) => w.position[2]));
    const zr = Math.min(...ws.map((w) => w.position[2]));
    this.wheelbase = zf - zr;
    this.zcg = zr + this.wheelbase * this.wf;
    const drive = meta.stats.drive || 'RWD';
    this.drive = drive;
    this.wheels = ws.map((w) => {
      const front = w.position[2] > this.zcg;
      const share = front ? this.wf : 1 - this.wf;
      const mCorner = this.mass * share / 2;
      const k = (front ? su.springFront : su.springRear) || 40000;
      const zeta = su.damping || 0.35;
      return {
        name: w.node.replace('Wheel_', ''),
        front,
        left: w.position[0] > 0,
        x: w.position[0],
        z: w.position[2] - this.zcg,
        zModel: w.position[2],
        R: w.radius,
        width: w.width,
        driven: !!w.drive,
        k,
        c: 2 * zeta * Math.sqrt(k * mCorner),
        arb: ((front ? su.antiRollFront : su.antiRollRear) || 0.5) * k * 0.6,
        travel: su.travel || 0.12,
        static: mCorner * G / k,                    // statische Einfederung
        inertia: 0.6 * 22 * w.radius * w.radius + 0.6,
        // Zustand
        omega: 0, comp: mCorner * G / k, compVel: 0, Fz: mCorner * G,
        slip: 0, slipAngle: 0, contact: true, groundY: 0, steer: 0, absK: 1, Fx: 0, Fy: 0,
        centerY: 0,
      };
    });
    this.track = Math.abs(this.wheels[0].x - this.wheels[1].x) || 1.6;
    this.Iz = this.mass * (this.wheelbase * this.wheelbase * 1.25 + this.track * this.track) / 12 * 1.15;
    this.Ipitch = this.mass * (this.wheelbase * this.wheelbase * 1.25 + 0.36) / 12;
    this.Iroll = this.mass * (this.track * this.track + 0.5) / 12;
    this.setAssists(opts.assists || 'full');

    // Zustand des Fahrzeugs (Welt)
    this.pos = { x: 0, y: this.hcg, z: 0 };       // Schwerpunkt
    this.vel = { x: 0, y: 0, z: 0 };
    this.yaw = 0; this.yawRate = 0;
    this.pitch = 0; this.pitchRate = 0;
    this.roll = 0; this.rollRate = 0;
    this.gear = 1;                                  // 1..n, 0 = N, -1 = R
    this.rpm = this.idle;
    this.shiftTimer = 0;
    this.clutch = 1;
    this.steerAngle = 0;                            // Radlenkwinkel (Gierkonvention, + = links)
    this.accLong = 0; this.accLat = 0;
    this.reverseHold = 0;
    this.tcsK = 1;
    this.handbrake = 0;
    this.speed = 0;                                 // m/s (vorwärts positiv)
    this.airTime = 0;
    // Anzeigen für das HUD: wie lange (s) die Fahrhilfe noch als „aktiv“ leuchtet
    this.absLamp = 0; this.tcsLamp = 0; this.escLamp = 0;
  }

  setPower(kw, nm) {
    this.powerW = kw * 1000;
    this.torquePeak = nm;
  }

  /**
   * Tuning aus der Garage übernehmen: Motorstufe (Leistung/Drehmoment), Käfig (Gewicht, Steifigkeit),
   * Tieferlegung (Schwerpunkt). Die Höchstgeschwindigkeit wächst mit der Leistung (Luftwiderstand ~ v³).
   */
  applyTuning(t = {}) {
    const meta = this.meta, p = meta.physics || {}, T = meta.tuning || {};
    if (this._base === undefined) {
      this._base = { mass: this.mass, hcg: this.hcg, vLimit: this.vLimit, powerKw: p.powerKw || meta.stats.powerKw,
        torque: this.torquePeak, k: this.wheels.map((w) => [w.k, w.c, w.arb]) };
    }
    const b = this._base;
    const eng = (T.engine && T.engine[t.engine || 0]) || null;
    const kw = eng ? eng.powerKw : b.powerKw;
    this.setPower(kw, eng && eng.torqueNm ? eng.torqueNm : b.torque);
    const cage = (T.cage && T.cage[t.cage || 0]) || {};
    this.mass = b.mass + (cage.massKg || 0);
    const stiff = cage.stiffness || 1;
    const low = Math.max(0, Math.min(meta.maxLoweringCm || 4, t.lowering || 0)) / 100;
    this.hcg = b.hcg - low * 0.8;
    this.wheels.forEach((w, i) => {
      const [k, c, arb] = b.k[i];
      w.k = k * (1 + low * 2.5); w.c = c * Math.sqrt(1 + low * 2.5) * stiff; w.arb = arb * stiff;
      const mCorner = this.mass * (w.front ? this.wf : 1 - this.wf) / 2;
      w.static = mCorner * G / w.k;
    });
    this.vLimit = b.vLimit * Math.cbrt(kw / b.powerKw);
    this.tuningApplied = { ...t };
  }

  setAssists(level) {
    this.assistLevel = ASSISTS[level] ? level : 'full';
    this.assist = ASSISTS[this.assistLevel];
  }

  /** Auto an eine Stelle setzen (stehend). */
  place(x, z, yaw, groundY = 0) {
    this.pos.x = x; this.pos.z = z; this.pos.y = groundY + this.hcg;
    this.vel.x = this.vel.y = this.vel.z = 0;
    this.yaw = yaw; this.yawRate = 0;
    this.pitch = this.pitchRate = this.roll = this.rollRate = 0;
    this.gear = 1; this.rpm = this.idle; this.shiftTimer = 0;
    for (const w of this.wheels) { w.omega = 0; w.comp = w.static; w.compVel = 0; w.groundY = groundY; }
  }

  // Motordrehmoment bei Drehzahl (Nm, Vollgas)
  engineTorque(rpm) {
    if (this.electric) {
      const w = Math.max(rpm, 1) * Math.PI / 30;
      return Math.min(this.torquePeak, this.powerW / w);
    }
    const r = Math.max(rpm, this.idle);
    // Kurve: steigt bis ~45 % der Maximaldrehzahl auf das Maximum, danach Leistungsgrenze
    const rise = Math.min(1, 0.55 + 0.45 * (r / (this.redline * 0.45)));
    const w = r * Math.PI / 30;
    const fall = r > this.redline * 0.9 ? Math.max(0.6, 1 - (r - this.redline * 0.9) / (this.redline * 0.25)) : 1;
    return Math.min(this.torquePeak * rise, this.powerW / w * 1.04) * fall;
  }

  ratio() {
    if (this.gear === 0) return 0;
    if (this.gear < 0) return -this.gears[0] * 1.1 * this.finalDrive;
    return this.gears[this.gear - 1] * this.finalDrive;
  }

  /**
   * Ein Zeitschritt. input: { throttle 0..1, brake 0..1, steer -1..1 (+ = rechts), handbrake 0..1 }
   * world: { groundHeight(x,z), grip(x,z) } (optional)
   */
  step(dt, input, world) {
    const sub = Math.max(1, Math.ceil(dt / (1 / 240)));
    const h = dt / sub;
    for (let i = 0; i < sub; i++) this._step(h, input, world);
  }

  _step(dt, inp, world) {
    this.absLamp = Math.max(0, this.absLamp - dt);
    this.tcsLamp = Math.max(0, this.tcsLamp - dt);
    this.escLamp = Math.max(0, this.escLamp - dt);
    const fwd = { x: Math.sin(this.yaw), z: Math.cos(this.yaw) };
    const left = { x: Math.cos(this.yaw), z: -Math.sin(this.yaw) };
    let u = this.vel.x * fwd.x + this.vel.z * fwd.z;      // vorwärts
    let v = this.vel.x * left.x + this.vel.z * left.z;    // nach links
    const speed = Math.hypot(u, v);
    this.speed = u;

    // ---------------- Eingaben: Gang/Richtung ----------------
    let throttle = Math.min(1, Math.max(0, inp.throttle || 0));
    let brake = Math.min(1, Math.max(0, inp.brake || 0));
    // Rückwärts: im Stand Bremse halten -> R; Gas im Rückwärtsgang = rückwärts fahren
    if (this.gear >= 0 && u < 0.6 && brake > 0.3 && throttle < 0.05) {
      this.reverseHold += dt;
      if (this.reverseHold > 0.35 && u < 0.3) { this.gear = -1; this.reverseHold = 0; }
    } else if (this.gear >= 0) {
      this.reverseHold = 0;
    }
    if (this.gear < 0) {
      // im Rückwärtsgang: „Bremse“ fährt rückwärts, „Gas“ bremst
      const t = throttle;
      throttle = brake; brake = t;
      if (brake > 0.3 && u > -0.6) { this.gear = 1; this.shiftTimer = 0; }
    }

    // ---------------- Lenkung ----------------
    const ref = 7.5;                                     // m/s
    const sAssist = this.assist.steerAssist;
    const limit = this.steerLock / Math.sqrt(1 + Math.pow(Math.max(0, Math.abs(u)) / ref, 2) * (0.35 + 0.65 * sAssist));
    let target = -(inp.steer || 0) * Math.max(limit, 0.035);
    // Gegenlenk-Hilfe: bei Übersteuern Räder in Fahrtrichtung drehen
    if (sAssist > 0 && Math.abs(u) > 4) {
      const beta = Math.atan2(v, Math.abs(u));
      target += beta * 0.45 * sAssist * (inp.counterSteer === false ? 0 : 1);
    }
    target = Math.max(-this.steerLock, Math.min(this.steerLock, target));
    const rate = 3.2;                                   // rad/s am Rad
    this.steerAngle += Math.max(-rate * dt, Math.min(rate * dt, target - this.steerAngle));

    // ---------------- Antrieb ----------------
    const ratio = this.ratio();
    const driven = this.wheels.filter((w) => w.driven);
    const avgOmega = driven.reduce((a, w) => a + w.omega, 0) / Math.max(1, driven.length);
    let engineRpm = Math.abs(avgOmega * ratio) * 30 / Math.PI;
    if (this.shiftTimer > 0) this.shiftTimer -= dt;
    // Anfahren: Kupplung schleift, Motor hält Drehzahl über Leerlauf
    const launchRpm = this.idle + throttle * (this.electric ? 0 : Math.min(3000, this.redline * 0.42));
    const slipping = !this.electric && engineRpm < launchRpm && this.gear !== 0;
    const rpmTarget = slipping ? launchRpm : Math.max(this.idle, engineRpm);
    this.rpm += (Math.min(rpmTarget, this.redline * 1.02) - this.rpm) * Math.min(1, dt * (slipping ? 8 : 30));

    // Automatik
    if (this.gear > 0 && this.shiftTimer <= 0 && !this.electric) {
      const up = this.redline * (0.82 + 0.12 * throttle);
      const down = this.redline * (0.38 + 0.14 * throttle);
      if (this.rpm > up && this.gear < this.gears.length && engineRpm > up * 0.98) {
        this.gear++; this.shiftTimer = 0.12;
      } else if (this.gear > 1 && engineRpm < down) {
        const next = this.gears[this.gear - 2] * this.finalDrive * Math.abs(avgOmega) * 30 / Math.PI;
        if (next < this.redline * 0.88) { this.gear--; this.shiftTimer = 0.1; }
      }
    }

    let torque = 0;
    if (this.gear !== 0 && this.shiftTimer <= 0) {
      const t = this.engineTorque(this.rpm) * throttle;
      const limiter = this.rpm >= this.redline || (u > this.vLimit && this.gear > 0) ? 0 : 1;
      torque = t * limiter;
      // Motorbremse (Verbrenner) ohne Gas
      // Motorbremse bzw. Rekuperation wirkt immer gegen die Drehrichtung
      const rot = Math.sign(avgOmega * ratio);
      if (!this.electric && throttle < 0.05 && engineRpm > this.idle * 1.2) torque -= rot * this.torquePeak * 0.12 * (engineRpm / this.redline);
      if (this.electric && throttle < 0.05 && Math.abs(u) > 2) torque -= rot * this.torquePeak * 0.06;   // Rekuperation
    }
    // Antriebsschlupfregelung
    const tcs = this.assist.tcs;
    if (tcs > 0 && torque > 0) {
      // Regelung auf den Spitzenschlupf (dort ist die Antriebskraft am größten)
      const maxSlip = Math.max(...driven.map((w) => w.slip));
      const err = (this.kappaPeak * 1.1 - maxSlip) / this.kappaPeak;
      this.tcsK = Math.max(0.1, Math.min(1, this.tcsK + dt * (err > 0 ? 6 : 14) * err));
      torque *= 1 - tcs + tcs * this.tcsK;
      if (this.tcsK < 0.93) this.tcsLamp = 0.35;
    } else {
      this.tcsK = Math.min(1, this.tcsK + dt * 3);
    }
    const wheelTorque = torque * ratio * 0.9;            // Wirkungsgrad

    // Verteilung auf die angetriebenen Räder
    const nF = driven.filter((w) => w.front).length, nR = driven.length - nF;
    const frontShare = nF && nR ? 0.4 : nF ? 1 : 0;

    // ---------------- Federung und Radlasten ----------------
    const gh = world && world.groundHeight ? world.groundHeight : null;
    const gripAt = world && world.grip ? world.grip : null;
    const cosY = Math.cos(this.yaw), sinY = Math.sin(this.yaw);
    let contacts = 0;
    for (const w of this.wheels) {
      const wx = this.pos.x + w.x * cosY + w.z * sinY;
      const wz = this.pos.z - w.x * sinY + w.z * cosY;
      w.wx = wx; w.wz = wz;
      w.groundY = gh ? gh(wx, wz) : 0;
      if (gh) {
        w.gx = (gh(wx + 0.12, wz) - gh(wx - 0.12, wz)) / 0.24;
        w.gz = (gh(wx, wz + 0.12) - gh(wx, wz - 0.12)) / 0.24;
      } else {
        w.gx = 0; w.gz = 0;
      }
      const mountY = this.pos.y - this.pitch * w.z + this.roll * w.x;
      const prev = w.comp;
      w.comp = w.static + (this.hcg - (mountY - w.groundY));
      w.compVel = (w.comp - prev) / dt;
      w.contact = w.comp > 0;
      if (w.contact) contacts++;
      w.mountY = mountY;
    }
    // Stabilisatoren: Differenz links/rechts je Achse
    for (const axle of [true, false]) {
      const pair = this.wheels.filter((w) => w.front === axle);
      if (pair.length !== 2) continue;
      const [a, b] = pair[0].left ? pair : [pair[1], pair[0]];
      const d = Math.max(0, a.comp) - Math.max(0, b.comp);
      a.arbF = a.arb * d;
      b.arbF = -a.arb * d;
    }
    let Fy_total = 0, tauPitch = 0, tauRoll = 0, slopeX = 0, slopeZ = 0;
    for (const w of this.wheels) {
      if (!w.contact) { w.Fz = 0; continue; }
      const bump = w.comp > w.static + w.travel ? (w.comp - w.static - w.travel) * w.k * 8 : 0;
      let Fz = w.k * w.comp + w.c * w.compVel + (w.arbF || 0) + bump;
      Fz = Math.max(0, Fz);
      w.Fz = Fz;
      Fy_total += Fz;
      // waagerechter Anteil der Normalkraft auf Schrägen (bergauf bremst, bergab schiebt)
      const g = Math.hypot(w.gx, w.gz);
      if (g > 1e-4) {
        const gl = Math.min(1.5, g);
        const H = Fz * gl / Math.sqrt(1 + gl * gl);     // waagerechter Anteil, Richtung bergab
        slopeX -= w.gx / g * H;
        slopeZ -= w.gz / g * H;
      }
      tauPitch += -w.z * Fz;
      tauRoll += w.x * Fz;
      w.centerY = w.groundY + w.R;
    }
    for (const w of this.wheels) if (!w.contact) w.centerY = w.mountY - (this.hcg - w.R) - w.static;

    // ---------------- Reifenkräfte ----------------
    let Fl_sum = 0, Ff_sum = 0, tauYaw = 0;
    const absOn = this.assist.abs;
    const hb = Math.min(1, Math.max(0, inp.handbrake || 0));
    for (const w of this.wheels) {
      const delta = w.front ? this.steerAngle : 0;
      w.steer = delta;
      // Geschwindigkeit am Radaufstandspunkt (Fahrzeugkoordinaten)
      const vl = v + this.yawRate * w.z;
      const vf = u - this.yawRate * w.x;
      const sd = Math.sin(delta), cd = Math.cos(delta);
      const vLong = vl * sd + vf * cd;
      const vLat = vl * cd - vf * sd;
      // Antriebs- und Bremsmoment
      let Tdrive = 0;
      if (w.driven) {
        const axleShare = w.front ? frontShare : 1 - frontShare;
        const n = w.front ? nF : nR;
        Tdrive = wheelTorque * axleShare / Math.max(1, n);
        if (w.front && this.torqueSteer) Tdrive *= 1 + (w.left ? 1 : -1) * this.torqueSteer * (inp.steer || 0) * 0.3;
      }
      const bias = w.front ? this.brakeBias : 1 - this.brakeBias;
      // Bremsanlage kann alle Räder blockieren; brakeForce bestimmt, wie kräftig das Pedal anspricht
      let Tbrake = brake * Math.min(1.6, 0.6 + this.brakeForce) * this.mass * G * 1.5 * bias * 0.5 * w.R;
      if (!w.front) Tbrake += hb * this.mass * G * 0.9 * w.R;
      if (absOn && brake > 0 && Math.abs(vLong) > 2.5) {
        // ABS: Bremsschlupf um den Spitzenwert halten
        const err = (this.kappaPeak * 1.05 + w.slip) / this.kappaPeak;      // < 0: blockiert zu stark
        w.absK = Math.max(0.15, Math.min(1, w.absK + dt * (err > 0 ? 10 : 25) * err));
        if (!(hb > 0 && !w.front)) Tbrake *= w.absK;
        if (w.absK < 0.97) this.absLamp = 0.35;
      } else {
        w.absK = 1;
      }
      // Reifenmodell
      const grip = this.grip * (w.front ? 1 : this.rearGrip) * (gripAt ? gripAt(w.wx, w.wz) : 1);
      const Fz0 = this.mass * G * (w.front ? this.wf : 1 - this.wf) / 2;
      const loadK = 1 - 0.1 * (w.Fz / Math.max(1, Fz0) - 1);   // Lastempfindlichkeit
      const muFz = grip * Math.max(0.6, loadK) * w.Fz;
      // Längsschlupf: Rad halb-implizit integrieren (stabil auch bei kleiner Geschwindigkeit)
      const vDen = Math.max(Math.abs(vLong), 1.2);
      const C_long = 1.55, C_lat = 1.4;
      const kLong = muFz * Math.tan(Math.PI / (2 * C_long)) * C_long / (this.kappaPeak * vDen); // dF/d(ωR - v)
      const I = w.inertia + (w.driven && this.gear !== 0 && this.shiftTimer <= 0 ? 0.25 * ratio * ratio / Math.max(1, driven.length) : 0);
      // Bremse wirkt gegen die Drehrichtung (bzw. Fahrtrichtung, wenn das Rad steht)
      const dir = Math.sign(w.omega) || Math.sign(vLong) || 1;
      const T = Tdrive - dir * Tbrake - dir * 0.012 * w.Fz * w.R;      // inkl. Rollwiderstand
      // Haften: Reifenkraft linear im Schlupf, ω implizit gelöst (stabil auch im Stand)
      let om = (I * w.omega + dt * (T + kLong * w.R * vLong)) / (I + dt * kLong * w.R * w.R);
      const Flin = kLong * (om * w.R - vLong);
      if (w.contact && Math.abs(Flin) > muFz) {
        // Gleiten: Reifen überträgt nur noch die Gleitreibung -> durchdrehen bzw. blockieren möglich
        const Fs = Math.sign(Flin) * muFz * 0.82;
        om = w.omega + dt * (T - w.R * Fs) / I;
      } else if (!w.contact) {
        om = w.omega + dt * T / I;
      }
      // Bremse kann das Rad höchstens blockieren, nicht rückwärts drehen
      if (Tbrake > 0 && om * dir < 0) om = 0;
      w.omega = om;
      const slipRatio = (om * w.R - vLong) / vDen;
      w.slip = slipRatio;
      const alpha = Math.atan2(vLat, Math.max(Math.abs(vLong), 1.6));
      w.slipAngle = alpha;
      // Reibungsellipse (kombinierter Schlupf)
      const sx = slipRatio / this.kappaPeak;
      const sy = alpha / this.alphaPeak;
      const s = Math.hypot(sx, sy);
      let Fx = 0, Fy = 0;
      if (w.contact && s > 1e-6) {
        const blend = Math.min(1, s);
        const C = C_lat + (C_long - C_lat) * (Math.abs(sx) / (Math.abs(sx) + Math.abs(sy) + 1e-9));
        const F = muFz * tireCurve(s, C) * (0.9 + 0.1 * blend);
        Fx = F * sx / s;
        Fy = -F * sy / s;
      }
      // Bei sehr kleiner Geschwindigkeit seitliches Rutschen dämpfen (kein Zittern im Stand)
      if (speed < 1.0) Fy += -vLat * w.Fz * 0.6 * (1 - speed);
      w.Fx = Fx; w.Fy = Fy;
      // in Fahrzeugkoordinaten (links, vorwärts)
      const Fl = Fx * sd + Fy * cd;
      const Ff = Fx * cd - Fy * sd;
      Fl_sum += Fl;
      Ff_sum += Ff;
      tauYaw += w.z * Fl - w.x * Ff;
      // Reifenkräfte greifen am Boden an -> Nick- und Wankmoment
      tauPitch += -this.hcg * Ff;
      tauRoll += this.hcg * Fl;
    }

    Fl_sum += slopeX * left.x + slopeZ * left.z;
    Ff_sum += slopeX * fwd.x + slopeZ * fwd.z;

    // Luftwiderstand und Abtrieb
    const drag = 0.5 * AIR * this.cd * this.area;
    Ff_sum -= drag * u * Math.abs(u);
    Fl_sum -= drag * 2.5 * v * Math.abs(v);

    // Stabilitätskontrolle: Gierrate auf das Machbare begrenzen
    const esc = this.assist.esc;
    if (esc > 0 && Math.abs(u) > 5) {
      const rTarget = u * Math.tan(this.steerAngle) / this.wheelbase;
      const rMax = this.grip * G * 1.05 / Math.abs(u);
      const rWant = Math.max(-rMax, Math.min(rMax, rTarget));
      const err = this.yawRate - rWant;
      if (Math.abs(err) > 0.08) { tauYaw -= err * this.Iz * 7 * esc; if (Math.abs(err) > 0.12) this.escLamp = 0.35; }
    }

    // ---------------- Integration ----------------
    const m = this.mass;
    const ax_l = Fl_sum / m, ax_f = Ff_sum / m;
    this.accLong = ax_f; this.accLat = ax_l;
    const awx = ax_l * left.x + ax_f * fwd.x;
    const awz = ax_l * left.z + ax_f * fwd.z;
    this.vel.x += awx * dt;
    this.vel.z += awz * dt;
    this.yawRate += tauYaw / this.Iz * dt;
    // Stillstand: nicht von selbst weiterrollen
    if (speed < 0.08 && throttle < 0.02 && (brake > 0.05 || hb > 0.05)) {
      this.vel.x *= 0.5; this.vel.z *= 0.5; this.yawRate *= 0.5;
    }
    this.pos.x += this.vel.x * dt;
    this.pos.z += this.vel.z * dt;
    this.yaw += this.yawRate * dt;

    // Heben, Nicken, Wanken
    const ay = Fy_total / m - G;
    this.vel.y += ay * dt;
    this.pos.y += this.vel.y * dt;
    this.pitchRate += (tauPitch / this.Ipitch) * dt;
    this.rollRate += (tauRoll / this.Iroll) * dt;
    this.pitchRate *= 1 - Math.min(1, dt * 2);
    this.rollRate *= 1 - Math.min(1, dt * 2);
    this.pitch += this.pitchRate * dt;
    this.roll += this.rollRate * dt;
    this.pitch = Math.max(-0.35, Math.min(0.35, this.pitch));
    this.roll = Math.max(-0.35, Math.min(0.35, this.roll));
    if (contacts === 0) this.airTime += dt; else this.airTime = 0;
    // nicht in den Boden fallen (z. B. nach Sprung): mindestens auf den Rädern stehen
    const minY = Math.max(...this.wheels.map((w) => w.groundY)) + 0.12;
    if (this.pos.y < minY) { this.pos.y = minY; if (this.vel.y < 0) this.vel.y = 0; }
  }

  // ---------------- Abfragen ----------------
  get speedKmh() { return this.speed * 3.6; }

  gearLabel() {
    if (this.gear < 0) return 'R';
    if (this.gear === 0) return 'N';
    if (Math.abs(this.speed) < 0.3 && this.rpm <= this.idle * 1.05) return this.electric ? 'D' : 'N';
    return this.electric ? 'D' : String(this.gear);
  }

  /** Vier Ecken des Fahrzeugs in der Ebene (für Kollisionen), Welt-Koordinaten. */
  footprint(dims) {
    const hl = dims.length / 2, hw = dims.width / 2;
    return { cx: this.pos.x + Math.sin(this.yaw) * (dims.centerZ - this.zcg), cz: this.pos.z + Math.cos(this.yaw) * (dims.centerZ - this.zcg),
      hl, hw, yaw: this.yaw };
  }
}
