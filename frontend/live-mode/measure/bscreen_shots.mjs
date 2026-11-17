// B 畫面截圖（工程驗證用）：開操作端跑自動路線，系統端（?role=system）在同一個瀏覽器；
// 當 HUD 狀態符合條件時截系統端畫面。只讀系統端 window.__hud（後台輸出推出來的顯示狀態），不讀操作端任何東西。
//   LIVE_BASE=http://127.0.0.1:8797 OUT=<資料夾> node measure/bscreen_shots.mjs "<操作端 query>" <秒數> <條件,條件,...> [檔名前綴]
// 條件：tracking | switch | lost | applied | none（回答都不是）| fallback | judging
import fs from 'node:fs';
import { launch, BASE, sleep } from './lib.mjs';
const [query, secs = '45', conds = 'tracking', prefix = ''] = process.argv.slice(2);
const out = process.env.OUT || 'out'; fs.mkdirSync(out, { recursive: true });
const want = new Set(conds.split(','));
const test = {
  tracking: (v) => v.track.kind === 'tracking' && v.cam && !v.switch,
  switch: (v) => !!v.switch,
  lost: (v) => v.track.kind === 'lost' && v.track.seconds >= 4,
  judging: (v) => v.track.kind === 'adjudicating' || v.status.text.startsWith('LLM 判斷中'),
  applied: (v) => v.decision && v.decision.applied && v.status.tone === 'llm',
  none: (v) => v.decision && v.decision.pick === '都不是' && v.status.tone === 'llm',
  fallback: (v) => v.source.tone === 'fallback' && v.status.tone === 'fallback',
};
const b = await launch(['--window-size=1600,900']);
const sys = await b.newPage(); await sys.setViewport({ width: 1600, height: 900 });
sys.on('pageerror', (e) => console.log('[sys err]', e.message));
await sys.goto(`${BASE}/?role=system`); await sys.waitForFunction('window.__ready === true');
const op = await b.newPage(); op.on('pageerror', (e) => console.log('[op err]', e.message));
await op.goto(`${BASE}/?${query}`); await op.waitForFunction('window.__ready === true', { timeout: 90000 });
const done = new Set(); const t0 = Date.now();
while (Date.now() - t0 < Number(secs) * 1000 && done.size < want.size) {
  const v = await sys.evaluate(() => window.__hud.view);
  if (v) for (const c of want) if (!done.has(c) && test[c](v)) {
    await sleep(250); // let the frame and HUD settle on the same tick
    const chk = await sys.evaluate(() => window.__hud.view); if (!chk || !test[c](chk)) continue; // state changed while settling
    const f = `${out}/${prefix}${c}.png`; await sys.screenshot({ path: f });
    const v2 = await sys.evaluate(() => window.__hud.view); fs.writeFileSync(f.replace('.png', '.json'), JSON.stringify(v2, null, 1));
    done.add(c); console.log('shot', c, ((Date.now() - t0) / 1000).toFixed(1) + 's');
  }
  await sleep(150);
}
const viol = await sys.evaluate(() => __log.violations.length);
console.log('done', [...done], 'missing', [...want].filter((c) => !done.has(c)), 'violations', viol);
await b.close();
