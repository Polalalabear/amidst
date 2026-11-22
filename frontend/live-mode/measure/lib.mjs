import puppeteer from 'puppeteer-core';
import {headlessMode} from '../../../scripts/browser_options.mjs';
export const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
export const BASE = process.env.LIVE_BASE || 'http://127.0.0.1:8791';
export async function launch(extra = []) {
  return puppeteer.launch({
    executablePath: CHROME, headless: headlessMode(), protocolTimeout: 3_600_000,
    args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--no-first-run',
      '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
      '--disable-backgrounding-occluded-windows', ...extra],
    defaultViewport: { width: 1280, height: 720 },
  });
}
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export function pct(a, p) {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  const i = (s.length - 1) * p, lo = Math.floor(i), hi = Math.ceil(i);
  return s[lo] + (s[hi] - s[lo]) * (i - lo);
}
