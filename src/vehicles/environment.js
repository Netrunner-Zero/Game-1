// Umgebungsreflexionen (Environment Maps) für Tag und Nacht.
//
// Statt externer HDR-Dateien wird eine kleine Szene mit leuchtenden
// Flächen (Softboxen bzw. Neonröhren) gebaut und mit dem PMREMGenerator
// in eine vorgefilterte Umgebungstextur umgerechnet. Lack, Chrom und Glas
// spiegeln damit realistische Lichtkanten.

import * as THREE from 'three';

function box(scene, w, h, d, color, intensity, pos, rot) {
  const m = new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), side: THREE.DoubleSide });
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
  mesh.position.set(pos[0], pos[1], pos[2]);
  if (rot) mesh.rotation.set(rot[0], rot[1], rot[2]);
  scene.add(mesh);
  return mesh;
}

function gradientRoom(scene, bottom, middle, top) {
  // Innenseite einer Kugel mit Farbverlauf (Boden dunkel, Decke hell)
  const geo = new THREE.SphereGeometry(30, 48, 24);
  const col = [];
  const pos = geo.attributes.position;
  const c0 = new THREE.Color(bottom), c1 = new THREE.Color(middle), c2 = new THREE.Color(top);
  const tmp = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const t = pos.getY(i) / 30; // -1..1
    if (t < 0) tmp.copy(c1).lerp(c0, Math.min(1, -t * 3));
    else tmp.copy(c1).lerp(c2, Math.pow(t, 0.8));
    col.push(tmp.r, tmp.g, tmp.b);
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide }));
  scene.add(mesh);
}

function studioScene() {
  const s = new THREE.Scene();
  gradientRoom(s, 0x0b0c0f, 0x2a2d34, 0x6d7380);
  // große Softbox über dem Auto + zwei lange Lichtstreifen (typische Studio-Reflexe im Lack)
  box(s, 7, 0.1, 3.2, 0xffffff, 7.0, [0, 9, 0]);
  box(s, 0.5, 0.1, 9, 0xffffff, 5.0, [-4.5, 8, 0]);
  box(s, 0.5, 0.1, 9, 0xffffff, 5.0, [4.5, 8, 0]);
  // seitliche Lichtwände (geben der Flanke eine Kante)
  box(s, 0.1, 2.5, 8, 0xeef2ff, 2.2, [-11, 3, 0]);
  box(s, 0.1, 2.5, 8, 0xfff4e8, 1.8, [11, 3, 0]);
  box(s, 8, 2.0, 0.1, 0xffffff, 1.2, [0, 3.5, -12]);
  // warmer Akzent vorne
  box(s, 4, 0.6, 0.1, 0xffd2a0, 1.5, [0, 2.0, 12]);
  return s;
}

function nightScene() {
  const s = new THREE.Scene();
  gradientRoom(s, 0x020204, 0x070912, 0x10142a);
  // Neonröhren der Stadt
  box(s, 14, 0.18, 0.18, 0xff2bd6, 5.0, [0, 2.2, -11]);
  box(s, 0.18, 0.18, 14, 0x00e5ff, 5.0, [-11, 3.0, 0]);
  box(s, 0.18, 0.18, 14, 0x7a5cff, 3.5, [11, 2.6, 0]);
  box(s, 10, 0.15, 0.15, 0xff8a00, 2.5, [0, 4.5, 11]);
  // gedämpfte Straßenbeleuchtung von oben
  box(s, 3, 0.1, 1.2, 0xffc78a, 2.2, [0, 9, 3]);
  box(s, 3, 0.1, 1.2, 0xbfd8ff, 1.6, [0, 9, -4]);
  // ferne Fensterlichter
  for (let i = 0; i < 26; i++) {
    const a = (i / 26) * Math.PI * 2;
    const r = 18 + (i % 3);
    const c = i % 4 === 0 ? 0x00e5ff : i % 4 === 1 ? 0xff2bd6 : i % 4 === 2 ? 0xffd27a : 0x9fb8ff;
    box(s, 0.6, 0.35 + (i % 5) * 0.2, 0.6, c, 2.0, [Math.cos(a) * r, 1.5 + (i % 7) * 1.2, Math.sin(a) * r]);
  }
  return s;
}

export function createEnvironment(renderer, mode = 'day') {
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();
  const scene = mode === 'night' ? nightScene() : studioScene();
  const rt = pmrem.fromScene(scene, mode === 'night' ? 0.02 : 0.03, 0.1, 100);
  scene.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) o.material.dispose();
  });
  pmrem.dispose();
  return rt.texture;
}
