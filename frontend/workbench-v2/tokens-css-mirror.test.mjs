import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8');
test('shared tokens: ui.css imports tokens.css and no longer declares them', () => {
  const ui = read('./ui.css'), tokens = read('./tokens.css');
  assert.match(ui, /^[^]*@import url\("tokens\.css"\);/);
  assert.ok(!ui.includes('--accent:#d97757'), 'tokens live only in tokens.css');
  assert.match(tokens, /#ui-v1,\.ui-admin-root,\.amidst-ui\{--bg:#141413/);
});
test('LIVE mode mirror stays byte-identical: it exists only for the frozen E3 recorder scripts/evaluation/e3_cases/record.mjs (SHA pinned in configs/evaluation/e3_reappearances_v1.json)', () => {
  assert.equal(read('../live-mode/src/tokens.css'), read('./tokens.css'));
});
test('non-frozen LIVE servers resolve /src/tokens.css to workbench-v2/tokens.css; only record.mjs still reads the mirror', () => {
  const targets = {
    'server.py': read('../../src/amidst/live_mode/server.py'),
    'ab_flow.test.mjs': read('../live-mode/test/ab_flow.test.mjs'),
    'ab_menu.test.mjs': read('../live-mode/test/ab_menu.test.mjs'),
    'n6_ceiling_compare.mjs': read('../live-mode/measure/n6_ceiling_compare.mjs'),
  };
  for (const [name, src] of Object.entries(targets)) assert.match(src, /workbench-v2/, `${name} must point at workbench-v2/tokens.css`);
  assert.match(targets['server.py'], /\/src\/tokens\.css/);
  // Any other script that routes /src/ requests to frontend/live-mode/src would serve the mirror.
  const walk = (dir) => readdirSync(new URL(dir, import.meta.url), {withFileTypes: true}).flatMap((e) =>
    e.name === 'node_modules' ? [] : e.isDirectory() ? walk(`${dir}${e.name}/`) : e.name.endsWith('.mjs') ? [`${dir}${e.name}`] : []);
  const routers = [...walk('../../scripts/'), ...walk('../live-mode/')]
    .filter((f) => /startsWith\(['"]\/src\/['"]\)|\^\\\/src\\\//.test(read(f)))
    .filter((f) => !/workbench-v2\/tokens\.css/.test(read(f)));
  assert.deepEqual(routers, ['../../scripts/evaluation/e3_cases/record.mjs']);
});
test('LIVE mode pages use the shared tokens and carry no copied token block or !important on tokens', () => {
  const html = read('../live-mode/index.html'), css = read('../live-mode/src/live.css');
  assert.match(html, /href="\/src\/tokens\.css"/); assert.match(html, /<body class="amidst-ui">/);
  assert.doesNotMatch(html + css, /--accent:#|--bg:#|--serif:'/);
});
