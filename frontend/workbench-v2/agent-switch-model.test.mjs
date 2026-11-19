import test from 'node:test';
import assert from 'node:assert/strict';
import {agentSwitchView} from './agent-switch-model.mjs';

test('Agent available: both modes selectable, follows the requested mode', () => {
  const run = {agent_available: true};
  assert.deepEqual([agentSwitchView(run, 'RULE_ONLY').effective, agentSwitchView(run, 'AGENT_SEQUENTIAL').effective], ['RULE_ONLY', 'AGENT_SEQUENTIAL']);
  assert.equal(agentSwitchView(run).agentEnabled, true);
});
test('gateway offline: Agent disabled, reason shown, always rule', () => {
  const v = agentSwitchView({agent_available: false, agent_unavailable_reason: 'GATEWAY_OFFLINE'}, 'AGENT_SEQUENTIAL');
  assert.equal(v.agentEnabled, false); assert.equal(v.effective, 'RULE_ONLY');
  assert.match(v.agentLabel, /不可用/); assert.match(v.note, /OpenAI gateway 沒有在執行/);
});
test('B-05: no decision point is 不適用, not an error', () => {
  const v = agentSwitchView({agent_available: false, agent_unavailable_reason: 'NOT_APPLICABLE_NO_DECIDER'});
  assert.match(v.agentLabel, /不適用/); assert.match(v.note, /此事件沒有 Agent 決策點/); assert.doesNotMatch(v.note, /不可用/);
});
test('no run loaded', () => { assert.equal(agentSwitchView(null).note, '尚未載入來源'); });
