import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolveAlias,validateAliases,displayOptions,regionOptions,selectedRegionIds} from './query-alias-model.mjs';
import {buildSearchRequest} from './search-dialog-model.mjs';
const classes=JSON.parse(await readFile(new URL('../../configs/q1q5/class_alias_v1.json',import.meta.url),'utf8'));
const regions=JSON.parse(await readFile(new URL('../../configs/q1q5/query_alias_v1.json',import.meta.url),'utf8')).region_aliases;
test('all 80 classes have Chinese labels and unchanged canonical values',()=>{
  const options=displayOptions(classes.class_labels,classes.aliases);
  assert.equal(options.length,80);assert.ok(options.every(o=>/[\u3400-\u9fff]/u.test(o.label)));
  assert.equal(options.find(o=>o.value==='laptop').label,'筆電');
  assert.equal(resolveAlias('筆電',classes.aliases,classes.class_labels),'laptop');
});
test('explicit region spellings map only within selected source whitelist',()=>{
  for(const v of ['101教室','101 教室','R101','r101'])assert.equal(resolveAlias(v,regions,['R101'],{allowUnavailable:true}),'R101');
  assert.throws(()=>resolveAlias('101教室',regions,['OTHER'],{allowUnavailable:true}),/ALIAS_TARGET_UNKNOWN/);
  for(const v of ['不存在','101  教室',' 101教室'])assert.throws(()=>resolveAlias(v,regions,['R101'],{allowUnavailable:true}),/ALIAS_UNKNOWN/);
});
test('ambiguity, canonical remap and unknown targets fail closed',()=>{
  assert.throws(()=>validateAliases({X:'a',x:'b'},['a','b']),/ALIAS_CONFLICT/);
  assert.throws(()=>validateAliases({a:'b'},['a','b']),/ALIAS_CONFLICT/);
  assert.throws(()=>validateAliases({字:'c'},['a','b']),/ALIAS_TARGET_UNKNOWN/);
});
const scoped=()=>({scene_id:'SYN_SCENE',scene_revision:'rSYN',region_graph_sha256:'a'.repeat(64),region_catalog:{scene_id:'SYN_SCENE',scene_revision:'rSYN',region_graph_sha256:'a'.repeat(64),regions:[{region_id:'R101',label:'101教室'}]}});
test('missing and mismatched catalogs fail closed, no fabricated regions',()=>{
  assert.deepEqual(regionOptions({}),{status:'UNKNOWN',options:[]});
  assert.throws(()=>selectedRegionIds({},'R101'),/REGION_UNKNOWN/);
  for(const field of ['scene_id','scene_revision','region_graph_sha256']){const r=scoped();r.region_catalog[field]='OTHER';assert.throws(()=>regionOptions(r),/REGION_CATALOG_MISMATCH/);}
  const r=scoped();r.region_catalog.regions.push(r.region_catalog.regions[0]);assert.throws(()=>regionOptions(r),/REGION_CATALOG_INVALID/);
});
test('dialog submits canonical Q1 region_ids and refuses unknown or tracking region',async()=>{
  const wrapper=JSON.parse(await readFile(new URL('fixtures/q-bootstrap.json',import.meta.url),'utf8'));
  const run={...JSON.parse(wrapper.bootstrap_json).runs[0],...scoped()};
  const form={mode:'find',classLabel:'person',start:'0:00:00',end:'0:00:01',regionId:'R101'};
  assert.deepEqual(buildSearchRequest(run,'SYN_SESSION',form).region_ids,['R101']);
  assert.throws(()=>buildSearchRequest(run,'SYN_SESSION',{...form,regionId:'OTHER'}),/REGION_UNKNOWN/);
  assert.throws(()=>buildSearchRequest(run,'SYN_SESSION',{...form,mode:'track'}),/REGION_FIND_ONLY/);
});
