// Statistics for measurement B. Same conventions as scripts/media_bench (D133): P90 = nearest rank
// (sorted[ceil(p*n)-1]); median of an even count = mean of the two middle values.
// CLI: node stats.mjs <export.json> [--out summary.json] [--field ms]   (prints a Markdown table)
import {readFileSync, writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';

export function quantile(values, p) {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  return s[Math.max(0, Math.ceil(p * s.length) - 1)];
}
export function median(values) {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b), i = Math.floor(s.length / 2);
  return s.length % 2 ? s[i] : (s[i - 1] + s[i]) / 2;
}
export function summarize(values) {
  const v = values.filter(x => Number.isFinite(x));
  if (!v.length) return {n: 0, min: null, p50: null, p90: null, max: null, mean: null};
  return {n: v.length, min: Math.min(...v), p50: median(v), p90: quantile(v, 0.9), max: Math.max(...v), mean: v.reduce((a, b) => a + b, 0) / v.length};
}
// rows: [{metric,event,error?,<field>}]; groups by metric then event ("ALL" = every event pooled). Rows with
// an error are counted, never silently dropped.
export function summarizeRows(rows, field = 'ms') {
  const out = [];
  for (const metric of [...new Set(rows.map(r => r.metric))]) {
    const mine = rows.filter(r => r.metric === metric);
    for (const event of [...new Set(mine.map(r => r.event)), 'ALL']) {
      const g = mine.filter(r => event === 'ALL' || r.event === event);
      const ok = g.filter(r => !r.error && Number.isFinite(r[field]));
      out.push({metric, event, field, attempts: g.length, errors: g.filter(r => r.error).length, ...summarize(ok.map(r => r[field]))});
    }
  }
  return out;
}
const f1 = x => x === null ? 'UNKNOWN' : x.toFixed(1);
export function toMarkdown(summary) {
  const head = '| metric | event | field | n | errors | min | P50 | P90 | max | mean |\n|---|---|---|--:|--:|--:|--:|--:|--:|--:|\n';
  return head + summary.map(s => `| ${s.metric} | ${s.event} | ${s.field} | ${s.n}/${s.attempts} | ${s.errors} | ${f1(s.min)} | ${f1(s.p50)} | ${f1(s.p90)} | ${f1(s.max)} | ${f1(s.mean)} |`).join('\n') + '\n';
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const args = process.argv.slice(2), file = args.find(a => !a.startsWith('--'));
  const opt = k => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : undefined; };
  if (!file) { console.error('usage: node stats.mjs <export.json> [--out summary.json] [--field ms|raf_ms|paint_ms]'); process.exit(2); }
  const doc = JSON.parse(readFileSync(file, 'utf8')), field = opt('field') ?? 'ms';
  const summary = summarizeRows(doc.rows, field);
  const hidden = doc.rows.filter(r => r.paneVisible === false).length;
  if (hidden) console.log(`WARNING: ${hidden} rows were taken with the browser pane hidden; paint timings are unreliable.\n`);
  console.log(toMarkdown(summary));
  if (opt('out')) writeFileSync(opt('out'), JSON.stringify({source: file, env: doc.env, field, summary}, null, 2));
}
