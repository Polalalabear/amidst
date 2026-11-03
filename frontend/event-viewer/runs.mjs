// 預期的 safe 結構，取自 docs/engineering/R004_EVENT_RUNS_RECEIPT.md（#394）。
// safe 區沒有 manifest／clock，故以此表為唯一預期；與磁碟不符即 UNAVAILABLE。
export const FPS = 5;
export const FRAME_WIDTH = 960;
export const FRAME_HEIGHT = 540;

export const RUNS = Object.freeze([
  Object.freeze({
    key: 'A4-1',
    label: 'A4-1（複雜事件，4 鏡頭）',
    runId: 'ctrl-lcorr-s1-a4-5fps-v1-r004',
    frames: 250,
    cameras: Object.freeze(['CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_ENTRY', 'CAM_W1']),
  }),
  Object.freeze({
    key: 'B4-1',
    label: 'B4-1（複雜事件，5 鏡頭）',
    runId: 'ctrl-lcorr-s1-b4-5fps-v1-r004',
    frames: 210,
    cameras: Object.freeze(['CAM_W1', 'CAM_W2', 'CAM_BRANCH', 'CAM_R101_IN', 'CAM_WIDE']),
  }),
]);
