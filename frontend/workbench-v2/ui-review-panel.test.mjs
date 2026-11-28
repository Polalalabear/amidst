import test from 'node:test';
import assert from 'node:assert/strict';
import {decisionRows, reviewSummary, mountReviewPanel} from './ui-review-panel.mjs';

const resp = {
  output_sha256: 'h', provenance: {producer: 'p', gt_read: false, parameter_mode: 'DEMO_DEFAULT', formal_eligible: false},
  agent: {switch_mode: 'AGENT_SEQUENTIAL', available: true, decisions: 1, adopted: 0, fallbacks: 1, agent_used: false},
  sightings: [{track_ref: 'T2', observation_ids: ['o1', 'o2']}],
  association_audit: [
    {reason: 'AGENT_SERVICE_DECISION', timestamp_us: 2_000_000, from_camera_id: 'A', to_camera_id: 'B', to_track_ref: 'T2', decision_source: 'RULE_FALLBACK',
     fallback_reason: 'ROUND_LIMIT', candidate_tracks: ['T2', 'T3'], answer: {answer: 'SELECT', camera_id: 'B', reason_codes: ['X']}, gt_actor: 'SECRET', identity_verdict: 'UNCONFIRMED'},
    {reason: 'DEMO_ASSOCIATION_HYPOTHESIS', timestamp_us: 1_000_000, from_camera_id: 'A', to_camera_id: 'B', evidence_state: 'INFERRED', confidence: 'LOW'},
  ],
};

test('rows are oldest first and copy only the response values; GT-looking keys are never shown', () => {
  const rows = decisionRows(resp);
  assert.deepEqual(rows.map(r => r.timestamp_us), [1_000_000, 2_000_000]);
  const agent = rows[1];
  assert.equal(agent.fields.find(f => f.key === 'fallback_reason').value, 'ROUND_LIMIT');
  assert.equal(agent.fields.find(f => f.key === 'answer.reason_codes').value, '["X"]');
  assert.equal(JSON.stringify(rows).includes('SECRET'), false);
  assert.deepEqual(agent.evidence, {count: 2, first: 'o1', last: 'o2'});
});

test('a field the response does not carry is UNKNOWN, never invented', () => {
  const rule = decisionRows(resp)[0];
  assert.equal(rule.hasMissing, true);
  assert.equal(rule.evidence.count, 0);
  assert.equal(reviewSummary({}).gt_read, 'UNKNOWN');
  assert.equal(reviewSummary(resp).agent.fallbacks, '1');
  assert.deepEqual(decisionRows(null), []);
});

test('nothing is mounted outside review mode', () => {
  let appended = 0;
  const mounted = mountReviewPanel({doc: {createElement() { throw new Error('no DOM expected'); }}, host: {append() { appended++; }}, store: {getState: () => ({reviewMode: false}), subscribe() { throw new Error('no subscribe'); }}, onSeek() {}});
  assert.equal(appended, 0); mounted.destroy();
});
