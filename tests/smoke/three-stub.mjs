// Sehr kleiner Ersatz für three.js – nur für den Rauchtest in Node (tests/smoke/run.mjs).
// Echte Mathematik (Vektoren, Quaternionen, Matrizen), Szenengraph und Materialien als Datenobjekte;
// gezeichnet wird nichts. So lassen sich Spiel-Logik und Verdrahtung ohne Browser ausführen.

export const SRGBColorSpace = 'srgb', ACESFilmicToneMapping = 4, PCFSoftShadowMap = 2, DoubleSide = 2, BackSide = 1,
  FrontSide = 0, DynamicDrawUsage = 35048, LinearSRGBColorSpace = 'srgb-linear', NoToneMapping = 0;

export const MathUtils = {
  clamp: (v, a, b) => Math.max(a, Math.min(b, v)),
  degToRad: (d) => d * Math.PI / 180,
  radToDeg: (r) => r * 180 / Math.PI,
  lerp: (a, b, t) => a + (b - a) * t,
};

function chk(...vals) {
  for (const v of vals) if (typeof v !== 'number' || !Number.isFinite(v)) throw new Error('NaN/Infinity in Mathematik: ' + v);
}

export class Vector2 { constructor(x = 0, y = 0) { this.x = x; this.y = y; } set(x, y) { this.x = x; this.y = y; return this; } }

export class Vector3 {
  constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; this.isVector3 = true; }
  set(x, y, z) { chk(x, y, z); this.x = x; this.y = y; this.z = z; return this; }
  copy(v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
  clone() { return new Vector3(this.x, this.y, this.z); }
  add(v) { this.x += v.x; this.y += v.y; this.z += v.z; return this; }
  sub(v) { this.x -= v.x; this.y -= v.y; this.z -= v.z; return this; }
  subVectors(a, b) { return this.set(a.x - b.x, a.y - b.y, a.z - b.z); }
  addVectors(a, b) { return this.set(a.x + b.x, a.y + b.y, a.z + b.z); }
  addScaledVector(v, s) { this.x += v.x * s; this.y += v.y * s; this.z += v.z * s; return this; }
  multiplyScalar(s) { this.x *= s; this.y *= s; this.z *= s; return this; }
  divideScalar(s) { return this.multiplyScalar(1 / s); }
  length() { return Math.hypot(this.x, this.y, this.z); }
  lengthSq() { return this.x * this.x + this.y * this.y + this.z * this.z; }
  normalize() { const l = this.length() || 1; return this.multiplyScalar(1 / l); }
  dot(v) { return this.x * v.x + this.y * v.y + this.z * v.z; }
  crossVectors(a, b) { const x = a.y * b.z - a.z * b.y, y = a.z * b.x - a.x * b.z, z = a.x * b.y - a.y * b.x; return this.set(x, y, z); }
  distanceTo(v) { return Math.hypot(this.x - v.x, this.y - v.y, this.z - v.z); }
  lerp(v, t) { this.x += (v.x - this.x) * t; this.y += (v.y - this.y) * t; this.z += (v.z - this.z) * t; return this; }
  applyQuaternion(q) {
    const { x, y, z } = this, qx = q.x, qy = q.y, qz = q.z, qw = q.w;
    const tx = 2 * (qy * z - qz * y), ty = 2 * (qz * x - qx * z), tz = 2 * (qx * y - qy * x);
    this.x = x + qw * tx + qy * tz - qz * ty; this.y = y + qw * ty + qz * tx - qx * tz; this.z = z + qw * tz + qx * ty - qy * tx;
    return this;
  }
  applyMatrix4(m) {
    const e = m.elements, x = this.x, y = this.y, z = this.z;
    const w = 1 / (e[3] * x + e[7] * y + e[11] * z + e[15]);
    this.x = (e[0] * x + e[4] * y + e[8] * z + e[12]) * w; this.y = (e[1] * x + e[5] * y + e[9] * z + e[13]) * w; this.z = (e[2] * x + e[6] * y + e[10] * z + e[14]) * w;
    return this;
  }
  setFromMatrixPosition(m) { const e = m.elements; return this.set(e[12], e[13], e[14]); }
}

