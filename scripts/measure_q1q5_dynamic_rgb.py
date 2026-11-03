"""Pixel-motion evidence only; no producer, routes, actor labels or expected answers."""

import argparse
import hashlib
import io
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from amidst.q1q5.baseline_runner import save
from amidst.q1q5.linked_runtime import load_rgb


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rgb", type=Path, required=True)
    p.add_argument("--rgb-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run = load_rgb(a.rgb, a.rgb_sha256)
    results = {}
    for camera in sorted(run.camera_ids):
        previous, unique, rows = None, set(), []
        for frame in range(run.manifest["sampling"]["sample_count_per_camera"]):
            raw = run.read_rgb(camera, frame)
            with Image.open(io.BytesIO(raw)) as opened:
                image = opened.convert("RGB")
            unique.add(hashlib.sha256(image.tobytes()).hexdigest())
            delta = (
                ImageStat.Stat(ImageChops.difference(image, previous)).mean if previous else None
            )
            # A color-pixel measurement, explicitly not a detector or human annotation.
            points = [
                (i % image.width, i // image.width)
                for i, (r, g, b) in enumerate(image.getdata())
                if r > 100 and r > 2 * g and r > 2 * b
            ]
            rows.append(
                dict(
                    frame_index=frame,
                    timestamp_s=frame / 20,
                    mean_absolute_rgb_change_255=None if delta is None else sum(delta) / 3,
                    red_pixel_count=len(points),
                    red_pixel_centroid_px=None
                    if len(points) < 40
                    else [
                        sum(v[0] for v in points) / len(points),
                        sum(v[1] for v in points) / len(points),
                    ],
                )
            )
            previous = image
        visible = [r for r in rows if r["red_pixel_centroid_px"]]
        results[camera] = dict(
            frames=len(rows),
            unique_pixel_frames=len(unique),
            changed_adjacent_frames=sum(
                r["mean_absolute_rgb_change_255"] is not None
                and r["mean_absolute_rgb_change_255"] > 0
                for r in rows
            ),
            red_pixel_source_range_s=None
            if not visible
            else [visible[0]["timestamp_s"], visible[-1]["timestamp_s"]],
            red_centroid_x_span_px=None
            if not visible
            else max(r["red_pixel_centroid_px"][0] for r in visible)
            - min(r["red_pixel_centroid_px"][0] for r in visible),
            per_frame=rows,
        )
    save(
        a.output,
        dict(
            schema_version="q-demo.dynamic-pixel-evidence.v1",
            source_rgb_file_sha256=a.rgb_sha256,
            source_sampling_fps=20,
            duration_s=8,
            gt_read=False,
            producer_read=False,
            correctness=None,
            identity_verdict="UNCONFIRMED",
            interpretation="COLOR_PIXEL_MOTION_ONLY_NOT_GROUND_TRUTH_OR_DETECTION",
            cameras=results,
        ),
    )


if __name__ == "__main__":
    main()
