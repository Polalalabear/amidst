// Official Khronos structural validation plus this delivery's material/data gates.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const options=Object.fromEntries(process.argv.slice(2).reduce((a,v,i,all)=>i%2===0?[...a,[v.replace(/^--/,''),all[i+1]]]:a,[]));
const validator=(await import(pathToFileURL(path.join(options.runtime,'node_modules/gltf-validator/index.js')))).default;
const root=options.assets;
const reports={};
for(const name of ['character','scene']){
  const bytes=await fs.readFile(path.join(root,name+'.glb'));
  assert.equal(bytes.toString('ascii',0,4),'glTF');assert.equal(bytes.readUInt32LE(4),2);
  assert.equal(bytes.readUInt32LE(8),bytes.length);
  const size=bytes.readUInt32LE(12);const d=JSON.parse(bytes.toString('utf8',20,20+size));
  const bin=bytes.subarray(28+size);
  const result=await validator.validateBytes(new Uint8Array(bytes),{uri:name+'.glb',maxIssues:200});
  assert.equal(result.issues.numErrors,0,JSON.stringify(result.issues));
  assert.equal(result.issues.numWarnings,0,JSON.stringify(result.issues));
  const text=JSON.stringify(d);
  assert(!/trajectory|visibility|ground.?truth|waypoint|depth|actor_id|t_us|clock_id/i.test(text),'Forbidden producer data in glTF JSON');
  assert(!d.cameras && !d.extensions?.KHR_lights_punctual);
  if(name==='character'){
    assert(bytes.length<=20_000_000);
    assert.deepEqual(new Set(d.animations.map(a=>a.name)),new Set(['walk','run','idle']));
    assert.equal(d.skins.length,1);assert.equal(d.skins[0].joints.length,17);
    assert.deepEqual(d.extensions.KHR_materials_variants.variants.map(v=>v.name),['T','A','B','C']);
    const material=n=>d.materials.find(m=>m.name===n).pbrMetallicRoughness.baseColorFactor;
    assert.deepEqual(material('T_PRODUCTION_P1_R004_SHIRT'),material('A_PRODUCTION_P1_R004_SHIRT'));
    for(const [n,expected] of [['B',[.65,.1976,.1625,1]],['C',[.1625,.299,.65,1]]]){
      material(n+'_PRODUCTION_P1_R004_SHIRT').forEach((v,i)=>assert(Math.abs(v-expected[i])<1e-6));
    }
    for(const mesh of d.meshes)for(const p of mesh.primitives){
      assert(p.attributes.JOINTS_0!==undefined && p.attributes.WEIGHTS_0!==undefined);
      assert.equal(p.extensions.KHR_materials_variants.mappings.length,4);
    }
  }else{
    assert(bytes.length<=150_000_000);assert(!d.animations && !d.skins);
    assert.equal(d.meshes.length,15);
    assert(d.nodes.every(n=>n.mesh===undefined||n.extras?.n6Collider===true));
    assert(d.materials.every(m=>m.extensions.KHR_materials_unlit));
    for(const mesh of d.meshes)for(const p of mesh.primitives)assert(p.attributes.TEXCOORD_1!==undefined);
    const view=d.bufferViews[d.asset.extras.n6Lighting.linearIrradiance.bufferView];
    const embedded=bin.subarray(view.byteOffset,view.byteOffset+view.byteLength);
    const original=await fs.readFile(path.join(root,'lightmap_irradiance.exr'));
    assert.deepEqual(crypto.createHash('sha256').update(embedded).digest(),crypto.createHash('sha256').update(original).digest());
  }
  reports[name]=result;
}
const viewer=JSON.parse(await fs.readFile(path.join(root,'verification/VIEWER_REPORT.json')));
assert.equal(viewer.cameras.length,8);assert.equal(viewer.page_errors.length,0);
for(const [name,m] of Object.entries(viewer.clips)){
  assert(m.seam_matrix_error<1e-5);
  assert(m.support_slip_m_s<.015,JSON.stringify({name,...m}));
  assert(m.min_ankle_minus_shoe_height_m>-.0001,JSON.stringify({name,...m}));
  if(name!=='idle')assert(m.articulated_rotation>.1);
}
assert.equal(viewer.irradiance.width,4096);assert.equal(viewer.irradiance.height,4096);
await fs.writeFile(path.join(root,'verification/GLTF_VALIDATION.json'),JSON.stringify(reports,null,2)+'\n');
console.log(JSON.stringify(Object.fromEntries(Object.entries(reports).map(([name,r])=>[name,{errors:r.issues.numErrors,warnings:r.issues.numWarnings,infos:r.issues.numInfos}]))));
