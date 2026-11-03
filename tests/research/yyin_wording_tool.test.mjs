// 題集工具.html 的核心邏輯測試（CSV 解析／匯出／檢查／草稿）。
// 執行：node --test tests/research/yyin_wording_tool.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const pack = join(here, '..', '..', 'docs', 'research', 'handoff', 'yyin_q1q3_wording_v1');
const html = readFileSync(join(pack, '題集工具.html'), 'utf8');
const templateText = readFileSync(join(pack, '題集模板.csv'), 'utf8');

const core = html.split('// ==CORE-START==')[1].split('// ==CORE-END==')[0];
const T = new Function(core + `; return { BOM, parseCsv, csvEscape, toCsv, toCsvFile, parseTable, headerName, headerOptions,
  colOf, getv, setv, isNum, fmtSec, exportFilename, dateStamp, splitCams, joinCams, isStarted, rowIssues, rowStatus, validate,
  serializeDraft, parseDraft, mergeDraft, addCRow, VIDEOS, LOCKED };`)();

const tpl = T.parseTable(templateText);
const fresh = () => tpl.rows.map(r => ({ ...r }));
const embedded = html.match(/<script type="text\/plain" id="templateCsv">([\s\S]*?)<\/script>/)[1];

function fill(rows, id, vals) {
  const r = rows.find(x => x[T.colOf(tpl.header, '編號')] === id);
  for (const [k, v] of Object.entries(vals)) T.setv(tpl.header, r, k, v);
  return r;
}
const good = { 使用者會說的話: '有人經過外面的時候', 想找什麼: '人', 場景: 'A4-1', 時間窗開始: '18.0', 時間窗結束: '23.4', 預期鏡頭: 'CAM_ENTRY;CAM_W1', 系統該反問嗎: '否', 預期結果: '找得到', 看不清或不確定: '否' };

test('內嵌的模板和 題集模板.csv 完全一致', () => {
  assert.equal(embedded.trim(), templateText.replace(/^﻿/, '').replace(/\r\n/g, '\n').trim());
});

test('模板：header 16 欄、90 列，三組各 30 列', () => {
  assert.equal(tpl.header.length, 16);
  assert.equal(tpl.rows.length, 90);
  for (const g of ['E1', 'E2', 'E3']) assert.equal(tpl.rows.filter(r => T.getv(tpl.header, r, '事件組') === g).length, 30);
});

test('parseCsv：逗號、雙引號、換行、CRLF、BOM、中文', () => {
  const text = '﻿a,b,c\r\n"x,y","he said ""hi""","line1\nline2"\r\n中文,,末尾';
  assert.deepEqual(T.parseCsv(text), [['a', 'b', 'c'], ['x,y', 'he said "hi"', 'line1\nline2'], ['中文', '', '末尾']]);
  assert.deepEqual(T.parseCsv('a,b\n'), [['a', 'b']]);
  assert.deepEqual(T.parseCsv('"",x\n'), [['', 'x']]);
});

test('csvEscape：只在需要時加引號', () => {
  assert.equal(T.csvEscape('abc'), 'abc');
  assert.equal(T.csvEscape('中文句子'), '中文句子');
  assert.equal(T.csvEscape('a,b'), '"a,b"');
  assert.equal(T.csvEscape('a"b'), '"a""b"');
  assert.equal(T.csvEscape('a\nb'), '"a\nb"');
  assert.equal(T.csvEscape('a\rb'), '"a\rb"');
  assert.equal(T.csvEscape(undefined), '');
});

test('toCsv 與 parseTable 來回不變（含中文、逗號、換行、引號）', () => {
  const rows = fresh();
  fill(rows, 'E1-F01-P', { 使用者會說的話: '有人經過「走廊,轉角」嗎？\n第二行 "引用"', 備註: '逗號,和\r\n換行', 預期鏡頭: 'CAM_ENTRY;CAM_W1' });
  const text = T.toCsvFile(tpl.header, rows);
  assert.ok(text.startsWith('﻿'));
  const back = T.parseTable(text);
  assert.deepEqual(back.header, tpl.header);
  assert.deepEqual(back.rows, rows);
});

