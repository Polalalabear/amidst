// Pure helpers for the search dialog: human-readable H:MM:SS <-> source microseconds, and the request builder.
// The dialog never changes the backend API; it reuses the Q3 builders (textRequest / manualRequest).
import {manualRequest,textRequest} from './q3-bar-model.mjs';
import {virtualToSourceUs,virtualTime} from './q-time.mjs';

export const SEARCH_MODES=Object.freeze({find:{task:'q1',label:'查找',hint:'列出所有拍到目標的鏡頭'},track:{task:'q2',label:'追蹤',hint:'單一畫面，目標離開時自動切鏡'}});

const DIGITS=/^\d+$/;
// Accepts "S", "M:SS", "H:MM:SS", each with optional ".ffffff" on the last field. Returns integer µs or throws TIME_INVALID.
export function parseHms(text) {
  const raw=String(text??'').trim();if(!raw)throw new Error('TIME_INVALID');
  const parts=raw.split(':');if(parts.length>3)throw new Error('TIME_INVALID');
  const [secField,fracField='']=parts.at(-1).split('.');
  const head=parts.slice(0,-1);
  if(!DIGITS.test(secField)||head.some(p=>!DIGITS.test(p))||(fracField!==''&&!DIGITS.test(fracField))||fracField.length>6||parts.at(-1).split('.').length>2)throw new Error('TIME_INVALID');
  const nums=[...head.map(Number),Number(secField)];
  if(nums.length>1&&nums.at(-1)>=60)throw new Error('TIME_INVALID');
  if(nums.length===3&&nums[1]>=60)throw new Error('TIME_INVALID');
  const seconds=nums.reduce((total,n)=>total*60+n,0);
  const us=seconds*1000000+Number(fracField.padEnd(6,'0')||0);
  if(!Number.isSafeInteger(us))throw new Error('TIME_INVALID');return us;
}
// A search time is either the declared virtual-world time ("2026-11-01 13:00:08", converted with the run's declared clock) or elapsed source time (H:MM:SS).
// Both become the same integer source µs, so the request and the backend API are unchanged.
export function parseSearchTime(text,mapping) {
  const raw=String(text??'').trim();
  return /^\d{4}-\d{2}-\d{2}/.test(raw)?virtualToSourceUs(raw,mapping):parseHms(raw);
}
export function formatVirtualInput(us,mapping) {const v=virtualTime(us,mapping);return v?v.text.replace(/\.00$/,''):null;}
export function formatHms(us) {
  if(!Number.isSafeInteger(us)||us<0)throw new Error('TIME_INVALID');
  const total=Math.floor(us/1000000),frac=us%1000000,h=Math.floor(total/3600),m=Math.floor(total%3600/60),s=total%60;
  const base=`${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return frac?`${base}.${String(frac).padStart(6,'0').replace(/0+$/,'')}`:base;
}
// form: {mode, text, classLabel, colorLabel, start, end, parserMode}. Free text wins when present (Q3 parses it);
// otherwise the condition fields build a Q1/Q2 request. Throws on invalid input; nothing is executed here.
export function buildSearchRequest(run,session,form,switchMode='RULE_ONLY') {
  if(!run)throw new Error('SOURCE_REQUIRED');
  const mode=SEARCH_MODES[form.mode];if(!mode)throw new Error('MODE_REQUIRED');
  if((form.text??'').trim())return textRequest(run,session,form.text,form.parserMode??'RULE_ONLY');
  const startUs=parseSearchTime(form.start,run.clock_mapping),endUs=parseSearchTime(form.end,run.clock_mapping);
  if(endUs<=startUs)throw new Error('TIME_ORDER');
  return manualRequest(run,session,{task:mode.task,classLabel:form.classLabel,colorLabel:form.colorLabel??'',startUs,endUs,switchMode});
}
export const ERROR_TEXT=Object.freeze({TIME_INVALID:'時間格式需為演示時間（例如 2026-11-01 13:01:30）或經過時間 時:分:秒（例如 0:01:30）',TIME_ORDER:'結束時間必須晚於開始時間',SOURCE_REQUIRED:'尚無可用來源',MODE_REQUIRED:'請選擇追蹤或查找',UNSUPPORTED_CLASS:'不支援此類別',UNSUPPORTED_CONDITION:'不支援此條件組合',Q3_LLM_NOT_CONFIGURED:'Qwen3 解析尚未設定'});
