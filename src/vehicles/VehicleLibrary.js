// Lädt models/cars.json und die Fahrzeug-GLBs (mit Zwischenspeicher).
//
//   const lib = new VehicleLibrary('../models/');
//   await lib.init();                     // cars.json
//   const car = await lib.create('vektra_gt', onProgress);
//   scene.add(car.object);

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Vehicle } from './Vehicle.js';

export class VehicleLibrary {
  constructor(baseUrl = 'models/', renderer = null) {
    this.baseUrl = baseUrl.endsWith('/') ? baseUrl : baseUrl + '/';
    this.loader = new GLTFLoader();
    this.cars = [];
    this.byId = {};
    this.cache = new Map();          // id -> Promise<gltf>
    this.renderer = renderer;
  }

  async init() {
    const res = await fetch(this.baseUrl + 'cars.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error('cars.json nicht gefunden (' + res.status + ')');
    const doc = await res.json();
    this.cars = doc.cars || [];
    for (const c of this.cars) this.byId[c.id] = c;
    return this.cars;
  }

  _load(id, onProgress) {
    if (!this.cache.has(id)) {
      const meta = this.byId[id];
      const p = new Promise((resolve, reject) => {
        this.loader.load(this.baseUrl + meta.file, resolve, (e) => {
          if (onProgress && e.total) onProgress(e.loaded / e.total);
        }, reject);
      });
      this.cache.set(id, p);
      p.catch(() => this.cache.delete(id));
    }
    return this.cache.get(id);
  }

  // Neues, unabhängiges Fahrzeug (eigene Materialien, damit Tuning pro Auto möglich ist)
  async create(id, onProgress) {
    const meta = this.byId[id];
    if (!meta) throw new Error('Unbekanntes Fahrzeug: ' + id);
    const gltf = await this._load(id, onProgress);
    const scene = cloneDeep(gltf.scene);
    const car = new Vehicle({ scene }, meta);
    if (this.renderer) {
      const maxAniso = this.renderer.capabilities.getMaxAnisotropy();
      for (const m of car.materialList) {
        for (const k of ['map', 'normalMap']) if (m[k]) m[k].anisotropy = Math.min(8, maxAniso);
      }
    }
    return car;
  }

  // Vorab laden (z. B. im Hintergrund)
  preload(id) {
    return this._load(id).catch(() => null);
  }
}

// Szene mit eigenen Materialien klonen (Geometrien und Texturen bleiben geteilt)
function cloneDeep(src) {
  const map = new Map();
  const out = src.clone(true);
  out.traverse((o) => {
    if (!o.isMesh) return;
    const conv = (m) => {
      if (!map.has(m)) {
        const c = m.clone();
        c.userData = JSON.parse(JSON.stringify(m.userData || {}));
        map.set(m, c);
      }
      return map.get(m);
    };
    o.material = Array.isArray(o.material) ? o.material.map(conv) : conv(o.material);
  });
  return out;
}

export { THREE };
