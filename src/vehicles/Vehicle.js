// Ein geladenes Fahrzeug: Tuning, Detailstufen (LOD), Lichter, Cockpit-Animation.
//
// Die GLB-Dateien aus tools/car-generator markieren alle wichtigen Knoten
// über extras (glTF) -> object.userData:
//   lod: 0|1|2                    Detailstufe (Geschwister-Gruppe = eine LOD-Gruppe)
//   tune: spoiler|livery|exhaust|cage|engine|rim|neon, variant / stage
//   wheel: FL|FR|RL|RR, steer, radius, drive     caliper: FL…
//   anim: steering|needle|pedal                  helper: Cam_Cockpit|Cam_Hood|Seat_Driver
//   shadow: true (Kontaktschatten)
// Materialien tragen userData.group (interior|display|lights|neon), base (Grund-Emission) und tune.

import * as THREE from 'three';
import { Displays } from './displays.js';

export const FINISHES = {
  gloss: { label: 'Glanz', metalness: 0.0, roughness: 0.22, clearcoat: 1.0, ccRough: 0.03, flakes: 0, irid: 0 },
  metallic: { label: 'Metallic', metalness: 0.55, roughness: 0.34, clearcoat: 1.0, ccRough: 0.03, flakes: 1, irid: 0 },
  pearl: { label: 'Perleffekt', metalness: 0.35, roughness: 0.28, clearcoat: 1.0, ccRough: 0.02, flakes: 0.6, irid: 0.8 },
  satin: { label: 'Satin', metalness: 0.45, roughness: 0.5, clearcoat: 0.35, ccRough: 0.35, flakes: 0.4, irid: 0 },
  matte: { label: 'Matt', metalness: 0.15, roughness: 0.78, clearcoat: 0.0, ccRough: 0.5, flakes: 0, irid: 0 },
  chrome: { label: 'Chrom', metalness: 1.0, roughness: 0.07, clearcoat: 0.0, ccRough: 0.0, flakes: 0, irid: 0 },
};

export function defaultTuning(meta) {
  return {
    paint: meta.defaultPaint || '#c8102e',
    finish: 'metallic',
    roofColor: null,              // null = wie Lack (sonst Zweifarb-/Kontrastdach)
    rim: 1,
    rimColor: meta.defaultRim || '#a3a9b2',
    caliper: meta.defaultCaliper || '#c8102e',
    spoiler: 0,
    livery: 0,
    liveryColor: '#f2f2f2',
    neon: false,
    neonColor: meta.defaultAccent || '#00e5ff',
    lowering: 0,                  // cm
    tint: 0.35,                   // 0 (klar) .. 1 (fast schwarz)
    exhaust: 1,
    engine: 0,
    cage: 0,
    ambient: null,                // Farbe der Ambiente-Beleuchtung (null = Werkseinstellung)
  };
}

export class Vehicle {
  constructor(gltf, meta) {
    this.meta = meta;
    this.root = gltf.scene;
    this.root.name = meta.id;
    this.object = new THREE.Group();        // äußerer Knoten (Position/Drehung im Spiel)
    this.object.add(this.root);
    this.state = { steer: 0, speedKmh: 0, rpm: 900, throttle: 0, brake: 0, gear: 'P', lights: false,
                   indicator: 0, reverse: false, odo: 0, spin: 0 };
    this.settingsView = { interiorLight: 0.25, displayBrightness: 0.7 };
    this.lodLevel = -1;
    this.forcedLod = null;
    this.night = false;
    this._index();
    this.tuning = defaultTuning(meta);
    this.displays = new Displays(this);
    this.applyTuning(this.tuning);
    this.setLOD(0);
  }

