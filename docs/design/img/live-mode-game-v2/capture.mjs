// Screenshot a mockup page once it reports ready (document.title starts with "ready"), via Chrome's
// remote debugging protocol. No npm packages. Usage:
//   chrome --headless=new --remote-debugging-port=9333 ... &
//   node capture.mjs <url> <out.png> <width> <height> [port]
import { writeFileSync } from 'node:fs';
const [url, out, w, h, port = '9333'] = process.argv.slice(2);
const tab = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' }).then((r) => r.json());
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send('Emulation.setDeviceMetricsOverride', { width: +w, height: +h, deviceScaleFactor: 1, mobile: false });
await send('Runtime.enable'); await send('Log.enable');
let title = '';
for (let i = 0; i < 240; i++) {
  const r = await send('Runtime.evaluate', { expression: 'document.title', returnByValue: true });
  title = r.result.result.value || '';
  if (title.startsWith('ready') || title.startsWith('error')) break;
  await new Promise((r) => setTimeout(r, 500));
}
await new Promise((r) => setTimeout(r, 400));
const shot = await send('Page.captureScreenshot', { format: 'png' });
writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
console.log(out, title.slice(0, 400));
await fetch(`http://127.0.0.1:${port}/json/close/${tab.id}`);
ws.close();
