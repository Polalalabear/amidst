import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';

// Every module the browser can load from app.mjs (static and dynamic relative imports, recursively)
// must be in the backend's static-asset allowlist, or the workbench stops at "loading" on a 403.
const here=new URL('./',import.meta.url);
const service=readFileSync(new URL('../../src/amidst/workbench/service.py',import.meta.url),'utf8');
const importPattern=/(?:\bfrom\s*|\bimport\s*\(?\s*)['"]\.\/([\w.-]+\.mjs)['"]/g;

function reachableModules(entry) {
  const seen=new Set(),queue=[entry];
  while(queue.length){
    const name=queue.pop();
    if(seen.has(name))continue;
    seen.add(name);
    if(!existsSync(new URL(name,here)))continue;
    const source=readFileSync(new URL(name,here),'utf8');
    for(const match of source.matchAll(importPattern))queue.push(match[1]);
  }
  return [...seen];
}

test('every module reachable from app.mjs is in the service.py static-asset allowlist',()=>{
  const modules=reachableModules('app.mjs');
  assert.ok(modules.includes('blind-hypothesis.mjs')&&modules.includes('scene.mjs'),'import walk found the expected modules');
  const missing=modules.filter(name=>!service.includes(`"/${name}"`));
  assert.deepEqual(missing,[],`missing from the service.py assets allowlist: ${missing.join(', ')}`);
});
