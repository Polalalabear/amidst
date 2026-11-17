import test from 'node:test';
import assert from 'node:assert/strict';
import { cameraStatus, MISSING_TEXT } from './sync.mjs';

test('a camera without footage is MISSING (無畫面), distinct from READY and PENDING', () => {
  assert.equal(cameraStatus(true), 'READY');
  assert.equal(cameraStatus(false), 'MISSING');
  assert.equal(cameraStatus(undefined), 'PENDING');
  assert.match(MISSING_TEXT, /無畫面/);
  assert.match(MISSING_TEXT, /MISSING/);
});
