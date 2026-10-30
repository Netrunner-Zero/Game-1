// Bewegliche Kleinteile (Pylonen): stehen herum, fliegen beim Anfahren weg, kullern aus und
// stellen sich später wieder auf ihren Platz. Gezeichnet als InstancedMesh (1 Draw Call je Material).

import * as THREE from 'three';
import { bodyOBB, testBoxCircle } from '../physics/collision.js';

const _m = new THREE.Matrix4();
const _q = new THREE.Quaternion();
const _s = new THREE.Vector3(1, 1, 1);
const _p = new THREE.Vector3();
const _axis = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);

export class Props {
  /**
   * @param {THREE.Object3D} template  Vorlage aus der Karten-GLB (wird versteckt)
   * @param {Array} list               [{x, z, yaw}]
   * @param {function} groundHeight    (x, z) -> Höhe
   */
  constructor(template, list, groundHeight, opts = {}) {
    this.group = new THREE.Group();
    this.group.name = 'Props';
    this.ground = groundHeight;
    this.radius = opts.radius || 0.19;
    this.items = list.map((p) => ({
      home: { x: p.x, z: p.z, yaw: p.yaw || 0 },
      pos: new THREE.Vector3(p.x, groundHeight(p.x, p.z), p.z),
      vel: new THREE.Vector3(),
      rot: new THREE.Quaternion().setFromAxisAngle(UP, p.yaw || 0),
      spin: new THREE.Vector3(),
      moving: false, displaced: false, restT: 0,
    }));
    this.meshes = [];
    template.updateMatrixWorld(true);
    template.traverse((o) => {
      if (!o.isMesh) return;
      // Geometrie in das Koordinatensystem der Vorlage backen (Knoten-Transformationen)
      const g = o.geometry.clone();
      const rel = new THREE.Matrix4().copy(template.matrixWorld).invert().multiply(o.matrixWorld);
      g.applyMatrix4(rel);
      const im = new THREE.InstancedMesh(g, o.material, this.items.length);
      im.castShadow = true;
      im.receiveShadow = true;
      im.frustumCulled = false;
      im.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      this.meshes.push(im);
      this.group.add(im);
    });
    template.visible = false;
    this.items.forEach((it, i) => this._write(i, it));
    this._obb = {};
    this._res = {};
    this.hits = 0;
  }

  _write(i, it) {
    _m.compose(it.pos, it.rot, _s);
    for (const im of this.meshes) im.setMatrixAt(i, _m);
  }

  /** bodies: [{ body, shape }] (Fahrzeuge). onHit(stärke) für Geräusche/Vibration. */
  update(dt, bodies, playerPos, onHit) {
    let dirty = false;
    const r = this.radius;
    for (let i = 0; i < this.items.length; i++) {
      const it = this.items[i];
      // Treffer durch Autos (nur wenn die Pylone am Boden ist)
      if (it.pos.y < this.ground(it.pos.x, it.pos.z) + 0.3) {
        for (const e of bodies) {
          const b = e.body;
          if (Math.abs(b.pos.x - it.pos.x) > 6 || Math.abs(b.pos.z - it.pos.z) > 6) continue;
          const A = bodyOBB(b, e.shape, this._obb);
          const c = testBoxCircle(A, { x: it.pos.x, z: it.pos.z, r }, this._res);
          if (!c) continue;
          // Geschwindigkeit des Autos am Kontaktpunkt
          const rx = c.px - b.pos.x, rz = c.pz - b.pos.z;
          const vx = b.vel.x + b.yawRate * rz, vz = b.vel.z - b.yawRate * rx;
          const sp = Math.hypot(vx, vz);
          if (sp < 0.4 && it.moving) continue;
          // Normale zeigt zum Auto -> Pylone fliegt in die Gegenrichtung
          it.vel.set(vx * 1.2 - c.nx * (1.0 + sp * 0.15), 1.2 + sp * (0.12 + Math.random() * 0.1), vz * 1.2 - c.nz * (1.0 + sp * 0.15));
          it.spin.set((Math.random() - 0.5) * sp * 1.6, (Math.random() - 0.5) * sp, (Math.random() - 0.5) * sp * 1.6);
          it.pos.x -= c.nx * c.depth;
          it.pos.z -= c.nz * c.depth;
          it.moving = true;
          it.displaced = true;
          it.restT = 0;
          it.restQ = null;
          this.hits++;
          if (onHit) onHit(Math.min(1, sp / 25));
          // kleiner Bremsstoß fürs Auto (Pylone wiegt ~3 kg)
          const k = 3 / b.mass;
          b.vel.x -= vx * k; b.vel.z -= vz * k;
        }
      }
      if (it.moving) {
        dirty = true;
        it.vel.y -= 9.81 * dt;
        it.pos.addScaledVector(it.vel, dt);
        const w = it.spin.length();
        if (w > 1e-4) {
          _axis.copy(it.spin).divideScalar(w);
          _q.setFromAxisAngle(_axis, w * dt);
          it.rot.premultiply(_q);
        }
        const gy = this.ground(it.pos.x, it.pos.z);
        const floor = gy + 0.02;
        if (it.pos.y < floor) {
          it.pos.y = floor;
          if (it.vel.y < 0) it.vel.y *= -0.28;
          it.vel.x *= 0.72; it.vel.z *= 0.72;
          it.spin.multiplyScalar(0.7);
          if (it.vel.lengthSq() < 0.25) {
            // zur Ruhe kommen: auf die Seite legen (Achse fast waagerecht, Spitze etwas tiefer)
            it.restT += dt;
            if (!it.restQ) {
              const ax = _p.set(0, 1, 0).applyQuaternion(it.rot);
              const hz = new THREE.Vector3(ax.x, 0, ax.z);
              if (hz.lengthSq() < 1e-4) hz.set(Math.random() - 0.5, 0, Math.random() - 0.5);
              hz.normalize();
              hz.y = -0.12;
              hz.normalize();
              it.restQ = new THREE.Quaternion().setFromUnitVectors(ax.clone(), hz).multiply(it.rot);
            }
            it.spin.set(0, 0, 0);
            it.rot.slerp(it.restQ, Math.min(1, dt * 8));
            it.pos.y = gy + 0.15;
            if (it.restT > 0.4) { it.moving = false; it.vel.set(0, 0, 0); it.rot.copy(it.restQ); }
          }
        }
        this._write(i, it);
      } else if (it.displaced && playerPos) {
        // nach einer Weile wieder aufstellen, wenn der Spieler weit genug weg ist
        it.restT += dt;
        const d = Math.hypot(playerPos.x - it.home.x, playerPos.z - it.home.z);
        if (it.restT > 12 && d > 45) {
          it.pos.set(it.home.x, this.ground(it.home.x, it.home.z), it.home.z);
          it.rot.setFromAxisAngle(UP, it.home.yaw);
          it.displaced = false;
          this._write(i, it);
          dirty = true;
        }
      }
    }
    if (dirty) for (const im of this.meshes) im.instanceMatrix.needsUpdate = true;
  }

  resetAll() {
    this.items.forEach((it, i) => {
      it.pos.set(it.home.x, this.ground(it.home.x, it.home.z), it.home.z);
      it.rot.setFromAxisAngle(UP, it.home.yaw);
      it.vel.set(0, 0, 0); it.spin.set(0, 0, 0);
      it.moving = false; it.displaced = false;
      this._write(i, it);
    });
    for (const im of this.meshes) im.instanceMatrix.needsUpdate = true;
  }
}
