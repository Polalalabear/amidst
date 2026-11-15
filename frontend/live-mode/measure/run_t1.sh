#!/bin/zsh
# T1 runs (rule-only tracker, N6 character + baked scene, 320x180). Server on a non-8785 port; $LIVE_BASE points at it.
cd "$(dirname $0)/.."
export OUT=${OUT:-out}; REPS=${REPS:-3}; mkdir -p $OUT
C="model=glb&w=320&h=180"
for r in $(seq 1 $REPS); do
  node measure/t1_record.mjs b4_8cam_1fps_r$r "auto=B4&run=B4-1-v2-4actor&$C&fps=1" 41 2>&1 | grep -v 404
  node measure/t1_record.mjs a4_8cam_1fps_r$r "auto=A4&run=A4-1-v2-4actor&$C&fps=1" 49 2>&1 | grep -v 404
  node measure/t1_record.mjs b4_3cam_2fps_r$r "auto=B4&run=B4-1-v2-4actor&$C&fps=2&cams=CAM_W1,CAM_W2,CAM_R101_IN" 41 2>&1 | grep -v 404
  node measure/t1_record.mjs a4_4cam_2fps_r$r "auto=A4&run=A4-1-v2-4actor&$C&fps=2&cams=CAM_EXT_CAR,CAM_EXT_CLEAR,CAM_ENTRY,CAM_W1" 49 2>&1 | grep -v 404
done
echo T1_DONE
