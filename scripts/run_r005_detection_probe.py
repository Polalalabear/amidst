"""Run the bounded #464 LOCAL probe with explicit inputs."""
import argparse
from pathlib import Path
from amidst.q1q5.r005_detection_probe import run_probe

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--receipt', type=Path, required=True)
parser.add_argument('--model-config', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
report = run_probe(args.source_root, args.receipt, args.model_config, args.output)
for row in report['rows']:
    top = max(row['shown'], key=lambda x: x['score']) if row['shown'] else None
    print(row['camera_id'], row['shown_count'],
          (top['class_label'], top['score'], top['bbox_xyxy_px']) if top else 'NOT_DETECTED')
