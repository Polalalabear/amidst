"""Trust-boundary tests for advisory static review packaging and returns."""

import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

ENGINE = Path(__file__).resolve().parents[2] / "src/amidst/evaluation/r004_prereview_pack.py"
spec = importlib.util.spec_from_file_location("r004_prereview_pack", ENGINE)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def png():
    return (
        p.PNG
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"tEXt", b"File\0/Users/private/source.blend")
        + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0"))
        + chunk(b"IEND", b"")
    )


def png_data(
    compressed, width=1, height=1, depth=8, color=2, compression=0, filtering=0, interlace=0
):
    header = struct.pack(">IIBBBBB", width, height, depth, color, compression, filtering, interlace)
    return p.PNG + chunk(b"IHDR", header) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


class PrereviewPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="r004-prereview-test-")
        self.root = Path(self.temp.name).resolve()
        self.camera_ids = [f"CAM_{i}" for i in range(8)]
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.assets = self.root / "assets"
        self.assets.mkdir()
        for name, data in {
            "index.html": b"<!doctype html><script src='data.js'></script>",
            "app.js": b"'use strict';",
            "style.css": b"body{}",
            "region_map.svg": b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        }.items():
            (self.assets / name).write_bytes(data)
        roles = {role: {} for role in p.COPY_ROLES | {"static_geometry"}}
        roles["region_graph"] = {
            "edges": [{"edge_id": f"E_{i}", "regions": ["A", "B"]} for i in range(6)]
        }
        roles["camera_graph"] = {
            "transitions": [
                {"transition_id": f"T_{i}", "from_camera_id": "CAM_0", "to_camera_id": "CAM_1"}
                for i in range(17)
            ]
        }
        roles["region_meshes"] = {
            "meshes": {
                "A": {
                    "vertices_world_m": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                    "triangles_or_polygons": [[0, 1, 2]],
                }
            }
        }
        roles["camera_catalog"] = {
            "cameras": [
                {
                    "camera_id": cid,
                    "camera_to_world": [[1, 0, 0, i], [0, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 1]],
                }
                for i, cid in enumerate(self.camera_ids)
            ]
        }
        roles["hsv_report"] = {
            "rows": [
                {
                    "rgb_ref": f"preview/{i}.png",
                    "detector_ordinal": 0,
                    "summary": {"verdicts": {"red": "NONE", "blue": "STRONG"}},
                }
                for i in range(35)
            ]
        }
        self.config = {
            "schema_version": "q-demo.r004-prereview-inputs.v1",
            "source_heads": {},
            "files": {},
            "static_frames": {},
            "overlay_frames": {},
            "hsv_crops": {},
        }
        for role, doc in roles.items():
            self.config["files"][role] = self.source(role + ".json", p.canonical(doc))
        for group in ["static_frames", "overlay_frames"]:
            for cid in self.camera_ids:
                self.config[group][cid] = self.source(group + cid + ".png", png())
        for i in range(1, 36):
            cid = f"crop_{i:03d}"
            self.config["hsv_crops"][cid] = self.source(cid + ".png", png())
        self.config_path = self.root / "inputs.json"
        self.config_path.write_bytes(p.canonical(self.config))
        self.report = {
            "schema_version": "q-demo.r004-prereview-check.v1",
            "status": "REVIEW_REQUIRED",
            "config_sha256": p.sha(self.config_path.read_bytes()),
            "engineering_checks": [],
            "unresolved": [{"id": "G4", "summary": "Review required"}],
            "counts": {},
            "camera_diagnostics": {},
        }
        self.report["output_sha256"] = p.sha(p.canonical(self.report))
        self.report_path = self.root / "report.json"
        self.report_path.write_bytes(p.canonical(self.report))
        self.output = self.root / "pack"

    def tearDown(self):
        self.temp.cleanup()

    def source(self, name, raw):
        path = self.sources / name
        path.write_bytes(raw)
        return {"path": str(path), "sha256": p.sha(raw)}

    def build(self):
        # Graph correctness is covered independently by the source-pinned graph
        # checker tests. This fixture isolates packaging/return trust boundaries.
        with mock.patch.object(
            p, "_render_map", return_value=(self.assets / "region_map.svg").read_bytes()
        ):
            self.receipt = p.build_pack(
                self.config_path,
                p.sha(self.config_path.read_bytes()),
                self.report_path,
                p.sha(self.report_path.read_bytes()),
                self.output,
                self.assets,
            )
        return self.receipt

    def filled(self):
        self.build()
        _, rows = p._parse_csv((self.output / "templates/審查表.csv").read_bytes())
        for row in rows:
            row.update(
                decision="不確定",
                reason="測試用回收欄位；不是人工答案",
                reviewer="fixture",
                date="2026-10-23",
            )
        return rows

    def returned(self, rows):
        path = self.root / "return.csv"
        path.write_bytes(p._csv(rows))
        return path

    def check(self, rows):
        return p.import_pack(self.output, self.receipt["manifest_sha256"], self.returned(rows))

    def test_blank_pack_is_incomplete_and_never_approves(self):
        self.build()
        result = p.import_pack(self.output, self.receipt["manifest_sha256"])
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["counts"]["expected"], 110)
        self.assertFalse(result["approval_granted"])
        self.assertFalse(result["evaluation_eligible"])
        self.assertEqual(result["counts"]["incomplete"], 110)

    def test_roundtrip_uses_new_hash_and_preserves_originals(self):
        rows = self.filled()
        template = (self.output / "templates/審查表.csv").read_bytes()
        result = self.check(rows)
        self.assertEqual(result["status"], "VALID")
        self.assertNotEqual(result["returned_csv_sha256"], result["template_csv_sha256"])
        self.assertEqual(template, (self.output / "templates/審查表.csv").read_bytes())

    def test_png_metadata_is_removed_with_pixel_encoding_preserved(self):
        original = png()
        export, receipt = p.sanitize_png(original)
        self.assertNotIn(b"/Users/", export)
        self.assertEqual(receipt["removed_metadata_chunks"], ["tEXt"])
        again, check = p.sanitize_png(export)
        self.assertEqual(again, export)
        self.assertEqual(receipt["pixel_data_sha256"], check["pixel_data_sha256"])
        self.build()
        self.assertEqual(
            _ := Path(self.config["static_frames"]["CAM_0"]["path"]).read_bytes(), original
        )
        self.assertNotIn(b"/Users/", (self.output / "images/static/CAM_0.png").read_bytes())

    def test_corrupt_and_truncated_png_rejected(self):
        for raw in [png()[:-1], png()[:20] + b"x" + png()[21:], p.PNG + chunk(b"IEND", b"")]:
            with self.subTest(raw=len(raw)), self.assertRaises(p.PackError):
                p.sanitize_png(raw)

    def test_crc_correct_but_bad_zlib_filter_size_or_stream_is_rejected(self):
        valid_stream = zlib.compress(b"\0\xff\0\0")
        streams = [
            b"not-zlib",
            valid_stream[:-1],
            valid_stream + b"tail",
            valid_stream + valid_stream,
            zlib.compress(b"\x05\xff\0\0"),
            zlib.compress(b"\0\xff\0"),
            zlib.compress(b"\0\xff\0\0\0"),
            zlib.compress(b"\0" * 8192),
        ]
        for index, stream in enumerate(streams):
            with self.subTest(index=index), self.assertRaises(p.PackError):
                p.sanitize_png(png_data(stream))

    def test_unsupported_png_modes_and_dimensions_rejected_before_inflate(self):
        variants = [
            {"width": 0},
            {"width": 4097},
            {"height": 4097},
            {"depth": 16},
            {"color": 3},
            {"compression": 1},
            {"filtering": 1},
            {"interlace": 1},
            {"width": 4096, "height": 4096, "color": 6},
        ]
        for fields in variants:
            with self.subTest(fields=fields), self.assertRaises(p.PackError):
                p.sanitize_png(png_data(zlib.compress(b"\0\xff\0\0"), **fields))

    def test_supported_png_scanlines_and_filters_are_accepted_without_reencoding(self):
        for color, channels in [(0, 1), (2, 3), (4, 2), (6, 4)]:
            for filter_byte in range(5):
                with self.subTest(color=color, filter=filter_byte):
                    raw = png_data(
                        zlib.compress(bytes([filter_byte]) + bytes(channels)), color=color
                    )
                    exported, receipt = p.sanitize_png(raw)
                    self.assertEqual(exported, raw)
                    self.assertEqual(receipt["inflated_scanline_bytes"], channels + 1)

    def test_wrong_config_or_report_pin_rejected(self):
        with self.assertRaises(p.PackError):
            p.build_pack(
                self.config_path,
                "0" * 64,
                self.report_path,
                p.sha(self.report_path.read_bytes()),
                self.output,
                self.assets,
            )
        self.report["counts"] = {"changed": True}
        self.report_path.write_bytes(p.canonical(self.report))
        with self.assertRaises(p.PackError):
            self.build()

    def test_source_tamper_and_symlink_rejected(self):
        path = Path(self.config["static_frames"]["CAM_0"]["path"])
        path.write_bytes(png() + b"changed")
        with self.assertRaises(p.PackError):
            self.build()
        path.unlink()
        target = self.sources / "target.png"
        target.write_bytes(png())
        path.symlink_to(target)
        with self.assertRaises(p.PackError):
            self.build()

    def test_immutable_pack_tamper_is_rejected(self):
        self.build()
        (self.output / "DATA.json").write_text("{}")
        with self.assertRaises(p.PackError):
            p.import_pack(self.output, self.receipt["manifest_sha256"])

    def test_template_tamper_is_rejected(self):
        self.build()
        (self.output / "templates/審查表.csv").write_text("edited")
        with self.assertRaises(p.PackError):
            p.verify_pack(self.output, self.receipt["manifest_sha256"])

    def test_report_from_another_config_is_rejected(self):
        self.report["config_sha256"] = "0" * 64
        self.report.pop("output_sha256")
        self.report["output_sha256"] = p.sha(p.canonical(self.report))
        self.report_path.write_bytes(p.canonical(self.report))
        with self.assertRaises(p.PackError):
            self.build()

    def test_manifest_trusted_pin_is_required(self):
        self.build()
        with self.assertRaises(p.PackError):
            p.verify_pack(self.output, "0" * 64)

    def test_fixed_column_change_is_invalid(self):
        rows = self.filled()
        rows[0]["statement"] += "changed"
        self.assertEqual(self.check(rows)["status"], "INVALID")

    def test_missing_duplicate_and_unknown_ids_are_invalid(self):
        rows = self.filled()
        for changed in [
            rows[:-1],
            rows + [rows[0]],
            [{**rows[0], "item_id": "UNKNOWN"}, *rows[1:]],
        ]:
            with self.subTest(length=len(changed)):
                self.assertEqual(self.check(changed)["status"], "INVALID")

    def test_bad_enum_date_and_missing_reviewer(self):
        rows = self.filled()
        rows[0]["decision"] = "APPROVED"
        self.assertEqual(self.check(rows)["status"], "INVALID")
        rows[0]["decision"] = "T"
        rows[0]["date"] = "2026-02-30"
        self.assertEqual(self.check(rows)["status"], "INVALID")
        rows[0]["date"] = "2026-10-23"
        rows[0]["reviewer"] = ""
        self.assertEqual(self.check(rows)["status"], "INCOMPLETE")

    def test_unresolved_all_decisions_require_reason_but_general_t_may_omit(self):
        rows = self.filled()
        generic = next(row for row in rows if row["category"] == "CAMERA_IDENTITY")
        generic.update(decision="T", reason="")
        self.assertEqual(self.check(rows)["status"], "VALID")
        unresolved = next(row for row in rows if row["category"] == "UNRESOLVED")
        for decision in ["T", "F", "不確定"]:
            unresolved.update(decision=decision, reason="")
            result = self.check(rows)
            self.assertEqual(result["status"], "INCOMPLETE")
            self.assertIn("reason", result["incomplete"][0]["missing"])
            unresolved["reason"] = "測試用缺口說明；不是核准"
            self.assertEqual(self.check(rows)["status"], "VALID")

    def test_formula_injection_rejected_and_neutralized_roundtrip_preserved(self):
        rows = self.filled()
        for text in ['=HYPERLINK("https://example.invalid")', "  +SUM(1)", "\t@x"]:
            rows[0]["reason"] = text
            self.assertEqual(self.check(rows)["status"], "INVALID")
            rows[0]["reason"] = p.csv_safe(text)
            result = self.check(rows)
            self.assertEqual(result["status"], "VALID")
            self.assertEqual(result["rows"][0]["reason"], text)

    def test_existing_output_is_not_overwritten(self):
        self.build()
        with self.assertRaises(p.PackError):
            self.build()

    def test_apostrophe_and_csv_quoting_roundtrip(self):
        rows = self.filled()
        for text in ["'=abc", "'ordinary", 'comma, quote" and\nnewline']:
            rows[0]["reason"] = p.csv_safe(text)
            result = self.check(rows)
            self.assertEqual(result["status"], "VALID")
            self.assertEqual(result["rows"][0]["reason"], text)

    def test_pack_is_portable_and_has_no_absolute_config_or_geometry(self):
        self.build()
        data = (self.output / "DATA.json").read_text()
        self.assertNotIn(str(self.root), data)
        self.assertFalse((self.output / "inputs.json").exists())
        self.assertFalse((self.output / "provenance/static_geometry.json").exists())
        result = subprocess.run(
            [
                sys.executable,
                str(self.output / "tools/verify_bundle.py"),
                "--manifest-sha256",
                self.receipt["manifest_sha256"],
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
