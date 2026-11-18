// 2026-11-17: live-mode entry (default 127.0.0.1:8791, overridable; disabled with a reason when unreachable).
import test from 'node:test';
import assert from 'node:assert/strict';
import {LIVE_DEFAULT_BASE, LIVE_BASE_KEY, normalizeLiveBase, resolveLiveBase, liveUrls, probeLive, liveEntryView} from './live-entry.mjs';

const store = v => ({getItem: k => (k === LIVE_BASE_KEY ? v : null)});

test('base: ?live= wins, then localStorage, then 127.0.0.1:8791; only http(s) origins', () => {
  assert.equal(resolveLiveBase({}), LIVE_DEFAULT_BASE);
  assert.equal(resolveLiveBase({storage: store('http://10.0.0.5:9000/x')}), 'http://10.0.0.5:9000');
  assert.equal(resolveLiveBase({pageUrl: 'http://127.0.0.1:8785/workbench-v2/admin.html?live=http://localhost:8800', storage: store('http://10.0.0.5:9000')}), 'http://localhost:8800');
  assert.equal(resolveLiveBase({pageUrl: 'http://x/admin.html?live=javascript:alert(1)'}), LIVE_DEFAULT_BASE);
  // #578 P3-1: ?live= takes loopback hosts only; a remote host needs the explicit localStorage setting
  assert.equal(resolveLiveBase({pageUrl: 'http://x/admin.html?live=http://evil.example:9000', storage: null}), LIVE_DEFAULT_BASE);
  assert.equal(resolveLiveBase({pageUrl: 'http://x/admin.html?live=http://[::1]:8800'}), 'http://[::1]:8800');
  assert.equal(normalizeLiveBase('http://10.0.0.5:9000'), null); assert.equal(normalizeLiveBase('http://10.0.0.5:9000', {allowRemote: true}), 'http://10.0.0.5:9000');
  assert.equal(liveUrls('http://10.0.0.5:9000').base, 'http://10.0.0.5:9000');   // a base the user set in storage stays usable
  assert.equal(normalizeLiveBase('ftp://a'), null); assert.equal(normalizeLiveBase(''), null);
  assert.equal(resolveLiveBase({storage: {getItem() { throw new Error('blocked'); }}}), LIVE_DEFAULT_BASE);
});

test('urls: operator and system pages of the live server', () => {
  assert.deepEqual(liveUrls('http://127.0.0.1:8791'), {base: 'http://127.0.0.1:8791', operator: 'http://127.0.0.1:8791/?role=operator', system: 'http://127.0.0.1:8791/?role=system'});
});

test('probe: reachable → available; refused or slow → unavailable with a reason; no body, no credentials', async () => {
  const seen = [];
  assert.deepEqual(await probeLive('http://127.0.0.1:8791', {fetchImpl: async (u, o) => { seen.push([u, o]); return {type: 'opaque'}; }}), {available: true, reason: null});
  assert.deepEqual(seen[0], ['http://127.0.0.1:8791/config', {mode: 'no-cors', cache: 'no-store', credentials: 'omit'}]);
  assert.deepEqual(await probeLive('http://127.0.0.1:8791', {fetchImpl: async () => { throw new TypeError('Failed to fetch'); }}), {available: false, reason: 'UNREACHABLE'});
  assert.deepEqual(await probeLive('http://127.0.0.1:8791', {fetchImpl: () => new Promise(() => {}), timeoutMs: 5}), {available: false, reason: 'TIMEOUT'});
});

test('view: buttons disabled while checking or unreachable, with the reason in words', () => {
  assert.equal(liveEntryView({checking: true, base: LIVE_DEFAULT_BASE}).disabled, true);
  const off = liveEntryView({checking: false, available: false, base: LIVE_DEFAULT_BASE});
  assert.equal(off.disabled, true); assert.match(off.text, /未啟動.*127\.0\.0\.1:8791/);
  assert.equal(liveEntryView({checking: false, available: true, base: LIVE_DEFAULT_BASE}).disabled, false);
});
