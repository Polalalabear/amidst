// Live-mode spike: scene built from R004_SCENE_GEOMETRY_2D_V1.json (walls/screens extruded, floors,
// 8 virtual cameras from the catalog intrinsics/extrinsics). Blender Z-up world -> three Y-up by
// a single root rotation, so catalog camera_to_world matrices are used unchanged.
import * as THREE from 'three';

export const COLORS = {
  red: 0xc01818, orange: 0xd9420e, blue: 0x2547c8, trousers: 0x23262e, skin: 0xd9b08c,
};

export function buildWorld(geometry, opts = {}) {
  const root = new THREE.Group();
  root.rotation.x = -Math.PI / 2; // Blender (x,y,z) -> three (x,z,-y)
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xb8bec6);
  scene.add(root);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x777777, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(6, 12, 4);
  scene.add(sun);

  // floors
  const floorMat = new THREE.MeshLambertMaterial({ color: 0x8d949c });
  for (const f of geometry.floors) {
    const w = f.x_m[1] - f.x_m[0], d = f.y_m[1] - f.y_m[0];
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), floorMat);
    m.position.set((f.x_m[0] + f.x_m[1]) / 2, (f.y_m[0] + f.y_m[1]) / 2, f.top_z_m);
    root.add(m);
  }
  // walls: every clearance segment becomes a thin full-height slab (vehicle lower)
  const wallMat = new THREE.MeshLambertMaterial({ color: 0xe3e0d8 });
  const screenMat = new THREE.MeshLambertMaterial({ color: 0xa7b4a0 });
  const blockers = [];
  const wallMats = [wallMat, screenMat];
  for (const s of geometry.clearance_segments) {
    const [ax, ay] = s.a, [bx, by] = s.b;
    const len = Math.hypot(bx - ax, by - ay);
    if (len < 1e-4) continue;
    const isVeh = s.collider.startsWith('R004_ENV_');
    const h = isVeh ? 1.5 : 3.0;
    const mat = s.collider.startsWith('OBSTACLE') ? screenMat : wallMat;
    const m = new THREE.Mesh(new THREE.BoxGeometry(len, 0.06, h), mat);
    m.position.set((ax + bx) / 2, (ay + by) / 2, h / 2);
    m.rotation.z = Math.atan2(by - ay, bx - ax);
    root.add(m);
    blockers.push(m);
  }
  return { scene, root, blockers, segments: geometry.clearance_segments, wallMats };
}

// catalog camera -> three PerspectiveCamera at a chosen render size (principal point is centred in
// the catalog, so only fy matters for FOV; aspect stays 16:9).
export function buildCameras(geometry, root, width, height) {
  const cams = {};
  for (const c of geometry.cameras) {
    const fov = 2 * Math.atan(c.cy / c.fy) * 180 / Math.PI;
    const cam = new THREE.PerspectiveCamera(fov, width / height, c.clip_start, c.clip_end);
    const M = new THREE.Matrix4().set(...c.camera_to_world.flat());
    cam.matrixAutoUpdate = false;
    cam.matrix.copy(M);
    cam.matrixWorld.copy(M);
    root.add(cam);
    root.updateMatrixWorld(true);
    cams[c.camera_id] = { camera: cam, spec: c, width, height, scale: width / c.width };
  }
  return cams;
}

// simplified person: capsule torso (clothing colour), sphere head, dark legs. Foot anchor at origin.
export function buildCapsulePerson(color) {
  const g = new THREE.Group();
  const top = new THREE.MeshLambertMaterial({ color });
  const trs = new THREE.MeshLambertMaterial({ color: COLORS.trousers });
  const skin = new THREE.MeshLambertMaterial({ color: COLORS.skin });
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 0.42, 4, 10), top);
  torso.rotation.x = Math.PI / 2; torso.position.z = 1.17;
  const legs = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.13, 0.78, 10), trs);
  legs.rotation.x = Math.PI / 2; legs.position.z = 0.39;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 10), skin);
  head.position.z = 1.62;
  g.add(torso, legs, head);
  return g;
}

export function setPersonPose(obj, x, y, heading) {
  obj.position.set(x, y, 0);
  obj.rotation.z = heading;
}

// ground-truth visibility (evaluation only, never sent to the system window): a body point is
// "seen" by a camera when it projects inside the frame and a ray to the camera hits no wall.
export function groundTruthVisible(cams, blockers, root, x, y) {
  const THREE_ = THREE;
  const out = [];
  const ray = new THREE_.Raycaster();
  const pts = [[x, y, 0.15], [x, y, 0.9], [x, y, 1.6]];
  for (const [id, c] of Object.entries(cams)) {
    const cam = c.camera;
    let seen = 0;
    for (const p of pts) {
      const v = new THREE_.Vector3(...p).applyMatrix4(root.matrixWorld); // world (three)
      const ndc = v.clone().project(cam);
      if (ndc.z > 1 || Math.abs(ndc.x) > 1 || Math.abs(ndc.y) > 1) continue;
      const camPos = new THREE_.Vector3().setFromMatrixPosition(cam.matrixWorld);
      const dir = v.clone().sub(camPos); const dist = dir.length(); dir.normalize();
      ray.set(camPos, dir); ray.far = dist - 0.05;
      if (ray.intersectObjects(blockers, false).length === 0) seen++;
    }
    if (seen >= 2) out.push(id);
  }
  return out;
}
