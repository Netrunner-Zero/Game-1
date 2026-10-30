// Ersatz für three/addons/* im Rauchtest.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import * as THREE from '../three-stub.mjs';

export class EffectComposer { constructor() { this.passes = []; } addPass(p) { this.passes.push(p); } setPixelRatio() {} setSize() {} render() {} }
export class RenderPass { constructor() {} }
export class OutputPass { constructor() {} }
export class UnrealBloomPass { constructor() { this.threshold = 1; this.strength = 1; this.radius = 0; } }
export class OrbitControls { constructor() { this.target = new THREE.Vector3(); } update() {} }

// GLTFLoader: liest die echte GLB (nur JSON-Teil) und baut Knoten, Namen, extras und Materialien nach.
export class GLTFLoader {
  load(url, onLoad, onProgress, onError) {
    try {
      const path = globalThis.__smokeResolve(url);
      const data = readFileSync(path);
      const jl = data.readUInt32LE(12);
      const js = JSON.parse(data.subarray(20, 20 + jl).toString('utf8'));
      const mats = (js.materials || []).map((m) => {
        const physical = m.extensions && Object.keys(m.extensions).some((k) => /clearcoat|sheen|iridescence|transmission|specular|ior|anisotropy/.test(k));
        const M = physical ? new THREE.MeshPhysicalMaterial() : new THREE.MeshStandardMaterial();
        M.name = m.name || '';
        M.userData = m.extras ? JSON.parse(JSON.stringify(m.extras)) : {};
        const pbr = m.pbrMetallicRoughness || {};
        M.roughness = pbr.roughnessFactor !== undefined ? pbr.roughnessFactor : 1;
        M.metalness = pbr.metallicFactor !== undefined ? pbr.metallicFactor : 1;
        M.transparent = m.alphaMode === 'BLEND';
        if (m.emissiveFactor) M.emissive = new THREE.Color(...m.emissiveFactor);
        const es = m.extensions && m.extensions.KHR_materials_emissive_strength;
        M.emissiveIntensity = es ? es.emissiveStrength : 1;
        if (pbr.baseColorTexture) M.map = new THREE.Texture();
        if (m.normalTexture) M.normalMap = new THREE.Texture();
        if (physical) { M.clearcoat = 1; }
        return M;
      });
      const build = (i) => {
        const n = js.nodes[i];
        let o;
        if (n.mesh !== undefined) {
          const prims = js.meshes[n.mesh].primitives;
          if (prims.length === 1) o = new THREE.Mesh(new THREE.BufferGeometry(), mats[prims[0].material]);
          else { o = new THREE.Group(); for (const p of prims) o.add(new THREE.Mesh(new THREE.BufferGeometry(), mats[p.material])); }
        } else o = new THREE.Group();
        o.name = n.name || '';
        if (n.extras) o.userData = JSON.parse(JSON.stringify(n.extras));
        if (n.translation) o.position.set(...n.translation);
        if (n.rotation) o.quaternion.set(...n.rotation);
        if (n.scale) o.scale.set(...n.scale);
        for (const c of n.children || []) o.add(build(c));
        return o;
      };
      const scene = new THREE.Group();
      for (const r of js.scenes[js.scene || 0].nodes) scene.add(build(r));
      if (onProgress) onProgress({ loaded: data.length, total: data.length });
      setTimeout(() => onLoad({ scene }), 0);
    } catch (e) {
      if (onError) onError(e); else throw e;
    }
  }
}
