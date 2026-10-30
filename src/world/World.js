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
    this.groups = { street: [], windows: [], neon: [] };
    this.wetMaterials = [];
    const seen = new Set();
    const maxAniso = renderer ? renderer.capabilities.getMaxAnisotropy() : 1;
    let template = null;
    for (const node of this.object.children[0] ? this.object.children[0].children : []) {
      const ex = node.userData || {};
      if (ex.template === 'cone') { template = node; continue; }
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
    this.setNight(0);
  }

  /** Nachtanteil 0 (Tag) .. 1 (Nacht): Fenster, Laternen und Neon. */
  setNight(k) {
    this.night = k;
    for (const m of this.groups.windows) m.emissiveIntensity = m.userData.baseEmissive * (0.02 + 0.98 * k);
    for (const m of this.groups.street) m.emissiveIntensity = m.userData.baseEmissive * Math.max(0, (k - 0.25) / 0.75);
    for (const m of this.groups.neon) m.emissiveIntensity = m.userData.baseEmissive * (0.35 + 0.65 * k);
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
    for (const zn of this.zones) if (Math.hypot(x - zn.x, z - zn.z) < zn.r) return zn.name;
    return null;
  }

  update(dt, bodies, playerPos, onPropHit) {
    if (this.props) this.props.update(dt, bodies, playerPos, onPropHit);
  }
}
