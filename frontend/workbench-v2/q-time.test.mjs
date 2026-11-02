import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parseRaw,contentHash } from './q-validate.mjs';
import { validateClock,wallUs,sourceToWallUs,wallToSourceUs,inside,stepUs,advanceUs,formatSource,displayClock } from './q-time.mjs';
const mapping=async()=>parseRaw(JSON.parse(await readFile(new URL('fixtures/q-bootstrap.json',import.meta.url),'utf8')).bootstrap_json).runs[0].clock_mapping;
const pin=async m=>({...m,content_sha256:await contentHash(m,{excludeRoot:['content_sha256']})});

test('declared timezone, hash and source offset validate; missing clocks stay UNKNOWN',async()=>{
 const m=await mapping();assert.equal((await validateClock(m)).ok,true);assert.equal(displayClock(0,null),'UNKNOWN · CLOCK_MAPPING_MISSING');
 const changed=await pin({...m,t0_us:200000});assert.equal((await validateClock(changed)).ok,true);
 assert.equal(sourceToWallUs(200001,changed),wallUs(m.wall_origin)+1n);
 assert.equal(wallToSourceUs('2026-11-01T13:00:00.000001+08:00',changed),200001);
 for(const patch of [{timezone:'Not/AZone'},{wall_origin:'2026-11-01T13:00:00+09:00'},{rate:2},{t0_us:-1}])assert.equal((await validateClock(await pin({...m,...patch}))).ok,false);
 assert.equal((await validateClock({...m,content_sha256:'0'.repeat(64)})).ok,false);
});

test('explicit DST fold offsets validate by instant; invalid wall dates fail',async()=>{
 const m=await mapping();for(const offset of ['+02:00','+01:00'])assert.equal((await validateClock(await pin({...m,timezone:'Europe/Zurich',wall_origin:'2026-10-25T02:30:00'+offset}))).ok,true);
 for(const literal of ['2026-02-30T13:00:00+08:00','2026-11-01T24:00:00+08:00','2026-11-01T13:00:00.0000001+08:00','13:00'])assert.throws(()=>wallUs(literal));
});

test('source half-open boundaries and index step use integers without wall clipping',()=>{
 assert.equal(inside(999999,[0,1000000]),true);assert.equal(inside(1000000,[0,1000000]),false);
 assert.equal(stepUs(1000000,200000,1,1000000),800000);assert.equal(stepUs(0,200000,-1,1000000),0);
 assert.equal(formatSource(1),'0.000001 s');const a=advanceUs(0,.0005,1,1000000);assert.equal(a.tUs,0);assert.equal(advanceUs(a.tUs,.0005,1,1000000,a.carry).tUs,1);
 assert.throws(()=>stepUs(.5,200000,1,1000000));
});
