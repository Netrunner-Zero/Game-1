// Autobahn-Kulisse: Straße, Gelände, Schutzwand, Leitplanken, Laternen, Bäume, Brücken
import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { ROAD, Z_NEAR, Z_FAR, rand, pick, smoothstep } from './config.js';
import {
  createRoadTexture, createAsphaltNormal, createGrassTexture, createConcreteTexture,
  createSignTexture, drawSign,
} from './textures.js';

const SPAN = Z_NEAR - Z_FAR;
const RECYCLE_Z = 45;              // Objekte hinter der Kamera werden nach vorn versetzt
const VEG_SPAN = RECYCLE_Z - Z_FAR + 20;

const CITIES = ['Berlin', 'Hamburg', 'München', 'Köln', 'Frankfurt', 'Stuttgart', 'Dresden', 'Leipzig',
  'Hannover', 'Nürnberg', 'Bremen', 'Kassel', 'Würzburg', 'Erfurt', 'Regensburg', 'Ulm', 'Kiel',
  'Rostock', 'Magdeburg', 'Freiburg', 'Karlsruhe', 'Augsburg', 'Dortmund', 'Passau'];
const EXITS = ['Seeblick', 'Waldau', 'Lindhorst', 'Bergheim', 'Talstadt', 'Neudorf', 'Ostring',
  'Altmühl', 'Hohenfels', 'Birkenau', 'Rosental', 'Kreuz Mitte', 'Steinbach', 'Am Hafen'];

// Geländehöhe neben der Straße. Hängt nur von x ab, deshalb muss das Gelände nicht mitscrollen.
export function terrainHeight(x) {
  const d = x > 0 ? x - ROAD.right : ROAD.left - x;
  if (d <= 0) return 0;
  return -0.05 + 3.8 * smoothstep(2, 45, d) + 1.2 * smoothstep(70, 200, d);
}

// Additive Materialien sollen im Nebel verblassen statt die Nebelfarbe aufzuaddieren
export function fadeInFog(material) {
  material.onBeforeCompile = shader => {
    shader.fragmentShader = shader.fragmentShader.replace('#include <fog_fragment>', `
      #ifdef USE_FOG
        #ifdef FOG_EXP2
          float fadeF = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
        #else
          float fadeF = smoothstep( fogNear, fogFar, vFogDepth );
        #endif
        gl_FragColor.rgb *= 1.0 - fadeF;
      #endif`);
  };
  return material;
}

export class World {
  constructor(scene, renderer) {
    this.scene = scene;
    this.aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    this.scroll = [];      // Texturen, die mit der Fahrt verschoben werden
    this.lampZ = [];       // lokale z-Positionen der Laternen (für Leuchteffekte)
    this.buildRoad();
    this.buildTerrain();
    this.buildBarrier();
    this.buildRails();
    this.buildLamps();
    this.buildVegetation();
    this.buildHills();
    this.buildGantry();
    this.buildBridge();
    this.night = -1;
  }