export class Quaternion {
  constructor(x = 0, y = 0, z = 0, w = 1) { this.x = x; this.y = y; this.z = z; this.w = w; }
  set(x, y, z, w) { this.x = x; this.y = y; this.z = z; this.w = w; return this; }
  copy(q) { return this.set(q.x, q.y, q.z, q.w); }
  clone() { return new Quaternion(this.x, this.y, this.z, this.w); }
  identity() { return this.set(0, 0, 0, 1); }
  setFromAxisAngle(a, ang) { chk(ang); const s = Math.sin(ang / 2); return this.set(a.x * s, a.y * s, a.z * s, Math.cos(ang / 2)); }
  multiply(q) { return this.multiplyQuaternions(this, q); }
  premultiply(q) { return this.multiplyQuaternions(q, this); }
  multiplyQuaternions(a, b) {
    const x = a.x * b.w + a.w * b.x + a.y * b.z - a.z * b.y, y = a.y * b.w + a.w * b.y + a.z * b.x - a.x * b.z;
    const z = a.z * b.w + a.w * b.z + a.x * b.y - a.y * b.x, w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z;
    return this.set(x, y, z, w);
  }
  setFromEuler(e) {
    chk(e.x, e.y, e.z);
    const c1 = Math.cos(e.x / 2), c2 = Math.cos(e.y / 2), c3 = Math.cos(e.z / 2), s1 = Math.sin(e.x / 2), s2 = Math.sin(e.y / 2), s3 = Math.sin(e.z / 2);
    if (e.order === 'YXZ') return this.set(s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 - s1 * s2 * c3, c1 * c2 * c3 + s1 * s2 * s3);
    return this.set(s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 + s1 * s2 * c3, c1 * c2 * c3 - s1 * s2 * s3);
  }
  setFromUnitVectors(a, b) {
    let r = a.dot(b) + 1;
    let x, y, z;
    if (r < 1e-8) { r = 0; if (Math.abs(a.x) > Math.abs(a.z)) { x = -a.y; y = a.x; z = 0; } else { x = 0; y = -a.z; z = a.y; } }
    else { x = a.y * b.z - a.z * b.y; y = a.z * b.x - a.x * b.z; z = a.x * b.y - a.y * b.x; }
    const l = Math.hypot(x, y, z, r);
    return this.set(x / l, y / l, z / l, r / l);
  }
  slerp(q, t) { // für den Test reicht lineare Mischung + Normierung
    this.x += (q.x - this.x) * t; this.y += (q.y - this.y) * t; this.z += (q.z - this.z) * t; this.w += (q.w - this.w) * t;
    const l = Math.hypot(this.x, this.y, this.z, this.w) || 1;
    return this.set(this.x / l, this.y / l, this.z / l, this.w / l);
  }
}

export class Euler {
  constructor(x = 0, y = 0, z = 0, order = 'XYZ') { this.x = x; this.y = y; this.z = z; this.order = order; }
  set(x, y, z, order) { chk(x, y, z); this.x = x; this.y = y; this.z = z; if (order) this.order = order; return this; }
}

