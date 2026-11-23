#!/usr/bin/env python3
"""F4 (#658, D350-3) GT proxy-box spot check, scoring side only (disclosure and sensitivity; never changes a verdict).

For a few decision points per family, draws the target's projected GT body box (0.5 x 0.5 x 1.75 m proxy, green) and every frozen
index detection (any class, score >= 0.3, yellow) on the camera frames where the GT says the target is visible, and measures the
best detection IoU and the centre offset (in GT-box heights). Output: <out>/spotcheck.json and <out>/sheet.png.
Reads GT boxes, so it must never be imported by inference code (it is not under src/).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def iou(a, b):
    ix, iy = max(0.0, min(a[2], b[2]) - max(a[0], b[0])), max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u > 0 else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--point', nargs=3, action='append', metavar=('ROOT', 'CASE', 'TICK'), required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows, tiles = [], []
    for root, case, tick in a.point:
        root, tick = Path(root), int(tick)
        gt = json.loads((root / 'gt-boxes' / f'{case}.a-log.json').read_text())
        t = next(x for x in gt['ticks'] if x['tick'] == tick)
        target = next(x for x in t['actors'] if x['id'] == 'T')
        m = json.loads((root / 'indexes' / case / 'detection_index.json').read_text())
        idx = {(r['camera_id'], r['frame_index']): r for r in map(json.loads, (root / 'indexes' / case / m['records_ref']).read_text().splitlines())}
        rgb = {(r['camera_id'], r['frame_index']): r for r in json.loads((root / 'rgb' / case / 'rgb_index.json').read_text())['records']}
        for cam in target['gt_visible']:
            body = target['gt_boxes'].get(cam)
            dets = [d for d in idx[(cam, tick)]['detections'] if d['score'] >= 0.3]
            best = max(dets, key=lambda d: iou(body, d['bbox_xyxy_px']), default=None) if body else None
            h = (body[3] - body[1]) if body else None
            off = None
            if best is not None and h:
                b = best['bbox_xyxy_px']
                off = round(((((b[0] + b[2]) - (body[0] + body[2])) / 2) ** 2 + (((b[1] + b[3]) - (body[1] + body[3])) / 2) ** 2) ** 0.5 / h, 3)
            others = [x for x in t['actors'] if x['id'] != 'T' and cam in x['gt_visible']]
            row = {'root': root.name, 'case_id': case, 'tick': tick, 'camera_id': cam, 'gt_box': body and [round(v, 1) for v in body],
                   'best_detection': best and {'class_label': best['class_label'], 'score': round(best['score'], 3), 'bbox': [round(v, 1) for v in best['bbox_xyxy_px']]},
                   'best_iou': round(iou(body, best['bbox_xyxy_px']), 3) if best else 0.0, 'centre_offset_gt_heights': off,
                   'other_people_visible_here': len(others)}
            rows.append(row)
            im = Image.open(root / rgb[(cam, tick)]['relative_path']).convert('RGB')
            d = ImageDraw.Draw(im)
            for x in dets:
                d.rectangle(x['bbox_xyxy_px'], outline=(255, 220, 0))
            if body:
                d.rectangle(body, outline=(0, 255, 0))
            d.text((3, 3), f"{case} t{tick} {cam} IoU {row['best_iou']}", fill=(255, 255, 255))
            tiles.append(im)
    (a.out / 'spotcheck.json').write_text(json.dumps(rows, indent=1))
    cols = 4
    sheet = Image.new('RGB', (320 * cols, 180 * ((len(tiles) + cols - 1) // cols)))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * 320, (i // cols) * 180))
    sheet.save(a.out / 'sheet.png')
    print(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main()