  // --------------------------------------------------------------
  _index() {
    this.wheels = [];
    this.calipers = [];
    this.tune = { spoiler: [], livery: [], exhaust: [], cage: [], engine: [], rim: [], neon: [] };
    this.lodGroups = [];
    this.anim = { steering: null, needles: [], pedals: [] };
    this.helpers = {};
    this.shadow = null;
    const mats = new Map();
    const lodParents = new Map();
    this.root.traverse((o) => {
      const u = o.userData || {};
      if (u.wheel) this.wheels.push({ obj: o, pos: u.wheel, steer: !!u.steer, radius: u.radius || 0.33, base: o.quaternion.clone() });
      if (u.caliper) this.calipers.push({ obj: o, steer: !!u.steer, base: o.quaternion.clone() });
      if (u.tune && this.tune[u.tune]) this.tune[u.tune].push(o);
      if (u.lod !== undefined && o.parent) {
        if (!lodParents.has(o.parent)) lodParents.set(o.parent, []);
        lodParents.get(o.parent).push(o);
      }
      if (u.anim === 'steering') this.anim.steering = { obj: o, base: o.quaternion.clone() };
      if (u.anim === 'needle') this.anim.needles.push({ obj: o, gauge: u.gauge, base: o.quaternion.clone() });
      if (u.anim === 'pedal') this.anim.pedals.push({ obj: o, pedal: u.pedal, base: o.quaternion.clone() });
      if (u.helper) this.helpers[u.helper] = o;
      if (u.shadow) this.shadow = o;
      if (o.isMesh) {
        const list = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of list) mats.set(m.uuid, m);
      }
    });
    for (const [parent, kids] of lodParents) {
      const maxk = Math.max(...kids.map((k) => k.userData.lod));
      this.lodGroups.push({ parent, kids, maxk });
    }
    this.materialList = [...mats.values()];
    this.mat = {};
    for (const m of this.materialList) this.mat[m.name] = m;
    // Karosserieteile (für Tieferlegung): alles außer Rädern, Bremssätteln und Kontaktschatten.
    // gltf.scene enthält genau einen Wurzelknoten (das Auto); dessen Kinder sind die Bauteile.
    this.carRoot = this.root.children.length === 1 ? this.root.children[0] : this.root;
    const isWheel = new Set([...this.wheels.map((w) => w.obj), ...this.calipers.map((c) => c.obj)]);
    this.bodyNodes = this.carRoot.children.filter((c) => !isWheel.has(c) && c !== this.shadow);
    for (const n of this.bodyNodes) n.userData.baseY = n.position.y;
    this._prepareMaterials();
  }

  _prepareMaterials() {
    for (const m of this.materialList) {
      const u = m.userData || {};
      m.userData.baseEmissive = u.base !== undefined ? u.base : m.emissiveIntensity;
      if (m.name === 'Paint' || m.name === 'Paint2') m.userData.flakes = m.normalMap || null;
      if (m.transparent) {                       // glTF alphaMode BLEND (Scheiben, Lampengläser, Deko-Glas)
        m.depthWrite = false;
        if (m.name === 'Glass') m.side = THREE.DoubleSide;
      }
      if (m.name === 'ContactShadow') {
        m.transparent = true;
        m.depthWrite = false;
        m.polygonOffset = true;
        m.polygonOffsetFactor = -2;
      }
      m.envMapIntensity = m.name.startsWith('Display') ? 0.35 : 1.0;
    }
    if (this.mat.Glass) {
      this.mat.Glass.userData.baseColor = this.mat.Glass.color.clone();
    }
    this.root.traverse((o) => {
      if (!o.isMesh) return;
      const name = o.material && o.material.name;
      const transparent = o.material && o.material.transparent;
      o.castShadow = !transparent && name !== 'ContactShadow';
      o.receiveShadow = !transparent;
      if (name === 'ContactShadow') {
        o.renderOrder = -1;
        o.castShadow = false;
        o.receiveShadow = false;
      }
      if (name === 'Glass') o.renderOrder = 2;
    });
  }

  // --------------------------------------------------------------
  // Qualität: Klarlack/Sheen/Iridescence nur bei Mittel/Hoch
  setQuality(q) {
    this.quality = q;
    for (const m of this.materialList) {
      if (!m.isMeshPhysicalMaterial) continue;
      if (m.userData.cc === undefined) {
        m.userData.cc = m.clearcoat;
        m.userData.sheen = m.sheen;
        m.userData.irid = m.iridescence;
      }
      const on = q.clearcoat;
      m.clearcoat = on ? m.userData.cc : 0;
      m.sheen = on ? m.userData.sheen : 0;
      if (!(m.name === 'Paint' || m.name === 'Paint2')) m.iridescence = on ? m.userData.irid : 0;
    }
    this.applyTuning(this.tuning);
  }

  // --------------------------------------------------------------
  applyTuning(t) {
    this.tuning = { ...this.tuning, ...t };
    const T = this.tuning;
    const fin = FINISHES[T.finish] || FINISHES.metallic;
    const highQ = !this.quality || this.quality.clearcoat;
    for (const [name, color] of [['Paint', T.paint], ['Paint2', T.roofColor || T.paint]]) {
      const m = this.mat[name];
      if (!m) continue;
      m.color.set(color);
      if (T.finish === 'chrome') m.color.lerp(new THREE.Color(0xd8dce4), 0.55);
      m.metalness = fin.metalness;
      m.roughness = fin.roughness;
      if (m.isMeshPhysicalMaterial) {
        m.clearcoat = highQ ? fin.clearcoat : 0;
        m.clearcoatRoughness = fin.ccRough;
        m.iridescence = highQ ? fin.irid : 0;
        m.iridescenceIOR = 1.6;
        m.iridescenceThicknessRange = [180, 620];
      }
      m.normalMap = fin.flakes > 0 ? m.userData.flakes : null;
      if (m.normalMap) m.normalScale.set(0.18 * fin.flakes, 0.18 * fin.flakes);
      // Shader nur neu übersetzen, wenn sich die benötigten Funktionen ändern (sonst ruckelt das Tuning)
      const feat = `${!!m.normalMap}|${m.clearcoat > 0}|${m.iridescence > 0}`;
      if (m.userData.feat !== feat) {
        m.userData.feat = feat;
        m.needsUpdate = true;
      }
    }
    for (const o of this.tune.rim) o.visible = o.userData.variant === T.rim;
    if (this.mat.Rim) this.mat.Rim.color.set(T.rimColor);
    if (this.mat.Caliper) this.mat.Caliper.color.set(T.caliper);
    for (const o of this.tune.spoiler) o.visible = o.userData.variant === T.spoiler;
    for (const o of this.tune.livery) o.visible = o.userData.variant === T.livery;
    if (this.mat.Livery) this.mat.Livery.color.set(T.liveryColor);
    for (const o of this.tune.exhaust) o.visible = o.userData.variant === T.exhaust;
    for (const o of this.tune.cage) o.visible = o.userData.variant === T.cage;
    for (const o of this.tune.engine) o.visible = o.userData.stage <= T.engine;
    for (const o of this.tune.neon) o.visible = !!T.neon;
    for (const name of ['Accent', 'Underglow']) {
      const m = this.mat[name];
      if (!m) continue;
      m.color.set(T.neonColor);
      m.emissive.set(T.neonColor);
      const on = name === 'Underglow' ? T.neon : true;   // Akzentkanten leuchten immer, Unterboden nur mit Neon
      m.emissiveIntensity = on ? m.userData.baseEmissive * (name === 'Accent' && !T.neon ? 0.35 : 1) : 0;
    }
    if (this.mat.InteriorAmbient && T.ambient) {
      this.mat.InteriorAmbient.color.set(T.ambient);
      this.mat.InteriorAmbient.emissive.set(T.ambient);
    }
    if (this.mat.Glass) {
      const g = this.mat.Glass;
      const k = THREE.MathUtils.clamp(T.tint, 0, 1);
      g.opacity = 0.14 + 0.78 * k;
      g.color.copy(g.userData.baseColor).multiplyScalar(1.0 - 0.6 * k);
    }
    const low = THREE.MathUtils.clamp(T.lowering, 0, this.meta.maxLoweringCm || 4) / 100;
    for (const n of this.bodyNodes) n.position.y = n.userData.baseY - low;
    this._applyLights();
    this._applyInterior();
  }

  // --------------------------------------------------------------
  setInteriorLight(v) {
    this.settingsView.interiorLight = v;
    this._applyInterior();
  }

  setDisplayBrightness(v) {
    this.settingsView.displayBrightness = v;
    this._applyInterior();
  }

  _applyInterior() {
    const il = this.settingsView.interiorLight;
    const db = this.settingsView.displayBrightness;
    for (const m of this.materialList) {
      const g = m.userData.group;
      if (g === 'interior') m.emissiveIntensity = m.userData.baseEmissive * il;
      else if (g === 'display') m.emissiveIntensity = m.userData.baseEmissive * (0.05 + 1.15 * db) * (this.night ? 0.8 : 1.0);
    }
    if (this.cabinLight) this.cabinLight.intensity = 0.6 * il;
  }

  setNight(on) {
    this.night = on;
    this._applyLights();
    this._applyInterior();
  }

  setLights(on) {
    this.state.lights = on;
    this._applyLights();
  }

  _applyLights() {
    const s = this.state;
    for (const m of this.materialList) {
      const u = m.userData;
      if (u.group !== 'lights') continue;
      let k = u.baseEmissive;
      switch (u.light) {
        case 'head': k = s.lights ? u.baseEmissive : 0.15; break;
        case 'drl': k = u.baseEmissive * (this.night ? 0.7 : 1.0); break;
        case 'tail': k = s.lights || this.night ? u.baseEmissive : u.baseEmissive * 0.45; break;
        case 'brake': k = s.brake > 0.05 ? (u.active || 6.0) : u.baseEmissive; break;
        case 'reverse': k = s.reverse ? (u.active || 4.0) : 0; break;
        case 'indicator': k = 0; break;   // blinkt in update()
      }
      m.emissiveIntensity = k;
    }
    if (this.headLamps) for (const l of this.headLamps) l.visible = s.lights;
  }

  // Scheinwerfer als echte Lichtquellen (Nacht)
  createHeadLamps() {
    if (this.headLamps) return this.headLamps;
    const pts = (this.meta.lights && this.meta.lights.head) || [];
    this.headLamps = [];
    const uniq = [];
    for (const p of pts) if (!uniq.some((q) => Math.abs(q[0] - p[0]) < 0.05 && Math.abs(q[2] - p[2]) < 0.05)) uniq.push(p);
    const list = uniq.length ? uniq.slice(0, 1) : [];
    for (const p of list) {
      for (const sx of [1, -1]) {
        const spot = new THREE.SpotLight(0xf2f6ff, 120, 45, 0.42, 0.45, 2.0);
        spot.position.set(sx * Math.abs(p[0]), p[1], p[2] + 0.02);
        spot.target.position.set(sx * Math.abs(p[0]) * 1.4, 0.0, p[2] + 14);
        spot.castShadow = false;
        spot.visible = this.state.lights;
        this.root.add(spot);
        this.root.add(spot.target);
        this.headLamps.push(spot);
      }
    }
    return this.headLamps;
  }

  createCabinLight() {
    if (this.cabinLight) return this.cabinLight;
    const eye = (this.meta.cockpit && this.meta.cockpit.eye) || [0.3, 1.0, 0];
    const l = new THREE.PointLight(0xffe2c0, 0.6 * this.settingsView.interiorLight, 1.6, 2);
    l.position.set(0, eye[1] + 0.05, eye[2] + 0.2);
    this.root.add(l);
    this.cabinLight = l;
    return l;
  }

  // --------------------------------------------------------------
  // Detailstufen
  setLOD(level) {
    if (level === this.lodLevel) return;
    this.lodLevel = level;
    for (const g of this.lodGroups) {
      for (const k of g.kids) {
        const lod = k.userData.lod;
        k.visible = g.maxk === 0 ? level === 0 : lod === Math.min(level, g.maxk);
      }
    }
  }

  updateLOD(camera, distances, forceNear = false) {
    if (this.forcedLod !== null && this.forcedLod !== undefined) {
      this.setLOD(this.forcedLod);
      return this.lodLevel;
    }
    if (forceNear) {
      this.setLOD(0);
      return 0;
    }
    const p = new THREE.Vector3();
    this.object.getWorldPosition(p);
    p.y += 0.6;
    const d = camera.position.distanceTo(p) * (camera.zoom ? 1 / camera.zoom : 1);
    // etwas Hysterese gegen Flackern an der Grenze
    const [d0, d1] = distances;
    const cur = this.lodLevel;
    let lvl = d < d0 ? 0 : d < d1 ? 1 : 2;
    if (cur === 0 && lvl === 1 && d < d0 * 1.08) lvl = 0;
    if (cur === 1 && lvl === 2 && d < d1 * 1.08) lvl = 1;
    this.setLOD(lvl);
    return this.lodLevel;
  }

  // --------------------------------------------------------------
  // Animation: Räder, Lenkrad, Nadeln, Pedale, Blinker, Displays
  update(dt, time) {
    const s = this.state;
    const v = s.speedKmh / 3.6;
    s.odo += Math.abs(v) * dt / 1000;
    const steerMax = THREE.MathUtils.degToRad((this.meta.physics && this.meta.physics.steerLockDeg) || 32);
    const steerAngle = s.steer * steerMax;
    const qSteer = new THREE.Quaternion();
    const qSpin = new THREE.Quaternion();
    const X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0), Z = new THREE.Vector3(0, 0, 1);
    for (const w of this.wheels) {
      if (w.spin === undefined) w.spin = 0;
      w.spin += (v / w.radius) * dt;
      qSteer.setFromAxisAngle(Y, w.steer ? -steerAngle : 0);
      qSpin.setFromAxisAngle(X, w.spin);
      w.obj.quaternion.copy(w.base).multiply(qSteer).multiply(qSpin);
    }
    for (const c of this.calipers) {
      qSteer.setFromAxisAngle(Y, c.steer ? -steerAngle : 0);
      c.obj.quaternion.copy(c.base).multiply(qSteer);
    }
    const ratio = (this.meta.cockpit && this.meta.cockpit.steeringRatioDeg) || 450;
    if (this.anim.steering) {
      const a = THREE.MathUtils.degToRad(ratio / 2) * s.steer;
      this.anim.steering.obj.quaternion.copy(this.anim.steering.base).multiply(new THREE.Quaternion().setFromAxisAngle(Z, a));
    }
    const g = this.meta.gauges || {};
    for (const n of this.anim.needles) {
      const f = n.gauge === 'speed' ? Math.min(1, Math.abs(s.speedKmh) / (g.speedMaxKmh || 300))
        : Math.min(1, s.rpm / ((g.rpmMaxThousand || 9) * 1000));
      n.obj.quaternion.copy(n.base).multiply(new THREE.Quaternion().setFromAxisAngle(Z, THREE.MathUtils.degToRad(270) * f));
    }
    for (const p of this.anim.pedals) {
      const k = p.pedal === 'brake' ? s.brake : s.throttle;
      p.obj.quaternion.copy(p.base).multiply(new THREE.Quaternion().setFromAxisAngle(X, -0.32 * k));
    }
    // Blinker
    const blink = s.indicator !== 0 && Math.floor(time * 2.6) % 2 === 0;
    const ind = this.mat.Indicator;
    if (ind) ind.emissiveIntensity = blink ? (ind.userData.active || 5.0) : 0;
    this.displays.update(time);
  }

  setBrake(v) {
    const was = this.state.brake > 0.05;
    this.state.brake = v;
    if (was !== v > 0.05) this._applyLights();
  }

  // Kamerapunkte (Weltkoordinaten)
  helperWorld(name, target = new THREE.Vector3()) {
    const h = this.helpers[name];
    if (!h) return null;
    return h.getWorldPosition(target);
  }

  triangleCount() {
    let n = 0;
    this.root.traverseVisible((o) => {
      if (o.isMesh && o.geometry.index) n += o.geometry.index.count / 3;
    });
    return Math.round(n);
  }

  // Geometrien und Texturen werden zwischen Fahrzeugen geteilt (VehicleLibrary) und
  // deshalb hier nicht freigegeben – nur die eigenen Materialien und Display-Texturen.
  dispose() {
    this.displays.dispose();
    for (const m of this.materialList) m.dispose();
    if (this.object.parent) this.object.parent.remove(this.object);
  }
}
