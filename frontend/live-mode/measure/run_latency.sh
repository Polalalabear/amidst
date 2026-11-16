#!/bin/zsh
# Latency matrix; server must already run with the wanted device. $DEV labels the output.
cd "$(dirname $0)/.."
export OUT=${OUT:-out}; D=${DEV:-mps}
B="auto=B4&duration=42&model=glb"
node measure/latency.mjs ${D}_8cam_320_5fps "$B&w=320&h=180&fps=5" 50 | cut -c1-400
node measure/latency.mjs ${D}_3cam_320_5fps "$B&w=320&h=180&fps=5&cams=CAM_W1,CAM_W2,CAM_R101_IN" 50 | cut -c1-400
node measure/latency.mjs ${D}_8cam_320_2fps "$B&w=320&h=180&fps=2" 50 | cut -c1-400
node measure/latency.mjs ${D}_8cam_640_5fps "$B&w=640&h=360&fps=5" 50 | cut -c1-400
node measure/latency.mjs ${D}_3cam_640_5fps "$B&w=640&h=360&fps=5&cams=CAM_W1,CAM_W2,CAM_R101_IN" 50 | cut -c1-400
