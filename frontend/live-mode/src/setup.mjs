// Shared world setup for the operator and sweep pages: N6 baked scene + N6 cameras when the server has the
// assets (/config n6=true), otherwise the spike's extruded-wall scene and catalog cameras.
import { buildWorld, buildCameras } from './world.mjs';
import { buildN6Cameras, makeLoader } from './n6.mjs';

export async function setupWorld(P, { scenario = false } = {}) {
  const config = await fetch('/config').then((r) => r.json());
  const [geometry, scen] = await Promise.all([
    fetch('/data/geometry.json').then((r) => r.json()), scenario ? fetch('/data/scenario.json').then((r) => r.json()) : null]);
  const useN6 = config.n6 && P.scene !== 'spike';
  let sceneGltf = null, camJson = null;
  if (useN6) {
    [sceneGltf, camJson] = await Promise.all([makeLoader().loadAsync('/data/scene.glb'), fetch('/data/cameras.three.json').then((r) => r.json())]);
  }
  const world = buildWorld(geometry, { sceneGltf });
  const cams = useN6 ? buildN6Cameras(camJson, world.scene, P.w, P.h) : buildCameras(geometry, world.root, P.w, P.h);
  world.scene.updateMatrixWorld(true);
  // #602: decorative exterior (never a blocker); ?ext=0 turns it off for before/after comparisons.
  if (new URLSearchParams(location.search).get('ext') !== '0') addExterior(world.scene);
  return { config, geometry, scenario: scen, world, cams, n6: useN6 };
}

// (import kept below the function so it does not touch the import block that #599 edits)
import { addExterior } from './exterior.mjs';