export class Matrix4 {
  constructor() { this.elements = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]; }
  copy(m) { this.elements = m.elements.slice(); return this; }
  clone() { return new Matrix4().copy(this); }
  identity() { this.elements = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]; return this; }
  multiply(m) { return this.multiplyMatrices(this, m); }
  multiplyMatrices(a, b) {
    const ae = a.elements, be = b.elements, te = new Array(16);
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += ae[k * 4 + i] * be[j * 4 + k];
      te[j * 4 + i] = s;
    }
    this.elements = te;
    return this;
  }
  compose(p, q, s) {
    const x = q.x, y = q.y, z = q.z, w = q.w, x2 = x + x, y2 = y + y, z2 = z + z;
    const xx = x * x2, xy = x * y2, xz = x * z2, yy = y * y2, yz = y * z2, zz = z * z2, wx = w * x2, wy = w * y2, wz = w * z2;
    const e = this.elements;
    e[0] = (1 - (yy + zz)) * s.x; e[1] = (xy + wz) * s.x; e[2] = (xz - wy) * s.x; e[3] = 0;
    e[4] = (xy - wz) * s.y; e[5] = (1 - (xx + zz)) * s.y; e[6] = (yz + wx) * s.y; e[7] = 0;
    e[8] = (xz + wy) * s.z; e[9] = (yz - wx) * s.z; e[10] = (1 - (xx + yy)) * s.z; e[11] = 0;
    e[12] = p.x; e[13] = p.y; e[14] = p.z; e[15] = 1;
    chk(...e);
    return this;
  }
  invert() { // allgemeine 4x4-Inverse (Gauss)
    const m = this.elements, a = [];
    for (let r = 0; r < 4; r++) { a.push([]); for (let c = 0; c < 4; c++) a[r].push(m[c * 4 + r]); for (let c = 0; c < 4; c++) a[r].push(r === c ? 1 : 0); }
    for (let c = 0; c < 4; c++) {
      let p = c; for (let r = c + 1; r < 4; r++) if (Math.abs(a[r][c]) > Math.abs(a[p][c])) p = r;
      [a[c], a[p]] = [a[p], a[c]];
      const d = a[c][c] || 1e-12;
      for (let k = 0; k < 8; k++) a[c][k] /= d;
      for (let r = 0; r < 4; r++) if (r !== c) { const f = a[r][c]; for (let k = 0; k < 8; k++) a[r][k] -= f * a[c][k]; }
    }
    for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) m[c * 4 + r] = a[r][c + 4];
    return this;
  }
}

export class Color {
  constructor(r = 1, g, b) { this.isColor = true; if (g === undefined) this.set(r); else { this.r = r; this.g = g; this.b = b; } }
  set(v) {
    if (v && v.isColor) return this.copy(v);
    if (typeof v === 'number') { this.r = ((v >> 16) & 255) / 255; this.g = ((v >> 8) & 255) / 255; this.b = (v & 255) / 255; return this; }
    if (typeof v === 'string') {
      const m = /^#([0-9a-f]{6})$/i.exec(v);
      if (!m) throw new Error('Farbe ungültig: ' + v);
      return this.set(parseInt(m[1], 16));
    }
    throw new Error('Farbe ungültig: ' + v);
  }
  copy(c) { this.r = c.r; this.g = c.g; this.b = c.b; return this; }
  clone() { return new Color(this.r, this.g, this.b); }
  lerp(c, t) { this.r += (c.r - this.r) * t; this.g += (c.g - this.g) * t; this.b += (c.b - this.b) * t; return this; }
  multiplyScalar(s) { this.r *= s; this.g *= s; this.b *= s; return this; }
  getHex() { const c = (v) => Math.max(0, Math.min(255, Math.round(v * 255))); return (c(this.r) << 16) | (c(this.g) << 8) | c(this.b); }
  getHexString() { return this.getHex().toString(16).padStart(6, '0'); }
  getStyle() { return '#' + this.getHexString(); }
  setRGB(r, g, b) { this.r = r; this.g = g; this.b = b; return this; }
}

