"""Focused D47 checks; synthetic pixels only, never task RGB or GT."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "d47", Path(__file__).with_name("screen_controlled_scene_d47.py"))
d47 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d47)


class D47Tests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(d47.pinned(d47.REPO / d47.CONFIG_REF, d47.CONFIG_PIN))

    def test_four_connected_and_exclusive_bbox(self):
        mask = np.zeros((9, 9), dtype=bool)
        mask[1:4, 2:5] = True
        mask[4, 5] = True  # diagonal must remain a distinct component
        self.assertEqual(d47.components(mask, 1), [[2, 1, 5, 4, 9], [5, 4, 6, 5, 1]])
        self.assertEqual(d47.components(mask, 2), [[2, 1, 5, 4, 9]])

    def test_union_bridging(self):
        mask = np.array([[1, 0, 1], [1, 1, 1]], dtype=bool)
        self.assertEqual(d47.components(mask, 1), [[0, 0, 3, 2, 5]])

    def test_rgb_only_detector_recovers_motion_without_route(self):
        images = [np.zeros((540, 960, 3), dtype=np.uint8) for _ in range(5)]
        images[2][100:240, 300:340] = 100
        detections = d47.detect_camera(images, self.config)
        self.assertEqual([len(x) for x in detections], [0, 0, 1, 0, 0])
        self.assertEqual(detections[2][0]["bbox_xyxy_px"], [300, 100, 340, 240])
        self.assertNotIn("MERGED_OR_AMBIGUOUS", detections[2][0]["labels"])

    def test_thresholds_are_strict_and_no_bbox_foot(self):
        row = {"camera_id": "CAM_W1", "frame_index": 22,
               "detections": [{"bbox_xyxy_px": [16, 16, 50, 128], "labels": []}],
               "projection": {"expected_present": True, "expected_count": 1,
                              "expected_bbox_xyxy_px": [16, 16, 50, 128],
                              "full_body_expected": True}}
        self.assertEqual(d47.frame_flags(row, "a", self.config["screening"]), [])
        row["detections"][0]["bbox_xyxy_px"] = [0, 16, 50, 127]
        flags = d47.frame_flags(row, "a", self.config["screening"])
        self.assertIn("HEIGHT_BELOW_112_PX", flags)
        self.assertIn("FRAME_EDGE_TOUCH", flags)
        self.assertNotIn("contact_pixel", row)

    def test_sampling_reproducible_excludes_required_and_ceil(self):
        def rows():
            return [{"camera_id": "CAM_R102_CTRL", "frame_index": i,
                     "detections": [], "flags": [] if i else ["test"]} for i in range(24)]
        a, b = rows(), rows()
        ra = d47.assign_reviews(a, "a", "seed", "run")
        rb = d47.assign_reviews(b, "a", "seed", "run")
        self.assertEqual(ra, rb)
        self.assertEqual(ra["CAM_R102_CTRL"]["selected_count"], 3)
        self.assertNotIn(0, ra["CAM_R102_CTRL"]["selected_indices"])
        self.assertTrue(a[0]["review_required"])

    def test_a4_boundaries_switches_and_d27(self):
        rows = [{"camera_id": "CAM_W1", "frame_index": i, "detections": [] if i < 55 else [{"labels": []}],
                 "flags": []} for i in range(100)]
        d47.assign_reviews(rows, "b1", "seed", "run")
        self.assertEqual([r["frame_index"] for r in rows if "BLIND_BOUNDARY" in r["review_reasons"]], [49, 50, 68, 69])
        self.assertEqual([r["frame_index"] for r in rows if "SWITCH_BOUNDARY" in r["review_reasons"]], [54, 55, 56])
        a = [{"camera_id": "CAM_W1", "frame_index": i, "detections": [], "flags": []} for i in range(50)]
        d47.assign_reviews(a, "a", "seed", "run")
        self.assertEqual(sum("D27_TARGET" in r["review_reasons"] for r in a), 11)

    def test_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
                d47.pinned(path, "0" * 64)
            with self.assertRaises(ValueError):
                d47.pinned(path.with_name("absent"), "0" * 64)

    def test_projection_reproduces_design_target_and_p2_start(self):
        design = d47.load_design()
        c = design["CAMS"]["CAM_W2"]
        head, foot = design["proj"](c, (6.5, 1.2, 1.7)), design["proj"](c, (6.5, 1.2, 0))
        self.assertAlmostEqual(abs(head[1] - foot[1]), 196.752, places=2)
        self.assertIsNone(design["route2"](10.8))
        self.assertEqual(design["route2"](11.0), (1.0, 1.2))
        self.assertTrue(d47.projection(design, "a", "CAM_W2", 5)["expected_present"])
        self.assertFalse(d47.projection(design, "a", "CAM_R102_CTRL", 5)["expected_present"])


if __name__ == "__main__":
    unittest.main()