test('匯出位元組以 UTF-8 BOM 開頭、欄位順序和模板相同', () => {
  const bytes = Buffer.from(T.toCsvFile(tpl.header, fresh()), 'utf8');
  assert.deepEqual([...bytes.subarray(0, 3)], [0xEF, 0xBB, 0xBF]);
  const first = bytes.toString('utf8').slice(1).split('\r\n')[0];
  assert.equal(first, templateText.replace(/^﻿/, '').split('\n')[0]);
  // 空白匯出和模板內容等價
  assert.deepEqual(T.parseTable(bytes.toString('utf8')).rows, tpl.rows);
});

test('headerName / headerOptions 從欄名動態取得選項', () => {
  assert.equal(T.headerName('時間窗開始(秒)'), '時間窗開始');
  assert.equal(T.headerName('編號'), '編號');
  assert.deepEqual(T.headerOptions('想找什麼(人/車/相機)'), ['人', '車', '相機']);
  assert.deepEqual(T.headerOptions('預期結果(找得到/找不到/不支援/超出時間/反問)'), ['找得到', '找不到', '不支援', '超出時間', '反問']);
  assert.equal(T.headerOptions('時間窗開始(秒)'), null);
  assert.equal(T.headerOptions('備註'), null);
});

test('檔名格式', () => {
  assert.equal(T.exportFilename(new Date(2026, 10, 3)), '題集_yyin_2026-11-03.csv');
  assert.equal(T.exportFilename(new Date(2026, 0, 9)), '題集_yyin_2026-01-09.csv');
});

test('檢查：空白模板沒有逐列錯誤，只有「尚未開始」提示', () => {
  const r = T.validate(tpl.header, fresh(), T.VIDEOS);
  assert.equal(r.issues.filter(i => i.level !== 'info').length, 0);
  assert.equal(r.unstarted.length, 30);
});

test('檢查：必填、時間窗、片長、鏡頭', () => {
  const rows = fresh();
  fill(rows, 'E1-F01-P', { 使用者會說的話: '有人經過轉角嗎' });
  let r = T.validate(tpl.header, rows, T.VIDEOS);
  const msgs = r.issues.filter(i => i.rowId === 'E1-F01-P').map(i => i.msg).join('\n');
  for (const n of ['想找什麼', '場景', '時間窗開始', '時間窗結束', '系統該反問嗎', '預期結果', '看不清或不確定']) assert.ok(msgs.includes(n), n);

  fill(rows, 'E1-F01-P', { ...good, 時間窗開始: '30', 時間窗結束: '20' });
  assert.ok(T.rowIssues(tpl.header, rows.find(x => x['編號'] === 'E1-F01-P'), T.VIDEOS).some(i => i.msg.includes('必須小於')));
  fill(rows, 'E1-F01-P', { ...good, 時間窗開始: '45', 時間窗結束: '51' });
  assert.ok(T.rowIssues(tpl.header, rows.find(x => x['編號'] === 'E1-F01-P'), T.VIDEOS).some(i => i.msg.includes('片長 50')));
  fill(rows, 'E1-F01-P', { ...good, 場景: 'P1', 時間窗開始: '1', 時間窗結束: '9' });
  assert.ok(T.rowIssues(tpl.header, rows.find(x => x['編號'] === 'E1-F01-P'), T.VIDEOS).some(i => i.msg.includes('片長 8')));
  fill(rows, 'E1-F01-P', { ...good, 時間窗開始: '1:30', 時間窗結束: '2.5' });
  assert.ok(T.rowIssues(tpl.header, rows.find(x => x['編號'] === 'E1-F01-P'), T.VIDEOS).some(i => i.msg.includes('不是數字')));
  fill(rows, 'E1-F01-P', { ...good, 預期鏡頭: 'CAM_BRANCH' });
  assert.ok(T.rowIssues(tpl.header, rows.find(x => x['編號'] === 'E1-F01-P'), T.VIDEOS).some(i => i.msg.includes('不屬於 A4-1')));
  fill(rows, 'E1-F01-P', { ...good });
  assert.deepEqual(T.rowIssues(tpl.header, rows.find(x => x['編號'] === 'E1-F01-P'), T.VIDEOS), []);
  assert.equal(T.rowStatus(tpl.header, rows.find(x => x['編號'] === 'E1-F01-P'), T.VIDEOS), 'done');
});

