// Deterministic SYNTHETIC fixture for the L2-3 long timeline page. Not a real run; no GT, no media paths.
import {writeFileSync} from 'node:fs';
let seed=246;const rnd=()=>(seed=(seed*1103515245+12345)%2147483648)/2147483648;
const DURATION=3600e6,cams=Array.from({length:8},(_,i)=>`FIX_CAM_0${i+1}`);
const cameras=cams.map((camera_id,i)=>{const segments=[];let t=0;
  while(t<DURATION){const len=Math.round((30+rnd()*240)*1e6/1e6)*1e6;const blind=i===6&&t>=900e6&&t<1500e6;const cut=i===6?(t<900e6?900e6:t<1500e6?1500e6:DURATION):DURATION;const end=Math.min(cut,t+len);const r=rnd();
    segments.push({range_us:[t,end],state:blind?'MISSING':r<.55?'OBSERVED':r<.8?'GAP':r<.92?'UNKNOWN':'MISSING'});t=end;}
  return {camera_id,segments};});
const events=[];let n=0;for(const c of cameras)for(const s of c.segments){const kind=s.state==='OBSERVED'?'OBS_START':s.state==='GAP'?'GAP_START':null;if(kind&&s.range_us[0]>0)events.push({id:`ev${++n}`,t_us:s.range_us[0],kind,camera_id:c.camera_id,label:`${c.camera_id} ${kind==='OBS_START'?'觀測開始':'觀測缺失開始'}`});}
events.sort((a,b)=>a.t_us-b.t_us);
const q1=Object.fromEntries(cameras.slice(0,4).map(c=>[c.camera_id,c.segments.filter(s=>s.state==='OBSERVED'&&s.range_us[1]-s.range_us[0]>=120e6).map(s=>({range_us:s.range_us,matched_frames:Math.round((s.range_us[1]-s.range_us[0])/2e5*.9),evaluated_frames:Math.round((s.range_us[1]-s.range_us[0])/2e5)}))]));
writeFileSync(new URL('./long_timeline_synthetic.json',import.meta.url),JSON.stringify({SYNTHETIC:'SYNTHETIC UI test fixture — 合成資料，不代表任何真實 run；僅供 L2-3 長時間軸測試與驗收',fixture_marker:'FIXTURE',schema_version:'l2-3.long-timeline-fixture.v1',source_duration_us:DURATION,cameras,events,q1_clips:q1},null,1)+'\n');
