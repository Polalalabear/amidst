import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { buildCapsulePerson, COLORS } from './world.mjs';

// A person handle hides the coordinate frames: capsule lives in the Z-up root, GLB (Y-up, +X forward)
// lives directly in the scene.
export async function makePerson(kind, world, colorName = 'red') {
  const c = COLORS[colorName];
  if (kind === 'glb') {
    const gltf = await new GLTFLoader().loadAsync('/data/character.glb');
    const o = gltf.scene;
    world.scene.add(o);
    return {
      kind, object: o, tris: countTris(o),
      setPose(x, y, h) { o.position.set(x, 0, -y); o.rotation.set(0, h, 0); },
      setVisible(v) { o.visible = v; },
    };
  }
  const o = buildCapsulePerson(c);
  world.root.add(o);
  return {
    kind, object: o, tris: countTris(o),
    setPose(x, y, h) { o.position.set(x, y, 0); o.rotation.z = h; },
    setVisible(v) { o.visible = v; },
  };
}
function countTris(o) {
  let n = 0;
  o.traverse((m) => { if (m.isMesh) n += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3; });
  return Math.round(n);
}
// pixel bbox of a person standing at (x,y): projects a 0.5 x 0.5 x 1.75 m box (evaluation only)
export function projectBox(cam, root, x, y, imgW, imgH) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, behind = false;
  for (const dx of [-0.25, 0.25]) for (const dy of [-0.25, 0.25]) for (const z of [0, 1.75]) {
    const v = new THREE.Vector3(x + dx, y + dy, z).applyMatrix4(root.matrixWorld).project(cam);
    if (v.z > 1) behind = true;
    const u = (v.x * 0.5 + 0.5) * imgW, w = (-v.y * 0.5 + 0.5) * imgH;
    x0 = Math.min(x0, u); x1 = Math.max(x1, u); y0 = Math.min(y0, w); y1 = Math.max(y1, w);
  }
  return behind ? null : [x0, y0, x1, y1];
}
