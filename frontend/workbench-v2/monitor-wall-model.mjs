// L2-3 monitor wall: pure state/layout for up to 8 cameras on one shared clock. Missing fields stay UNKNOWN; nothing is inferred.
import {clipSegments} from './timeline-model.mjs';
export const WALL_MAX=8;
export function wallLayout(n){need(Number.isInteger(n)&&n>=0&&n<=WALL_MAX,'WALL_COUNT');if(n<=1)return {cols:1,rows:1};if(n<=2)return {cols:2,rows:1};if(n<=4)return {cols:2,rows:2};if(n<=6)return {cols:3,rows:2};return {cols:4,rows:2};}
function need(ok,code){if(!ok)throw new Error(code);}
export const STATES=['OBSERVED','GAP','MISSING','UNKNOWN'];
// Per camera: segments [{range_us,state}] with half-open ranges. Time outside every segment => UNKNOWN (no coverage declared), never OBSERVED.
export function stateAt(segments,t){const s=(segments??[]).find(x=>x.range_us[0]<=t&&t<x.range_us[1]);return s?{state:STATES.includes(s.state)?s.state:'UNKNOWN',segment:s}:{state:'UNKNOWN',segment:null};}
export function wallCells(cameras,t){
  need(cameras.length<=WALL_MAX,'WALL_COUNT');
  return cameras.map(c=>{const {state,segment}=stateAt(c.segments,t);return {camera_id:c.camera_id,state,label:LABEL[state],segment_range_us:segment?.range_us??null};});
}
const LABEL={OBSERVED:'OBS · 有觀測',GAP:'GAP · 觀測缺失',MISSING:'MISSING · 無資料',UNKNOWN:'UNKNOWN · 無覆蓋宣告'};
export function summary(cells){const c=Object.fromEntries(STATES.map(s=>[s,0]));for(const x of cells)c[x.state]++;return c;}
// Per-camera lanes on the zoomable axis. Long Q1 clips (matched segments) are drawn above the state strip and aligned by SOURCE time.
export function lanes(cameras,q1ByCamera,view){
  return cameras.map(c=>({camera_id:c.camera_id,states:clipSegments((c.segments??[]).map(s=>({...s,id:`${c.camera_id}:${s.range_us[0]}`})),view),
    q1:clipSegments((q1ByCamera[c.camera_id]??[]).map(s=>({...s,id:`q1:${c.camera_id}:${s.range_us[0]}`})),view)}));
}
// Convert a Q1 response (results[].matched_segments[]) to per-camera clip lists; keeps only declared fields.
export function q1Clips(response){const out={};for(const r of response?.results??[])out[r.camera_id]=(r.matched_segments??[]).map(s=>({range_us:s.range_us,matched_frames:s.matched_frames,evaluated_frames:s.evaluated_frames}));return out;}
export function longestClips(q1ByCamera,minUs){return Object.entries(q1ByCamera).flatMap(([camera_id,l])=>l.filter(s=>s.range_us[1]-s.range_us[0]>=minUs).map(s=>({camera_id,range_us:s.range_us}))).sort((a,b)=>a.range_us[0]-b.range_us[0]||a.camera_id.localeCompare(b.camera_id));}