  // ---------------------------------------------------------------- Straße
  buildRoad() {
    const width = ROAD.right - ROAD.left;
    const geo = new THREE.PlaneGeometry(width, SPAN, 1, 24);
    geo.rotateX(-Math.PI / 2);
    geo.translate((ROAD.left + ROAD.right) / 2, 0, (Z_NEAR + Z_FAR) / 2);
    const pos = geo.attributes.position, uv = geo.attributes.uv;
    for (let i = 0; i < pos.count; i++) uv.setXY(i, pos.getX(i) - ROAD.left, -pos.getZ(i));
    const map = createRoadTexture(this.aniso);
    map.repeat.set(1 / width, 1 / 18);
    const normalMap = createAsphaltNormal(this.aniso);
    normalMap.repeat.set(1 / 2.5, 1 / 2.5);
    const mat = new THREE.MeshStandardMaterial({
      map, normalMap, normalScale: new THREE.Vector2(0.55, 0.55), roughness: 0.88, metalness: 0,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.receiveShadow = true;
    this.scene.add(mesh);
    this.scroll.push({ tex: map, period: 18 }, { tex: normalMap, period: 2.5 });
  }

  // ---------------------------------------------------------------- Gelände
  buildTerrain() {
    const tex = createGrassTexture(this.aniso);
    tex.repeat.set(1 / 7, 1 / 7);
    this.scroll.push({ tex, period: 7 });
    const mat = new THREE.MeshStandardMaterial({ map: tex, roughness: 1, metalness: 0 });
    const ds = [0, 0.6, 1.5, 3, 5, 8, 12, 17, 23, 30, 38, 47, 58, 72, 90, 115, 150, 200, 280, 400, 600];
    const rows = 8;
    for (const side of [1, -1]) {
      const edge = side > 0 ? ROAD.right : ROAD.left;
      const pos = [], uv = [], idx = [];
      for (let r = 0; r <= rows; r++) {
        const z = Z_NEAR - (SPAN * r) / rows;
        for (const d of ds) {
          const x = edge + side * d;
          pos.push(x, terrainHeight(x), z);
          uv.push(x, -z);
        }
      }
      const C = ds.length;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < C - 1; c++) {
          const a = r * C + c, b = a + 1, d = a + C, e = d + 1;
          if (side > 0) idx.push(a, b, d, b, e, d);
          else idx.push(a, d, b, b, d, e);
        }
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
      geo.setIndex(idx);
      geo.computeVertexNormals();
      const mesh = new THREE.Mesh(geo, mat);
      mesh.receiveShadow = true;
      this.scene.add(mesh);
    }
  }

  // ---------------------------------------------------------------- Betonschutzwand (Mitte)
  buildBarrier() {
    const pts = [[-0.3, 0], [-0.28, 0.07], [-0.19, 0.32], [-0.1, 0.84], [-0.09, 0.9],
      [0.09, 0.9], [0.1, 0.84], [0.19, 0.32], [0.28, 0.07], [0.3, 0]];
    const shape = new THREE.Shape(pts.map(p => new THREE.Vector2(p[0], p[1])));
    const geo = new THREE.ExtrudeGeometry(shape, { depth: SPAN, bevelEnabled: false, steps: 1 });
    geo.translate(ROAD.median, 0, Z_FAR);
    const tex = createConcreteTexture();
    tex.repeat.set(1 / 0.9, 1 / 6);
    this.scroll.push({ tex, period: 6 });
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: tex, roughness: 0.92, metalness: 0 }));
    mesh.castShadow = mesh.receiveShadow = true;
    this.scene.add(mesh);
  }

  // ---------------------------------------------------------------- Leitplanken
  buildRails() {
    // Profil einer Schutzplanke (W-Form), zur Fahrbahn hin gewölbt
    const prof = [[0, 0.5], [0.045, 0.525], [0.055, 0.555], [0.03, 0.6], [0.055, 0.645], [0.045, 0.675], [0, 0.7]];
    const metal = new THREE.MeshStandardMaterial({ color: 0xaeb3b8, metalness: 0.75, roughness: 0.38 });
    const rails = [];
    for (const [x0, dir] of [[ROAD.railRight, -1], [ROAD.railLeft, 1]]) {
      const front = prof.map(([a, y]) => new THREE.Vector2(x0 + dir * a, y));
      const back = prof.map(([a, y]) => new THREE.Vector2(x0 + dir * a - dir * 0.012, y)).reverse();
      const geo = new THREE.ExtrudeGeometry(new THREE.Shape(front.concat(back)), { depth: SPAN, bevelEnabled: false });
      geo.translate(0, 0, Z_FAR);
      geo.deleteAttribute('uv');
      rails.push(geo);
    }
    const railMesh = new THREE.Mesh(mergeGeometries(rails), metal);
    railMesh.castShadow = railMesh.receiveShadow = true;
    this.scene.add(railMesh);

    // Pfosten alle 4 m: Gruppe wird um (Fahrstrecke mod 4) verschoben → keine Einzel-Updates nötig
    const postGeo = new THREE.BoxGeometry(0.1, 0.72, 0.12);
    postGeo.translate(0, 0.36, 0);
    const n = Math.floor((Z_NEAR + 520) / 4);
    const posts = new THREE.InstancedMesh(postGeo, metal, n * 2);
    const m = new THREE.Matrix4();
    let k = 0;
    for (let i = 0; i < n; i++) {
      const z = Z_NEAR - i * 4;
      posts.setMatrixAt(k++, m.makeTranslation(ROAD.railRight + 0.09, 0, z));
      posts.setMatrixAt(k++, m.makeTranslation(ROAD.railLeft - 0.09, 0, z));
    }
    posts.castShadow = true;
    this.postGroup = new THREE.Group();
    this.postGroup.add(posts);

    // Rückstrahler an der Leitplanke alle 48 m
    this.reflMat = new THREE.MeshBasicMaterial({ color: 0xffb000 });
    const rn = Math.floor((Z_NEAR - Z_FAR) / 48);
    const refl = new THREE.InstancedMesh(new THREE.BoxGeometry(0.03, 0.08, 0.05), this.reflMat, rn * 2);
    k = 0;
    for (let i = 0; i < rn; i++) {
      const z = Z_NEAR - i * 48;
      refl.setMatrixAt(k++, m.makeTranslation(ROAD.railRight - 0.05, 0.6, z));
      refl.setMatrixAt(k++, m.makeTranslation(ROAD.railLeft + 0.05, 0.6, z));
    }
    this.reflGroup = new THREE.Group();
    this.reflGroup.add(refl);
    this.scene.add(this.postGroup, this.reflGroup);
  }

  // ---------------------------------------------------------------- Laternen auf der Mittelwand
  buildLamps() {
    const SP = 64;
    this.lampSpacing = SP;
    const steel = new THREE.MeshStandardMaterial({ color: 0x80868c, metalness: 0.7, roughness: 0.45 });
    const parts = [];
    const pole = new THREE.CylinderGeometry(0.08, 0.13, 9.2, 8);
    pole.translate(0, 0.9 + 4.6, 0);
    parts.push(pole);
    for (const s of [1, -1]) {
      const arm = new THREE.BoxGeometry(3.7, 0.09, 0.09);
      arm.rotateZ(s * 0.06);
      arm.translate(s * 1.8, 9.95, 0);
      parts.push(arm);
      const head = new THREE.BoxGeometry(0.8, 0.14, 0.34);
      head.translate(s * 3.55, 10.02, 0);
      parts.push(head);
    }
    const lampGeo = mergeGeometries(parts.map(g => (g.index ? g.toNonIndexed() : g)));
    const lensGeo = new THREE.BoxGeometry(0.62, 0.03, 0.24);
    this.lensMat = new THREE.MeshBasicMaterial({ color: 0xfff0d8 });
    this.poolMat = fadeInFog(new THREE.MeshBasicMaterial({
      color: 0xffd9a8, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4,
    }));
    const n = Math.floor((Z_NEAR - Z_FAR) / SP) + 1;
    const lamps = new THREE.InstancedMesh(lampGeo, steel, n);
    const lenses = new THREE.InstancedMesh(lensGeo, this.lensMat, n * 2);
    const poolGeo = new THREE.CircleGeometry(0.5, 24).rotateX(-Math.PI / 2);
    const pools = new THREE.InstancedMesh(poolGeo, this.poolMat, n * 2);
    pools.renderOrder = 2;
    this.poolMat.map = this.makePoolTexture();
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
    for (let i = 0; i < n; i++) {
      const z = Z_NEAR - i * SP;
      this.lampZ.push(z);
      lamps.setMatrixAt(i, m.makeTranslation(ROAD.median, 0, z));
      for (const [j, sx] of [[0, 1], [1, -1]]) {
        lenses.setMatrixAt(i * 2 + j, m.makeTranslation(ROAD.median + sx * 3.55, 9.94, z));
        p.set(ROAD.median + sx * 3.9, 0.02, z);
        s.set(15, 1, 19);
        pools.setMatrixAt(i * 2 + j, m.compose(p, q, s));
      }
    }
    lamps.castShadow = true;
    this.lampGroup = new THREE.Group();
    this.lampGroup.add(lamps, lenses, pools);
    this.pools = pools;
    this.scene.add(this.lampGroup);
  }

  makePoolTexture() {
    const c = document.createElement('canvas');
    c.width = c.height = 128;
    const g = c.getContext('2d');
    const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grd.addColorStop(0, 'rgba(255,255,255,0.9)');
    grd.addColorStop(0.35, 'rgba(255,255,255,0.55)');
    grd.addColorStop(0.7, 'rgba(255,255,255,0.15)');
    grd.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }

  // Weltpositionen der Laternenköpfe (für Leuchteffekte)
  forEachLampHead(fn) {
    const off = this.lampGroup.position.z;
    for (const z of this.lampZ) {
      const wz = z + off;
      if (wz > 30 || wz < -700) continue;
      fn(ROAD.median + 3.55, 9.75, wz);
      fn(ROAD.median - 3.55, 9.75, wz);
    }
  }

  // ---------------------------------------------------------------- Bäume und Büsche
  buildVegetation() {
    const jitter = (g, amount, seed) => {
      const p = g.attributes.position;
      for (let i = 0; i < p.count; i++) {
        const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
        const n = Math.sin(x * 3.1 + y * 1.7 + seed) * Math.cos(z * 2.3 - y * 1.1 + seed * 2);
        p.setXYZ(i, x * (1 + n * amount), y + n * amount * 0.6, z * (1 + n * amount));
      }
      return g;
    };
    const smooth = g => {
      g.deleteAttribute('normal');
      g.deleteAttribute('uv');
      const m = mergeVertices(g, 1e-3);
      m.computeVertexNormals();
      return m.toNonIndexed();
    };
    const trunk = new THREE.CylinderGeometry(0.12, 0.2, 2.6, 6);
    trunk.translate(0, 1.3, 0);
    const cone = (r, h, y) => {
      const g = new THREE.ConeGeometry(r, h, 9, 2);
      g.translate(0, y, 0);
      return g;
    };
    const conifer = smooth(jitter(mergeGeometries([cone(1.8, 3.6, 3.0), cone(1.35, 3.1, 4.6), cone(0.9, 2.5, 6.0)]
      .map(g => g.toNonIndexed())), 0.07, 1));
    const ico = (r, x, y, z) => {
      const g = new THREE.IcosahedronGeometry(r, 1);
      g.translate(x, y, z);
      return g;
    };
    const blob = smooth(jitter(mergeGeometries([ico(1.9, 0, 3.9, 0), ico(1.4, 0.9, 4.7, 0.3), ico(1.3, -0.8, 4.4, -0.5)]), 0.12, 2));

    const trunkMat = new THREE.MeshStandardMaterial({ color: 0x5b4532, roughness: 0.95 });
    const leafMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9 });
    // Je Art eigene Meshes, damit sich die Anzahl pro Grafikstufe sauber kürzen lässt
    const make = (geo, mat, n) => {
      const im = new THREE.InstancedMesh(geo, mat, n);
      im.frustumCulled = false;
      im.castShadow = true;
      im.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      this.scene.add(im);
      return im;
    };
    const kinds = [['conifer', conifer, 130, true], ['tree', blob, 110, true], ['bush', blob, 100, false]];
    this.vegMeshes = [];
    this.slots = [];
    for (const [kind, geo, n, hasTrunk] of kinds) {
      const crown = make(geo, leafMat, n);
      const trunkMesh = hasTrunk ? make(trunk, trunkMat, n) : null;
      this.vegMeshes.push({ crown, trunk: trunkMesh, max: n });
      for (let i = 0; i < n; i++) this.slots.push({ kind, mesh: crown, trunk: trunkMesh, i });
    }
    this.tmpM = new THREE.Matrix4();
    this.tmpQ = new THREE.Quaternion();
    this.tmpS = new THREE.Vector3();
    this.tmpP = new THREE.Vector3();
    this.tmpC = new THREE.Color();
    this.yAxis = new THREE.Vector3(0, 1, 0);
  }

  placeVeg(slot, s) {
    slot.s = s;
    const right = Math.random() < 0.55;
    let x, sc;
    if (slot.kind === 'bush') {
      x = right ? ROAD.right + rand(1.2, 6) : ROAD.left - rand(1.2, 6);
      sc = rand(0.35, 0.7);
    } else {
      const d = 4 + Math.pow(Math.random(), 1.5) * 80;
      x = right ? ROAD.right + d : ROAD.left - d;
      sc = rand(0.8, 1.45);
    }
    const y = terrainHeight(x);
    this.tmpQ.setFromAxisAngle(this.yAxis, Math.random() * Math.PI * 2);
    slot.x = x;
    // Busch: Krone abgesenkt, damit sie am Boden sitzt
    const yOff = slot.kind === 'bush' ? 0.6 - 3.9 * sc : 0;
    this.tmpS.set(sc * rand(0.9, 1.1), sc * rand(0.9, 1.2), sc * rand(0.9, 1.1));
    this.tmpM.compose(this.tmpP.set(x, y + yOff, 0), this.tmpQ, this.tmpS);
    slot.mesh.setMatrixAt(slot.i, this.tmpM);
    const c = this.tmpC;
    if (slot.kind === 'conifer') c.setHSL(rand(0.27, 0.33), rand(0.35, 0.5), rand(0.16, 0.24));
    else if (slot.kind === 'tree') c.setHSL(rand(0.2, 0.3), rand(0.4, 0.55), rand(0.22, 0.33));
    else c.setHSL(rand(0.2, 0.28), rand(0.35, 0.5), rand(0.2, 0.28));
    slot.mesh.setColorAt(slot.i, c);
    slot.mesh.instanceColor.needsUpdate = true;
    if (slot.trunk) {
      this.tmpS.set(sc, sc, sc);
      this.tmpM.compose(this.tmpP.set(x, y, 0), this.tmpQ, this.tmpS);
      slot.trunk.setMatrixAt(slot.i, this.tmpM);
    }
  }

  // ---------------------------------------------------------------- Hügel in der Ferne
  buildHills() {
    const g = new THREE.SphereGeometry(1, 24, 10, 0, Math.PI * 2, 0, Math.PI / 2);
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
      const n = 1 + 0.18 * Math.sin(x * 4.0 + z * 2.0) * Math.cos(z * 3.0 - x);
      p.setXYZ(i, x * n, y * (0.85 + 0.15 * n), z * n);
    }
    g.computeVertexNormals();
    this.hills = new THREE.InstancedMesh(g, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1 }), 18);
    this.hills.frustumCulled = false;
    this.hills.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.scene.add(this.hills);
    this.hillSlots = [];
    for (let i = 0; i < 18; i++) this.hillSlots.push({ i });
  }

  placeHill(h, s) {
    h.s = s;
    const right = h.i % 2 === 0;
    const d = rand(140, 420);
    const x = right ? ROAD.right + d : ROAD.left - d;
    this.tmpQ.setFromAxisAngle(this.yAxis, Math.random() * Math.PI);
    this.tmpS.set(rand(70, 170), rand(14, 42), rand(60, 150));
    this.tmpM.compose(this.tmpP.set(x, terrainHeight(x) - 3, 0), this.tmpQ, this.tmpS);
    this.hills.setMatrixAt(h.i, this.tmpM);
    this.hills.setColorAt(h.i, this.tmpC.setHSL(rand(0.22, 0.3), rand(0.25, 0.4), rand(0.22, 0.3)));
    this.hills.instanceColor.needsUpdate = true;
  }

  // ---------------------------------------------------------------- Schilderbrücke
  buildGantry() {
    const g = new THREE.Group();
    const steel = new THREE.MeshStandardMaterial({ color: 0x8f959b, metalness: 0.6, roughness: 0.5 });
    const add = (geo, mat, x, y, z) => {
      const m = new THREE.Mesh(geo, mat);
      m.position.set(x, y, z);
      m.castShadow = true;
      g.add(m);
      return m;
    };
    const right = ROAD.railRight + 1.2;
    add(new THREE.BoxGeometry(0.45, 8.6, 0.45), steel, ROAD.median, 4.3, 0);
    add(new THREE.BoxGeometry(0.45, 8.6, 0.45), steel, right, 4.3, 0);
    const span = right - ROAD.median + 0.6;
    add(new THREE.BoxGeometry(span, 0.5, 0.5), steel, (right + ROAD.median) / 2, 8.15, 0);
    add(new THREE.BoxGeometry(span, 0.3, 0.3), steel, (right + ROAD.median) / 2, 5.55, 0);
    this.signTex = [createSignTexture(this.aniso), createSignTexture(this.aniso)];
    this.signMats = this.signTex.map(t => new THREE.MeshStandardMaterial({
      map: t, emissiveMap: t, emissive: 0xffffff, emissiveIntensity: 0, roughness: 0.55, metalness: 0,
    }));
    for (const [i, x] of [[0, -3.6], [1, 3.6]]) {
      add(new THREE.BoxGeometry(6.5, 2.55, 0.12), steel, x, 6.85, 0.2);
      const panel = add(new THREE.PlaneGeometry(6.5, 2.54), this.signMats[i], x, 6.85, 0.265);
      panel.castShadow = false;
    }
    this.gantry = { group: g, s: 0 };
    this.scene.add(g);
  }

  refreshSigns() {
    const a = pick(CITIES);
    let b = pick(CITIES);
    while (b === a) b = pick(CITIES);
    drawSign(this.signTex[0], { arrow: 'up', top: a, bottom: b, tag: 'A ' + Math.floor(rand(1, 99)) });
    drawSign(this.signTex[1], { arrow: 'right', top: 'Ausfahrt', bottom: pick(EXITS), tag: String(Math.floor(rand(2, 60))) });
  }

  // ---------------------------------------------------------------- Brücke über die Autobahn
  buildBridge() {
    const g = new THREE.Group();
    const concrete = new THREE.MeshStandardMaterial({ color: 0xa8a399, roughness: 0.9 });
    const metal = new THREE.MeshStandardMaterial({ color: 0x6f757b, metalness: 0.6, roughness: 0.5 });
    const add = (w, h, d, mat, x, y, z) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
      m.position.set(x, y, z);
      m.castShadow = m.receiveShadow = true;
      g.add(m);
    };
    const x0 = ROAD.left - 16, x1 = ROAD.right + 16, cx = (x0 + x1) / 2, w = x1 - x0;
    add(w, 1.3, 11, concrete, cx, 6.95, 0);
    add(w, 0.9, 0.3, concrete, cx, 8.05, 5.35);
    add(w, 0.9, 0.3, concrete, cx, 8.05, -5.35);
    add(w, 0.08, 0.08, metal, cx, 8.75, 5.35);
    add(w, 0.08, 0.08, metal, cx, 8.75, -5.35);
    add(0.9, 6.3, 7.5, concrete, ROAD.median, 3.15, 0);
    add(3.5, 8.0, 11, concrete, ROAD.right + 4.2, 3.6, 0);
    add(3.5, 8.0, 11, concrete, ROAD.left - 4.2, 3.6, 0);
    this.bridge = { group: g, s: 0 };
    this.scene.add(g);
  }

  // Laternen stehen bei s ≡ 4 (mod 64). Brücken mittig dazwischen setzen, damit kein Mast durchragt.
  betweenLamps(s) {
    return Math.round((s - 36) / this.lampSpacing) * this.lampSpacing + 36;
  }

  // ---------------------------------------------------------------- Start und Laufzeit
  reset(travel) {
    for (const sl of this.slots) this.placeVeg(sl, travel + rand(-RECYCLE_Z, -Z_FAR));
    for (const h of this.hillSlots) this.placeHill(h, travel + rand(-200, 1000));
    this.gantry.s = this.betweenLamps(travel + rand(250, 450));
    this.bridge.s = this.betweenLamps(travel + rand(700, 900));
    this.refreshSigns();
  }

  setQuality(level) {
    const f = level === 0 ? 0.55 : level === 1 ? 0.8 : 1;
    for (const m of this.vegMeshes) {
      m.crown.count = Math.floor(m.max * f);
      if (m.trunk) m.trunk.count = m.crown.count;
    }
  }

  update(travel, night) {
    for (const s of this.scroll) s.tex.offset.y = (travel / s.period) % 1;
    this.postGroup.position.z = travel % 4;
    this.reflGroup.position.z = travel % 48;
    this.lampGroup.position.z = travel % this.lampSpacing;

    // Bäume/Büsche: nur die z-Position ändert sich
    for (const sl of this.slots) {
      if (travel - sl.s > RECYCLE_Z) this.placeVeg(sl, sl.s + VEG_SPAN);
      const z = travel - sl.s;
      sl.mesh.instanceMatrix.array[sl.i * 16 + 14] = z;
      if (sl.trunk) sl.trunk.instanceMatrix.array[sl.i * 16 + 14] = z;
    }
    for (const m of this.vegMeshes) {
      m.crown.instanceMatrix.needsUpdate = true;
      if (m.trunk) m.trunk.instanceMatrix.needsUpdate = true;
    }

    for (const h of this.hillSlots) {
      if (travel - h.s > 400) this.placeHill(h, h.s + rand(1300, 1500));
      this.hills.instanceMatrix.array[h.i * 16 + 14] = travel - h.s;
    }
    this.hills.instanceMatrix.needsUpdate = true;

    if (travel - this.gantry.s > 60) {
      let s = travel + rand(950, 1300);
      if (Math.abs(s - this.bridge.s) < 150) s += 300;
      this.gantry.s = this.betweenLamps(s);
      this.refreshSigns();
    }
    this.gantry.group.position.z = travel - this.gantry.s;
    if (travel - this.bridge.s > 60) {
      let s = travel + rand(1300, 1800);
      if (Math.abs(this.gantry.s - s) < 150) s += 300;
      this.bridge.s = this.betweenLamps(s);
    }
    this.bridge.group.position.z = travel - this.bridge.s;

    if (Math.abs(night - this.night) > 0.01) {
      this.night = night;
      this.lensMat.color.setRGB(1, 0.93, 0.82).multiplyScalar(0.25 + night * 5);
      this.poolMat.color.setRGB(1, 0.8, 0.58).multiplyScalar(night * 0.42);
      this.pools.visible = night > 0.02;
      this.reflMat.color.setRGB(1, 0.62, 0.1).multiplyScalar(0.25 + night * 1.6);
      for (const m of this.signMats) m.emissiveIntensity = night * 0.35;
    }
  }
}
