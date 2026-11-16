// N6 asset integration (#539): cameras.three.json, character.glb (KHR_materials_variants + in-place clips),
// scene.glb. Pure three.js, no DOM, so node --test can import it. Frames: glTF Y-up metres,
// Blender (x,y,z) -> (x,z,-y), character forward = +X.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkinned } from 'three/addons/utils/SkeletonUtils.js';

export const NOMINAL = { walk: 1.2, run: 2.5 }; // m/s, N6 clip speeds (character asset.extras)
export const VARIANTS = ['T', 'A', 'B', 'C'];

// Blender (x,y,z) -> glTF (x,z,-y) as a 4x4 (row-major rows)
export const BLENDER_TO_GLTF = [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]];
export const blenderToGltf = (x, y, z = 0) => [x, z, -y];

// Matrices in cameras.three.json are row-major nested arrays: Matrix4.set(...rows.flat()).
export const rowMajor = (rows) => new THREE.Matrix4().set(...rows.flat());

// N6 cameras at a chosen render size. fov from fy/cy (principal point centred, 16:9 kept).
export function buildN6Cameras(camJson, scene, width, height) {
  const cams = {};
  for (const c of camJson.cameras) {
    const fov = 2 * Math.atan(c.cy / c.fy) * 180 / Math.PI;
    const cam = new THREE.PerspectiveCamera(fov, width / height, c.near, c.far);
    cam.matrixAutoUpdate = false;
    const M = rowMajor(c.camera_to_world);
    cam.matrix.copy(M); cam.matrixWorld.copy(M);
    cam.matrixWorldInverse.copy(M).invert();
    scene.add(cam);
    cams[c.camera_id] = { camera: cam, spec: c, width, height, scale: width / c.width };
  }
  return cams;
}

// GLTFLoader plugin: KHR_materials_variants is not handled by three core, so keep the mapping per mesh.
class VariantsPlugin {
  constructor(parser) { this.parser = parser; this.name = 'KHR_materials_variants'; }
  async afterRoot(result) {
    const parser = this.parser;
    const names = (parser.json.extensions?.KHR_materials_variants?.variants || []).map((v) => v.name);
    result.userData.variants = names;
    // keyed by mesh name, NOT in mesh.userData: Object3D.clone() JSON-copies userData and would turn materials into plain objects
    const table = (result.userData.variantTable = {});
    const jobs = [];
    result.scene.traverse((o) => {
      const a = parser.associations.get(o);
      if (!o.isMesh || !a || a.meshes === undefined || a.primitives === undefined) return;
      const ext = parser.json.meshes[a.meshes].primitives[a.primitives].extensions?.KHR_materials_variants;
      if (!ext) return;
      const row = (table[o.name] = { default: o.material, variants: {} });
      for (const m of ext.mappings) {
        jobs.push(parser.getDependency('material', m.material).then((mat) => { for (const v of m.variants) row.variants[names[v]] = mat; }));
      }
    });
    await Promise.all(jobs);
  }
}

export function makeLoader() { return new GLTFLoader().register((p) => new VariantsPlugin(p)); }

// A character handle. The source GLTF is cloned (skeleton-safe) so several people can share one load.
// Locomotion: clips are in place, so the action plays at timeScale = actualSpeed / nominalSpeed.
export function makeCharacter(gltf, variant = 'T') {
  const table = gltf.userData.variantTable || {};
  const object = cloneSkinned(gltf.scene);
  const mixer = new THREE.AnimationMixer(object);
  const actions = {};
  for (const clip of gltf.animations) actions[clip.name] = mixer.clipAction(clip);
  const h = {
    object, mixer, actions, variant, current: null, tris: 0,
    setVariant(name) {
      if (!VARIANTS.includes(name)) throw new Error(`unknown variant ${name}`);
      object.traverse((o) => { const row = o.isMesh && table[o.name]; if (row) o.material = row.variants[name] || row.default; });
      h.variant = name;
    },
    // speed in m/s -> clip + timeScale. 0 -> idle; <= walk-ish uses walk; above midpoint uses run.
    setSpeed(speed, running = speed > (NOMINAL.walk + NOMINAL.run) / 2) {
      const name = speed <= 1e-6 ? 'idle' : running ? 'run' : 'walk';
      const ts = name === 'idle' ? 1 : speed / NOMINAL[name];
      const a = actions[name];
      if (h.current !== a) { if (h.current) a.crossFadeFrom(h.current, 0.15, false); a.reset().play(); h.current = a; }
      a.timeScale = ts;
      return { clip: name, timeScale: ts };
    },
    update(dt) { mixer.update(dt); },
    setPose(x, y, heading) { object.position.set(x, 0, -y); object.rotation.set(0, heading, 0); },
    setVisible(v) { object.visible = v; },
  };
  object.traverse((m) => { if (m.isMesh) h.tris += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3; });
  h.tris = Math.round(h.tris);
  h.setVariant(variant);
  h.setSpeed(0);
  return h;
}
