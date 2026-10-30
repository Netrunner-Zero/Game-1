// Eine Karte der Spielwelt laden: Grafik (GLB) und Spieldaten (JSON) aus tools/world-generator.
//
//   const world = await World.load('../world/', 'testgelaende', renderer);
//   scene.add(world.object);
//   physics.step(dt, input, world);            // world.groundHeight(x, z), world.grip(x, z)
//   collisions = new Collisions(world.statics);
//   world.setNight(0..1); world.update(dt, bodies, playerPos);

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { StaticWorld } from '../physics/collision.js';
import { Props } from './props.js';
import { makeGround } from './ground.js';

export class World {
  static async load(baseUrl, id, renderer, onProgress) {
    const base = baseUrl.endsWith('/') ? baseUrl : baseUrl + '/';
    const res = await fetch(base + id + '.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error('Karte ' + id + ' nicht gefunden (' + res.status + ')');
    const meta = await res.json();
    const gltf = await new Promise((resolve, reject) => {
      new GLTFLoader().load(base + meta.file, resolve, (e) => {
        if (onProgress && e.total) onProgress(e.loaded / e.total);
      }, reject);
    });
    return new World(meta, gltf, renderer);
  }

  constructor(meta, gltf, renderer) {
    this.meta = meta;
    this.object = gltf.scene;
    this.object.name = 'World_' + meta.id;
    // ---- Kollisionen
    this.statics = new StaticWorld(24);
    for (const c of meta.colliders || []) {
      if (c.t === 'box') this.statics.addBox({ x: c.x, z: c.z, hx: c.hx, hz: c.hz, yaw: c.yaw || 0, top: c.top, kind: c.kind, mu: c.mu, e: c.e });
      else this.statics.addCircle({ x: c.x, z: c.z, r: c.r, top: c.top, kind: c.kind, mu: c.mu, e: c.e });
    }
    // ---- Bodenhöhe: Rampen, Wellen
    this.groundHeight = makeGround(meta.regions);
    const b = meta.bounds || [-1e9, -1e9, 1e9, 1e9];
    this.wetness = 0;
    this.grip = (x, z) => {
      const inside = x > b[0] && x < b[2] && z > b[1] && z < b[3];
      return (inside ? 1.0 : 0.62) * (1 - 0.32 * this.wetness);
    };
    // ---- Materialgruppen (Tag/Nacht), Schatten, Vorlagen
    this.groups = { street: [], windows: [], neon: [], shops: [], water: [] };
    this.wetMaterials = [];
    const seen = new Set();
    const maxAniso = renderer ? renderer.capabilities.getMaxAnisotropy() : 1;
    let template = null;
    this.templates = {};
    for (const node of this.object.children[0] ? this.object.children[0].children : []) {
      const ex = node.userData || {};
      if (ex.template === 'cone') { template = node; continue; }
      if (ex.template) { this.templates[node.name] = node; node.visible = false; continue; }
      const shadow = ex.shadow || 'both';
      node.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = shadow === 'both' || shadow === 'cast';
        o.receiveShadow = shadow === 'both' || shadow === 'receive';
        if (ex.far) o.frustumCulled = false;
      });
    }
    this.object.traverse((o) => {
      if (!o.isMesh) return;
      for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
        if (seen.has(m)) continue;
        seen.add(m);
        for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap']) {
          if (m[k]) m[k].anisotropy = Math.min(8, maxAniso);
        }
        const u = m.userData || {};
        if (u.group && this.groups[u.group]) {
          u.baseEmissive = u.base !== undefined ? u.base : m.emissiveIntensity;
          this.groups[u.group].push(m);
        }
        if (u.wet) {
          u.dryRough = m.roughness;
          u.dryColor = m.color.clone();
          this.wetMaterials.push(m);
        }
      }
    });
    this.props = template ? new Props(template, (meta.props || []).filter((p) => p.type === 'cone'), this.groundHeight) : null;
    if (this.props) this.object.add(this.props.group);
    this.spawns = meta.spawn || [{ x: 0, z: 0, yaw: 0, name: 'Start' }];
    this.zones = meta.zones || [];
    this.time = 0;
    this._buildInstances();
    this._buildSignals();
    this.setNight(0);
  }

  // ---------------------------------------------------------------- Wiederholteile (Laternen, Ampeln, Bäume)
  _buildInstances() {
    this.instanced = [];
    this.lampHeads = [];
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), pos = new THREE.Vector3(), sc = new THREE.Vector3();
    const Y = new THREE.Vector3(0, 1, 0);
    for (const [kind, def] of Object.entries(this.meta.instances || {})) {
      const tpl = this.templates[def.template];
      const items = def.items || [];
      if (!tpl || !items.length) continue;
      tpl.updateMatrixWorld(true);
      const inv = new THREE.Matrix4().copy(tpl.matrixWorld).invert();
      const meshes = [];
      tpl.traverse((o) => {
        if (!o.isMesh) return;
        const g = o.geometry.clone();
        g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld));
        const im = new THREE.InstancedMesh(g, o.material, items.length);
        im.name = 'Inst_' + kind;
        im.frustumCulled = false;
        im.receiveShadow = true;
        im.castShadow = false;
        meshes.push(im);
        this.object.add(im);
      });
      items.forEach((it, i) => {
        const [x, z, yaw = 0, s = 1] = it;
        pos.set(x, this.groundHeight(x, z), z);
        q.setFromAxisAngle(Y, yaw);
        sc.set(s, s, s);
        m4.compose(pos, q, sc);
        for (const im of meshes) im.setMatrixAt(i, m4);
        if (def.collider) this.statics.addCircle({ x, z, r: def.collider.r * s, top: def.collider.top, kind });
        if (def.head) {
          const [hx, hy, hz] = def.head;
          const c = Math.cos(yaw), sn = Math.sin(yaw);
          this.lampHeads.push({ x: x + hx * c + hz * sn, y: pos.y + hy, z: z - hx * sn + hz * c });
        }
      });
      for (const im of meshes) im.instanceMatrix.needsUpdate = true;
      this.instanced.push({ kind, meshes });
    }
  }

  /** Schatten der Wiederholteile nur bei hoher Qualität (spart viel Rechenzeit auf dem Handy). */
  setQuality(Q) {
    const on = !!(Q && Q.shadows && Q.shadowSize >= 2048);
    for (const g of this.instanced || []) for (const im of g.meshes) im.castShadow = on && g.kind !== 'signal';
  }

  // ---------------------------------------------------------------- Ampeln
  _buildSignals() {
    const S = this.meta.signals;
    this.signal = null;
    if (!S || !S.heads || !S.heads.length) return;
    const heads = S.heads;
    const n = heads.length * 3;
    const geo = new THREE.CircleGeometry(0.12, 10);
    const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const im = new THREE.InstancedMesh(geo, mat, n);
    im.name = 'SignalLamps';
    im.frustumCulled = false;
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), pos = new THREE.Vector3(), one = new THREE.Vector3(1, 1, 1);
    const Y = new THREE.Vector3(0, 1, 0);
    heads.forEach((h, i) => {
      const [x, y, z, face] = h;
      const big = y > 4;
      const dy = big ? 0.36 : 0.3;
      const fx = Math.sin(face) * (big ? 0.17 : 0.15), fz = Math.cos(face) * (big ? 0.17 : 0.15);
      q.setFromAxisAngle(Y, face);
      for (let k = 0; k < 3; k++) {
        pos.set(x + fx, y + dy * (1 - k), z + fz);
        m4.compose(pos, q, one);
        im.setMatrixAt(i * 3 + k, m4);
        im.setColorAt(i * 3 + k, new THREE.Color(0.03, 0.03, 0.03));
      }
    });
    im.instanceMatrix.needsUpdate = true;
    this.object.add(im);
    this.signal = { im, heads, state: new Int8Array(heads.length).fill(-1), cycle: S.cycle || 32, green: S.green || 12,
      yellow: S.yellow || 3 };
    this._updateSignals(true);
  }

  /** Zustand einer Ampelgruppe (0 = Nord-Süd, 1 = Ost-West): 'green' | 'yellow' | 'red' und Restzeit. */
  signalState(group, offset, time = this.time) {
    const s = this.signal;
    if (!s) return { state: 'green', left: 99 };
    const C = s.cycle;
    const tg = (((time + offset - group * C / 2) % C) + C) % C;
    if (tg < s.green) return { state: 'green', left: s.green - tg };
    if (tg < s.green + s.yellow) return { state: 'yellow', left: s.green + s.yellow - tg };
    return { state: 'red', left: C - tg };
  }

  _updateSignals(force = false) {
    const s = this.signal;
    if (!s) return;
    const OFF = new THREE.Color(0.035, 0.035, 0.035);
    const ON = [new THREE.Color(5.0, 0.25, 0.12), new THREE.Color(4.2, 2.4, 0.15), new THREE.Color(0.15, 3.6, 1.3)];
    let dirty = false;
    s.heads.forEach((h, i) => {
      const st = this.signalState(h[4], h[5]).state;
      const k = st === 'red' ? 0 : st === 'yellow' ? 1 : 2;
      if (!force && s.state[i] === k) return;
      s.state[i] = k;
      for (let j = 0; j < 3; j++) s.im.setColorAt(i * 3 + j, j === k ? ON[j] : OFF);
      dirty = true;
    });
    if (dirty && s.im.instanceColor) s.im.instanceColor.needsUpdate = true;
  }

  /** Nachtanteil 0 (Tag) .. 1 (Nacht): Fenster, Laternen und Neon. */
  setNight(k) {
    this.night = k;
    for (const m of this.groups.windows) m.emissiveIntensity = m.userData.baseEmissive * (0.02 + 0.98 * k);
    for (const m of this.groups.street) m.emissiveIntensity = m.userData.baseEmissive * Math.max(0, (k - 0.25) / 0.75);
    for (const m of this.groups.neon) m.emissiveIntensity = m.userData.baseEmissive * (0.35 + 0.65 * k);
    for (const m of this.groups.shops) m.emissiveIntensity = m.userData.baseEmissive * (0.3 + 0.7 * k);
  }

  /** Nässe 0..1 (Regen): dunklere, glattere Fahrbahn und weniger Grip. */
  setWetness(w) {
    this.wetness = w;
    for (const m of this.wetMaterials) {
      m.roughness = THREE.MathUtils.lerp(m.userData.dryRough, 0.12, w);
      m.color.copy(m.userData.dryColor).multiplyScalar(1 - 0.35 * w);
    }
  }

  /** Name der Zone an der Stelle (für die Anzeige), sonst null. */
  zoneAt(x, z) {
    for (const zn of this.zones) {
      if (zn.rect) { if (x >= zn.rect[0] && x <= zn.rect[2] && z >= zn.rect[1] && z <= zn.rect[3]) return zn.name; }
      else if (Math.hypot(x - zn.x, z - zn.z) < zn.r) return zn.name;
    }
    return null;
  }

  update(dt, bodies, playerPos, onPropHit) {
    this.time += dt;
    if (this.props) this.props.update(dt, bodies, playerPos, onPropHit);
    this._updateSignals();
    for (const m of this.groups.water) if (m.normalMap) { m.normalMap.offset.x += dt * 0.006; m.normalMap.offset.y += dt * 0.004; }
  }

  dispose() {
    if (this.object.parent) this.object.parent.remove(this.object);
    this.object.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
        for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap']) if (m[k]) m[k].dispose();
        m.dispose();
      }
    });
  }
}
