"""Generate the SYNTHETIC CS-B review fixture (small PNGs + d47_screening.json).

Not real renders; no GT. Run: python tests/cs_b_review/make_fixture.py
"""

import hashlib
import json
import struct
import zlib
from pathlib import Path

W, H = 960, 540
RUN_ID = "SYNTHETIC-ctrl-run"
OUT = Path(__file__).parent / "fixtures" / RUN_ID


def png(frame_index: int, camera: int) -> bytes:
    bg = (30 + 40 * camera, 45, 60)
    x0 = 100 + 30 * frame_index
    rows = []
    for y in range(H):
        row = bytearray([0])
        for x in range(W):
            inside = x0 <= x < x0 + 60 and 200 <= y < 400
            row += bytes((230, 180, 90) if inside else bg)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main() -> None:
    (OUT / "safe_bundle").mkdir(parents=True, exist_ok=True)
    (OUT / "acceptance").mkdir(parents=True, exist_ok=True)
    idx, frames = [], []
    for ci, cam in enumerate(["CAM_W1", "CAM_W2"]):
        d = OUT / "safe_bundle" / "rgb" / cam
        d.mkdir(parents=True, exist_ok=True)
        for i in range(6):
            data = png(i, ci)
            ref = f"rgb/{cam}/frame_{i:06d}.png"
            (OUT / "safe_bundle" / ref).write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            idx.append({"camera_id": cam, "frame_index": i, "rgb_ref": ref, "file_sha256": sha})
            x0 = 100 + 30 * i
            flagged = i == 2
            reasons = ["FLAGGED"] if flagged else (["BLIND_BOUNDARY"] if i == 4 else (["RANDOM_SAMPLE"] if i == 0 else []))
            if cam == "CAM_W2" and i == 3:
                reasons = ["SWITCH_BOUNDARY", "D27_TARGET"]
            frames.append({
                "camera_id": cam, "frame_index": i, "timestamp_s": i * 0.2,
                "rgb_ref": ref, "file_sha256": sha,
                "detections": [] if (cam == "CAM_W2" and i == 5) else
                [{"bbox_xyxy_px": [x0, 200, x0 + 60, 400], "score": 0.9 - 0.05 * i,
                  "labels": ["merged"] if flagged else ["person"]}],
                "projection": {"expected_present": i != 5,
                               "expected_bbox_xyxy_px": [x0 + (25 if flagged else 3), 205, x0 + 62, 395]},
                "flags": ["D27_HEIGHT_LT_112", "PROJECTION_MISMATCH"] if flagged else [],
                "review_reasons": reasons, "review_required": bool(reasons),
            })
    index_bytes = json.dumps({"frames": idx}, indent=1).encode()
    (OUT / "safe_bundle" / "rgb_index.json").write_bytes(index_bytes)
    scr = {"schema_version": "d47_screening_v1", "run_id": RUN_ID,
           "rgb_index_sha256": hashlib.sha256(index_bytes).hexdigest(),
           "detector": {"name": "SYNTHETIC", "version": "0", "config_ref": "none", "config_sha256": "0" * 64},
           "sampling": {"seed_ref": "none", "seed_sha256": "0" * 64,
                        "rule": "sha256(seed,run_id,camera_id,frame_index) top ceil(10%)"},
           "frames": frames}
    (OUT / "acceptance" / "d47_screening.json").write_text(json.dumps(scr, indent=1))


if __name__ == "__main__":
    main()
