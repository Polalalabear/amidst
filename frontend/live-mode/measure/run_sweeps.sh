#!/bin/zsh
# Detection-rate matrix. Server must be running (mps). Output dir: $OUT
cd "$(dirname $0)/.."
export OUT=${OUT:-out}
for cfg in "capsule 320 180" "glb 320 180" "capsule 480 270" "glb 480 270" "capsule 640 360" "glb 640 360"; do
  set -- ${=cfg}
  node measure/detect_sweep.mjs ${1}_${2}x${3} $1 $2 $3 1.0 0,90,180,270 2>&1 | grep -v "404"
done