test('檢查：時間窗結束剛好等於片長可以', () => {
  const rows = fresh();
  fill(rows, 'E1-F01-P', { ...good, 時間窗開始: '0', 時間窗結束: '50.0' });
  assert.deepEqual(T.rowIssues(tpl.header, rows[0], T.VIDEOS), []);
});

test('檢查：題族缺 P／V／T 要列出，三句都有就算完成', () => {
  const rows = fresh();
  fill(rows, 'E1-F01-P', good);
  let r = T.validate(tpl.header, rows, T.VIDEOS);
  const miss = r.issues.filter(i => i.msg.includes('E1-F01') && i.msg.includes('缺'));
  assert.deepEqual(miss.map(i => i.msg.match(/缺 (\w)/)[1]).sort(), ['T', 'V']);
  assert.equal(r.summary.E1.started, 1);
  assert.equal(r.summary.E1.complete, 0);
  fill(rows, 'E1-F01-V', { ...good, 使用者會說的話: '外面有人走過嗎' });
  fill(rows, 'E1-F01-T', { ...good, 使用者會說的話: '開始後約 20 秒有人走過去' });
  r = T.validate(tpl.header, rows, T.VIDEOS);
  assert.equal(r.issues.filter(i => i.level !== 'info').length, 0);
  assert.equal(r.summary.E1.complete, 1);
});

test('檢查：同題族時間窗不一致、反問矛盾、不確定缺備註、禁止題型', () => {
  const rows = fresh();
  fill(rows, 'E1-F01-P', good);
  fill(rows, 'E1-F01-V', { ...good, 時間窗結束: '30', 使用者會說的話: '這個人是不是同一個人', 預期結果: '反問', 系統該反問嗎: '否', 看不清或不確定: '是' });
  const msgs = T.validate(tpl.header, rows, T.VIDEOS).issues.map(i => i.msg).join('\n');
  assert.ok(msgs.includes('不一致'));
  assert.ok(msgs.includes('預期結果是「反問」'));
  assert.ok(msgs.includes('請在備註寫原因'));
  assert.ok(msgs.includes('不支援問身分'));
});

test('預期鏡頭可以留空但要有備註', () => {
  const rows = fresh();
  fill(rows, 'E1-F01-P', { ...good, 預期鏡頭: '' });
  assert.ok(T.rowIssues(tpl.header, rows[0], T.VIDEOS).some(i => i.level === 'warn'));
  fill(rows, 'E1-F01-P', { 備註: '看不出哪台' });
  assert.equal(T.rowIssues(tpl.header, rows[0], T.VIDEOS).length, 0);
});

test('joinCams / splitCams 依鏡頭順序', () => {
  assert.equal(T.joinCams(['CAM_W1', 'CAM_ENTRY'], ['CAM_ENTRY', 'CAM_EXT_CAR', 'CAM_W1']), 'CAM_ENTRY;CAM_W1');
  assert.deepEqual(T.splitCams('CAM_ENTRY; CAM_W1；CAM_W2'), ['CAM_ENTRY', 'CAM_W1', 'CAM_W2']);
  assert.deepEqual(T.splitCams(''), []);
});

