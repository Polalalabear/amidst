// Compare every saved as-of response to the independently delivered #410 consumer.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const options=Object.fromEntries(process.argv.slice(2).map(s=>s.replace(/^--/,'').split('=',2)));
assert.ok(options.source&&options.output,'explicit clean #452 source and output directory required');
const requiredHead='088252833665a4bca9fcfbf31597b4bb296fb549';
assert.equal(execFileSync('git',['rev-parse','HEAD'],{cwd:options.source,encoding:'utf8'}).trim(),requiredHead);
assert.equal(execFileSync('git',['status','--porcelain'],{cwd:options.source,encoding:'utf8'}).trim(),'');
const {singleViewSequence}=await import(pathToFileURL(path.join(options.source,'frontend/workbench-v2/core-search-track-model.mjs')));
const {contentHash}=await import(pathToFileURL(path.join(options.source,'frontend/workbench-v2/q-validate.mjs')));
let checked=0;const runs=[];
for(const label of ['A4-1','B4-1']){
  const root=path.join(options.output,label),receipt=JSON.parse(await readFile(path.join(root,'receipt.json'),'utf8'));
  for(const [name,pin] of Object.entries(receipt.files)){
    const bytes=await readFile(path.join(root,name));
    assert.equal(bytes.length,pin.bytes);assert.equal(createHash('sha256').update(bytes).digest('hex'),pin.sha256);
  }
  const lines=(await readFile(path.join(root,'responses.jsonl'),'utf8')).trim().split('\n');
  for(const line of lines){
    const r=JSON.parse(line);
    assert.equal(r.schema_version,'q-core.track-response.v1');
    assert.deepEqual(r.single_view,singleViewSequence(r.sightings,{asOfUs:r.as_of_us}));
    assert.equal(r.output_sha256,await contentHash(r,{excludeRoot:['output_sha256','stats']}));
    assert.equal(r.identity_verdict,'UNCONFIRMED');assert.equal(r.physical_navigation,'UNKNOWN');
    assert.ok(r.sightings.every(s=>s.range_us[0]<r.as_of_us&&s.range_us[1]<=r.as_of_us));
    assert.ok(r.single_view.filter(s=>s.kind!=='ON_CAMERA').every(s=>s.camera_id===null&&s.evidence_state==='UNKNOWN'));
    checked++;
  }
  runs.push({label,as_of_responses:lines.length});
}
console.log(JSON.stringify({status:'PASS',source_head:requiredHead,checked_as_of_responses:checked,runs},null,2));
