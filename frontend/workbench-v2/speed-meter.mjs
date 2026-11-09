// 實際倍速量測（只讀、只影響播放列小字）。實際倍速 = 視窗內「來源時間前進量 ÷ 牆鐘經過量」。
// 解碼跟不上設定值時，播放本來就是等影格就緒才前進（不跳格、不卡頓），所以來源時間自然降到能達到的速度；這裡只把實際值顯示出來。
// 標籤與演示時間不受影響：它們只由來源時間算出。
export const WINDOW_MS=2000,MIN_SPAN_MS=500,MAX_STEP_US=500000;
export function createSpeedMeter({windowMs=WINDOW_MS,minSpanMs=MIN_SPAN_MS,maxStepUs=MAX_STEP_US}={}){
  let samples=[];
  return {
    reset(){samples=[];},
    // A jump larger than one playback step (a seek) or a step backwards restarts the window instead of faking a speed.
    record(sourceUs,nowMs){
      if(!Number.isFinite(sourceUs)||!Number.isFinite(nowMs))return;
      const last=samples.at(-1);
      if(last&&(sourceUs<last.us||sourceUs-last.us>maxStepUs||nowMs<last.ms))samples=[];
      samples.push({us:sourceUs,ms:nowMs});
      while(samples.length>2&&nowMs-samples[0].ms>windowMs)samples.shift();
    },
    // With nowMs the window ends now, so a stall (no new frame) lowers the figure instead of leaving a stale one.
    actual(nowMs=null){
      if(samples.length<2)return null;
      const live=Number.isFinite(nowMs)?samples.filter(x=>nowMs-x.ms<=windowMs):samples;
      if(live.length<1)return null;
      const a=live[0],b=samples.at(-1),end=Number.isFinite(nowMs)?Math.max(nowMs,b.ms):b.ms,span=end-a.ms;
      return span>=minSpanMs&&b.us>=a.us&&b!==a?(b.us-a.us)/1000/span:(span>=minSpanMs&&b===a?0:null);
    },
  };
}
const x=n=>`${Math.round(n*10)/10}×`;
export function formatSpeedNote(setting,actual){
  return Number.isFinite(actual)?`設定 ${x(setting)} · 實際 ${x(actual)}`:`設定 ${x(setting)}`;
}
