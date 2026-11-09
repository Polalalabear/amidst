import test from 'node:test';
import assert from 'node:assert/strict';
import {quantile, median, summarize, summarizeRows, toMarkdown} from './stats.mjs';

test('nearest-rank P90 matches D133 convention', () => {
  const v = Array.from({length: 30}, (_, i) => i + 1);          // 1..30
  assert.equal(quantile(v, 0.9), 27);                            // ceil(0.9*30)=27 -> 27th value
  assert.equal(quantile([5], 0.9), 5);
  assert.equal(quantile([], 0.9), null);
  assert.equal(quantile([3, 1, 2], 0.5), 2);
});
test('median averages the middle pair for even n', () => {
  assert.equal(median([4, 1, 3, 2]), 2.5);
  assert.equal(median([9, 1, 5]), 5);
  assert.equal(median([]), null);
});
test('summarize ignores non-finite values and does not mutate input', () => {
  const v = [30, 10, NaN, 20, undefined];
  const s = summarize(v);
  assert.deepEqual([s.n, s.min, s.p50, s.p90, s.max, s.mean], [3, 10, 20, 30, 30, 20]);
  assert.equal(v[0], 30);
  assert.equal(summarize([]).p50, null);
});
test('summarizeRows groups by metric and event, counts errors, pools ALL', () => {
  const rows = [
    {metric: 'switch', event: 'B-05', ms: 10}, {metric: 'switch', event: 'B-05', ms: 20},
    {metric: 'switch', event: 'A4-1', ms: 40}, {metric: 'switch', event: 'A4-1', error: 'TIMEOUT: x'},
    {metric: 'lock', event: 'B-05', ms: 100},
  ];
  const s = summarizeRows(rows);
  const get = (m, e) => s.find(x => x.metric === m && x.event === e);
  assert.equal(get('switch', 'B-05').p50, 15);
  assert.deepEqual([get('switch', 'A4-1').n, get('switch', 'A4-1').attempts, get('switch', 'A4-1').errors], [1, 2, 1]);
  assert.deepEqual([get('switch', 'ALL').n, get('switch', 'ALL').attempts, get('switch', 'ALL').max], [3, 4, 40]);
  assert.equal(get('lock', 'ALL').p90, 100);
});
test('other fields; missing field is excluded not zero', () => {
  const rows = [{metric: 'search', event: 'B-05', ms: 5, raf_ms: 20}, {metric: 'search', event: 'B-05', ms: 7, raf_ms: null}];
  assert.equal(summarizeRows(rows, 'raf_ms').find(x => x.event === 'B-05').n, 1);
});
test('markdown prints UNKNOWN for empty groups', () => {
  const md = toMarkdown(summarizeRows([{metric: 'lock', event: 'B-05', error: 'e'}]));
  assert.match(md, /UNKNOWN/);
  assert.match(md, /\| lock \| B-05 \| ms \| 0\/1 \| 1 \|/);
});
