// 預期的 safe 結構，取自 docs/engineering/R004_EVENT_RUNS_RECEIPT.md（#394）。
// safe 區沒有 manifest／clock，故以此表為唯一預期；與磁碟不符即 UNAVAILABLE。
export const FPS = 5;
export const FRAME_WIDTH = 960;
export const FRAME_HEIGHT = 540;

// 各 run 已宣告的展示時鐘，逐欄取自 configs/q1q5/clocks/r004_{a4,b4}_v1.json（viewer.test.mjs 逐欄比對）。
// 虛擬世界時間 = wall_origin + 來源時間（frame ÷ fps）；不是牆鐘、不是 GT 或渲染時間。
const declaredClock = (c) => Object.freeze(c);
export const RUNS = Object.freeze([
  Object.freeze({
    key: 'A4-1',
    label: 'A4-1（複雜事件，4 鏡頭）',
    runId: 'ctrl-lcorr-s1-a4-5fps-v1-r004',
    frames: 250,
    clock: declaredClock({ clock_id: 'clock:r004:a4:declared-demo:v1', mapping_kind: 'DECLARED_DEMO_CLOCK', timezone: 'Asia/Taipei', wall_origin: '2026-11-01T14:00:00+08:00', t0_us: 0, rate: 1 }),
    cameras: Object.freeze(['CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_ENTRY', 'CAM_W1']),
  }),
  Object.freeze({
    key: 'B4-1',
    label: 'B4-1（複雜事件，5 鏡頭）',
    runId: 'ctrl-lcorr-s1-b4-5fps-v1-r004',
    frames: 210,
    clock: declaredClock({ clock_id: 'clock:r004:b4:declared-demo:v1', mapping_kind: 'DECLARED_DEMO_CLOCK', timezone: 'Asia/Taipei', wall_origin: '2026-11-01T14:10:00+08:00', t0_us: 0, rate: 1 }),
    cameras: Object.freeze(['CAM_W1', 'CAM_W2', 'CAM_BRANCH', 'CAM_R101_IN', 'CAM_WIDE']),
  }),
]);
