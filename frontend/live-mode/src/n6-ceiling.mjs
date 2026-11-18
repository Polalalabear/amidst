// The ceiling shares the unlit baked atlas with the walls and floor. Compress
// contrast only on the ceiling to soften baked tile boundaries and highlights.
export function softenBakedCeiling(scene) {
  const ceiling = scene.getObjectByName('CEILING_STATIC_LIVE');
  ceiling?.traverse(mesh => {
    if (!mesh.isMesh || !mesh.material.isMeshBasicMaterial || !mesh.material.map) return;

    const material = mesh.material.clone();
    material.onBeforeCompile = shader => {
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <map_fragment>',
        `#include <map_fragment>
        diffuseColor.rgb = mix(vec3(0.18, 0.175, 0.16), diffuseColor.rgb, 0.22);`,
      );
    };
    mesh.material = material;
  });
}
