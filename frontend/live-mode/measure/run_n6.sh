#!/bin/zsh
# N6 integration measurements (#539 -> live mode). Server must run (MPS) on a non-8785 port; $LIVE_BASE points at it.
# Same scripts as the spike; every configuration runs $REPS times (default 2). Logs machine load around each run.
cd "$(dirname $0)/.."
export OUT=${OUT:-out}; REPS=${REPS:-2}; mkdir -p $OUT
load() { echo "{\"t\":\"$(date +%H:%M:%S)\",\"load1\":$(sysctl -n vm.loadavg | awk '{print $2}'),\"gpu\":\"$(ioreg -r -d 1 -w0 -c IOAccelerator | grep -o '"Device Utilization %"=[0-9]*' | head -1)\"}"; }
for r in $(seq 1 $REPS); do
  for cfg in "glb 320 180 n6" "glb 320 180 spike" "capsule 320 180 n6"; do
    set -- ${=cfg}
    echo "LOAD_BEFORE $(load)" >> $OUT/load.log
    node measure/detect_sweep.mjs ${1}_${4}scene_${2}x${3}_r$r $1 $2 $3 1.0 0,90,180,270 $4 2>&1 | grep -v 404
    echo "LOAD_AFTER $(load)" >> $OUT/load.log
  done
done
B="auto=B4&duration=42&model=glb&w=320&h=180"
for r in $(seq 1 $REPS); do
  for cfg in "3cam_2fps fps=2&cams=CAM_W1,CAM_W2,CAM_R101_IN" "2cam_3fps fps=3&cams=CAM_W1,CAM_W2" "2cam_4fps fps=4&cams=CAM_W1,CAM_W2" "3cam_5fps fps=5&cams=CAM_W1,CAM_W2,CAM_R101_IN"; do
    set -- ${=cfg}
    echo "LOAD_BEFORE $(load)" >> $OUT/load.log
    node measure/latency.mjs n6_${1}_r$r "$B&$2" 50 | cut -c1-300
    echo "LOAD_AFTER $(load)" >> $OUT/load.log
  done
done