let uuid = 0;
export class Object3D {
  constructor() {
    this.uuid = 'o' + (++uuid); this.name = ''; this.children = []; this.parent = null; this.visible = true; this.userData = {};
    this.position = new Vector3(); this.quaternion = new Quaternion(); this.scale = new Vector3(1, 1, 1);
    const self = this;
    this.rotation = new Euler();
    const set = this.rotation.set.bind(this.rotation);
    this.rotation.set = (x, y, z, o) => { set(x, y, z, o); self.quaternion.setFromEuler(self.rotation); return self.rotation; };
    this.matrixWorld = new Matrix4(); this.up = new Vector3(0, 1, 0); this.castShadow = false; this.receiveShadow = false;
    this.frustumCulled = true; this.renderOrder = 0; this.matrixAutoUpdate = true;
  }
  add(...objs) { for (const o of objs) { if (o.parent) o.parent.remove(o); o.parent = this; this.children.push(o); } return this; }
  remove(o) { const i = this.children.indexOf(o); if (i >= 0) { this.children.splice(i, 1); o.parent = null; } return this; }
  traverse(fn) { fn(this); for (const c of this.children.slice()) c.traverse(fn); }
  traverseVisible(fn) { if (!this.visible) return; fn(this); for (const c of this.children) c.traverseVisible(fn); }
  updateMatrixWorld() { this.updateWorldMatrix(false, true); }
  updateWorldMatrix(parents, children) {
    if (parents && this.parent) this.parent.updateWorldMatrix(true, false);
    const local = new Matrix4().compose(this.position, this.quaternion, this.scale);
    this.matrixWorld = this.parent ? new Matrix4().multiplyMatrices(this.parent.matrixWorld, local) : local;
    if (children) for (const c of this.children) c.updateWorldMatrix(false, true);
  }
  getWorldPosition(t) { this.updateWorldMatrix(true, false); return t.setFromMatrixPosition(this.matrixWorld); }
  getWorldQuaternion(t) {
    this.updateWorldMatrix(true, false);
    let q = new Quaternion(); const chain = []; let o = this; while (o) { chain.unshift(o); o = o.parent; }
    for (const n of chain) q.multiply(n.quaternion);
    return t.copy(q);
  }
  localToWorld(v) { this.updateWorldMatrix(true, false); return v.applyMatrix4(this.matrixWorld); }
  lookAt(v) { this._lookAt = v.clone ? v.clone() : v; }
  clone(recursive = true) {
    const c = new this.constructor();
    c.name = this.name; c.userData = JSON.parse(JSON.stringify(this.userData)); c.visible = this.visible;
    c.position.copy(this.position); c.quaternion.copy(this.quaternion); c.scale.copy(this.scale);
    c.geometry = this.geometry; c.material = this.material; c.isMesh = this.isMesh;
    if (recursive) for (const k of this.children) c.add(k.clone(true));
    return c;
  }
}
export class Group extends Object3D {}
export class Scene extends Object3D { constructor() { super(); this.background = null; this.environment = null; this.fog = null; } }
export class Mesh extends Object3D { constructor(geometry, material) { super(); this.isMesh = true; this.geometry = geometry; this.material = material; } }
export class InstancedMesh extends Mesh {
  constructor(g, m, count) { super(g, m); this.count = count; this.instanceMatrix = { needsUpdate: false, setUsage() {} }; this._mats = []; }
  setMatrixAt(i, m) { if (i >= this.count) throw new Error('Instanz außerhalb'); this._mats[i] = m.elements.slice(); }
  setColorAt(i, c) {
    if (i >= this.count) throw new Error('Instanz außerhalb');
    if (!this.instanceColor) this.instanceColor = { needsUpdate: false, array: new Float32Array(this.count * 3) };
    this.instanceColor.array.set([c.r, c.g, c.b], i * 3);
  }
}
export class Camera extends Object3D {}
export class PerspectiveCamera extends Camera {
  constructor(fov = 50, aspect = 1, near = 0.1, far = 2000) { super(); Object.assign(this, { fov, aspect, near, far, zoom: 1 }); }
  updateProjectionMatrix() { chk(this.fov, this.aspect, this.near, this.far); }
}

export class BufferGeometry {
  constructor() { this.attributes = {}; this.index = { count: 300 }; }
  clone() { return new this.constructor(); }
  applyMatrix4() { return this; }
  dispose() {}
  setAttribute(n, a) { this.attributes[n] = a; return this; }
}
export class SphereGeometry extends BufferGeometry { constructor() { super(); this.attributes.position = { count: 10, getY: () => 0 }; } }
export class CircleGeometry extends BufferGeometry {}
export class BoxGeometry extends BufferGeometry {}
export class CylinderGeometry extends BufferGeometry {}
export class TorusGeometry extends BufferGeometry {}
export class Float32BufferAttribute { constructor(a, n) { this.array = a; this.itemSize = n; } }

