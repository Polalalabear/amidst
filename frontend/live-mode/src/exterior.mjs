// Exterior backdrop (#602, mock #600/D307): sky dome, far ground, road, trees, house silhouettes, haze.
// Source: generated in code (three.js primitives + fixed-seed LCG), no image/model assets, nothing re-rendered.
// Decoration only, outside the N6 yard (x -15.2..-3.2, z -8..6, three Y-up): it is never added to
// world.blockers / world.segments and sim.mjs is untouched, so the walkable area and GT visibility are unchanged.
// Detection safety: no red/blue materials (those hues are the person colours), no person-sized upright
// humanoid shapes; everything beyond ~40 m fades to haze (camera far is 100 m for N6 cameras).
import * as THREE from 'three';

const HAZE = 0xc9d3dc;
export const FOG_NEAR = 12, FOG_FAR = 98; // N6 camera far = 100: backdrop fades fully into haze before it clips. Near=12 keeps
// the doorway view (CAM_W2 end door) a soft haze: with 40 a dark tree edge made the detector add a head box (+1 candidate)
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
const lam = (c) => new THREE.MeshLambertMaterial({ color: c });

export function addExterior(scene, opts = {}) {
  // the existing scene (N6 glb, walls, people) keeps its colours: haze is for the backdrop only
  scene.traverse((o) => { for (const m of [].concat(o.material || [])) if (m.fog) { m.fog = false; m.needsUpdate = true; } });
  const g = new THREE.Group(); g.name = 'EXTERIOR_BACKDROP';
  const R = rng(opts.seed ?? 7);
  // sky: vertex-coloured dome, unaffected by fog
  const sky = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false,
    uniforms: { top: { value: new THREE.Color(0x5b8fd0) }, hor: { value: new THREE.Color(HAZE) } },
    vertexShader: 'varying float h; void main(){ h = normalize(position).y; gl_Position = (projectionMatrix*mat4(mat3(modelViewMatrix))*vec4(position,1.)).xyww; }',
    fragmentShader: 'uniform vec3 top; uniform vec3 hor; varying float h; void main(){ gl_FragColor = vec4(mix(hor, top, pow(clamp(h,0.,1.), .55)), 1.); }',
  }));
  sky.renderOrder = -10; sky.frustumCulled = false; g.add(sky); // xyww: sits on the far plane whatever the camera far is
  // ground: grass to the horizon, asphalt lot around the yard, a road further out
  const Y = -0.25;
  const plane = (w, d, x, z, c, y = Y) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), lam(c)); m.rotation.x = -Math.PI / 2; m.position.set(x, y, z); g.add(m); return m; };
  plane(900, 900, 0, 0, 0x6f8f55, Y - 0.02);               // grass
  plane(60, 40, -26, -1, 0x4a4d52, Y);                       // parking-lot asphalt around the yard
  plane(14, 400, -58, 0, 0x3b3e43, Y + 0.01);                // road running N-S
  for (let z = -190; z < 190; z += 6) plane(0.2, 3, -58, z, 0xe8e2c0, Y + 0.02); // centre dashes
  for (let z = -4; z <= 6; z += 2.8) plane(0.1, 5, -40, z, 0xdcdcdc, Y + 0.02);   // parking stall lines
  // parked cars further along the lot (box + cabin)
  const carCols = [0x8c8a82, 0x6f6a58, 0xd8d8d8, 0x30343a, 0x4e6b4a]; // no red/blue
  for (let i = 0; i < 6; i++) {
    const z = -14 + i * 4.6, c = lam(carCols[i % 5]);
    const b = new THREE.Mesh(new THREE.BoxGeometry(1.9, 0.7, 4.2), c); b.position.set(-34, 0.35 + Y, z);
    const k = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.6, 2.2), lam(0x9fb4c4)); k.position.set(-34, 0.95 + Y, z - 0.2);
    g.add(b, k);
  }
  // street lamps along the lot edge
  for (let z = -16; z <= 16; z += 8) {
    const p = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 6.5, 6), lam(0x5a5f66)); p.position.set(-46, 3.0, z);
    const l = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.12, 0.35), lam(0x5a5f66)); l.position.set(-45.4, 6.2, z);
    g.add(p, l);
  }
  // trees: trunk + stacked foliage blobs, thicker with distance (shared geometry)
  const trunk = new THREE.CylinderGeometry(0.18, 0.28, 3, 6), blob = new THREE.IcosahedronGeometry(1, 1);
  const leafCols = [0x3d6b34, 0x4a7a3a, 0x335c2e, 0x58853f];
  const tree = (x, z, s) => {
    const t = new THREE.Mesh(trunk, lam(0x4d3a2a)); t.scale.setScalar(s); t.position.set(x, 1.5 * s + Y, z); g.add(t);
    for (let i = 0; i < 3; i++) {
      const f = new THREE.Mesh(blob, lam(leafCols[(R() * 4) | 0]));
      f.scale.set(2.2 * s, (1.8 + R() * 0.8) * s, 2.2 * s); f.position.set(x + (R() - .5) * s, (3.4 + i * 1.5) * s + Y, z + (R() - .5) * s); g.add(f);
    }
  };
  for (let i = 0; i < 90; i++) {                              // ring of trees 45..95 m out, skipping the road corridor
    const a = R() * Math.PI * 2, r = 45 + R() * 50, x = Math.cos(a) * r, z = Math.sin(a) * r;
    if (Math.abs(x + 58) < 9) continue; tree(x, z, 1.2 + R() * 1.4);
  }
  for (let i = 0; i < 14; i++) tree(-70 + R() * 6, -20 + i * 3 + R() * 2, 1 + R() * .8);   // tree line behind the road
  // suburban house silhouettes (box + gable roof) at 70..120 m
  const wall = [0xd9cdb8, 0xc6b9a0, 0xb8c4cc, 0xdad3c2], roof = [0x5b4a44, 0x4a4f57, 0x5b4636];
  for (let i = 0; i < 12; i++) {
    const a = R() * Math.PI * 2, r = 60 + R() * 35, x = Math.cos(a) * r, z = Math.sin(a) * r;
    if (Math.abs(x + 58) < 12) continue;
    const w = 9 + R() * 5, d = 7 + R() * 3, h = 4 + R() * 2.5;
    const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), lam(wall[(R() * 4) | 0])); b.position.set(x, h / 2 + Y, z); b.rotation.y = R() * 3;
    const rf = new THREE.Mesh(new THREE.CylinderGeometry(0, d * 0.78, 2.6, 4), lam(roof[(R() * 3) | 0])); rf.rotation.y = Math.PI / 4 + b.rotation.y; rf.scale.set(w / d * 1.0, 1, 1);
    rf.position.set(x, h + 1.3 + Y, z); g.add(b, rf);
  }
  scene.add(g);
  g.updateMatrixWorld(true);
  scene.fog = new THREE.Fog(HAZE, FOG_NEAR, FOG_FAR);         // existing scene has fog disabled above: untouched
  scene.background = new THREE.Color(HAZE);
  return g;
}

// Mesh colours of the backdrop (for the no-red/blue test); the sky is a gradient shader, not a person-sized object.
export function exteriorColors(g) {
  const out = [];
  g.traverse((o) => { if (o.isMesh && o.material.color) out.push(o.material.color.getHex()); });
  return out;
}
