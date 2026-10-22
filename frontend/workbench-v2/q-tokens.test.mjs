import test from 'node:test';import assert from 'node:assert/strict';
import {Q_STATES,Q_DECIDERS,Q_LEGEND} from './q-tokens.mjs';
test('execution states and deciders stay monochrome; evidence distinctions keep line patterns',()=>{
 assert.deepEqual(Object.keys(Q_STATES),['PLAYING','TEMP_LOST','SEARCHING','SWITCHING','RETURNED_TO_ORIGIN','ENDED']);
 assert.ok(Object.values(Q_STATES).every(x=>x.color==='--ink'&&Object.isFrozen(x)));
 assert.deepEqual(Object.keys(Q_DECIDERS),['AGENT','RULE_ONLY','RULE_FALLBACK','USER']);
 assert.equal(new Set(Q_LEGEND.map(x=>x.code)).size,4);assert.equal(new Set(Q_LEGEND.map(x=>x.line)).size,4);
});

test('recorded/live synthetic and pilot sources keep a visible exclusion marker',async()=>{
 const {sourcePresentation}=await import('./q-tokens.mjs');
 assert.equal(sourcePresentation('LIVE','SYNTHETIC').visible,true);
 assert.match(sourcePresentation('RECORDED','SYNTHETIC').label,/SYNTHETIC/);
 assert.match(sourcePresentation('RECORDED','ACTUAL_BLENDER_PILOT').label,/PILOT/);
 assert.equal(sourcePresentation('LIVE','ACTUAL_BLENDER').visible,false);
});
