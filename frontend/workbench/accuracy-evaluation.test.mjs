import test from 'node:test';
import assert from 'node:assert/strict';
import {accuracyEvaluationHTML} from './accuracy-evaluation.mjs';

const row=(variant,recall,queries=8)=>({variant,mode:'photos_only',freeze_sha256:'a'.repeat(64),population:{measurement_count:150,track_count:18,segment_count:18,pair_count:115,eligible_pair_positives:15,eligible_queries:queries,candidate_pool_sha256:variant==='end_to_end'?'b'.repeat(64):'a'.repeat(64)},pixels:{id_switches:8,fragmented_tracks:0,contact_recall:.9,ground_rms_m:.305},association:{pair_precision:.35,pair_recall:.467,rank_recall_at_k:{'1':recall}},behavior:{unknown_count:7,per_kind:{CORNER:{true_positive:0,false_positive:2,false_negative:4,unresolved:1,precision:0,recall:0}}}});
const dto=()=>({schema_version:'workbench.accuracy-evaluation.v1',status:'CERTIFIED_LOCAL_SYNTHETIC',binding:{experiment_id:'frozen-v2',source_run_id:'synthetic-source'},modes:['photos_only'],variants:[row('baseline',.375),row('prior_only',.75),row('end_to_end',.625,16)],comparisons:[{mode:'photos_only',variant:'prior_only',population_comparable:true},{mode:'photos_only',variant:'end_to_end',population_comparable:false}],regressions:[],limitations:[]});

test('changed populations stay in the table but outside the comparison chart',()=>{
  const html=accuracyEvaluationHTML(dto()),chart=html.match(/<figure[\s\S]*?<\/figure>/)[0];
  assert.match(html,/母體改變，分開解讀/);
  assert.match(html,/16／15／115/);
  assert.match(chart,/時空先驗/);
  assert.doesNotMatch(chart,/v2 完整組合/);
  assert.match(html,/0／2／4/);
  assert.match(html,/v2 未定事件：7/);
});
test('missing metrics remain N/A and evidence text is escaped',()=>{
  const value=dto();value.binding.experiment_id='<img src=x onerror=alert(1)>';
  value.variants[2].pixels.ground_rms_m=null;value.variants[2].association.rank_recall_at_k={};
  const html=accuracyEvaluationHTML(value);
  assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img/);assert.match(html,/0\.900／N\/A/);
});
test('uncertified DTOs are refused and finite chart bounds are retained',()=>{
  assert.doesNotMatch(accuracyEvaluationHTML({...dto(),status:'STALE'}),/<table/);
  const value=dto();value.variants[1].association.rank_recall_at_k['1']=Infinity;
  assert.doesNotMatch(accuracyEvaluationHTML(value),/<meter/);
});
