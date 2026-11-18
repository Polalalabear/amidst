// #602: the exterior backdrop is decoration only. Walkable area, blockers and GT visibility must not change,
// and nothing in it may look like a red/blue person to the detector.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { addExterior, exteriorColors, FOG_FAR } from '../src/exterior.mjs';
import { buildWorld } from '../src/world.mjs';
import { blocked, stepPlayer } from '../src/sim.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const GEOM = JSON.parse(fs.readFileSync(path.join(here, '../../../docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'), 'utf8'));
const SEGS = GEOM.clearance_segments;

test('walkable area unchanged: points on every clearance segment stay blocked, stepping into a wall is refused', () => {
  const before = JSON.stringify(SEGS);
  const world = buildWorld(GEOM, {});
  addExterior(world.scene);
  assert.equal(JSON.stringify(world.segments), before, 'segments untouched');
  assert.equal(world.segments.length, SEGS.length);
  for (const s of SEGS) { // endpoints and midpoint of each wall segment
    for (const t of [0, 0.5, 1]) assert.ok(blocked(s.a[0] + (s.b[0] - s.a[0]) * t, s.a[1] + (s.b[1] - s.a[1]) * t, SEGS), `segment ${JSON.stringify(s)} @${t}`);
  }
  // a player walking into every wall segment from either side never ends up closer than the clearance radius
  for (const sg of SEGS) {
    const dx = sg.b[0] - sg.a[0], dy = sg.b[1] - sg.a[1], l = Math.hypot(dx, dy) || 1;
    const mx = (sg.a[0] + sg.b[0]) / 2, my = (sg.a[1] + sg.b[1]) / 2;
    for (const side of [1, -1]) {
      const nx = -dy / l * side, ny = dx / l * side;
      const p = { x: mx + nx * 0.6, y: my + ny * 0.6, heading: 0 };
      if (blocked(p.x, p.y, SEGS)) continue; // start itself inside another wall's clearance
      const keys = { d: nx < 0 && Math.abs(nx) > Math.abs(ny), a: nx > 0 && Math.abs(nx) > Math.abs(ny), w: ny < 0 && Math.abs(ny) >= Math.abs(nx), s: ny > 0 && Math.abs(ny) >= Math.abs(nx) };
      for (let i = 0; i < 200; i++) stepPlayer(p, keys, 0.05, SEGS);
      assert.ok(!blocked(p.x, p.y, SEGS), `player ended inside clearance at ${p.x.toFixed(2)},${p.y.toFixed(2)}`);
    }
  }
});

test('exterior adds no blockers and no collision data', () => {
  const world = buildWorld(GEOM, {});
  const nBlock = world.blockers.length, nRoot = world.root.children.length;
  const g = addExterior(world.scene);
  assert.equal(world.blockers.length, nBlock);
  assert.equal(world.root.children.length, nRoot, 'nothing added to the Z-up wall root');
  assert.equal(g.parent, world.scene);
  g.traverse((o) => assert.ok(!world.blockers.includes(o)));
});

test('exterior stays out of the yard footprint (x -15.2..-3.2, z -8..6) above the ground plane', () => {
  const g = addExterior(new THREE.Scene());
  g.updateMatrixWorld(true);
  const yard = new THREE.Box3(new THREE.Vector3(-15.2, -0.2, -8), new THREE.Vector3(-3.2, 10, 6));
  g.traverse((o) => {
    if (!o.isMesh || o.material.isShaderMaterial) return;
    const b = new THREE.Box3().setFromObject(o);
    if (b.max.y - b.min.y < 0.05) return; // flat ground decals / planes
    assert.ok(!b.intersectsBox(yard), `${o.geometry.type} at ${b.min.toArray()} intrudes into the yard`);
  });
});

test('no red or blue materials (person colours)', () => {
  const g = addExterior(new THREE.Scene());
  for (const hex of exteriorColors(g)) {
    const { h, s } = new THREE.Color(hex).getHSL({});
    const hue = h * 360;
    const redish = (hue < 20 || hue > 340) && s > 0.35;
    const blueish = hue > 190 && hue < 260 && s > 0.35;
    assert.ok(!redish && !blueish, `0x${hex.toString(16)} hue ${hue.toFixed(0)} sat ${s.toFixed(2)}`);
  }
});

test('fog fully hazes geometry before the N6 camera far plane (100 m)', () => {
  const scene = new THREE.Scene();
  addExterior(scene);
  assert.ok(scene.fog.far <= 100 && scene.fog.far === FOG_FAR);
});