test('新增 C 類列：編號、插入位置、不重複', () => {
  const rows = fresh();
  const names = { E1: '經過某處', E2: '進出室內外', E3: '停留或折返' };
  const a = T.addCRow(tpl.header, rows, 'E1', 'E1-F01', names);
  assert.equal(a.created, true);
  assert.equal(a.rows.length, 91);
  assert.equal(a.rows[a.index]['編號'], 'E1-F01-C');
  assert.equal(a.rows[a.index - 1]['編號'], 'E1-F01-T');
  assert.equal(a.rows[a.index + 1]['編號'], 'E1-F02-P');
  assert.equal(T.getv(tpl.header, a.rows[a.index], '說法類型'), 'C');
  assert.equal(T.getv(tpl.header, a.rows[a.index], '事件類別'), '經過某處');
  assert.equal(T.getv(tpl.header, a.rows[a.index], '題族編號'), 'E1-F01');
  const b = T.addCRow(tpl.header, a.rows, 'E1', 'E1-F01', names);
  assert.equal(b.created, false);
  assert.equal(b.rows.length, 91);
  assert.throws(() => T.addCRow(tpl.header, rows, 'E1', 'E1-F99', names));
});

test('草稿：序列化後可還原，C 類列也在；欄位不符或格式錯誤會拒絕', () => {
  const rows = fresh();
  fill(rows, 'E2-F03-V', { ...good, 使用者會說的話: '有人從外面,進來嗎\n再問一次' });
  const names = { E1: 'x', E2: '進出室內外', E3: 'y' };
  const added = T.addCRow(tpl.header, rows, 'E2', 'E2-F03', names);
  T.setv(tpl.header, added.rows[added.index], '使用者會說的話', '開始後 15 秒，有人走進入口');
  const json = T.serializeDraft(tpl.header, added.rows, new Date('2026-11-03T00:00:00Z'));
  const back = T.parseDraft(json, tpl.header, tpl.rows);
  assert.deepEqual(back, added.rows);
  assert.throws(() => T.parseDraft('not json', tpl.header, tpl.rows), /JSON/);
  assert.throws(() => T.parseDraft('{"schema":"x"}', tpl.header, tpl.rows), /schema/);
  const bad = JSON.parse(json); bad.header = bad.header.slice(1);
  assert.throws(() => T.parseDraft(JSON.stringify(bad), tpl.header, tpl.rows), /欄位/);
});

test('草稿：鎖定欄位以模板為準，缺的模板列補回', () => {
  const rows = fresh().slice(0, 5);
  rows[0]['事件類別'] = '被亂改';
  rows[0]['使用者會說的話'] = '保留這句';
  const json = T.serializeDraft(tpl.header, rows);
  const back = T.parseDraft(json, tpl.header, tpl.rows);
  assert.equal(back.length, 90);
  assert.equal(back[0]['事件類別'], '經過某處');
  assert.equal(back[0]['使用者會說的話'], '保留這句');
});

test('影片清單的片長、fps 與 README 一致', () => {
  const readme = readFileSync(join(pack, 'README.md'), 'utf8');
  assert.ok(readme.includes('| A4-1 | 50 秒 |') && readme.includes('| B4-1 | 42 秒 |') && readme.includes('| P1 | 8 秒 |'));
  const by = s => T.VIDEOS.filter(v => v.scene === s);
  assert.deepEqual(by('A4-1').map(v => v.camera), ['CAM_ENTRY', 'CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_W1']);
  assert.deepEqual(by('B4-1').map(v => v.camera), ['CAM_BRANCH', 'CAM_R101_IN', 'CAM_W1', 'CAM_W2', 'CAM_WIDE']);
  assert.deepEqual(by('P1').map(v => v.camera), ['A', 'B']);
  assert.ok(by('A4-1').every(v => v.fps === 5 && v.duration === 50));
  assert.ok(by('P1').every(v => v.fps === 20 && v.duration === 8));
});

test('工具不含外部網路資源，也不含 GT／劇本／路線字樣', () => {
  assert.equal(/https?:\/\//.test(html.replace(/<[^>]*>/g, '')), false);
  assert.equal(/<(script|link|img)[^>]+(src|href)=["']https?:/i.test(html), false);
  assert.equal(/ground[_ ]?truth|visibility|depth/i.test(html), false);
});
