// F2 (#656): wall-clipped coverage from static geometry (coverage.mjs)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {wallsOf, isWall, rayHit, visibilityPolygon, pointInPolygon, polygonArea, coverageOf, seesPoint} from '../src/coverage.mjs';

const GEOM = JSON.parse(fs.readFileSync(new URL('../../../docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json', import.meta.url), 'utf8'));
const WALLS = wallsOf(GEOM);
const cam = id => GEOM.cameras.find(c => c.camera_id === id);

test('vehicles are not walls; every other clearance segment is', () => {
  assert.equal(isWall({collider: 'R004_ENV_CAR_1'}), false);
  assert.equal(isWall({collider: 'WALL_X'}), true);
  assert.equal(WALLS.length, GEOM.occluders_full_height.length);   // D346: occluders only
});

test('rayHit finds the nearest wall and ignores walls behind', () => {
  const walls = [[2, -1, 2, 1], [5, -1, 5, 1], [-1, -1, -1, 1]];
  assert.ok(Math.abs(rayHit(0, 0, 0, walls) - 2) < 1e-9);
  assert.equal(rayHit(0, 0, Math.PI / 2, walls), Infinity);
});

test('a wall in front of a camera clips its coverage', () => {
  for (const c of GEOM.cameras) {
    const open = visibilityPolygon(c, []), clipped = visibilityPolygon(c, WALLS);
    assert.ok(polygonArea(clipped.polygon) <= polygonArea(open.polygon) + 1e-6, c.camera_id);
  }
  const total = GEOM.cameras.reduce((s, c) => s + polygonArea(visibilityPolygon(c, WALLS).polygon), 0);
  const open = GEOM.cameras.reduce((s, c) => s + polygonArea(visibilityPolygon(c, []).polygon), 0);
  assert.ok(total < open, `walls must remove some area (${total.toFixed(1)} vs ${open.toFixed(1)})`);
});

test('every covered polygon vertex is seen by the camera and not behind a wall', () => {
  for (const c of GEOM.cameras) {
    const {polygon} = visibilityPolygon(c, WALLS), M = c.camera_to_world, o = [M[0][3], M[1][3]];
    for (const [x, y] of polygon) {
      assert.ok(seesPoint(c, x, y, 0.9), `${c.camera_id} ${x},${y}`);
      const d = Math.hypot(x - o[0], y - o[1]);
      assert.ok(rayHit(o[0], o[1], Math.atan2(y - o[1], x - o[0]), WALLS) >= d - 1e-9, `${c.camera_id} through wall`);
    }
  }
});

test('coverageOf limits cameras and reports blind floor cells outside every polygon', () => {
  const cov = coverageOf(GEOM, ['CAM_W1', 'CAM_W2']);
  assert.deepEqual(cov.cameras.map(c => c.camera_id).sort(), ['CAM_W1', 'CAM_W2']);
  for (const [x, y] of cov.blind) assert.ok(!cov.cameras.some(c => pointInPolygon(x, y, c.polygon)));
  const all = coverageOf(GEOM);
  assert.ok(all.blind.length < cov.blind.length, 'more cameras, fewer blind cells');
  assert.ok(cov.cameras.every(c => c.pose && Number.isFinite(c.pose.yaw)));
});

test('coverage uses static geometry only (no GT, people or renderer fields)', () => {
  const src = fs.readFileSync(new URL('../src/coverage.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(src, /ground_?truth|gt_visible|groundTruthVisible|trajector|depth_map|from ['"]three/i);
  assert.ok(cam('CAM_WIDE'));
});