class Material {
  constructor(p = {}) {
    this.uuid = 'm' + (++uuid); this.name = ''; this.userData = {}; this.color = new Color(1, 1, 1); this.emissive = new Color(0, 0, 0);
    this.emissiveIntensity = 1; this.roughness = 1; this.metalness = 0; this.transparent = false; this.opacity = 1; this.side = 0;
    this.depthWrite = true; this.envMapIntensity = 1; this.normalScale = new Vector2(1, 1); this.needsUpdate = false;
    for (const [k, v] of Object.entries(p)) { if (v && v.isColor) this[k] = v; else if (k === 'color' || k === 'emissive') this[k] = new Color(v); else this[k] = v; }
  }
  clone() { const m = new this.constructor(); Object.assign(m, this); m.color = this.color.clone(); m.emissive = this.emissive.clone(); m.uuid = 'm' + (++uuid); return m; }
  dispose() {}
}
export class MeshStandardMaterial extends Material { constructor(p) { super(p); this.isMeshStandardMaterial = true; } }
export class MeshPhysicalMaterial extends MeshStandardMaterial { constructor(p) { super(p); this.isMeshPhysicalMaterial = true; this.clearcoat = 0; this.sheen = 0; this.iridescence = 0; } }
export class MeshBasicMaterial extends Material {}
export class ShaderMaterial extends Material { constructor(p = {}) { super({}); this.uniforms = p.uniforms; this.vertexShader = p.vertexShader; this.fragmentShader = p.fragmentShader; } }

export class Texture { constructor() { this.anisotropy = 1; this.offset = new Vector2(); this.repeat = new Vector2(1, 1); } dispose() {} }
export class CanvasTexture extends Texture { constructor(c) { super(); this.image = c; } }

class Light extends Object3D { constructor(color, intensity = 1) { super(); this.color = new Color(color === undefined ? 0xffffff : color); this.intensity = intensity; } }
export class DirectionalLight extends Light {
  constructor(c, i) {
    super(c, i); this.target = new Object3D();
    this.shadow = { bias: 0, normalBias: 0, radius: 1, mapSize: new Vector2(512, 512), map: null,
      camera: { left: -5, right: 5, top: 5, bottom: -5, near: 0.5, far: 500, updateProjectionMatrix() {} } };
  }
}
export class SpotLight extends DirectionalLight { constructor(c, i, d, a, p, dc) { super(c, i); this.distance = d; this.angle = a; } }
export class PointLight extends Light { constructor(c, i, d) { super(c, i); this.distance = d; } }
export class HemisphereLight extends Light { constructor(s, g, i) { super(s, i); this.groundColor = new Color(g); } }
export class Fog { constructor(c, n, f) { this.color = new Color(c); this.near = n; this.far = f; } }

export class Clock {
  constructor() { this.elapsedTime = 0; }
  getDelta() { const d = globalThis.__smokeDt || 1 / 60; this.elapsedTime += d; return d; }
}

export class WebGLRenderer {
  constructor() {
    this.info = { autoReset: true, render: { triangles: 0, calls: 0 }, reset() {} };
    this.shadowMap = { enabled: false, type: 0 }; this.capabilities = { getMaxAnisotropy: () => 16 };
    this.toneMappingExposure = 1; this.renders = 0; this.pr = 1;
  }
  setPixelRatio(p) { this.pr = p; } getPixelRatio() { return this.pr; } setSize() {}
  render(scene, camera) {
    this.renders++;
    // Szene einmal komplett durchlaufen: findet NaN in Positionen/Drehungen
    scene.traverse((o) => { if (o.position) chk(o.position.x, o.position.y, o.position.z, o.quaternion.x, o.quaternion.w); });
    chk(camera.position.x, camera.position.y, camera.position.z, camera.fov);
  }
}
export class PMREMGenerator {
  constructor() {} compileEquirectangularShader() {} dispose() {}
  fromScene() { return { texture: new Texture(), dispose() {} }; }
}
export class GridHelper extends Object3D { constructor() { super(); this.material = new MeshBasicMaterial(); } }
export const AdditiveBlending = 2, NormalBlending = 1;
export class BufferAttribute { constructor(a, n) { this.array = a; this.itemSize = n; this.count = a.length / n; } }
export class LineSegments extends Object3D { constructor(g, m) { super(); this.geometry = g; this.material = m; } }
export class PlaneGeometry extends BufferGeometry { rotateX() { return this; } }
BufferGeometry.prototype.setDrawRange = function (a, b) { this.drawRange = { start: a, count: b }; };
