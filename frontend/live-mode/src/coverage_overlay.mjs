// F2 (#656): 3D overlay of camera icons, wall-clipped FOV floor polygons and blind cells for the A operator view only.
// The group is hidden by default; makeOperatorView shows it inside the operator render and hides it again (finally)
// before any virtual camera capture, so detector frames never contain it.
import * as THREE from 'three';

export const OVERLAY_NAME = 'OPERATOR_OVERLAY_LIVE';
const Z = 0.04;   // just above the floor (world z up -> three y up, three z = -world y)

function label(text, color) {
  if (typeof document === 'undefined') return null;
  const c = document.createElement('canvas'); c.width = 256; c.height = 64;
  const g = c.getContext('2d'); g.fillStyle = 'rgba(17,17,17,.75)'; g.fillRect(0, 0, 256, 64);
  g.fillStyle = color; g.font = 'bold 34px sans-serif'; g.textBaseline = 'middle'; g.fillText(text, 12, 32);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({map: new THREE.CanvasTexture(c), depthTest: false}));
  s.scale.set(1.6, .4, 1); s.renderOrder = 12; return s;
}

export function buildCoverageOverlay(coverage, colors, {blindCell = .5} = {}) {
  const group = new THREE.Group(); group.name = OVERLAY_NAME; group.visible = false;
  for (const c of coverage.cameras) {
    const color = new THREE.Color(colors[c.camera_id]);
    if (c.polygon.length >= 3) {
      const shape = new THREE.Shape(c.polygon.map(([x, y]) => new THREE.Vector2(x, y)));
      const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape),
        new THREE.MeshBasicMaterial({color, transparent: true, opacity: .22, depthWrite: false, side: THREE.DoubleSide}));
      mesh.rotation.x = -Math.PI / 2; mesh.position.y = Z; mesh.renderOrder = 10; mesh.name = 'FOV_' + c.camera_id; group.add(mesh);
      const edge = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(c.polygon.map(([x, y]) => new THREE.Vector3(x, Z + .01, -y))),
        new THREE.LineBasicMaterial({color})); edge.renderOrder = 11; group.add(edge);
    }
    const {pos: [x, y, z], yaw} = c.pose;
    const icon = new THREE.Mesh(new THREE.ConeGeometry(.22, .5, 12), new THREE.MeshBasicMaterial({color, depthTest: false}));
    icon.name = 'ICON_' + c.camera_id; icon.position.set(x, z, -y); icon.rotation.set(0, 0, -Math.PI / 2); icon.rotation.y = yaw;   // cone tip along the camera yaw
    icon.renderOrder = 12; group.add(icon);
    const tag = label(c.camera_id.replace('CAM_', ''), colors[c.camera_id]);
    if (tag) { tag.position.set(x, z + .55, -y); group.add(tag); }
  }
  if (coverage.blind.length) {
    const geo = new THREE.PlaneGeometry(blindCell * .92, blindCell * .92); geo.rotateX(-Math.PI / 2);
    const blind = new THREE.InstancedMesh(geo, new THREE.MeshBasicMaterial({color: 0xdc2626, transparent: true, opacity: .3, depthWrite: false}), coverage.blind.length);
    const m = new THREE.Matrix4();
    coverage.blind.forEach(([x, y], i) => blind.setMatrixAt(i, m.makeTranslation(x, Z - .01, -y)));
    blind.name = 'BLIND_CELLS'; blind.renderOrder = 9; group.add(blind);
  }
  return group;
}
