// SOURCE integers are authoritative. Wall clocks are declared demo clocks only.
import { contentHash,integer,freezeDeep,parseRaw,canonicalJSON } from './q-validate.mjs';
const check=(v,code)=>{if(!v)throw new Error(code);};
export function wallUs(literal) {
  const match=typeof literal==='string'&&literal.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?(Z|[+-]\d{2}:\d{2})$/);
  check(match,'TIME_LITERAL_INVALID');const [,ys,mos,ds,hs,mis,ss='0',fraction='',zone]=match;
  const [year,month,day,hour,minute,second]=[ys,mos,ds,hs,mis,ss].map(Number);
  check(year>=1&&month>=1&&month<=12&&day>=1&&day<=31&&hour<24&&minute<60&&second<60,'TIME_LITERAL_INVALID');
  const date=new Date(0);date.setUTCFullYear(year,month-1,day);date.setUTCHours(hour,minute,second,0);
  check(date.getUTCFullYear()===year&&date.getUTCMonth()===month-1&&date.getUTCDate()===day,'TIME_LITERAL_INVALID');
  const offset=zone==='Z'?0:(zone[0]==='-'?-1:1)*(Number(zone.slice(1,3))*60+Number(zone.slice(4,6)));
  check(zone==='Z'||(Number(zone.slice(1,3))<24&&Number(zone.slice(4,6))<60),'TIME_LITERAL_INVALID');
  return BigInt(date.getTime()-offset*60000)*1000n+BigInt(fraction.padEnd(6,'0'));
}
function msFloor(us){let q=us/1000n;if(us<0n&&us%1000n)q--;return Number(q);}
export async function validateClock(input) {
  try {
    const mapping=typeof input==='string'?parseRaw(input):parseRaw(canonicalJSON(input));
    check(mapping?.schema_version==='q-demo.clock-mapping.v1'&&mapping.mapping_kind==='DECLARED_DEMO_CLOCK'&&mapping.rate===1,'CLOCK_SCHEMA');
    for(const field of ['run_id','clock_id','timezone','wall_origin','mapping_version','declaration_source','declared_by','declared_at'])check(typeof mapping[field]==='string'&&mapping[field],'CLOCK_DECLARATION_MISSING');
    check(integer(mapping.t0_us)&&integer(mapping.source_duration_us)&&mapping.t0_us<mapping.source_duration_us,'CLOCK_RANGE');
    const origin=wallUs(mapping.wall_origin);wallUs(mapping.declared_at);
    const fields=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:mapping.timezone,calendar:'iso8601',numberingSystem:'latn',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(msFloor(origin))).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
    const local=mapping.wall_origin.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?/)[0];
    const declared=local.length===16?local+':00':local;
    check(`${fields.year.padStart(4,'0')}-${fields.month}-${fields.day}T${fields.hour}:${fields.minute}:${fields.second}`===declared,'CLOCK_OFFSET_MISMATCH');
    check(await contentHash(mapping,{excludeRoot:['content_sha256']})===mapping.content_sha256,'CLOCK_HASH_MISMATCH');
    return {ok:true,data:freezeDeep(mapping)};
  } catch(error){return {ok:false,error:{code:error.message}};}
}
export function sourceToWallUs(sourceUs,mapping) {
  check(integer(sourceUs),'SOURCE_INTEGER_REQUIRED');return wallUs(mapping.wall_origin)+BigInt(sourceUs-mapping.t0_us);
}
export function wallToSourceUs(literal,mapping) {
  const delta=wallUs(literal)-wallUs(mapping.wall_origin)+BigInt(mapping.t0_us);
  check(delta>=BigInt(Number.MIN_SAFE_INTEGER)&&delta<=BigInt(Number.MAX_SAFE_INTEGER),'SOURCE_PRECISION_UNSAFE');return Number(delta);
}
export const inside=(t,span)=>integer(t)&&Array.isArray(span)&&span[0]<=t&&t<span[1];
export function stepUs(t,interval,direction,duration) {
  check(integer(t)&&integer(interval)&&interval>0&&integer(duration)&&duration>0&&[-1,1].includes(direction),'SOURCE_GRID_REQUIRED');
  return Math.max(0,Math.min(Math.floor((duration-1)/interval)*interval,(Math.floor(t/interval)+direction)*interval));
}
export function advanceUs(t,deltaMs,speed,duration,carry=0) {
  check(integer(t)&&Number.isFinite(deltaMs)&&deltaMs>=0&&[.5,1,2].includes(speed)&&integer(duration)&&Number.isFinite(carry)&&carry>=0,'PLAYBACK_CLOCK_INVALID');
  const amount=deltaMs*1000*speed+carry;const whole=Math.floor(amount);
  return {tUs:Math.min(duration,t+whole),carry:amount-whole,ended:t+whole>=duration};
}
export function formatSource(t){check(integer(t),'SOURCE_INTEGER_REQUIRED');return `${Math.floor(t/1000000)}.${String(t%1000000).padStart(6,'0')} s`;}
export function displayClock(t,mapping) {
  if(!mapping)return 'UNKNOWN · CLOCK_MAPPING_MISSING';
  try {
    const us=sourceToWallUs(t,mapping);return new Intl.DateTimeFormat('zh-TW',{timeZone:mapping.timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(msFloor(us)))+' · 展示時鐘';
  } catch {return 'UNKNOWN · CLOCK_MAPPING_INVALID';}
}
