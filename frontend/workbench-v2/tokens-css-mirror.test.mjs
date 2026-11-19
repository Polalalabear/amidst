import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8');
test('shared tokens: ui.css imports tokens.css and no longer declares them', () => {
  const ui = read('./ui.css'), tokens = read('./tokens.css');
  assert.match(ui, /^[^]*@import url\("tokens\.css"\);/);
  assert.ok(!ui.includes('--accent:#d97757'), 'tokens live only in tokens.css');
  assert.match(tokens, /#ui-v1,\.ui-admin-root,\.amidst-ui\{--bg:#141413/);
});
test('LIVE mode mirror of tokens.css is byte-identical until the stage-2 server route replaces it', () => {
  assert.equal(read('../live-mode/src/tokens.css'), read('./tokens.css'));
});
test('LIVE mode pages use the shared tokens and carry no copied token block or !important on tokens', () => {
  const html = read('../live-mode/index.html'), css = read('../live-mode/src/live.css');
  assert.match(html, /href="\/src\/tokens\.css"/); assert.match(html, /<body class="amidst-ui">/);
  assert.doesNotMatch(html + css, /--accent:#|--bg:#|--serif:'/);
});
