import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const src=readFileSync(new URL('search-dialog-view.mjs',import.meta.url),'utf8');
test('search dialog is selection-first: mode radios, class / colour / parser / start / end selects; typing is an optional aid',()=>{
  assert.match(src,/type='radio'/);
  for(const name of ['classes','colors','parser','startSel','endSel'])assert.match(src,new RegExp(`${name}=el\\('select'\\)|${name}=el\\('select'\\)|,${name}=el\\('select'\\)`),name);
  assert.match(src,/el\('details',undefined,'search-adv'\)/);                 // manual time entry is folded away
  assert.match(src,/特徵描述（輔助，選填/);                                       // free text is labelled as an aid
  assert.match(src,/startSel\.onchange=fromSel\(startSel,start\)/);             // the selects drive the same inputs the request is built from
  assert.doesNotMatch(src,/api\.(query|replay)/);                               // no backend contract here: the request still goes through execute()
});
