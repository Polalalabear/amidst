"""RQ1 contact report on tiny synthetic CSVs; no run data is committed."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.engineering.contact_rq1 import (
    ALL_CAMERAS,
    build_report,
    load_comparison,
    load_errors,
    paired_errors,
    rejection_summary,
    speed_jumps,
)

FRONT = "CAM_TEST_FRONT"
REAR = "CAM_TEST_REAR"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_contact_rq1.py"
COMPARISON_FIELDS = [
    "frame_id",
    "timestamp",
    "camera_id",
    "old_pixels",
    "old_world_positions_m",
    "new_pixels",
    "new_world_positions_m",
    "new_states",
    "new_reasons",
    "pixel_sensitivity_max_m",
]


def _write(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: json.dumps(v) if isinstance(v, list) else v for k, v in row.items()}
            )
    return path


def _comparison(
    frame: int,
    camera: str,
    old: list[Any],
    new: list[Any],
    reasons: list[Any],
    sensitivity: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "frame_id": frame,
        "timestamp": round(frame * 0.2, 1),
        "camera_id": camera,
        "old_pixels": [[0.0, 0.0] for _ in old],
        "old_world_positions_m": old,
        "new_pixels": [[0.0, 0.0] for _ in new],
        "new_world_positions_m": new,
        "new_states": ["OBSERVED" if p is not None else "MISSING" for p in new],
        "new_reasons": reasons,
        "pixel_sensitivity_max_m": sensitivity if sensitivity is not None else [0.1 for _ in new],
    }


@pytest.fixture
def run_dir(tmp_path: Path) -> dict[str, Path]:
    errors = _write(
        tmp_path / "errors.csv",
        ["frame_id", "timestamp", "camera_id", "v1_errors_m", "v2_errors_m", "v2_reasons"],
        [
            # FRONT: 3 timestamps, v2 rejected at t=0.2
            {
                "frame_id": 0,
                "timestamp": 0.0,
                "camera_id": FRONT,
                "v1_errors_m": [0.2],
                "v2_errors_m": [0.1],
                "v2_reasons": [[]],
            },
            {
                "frame_id": 1,
                "timestamp": 0.2,
                "camera_id": FRONT,
                "v1_errors_m": [0.4],
                "v2_errors_m": [None],
                "v2_reasons": [["LOW_INCIDENCE"]],
            },
            {
                "frame_id": 2,
                "timestamp": 0.4,
                "camera_id": FRONT,
                "v1_errors_m": [0.3],
                "v2_errors_m": [0.2],
                "v2_reasons": [[]],
            },
            # REAR: one paired, one rejected with two reasons, one v1-only gap
            {
                "frame_id": 0,
                "timestamp": 0.0,
                "camera_id": REAR,
                "v1_errors_m": [0.1],
                "v2_errors_m": [None],
                "v2_reasons": [["TOUCHES_IMAGE_EDGE", "CONTACT_OCCLUDED"]],
            },
            {
                "frame_id": 1,
                "timestamp": 0.2,
                "camera_id": REAR,
                "v1_errors_m": [0.5],
                "v2_errors_m": [0.3],
                "v2_reasons": [[]],
            },
            {
                "frame_id": 2,
                "timestamp": 0.4,
                "camera_id": REAR,
                "v1_errors_m": [None],
                "v2_errors_m": [None],
                "v2_reasons": [["LOW_INCIDENCE"]],
            },
        ],
    )
    auditorium = _write(
        tmp_path / "auditorium-comparison.csv",
        COMPARISON_FIELDS,
        [
            _comparison(0, FRONT, [[0.0, 0.0, 0.5]], [[0.0, 0.0, 0.5]], [[]], [0.05]),
            _comparison(1, FRONT, [[0.2, 0.0, 0.5]], [None], [["LOW_INCIDENCE"]], [0.12]),
            # 2.0 m in 0.2 s = 10 m/s for v1; v2 skips t=0.2 so 2.0 m / 0.4 s = 5 m/s
            _comparison(2, FRONT, [[2.2, 0.0, 0.5]], [[2.0, 0.0, 0.5]], [[]], [0.07]),
            _comparison(
                0, REAR, [[5.0, 5.0, 0.5]], [None], [["TOUCHES_IMAGE_EDGE", "CONTACT_OCCLUDED"]]
            ),
            _comparison(1, REAR, [[5.0, 5.2, 0.5]], [[5.0, 5.1, 0.5]], [[]]),
            _comparison(2, REAR, [None], [None], [["LOW_INCIDENCE"]]),
        ],
    )
    office = _write(
        tmp_path / "office-comparison.csv",
        COMPARISON_FIELDS,
        [
            # two v1 components in one frame, one far away; the near one continues the track
            _comparison(0, FRONT, [[0.0, 0.0, 0.5]], [None], [["LOW_INCIDENCE"]]),
            _comparison(
                1,
                FRONT,
                [[0.1, 0.0, 0.5], [4.0, 0.0, 0.5]],
                [None],
                [["LOW_INCIDENCE", "CONTACT_OCCLUDED"]],
            ),
            _comparison(2, FRONT, [], [], ["NO_DETECTION"], []),
            _comparison(0, REAR, [], [], ["NO_DETECTION"], []),
            _comparison(1, REAR, [[9.0, 9.0, 0.5]], [None], [["LOW_INCIDENCE"]]),
            _comparison(2, REAR, [], [], ["NO_DETECTION"], []),
        ],
    )
    visibility = _write(
        tmp_path / "visibility.csv",
        [
            "frame_id",
            "timestamp",
            "camera_id",
            "middle_visible",
            "bottom_visible",
            "bottom_incidence",
            "incidence_eligible",
        ],
        [
            {
                "frame_id": i,
                "timestamp": round(i * 0.2, 1),
                "camera_id": cam,
                "middle_visible": "True",
                "bottom_visible": "True",
                "bottom_incidence": inc,
                "incidence_eligible": str(inc >= 0.25),
            }
            for cam in (FRONT, REAR)
            for i, inc in enumerate((0.3, 0.2, 0.4))
        ],
    )
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(
        json.dumps(
            {
                "dataset_sha256": "d" * 64,
                "prediction_sha256": "p" * 64,
                "summary": {
                    "v1": {"projected_count": 5, "mean_m": 0.3, "max_m": 0.5},
                    "v2": {"projected_count": 3, "mean_m": 0.2, "max_m": 0.3},
                },
                "paired_same_frames": {
                    "v1": {"count": 3, "mean_m": (0.2 + 0.3 + 0.5) / 3, "max_m": 0.5},
                    "v2": {"count": 3, "mean_m": 0.2, "max_m": 0.3},
                },
            }
        ),
        encoding="utf-8",
    )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "run_id": "synthetic-contact-v1",
                "coverage": {
                    "timestamps_with_at_least_one_v2_position": 3,
                    "rejection_reasons": {
                        "LOW_INCIDENCE": 2,
                        "TOUCHES_IMAGE_EDGE": 1,
                        "CONTACT_OCCLUDED": 1,
                    },
                },
                "office_regression": {
                    "old_projected_count": 4,
                    "v2_components": 3,
                    "v2_projected": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    return {
        "errors_csv": errors,
        "auditorium_comparison_csv": auditorium,
        "office_comparison_csv": office,
        "visibility_csv": visibility,
        "evaluation_json": evaluation,
        "receipt_json": receipt,
    }


def test_pairing_uses_only_frames_where_both_versions_exist(run_dir: dict[str, Path]) -> None:
    paired = paired_errors(load_errors(run_dir["errors_csv"]))
    assert paired[FRONT] == {"v1": [0.2, 0.3], "v2": [0.1, 0.2]}
    assert paired[REAR] == {"v1": [0.5], "v2": [0.3]}


def test_report_errors_coverage_and_crosscheck(run_dir: dict[str, Path]) -> None:
    report = build_report(**run_dir)
    errors = report["auditorium"]["errors"]
    combined = errors[ALL_CAMERAS]
    assert combined["paired"]["v1"]["count"] == 3
    assert combined["paired"]["v1"]["mean_m"] == pytest.approx(1.0 / 3)
    assert combined["paired"]["v1"]["median_m"] == pytest.approx(0.3)
    assert combined["paired"]["v2"]["max_m"] == pytest.approx(0.3)
    assert combined["all_available"]["v1"]["count"] == 5
    assert combined["all_available"]["v2"]["count"] == 3
    assert errors[FRONT]["paired"]["v2"]["mean_m"] == pytest.approx(0.15)

    coverage = report["auditorium"]["coverage"]
    assert coverage["v1"][FRONT] == {"with_position": 3, "total": 3}
    assert coverage["v1"][REAR] == {"with_position": 2, "total": 3}
    assert coverage["v2"][FRONT] == {"with_position": 2, "total": 3}
    assert coverage["v2"][ALL_CAMERAS] == {"with_position": 3, "total": 3}

    assert report["crosscheck"]["all_match"], report["crosscheck"]
    assert set(report["inputs"]) == set(run_dir)
    for role, path in run_dir.items():
        assert report["inputs"][role]["filename"] == path.name
        assert len(report["inputs"][role]["sha256"]) == 64
    assert str(run_dir["errors_csv"].parent) not in json.dumps(report)


def test_crosscheck_flags_a_claim_that_disagrees(run_dir: dict[str, Path]) -> None:
    evaluation = json.loads(run_dir["evaluation_json"].read_text())
    evaluation["paired_same_frames"]["v2"]["max_m"] = 0.25
    run_dir["evaluation_json"].write_text(json.dumps(evaluation))
    check = build_report(**run_dir)["crosscheck"]
    assert not check["all_match"]
    failed = [item["check"] for item in check["checks"] if not item["match"]]
    assert failed == ["paired.v2.max_m"]


def test_jumps_count_steps_above_cap_between_available_timestamps(
    run_dir: dict[str, Path],
) -> None:
    rows = load_comparison(run_dir["auditorium_comparison_csv"])
    v1 = speed_jumps(rows, "v1", 8.0)
    assert v1[FRONT]["jump_count"] == 1
    assert v1[FRONT]["jumps"][0]["from_s"] == pytest.approx(0.2)
    assert v1[FRONT]["jumps"][0]["speed_m_s"] == pytest.approx(10.0)
    assert v1[REAR]["jump_count"] == 0
    v2 = speed_jumps(rows, "v2", 8.0)
    assert v2[FRONT]["jump_count"] == 0
    assert v2[FRONT]["max_speed_m_s"] == pytest.approx(5.0)
    assert speed_jumps(rows, "v1", 12.0)[ALL_CAMERAS]["jump_count"] == 0


def test_rejection_histogram_counts_every_label_and_primary_once(
    run_dir: dict[str, Path],
) -> None:
    summary = rejection_summary(load_comparison(run_dir["auditorium_comparison_csv"]))
    assert summary[REAR]["reasons"] == {
        "CONTACT_OCCLUDED": 1,
        "LOW_INCIDENCE": 1,
        "TOUCHES_IMAGE_EDGE": 1,
    }
    assert summary[REAR]["by_primary"] == {"LOW_INCIDENCE": 1, "TOUCHES_IMAGE_EDGE": 1}
    assert summary[ALL_CAMERAS]["kept"] == 3
    assert summary[ALL_CAMERAS]["rejected"] == 3
    assert sum(summary[ALL_CAMERAS]["by_primary"].values()) == 3


def test_office_kept_vs_rejected_and_multi_component_jump(run_dir: dict[str, Path]) -> None:
    office = build_report(**run_dir)["office"]
    assert office[FRONT]["v1_positions"] == 3
    assert office[FRONT]["v1_timestamps_with_position"] == 2
    assert office[FRONT]["v1_jump_count"] == 0  # near component continues at 0.5 m/s
    assert office[FRONT]["v2_components"] == 2
    assert office[FRONT]["v2_kept"] == 0
    assert office[FRONT]["v2_reasons"] == {"CONTACT_OCCLUDED": 1, "LOW_INCIDENCE": 2}
    assert office[FRONT]["no_detection_timestamps"] == 1
    assert office[REAR]["no_detection_timestamps"] == 2
    assert office[ALL_CAMERAS]["v1_positions"] == 4
    assert office[ALL_CAMERAS]["v2_rejected"] == 3


def test_pixel_sensitivity_split_by_v2_outcome(run_dir: dict[str, Path]) -> None:
    sensitivity = build_report(**run_dir)["auditorium"]["pixel_sensitivity"][FRONT]
    assert sensitivity["v2_kept"]["count"] == 2
    assert sensitivity["v2_kept"]["max_m"] == pytest.approx(0.07)
    assert sensitivity["v2_rejected"]["median_m"] == pytest.approx(0.12)
    assert sensitivity["visibility"]["incidence_eligible"] == 2
    assert sensitivity["visibility"]["bottom_incidence_min"] == pytest.approx(0.2)


def test_cli_writes_report_and_three_charts(run_dir: dict[str, Path], tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("evaluate_contact_rq1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path / "out"
    code = module.main(
        [
            "--errors",
            str(run_dir["errors_csv"]),
            "--auditorium-comparison",
            str(run_dir["auditorium_comparison_csv"]),
            "--office-comparison",
            str(run_dir["office_comparison_csv"]),
            "--visibility",
            str(run_dir["visibility_csv"]),
            "--evaluation",
            str(run_dir["evaluation_json"]),
            "--receipt",
            str(run_dir["receipt_json"]),
            "--report",
            str(out / "report.json"),
            "--chart-dir",
            str(out / "charts"),
        ]
    )
    assert code == 0
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["charts"] == [
        "rq1_error_over_time.png",
        "rq1_error_distribution.png",
        "rq1_coverage_rejection.png",
    ]
    for name in report["charts"]:
        assert (out / "charts" / name).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_cli_refuses_to_write_into_input_directory(run_dir: dict[str, Path]) -> None:
    spec = importlib.util.spec_from_file_location("evaluate_contact_rq1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = run_dir["errors_csv"].parent
    args = [
        "--errors",
        str(run_dir["errors_csv"]),
        "--auditorium-comparison",
        str(run_dir["auditorium_comparison_csv"]),
        "--office-comparison",
        str(run_dir["office_comparison_csv"]),
        "--visibility",
        str(run_dir["visibility_csv"]),
        "--evaluation",
        str(run_dir["evaluation_json"]),
        "--receipt",
        str(run_dir["receipt_json"]),
        "--report",
        str(source / "report.json"),
        "--chart-dir",
        str(source.parent / "charts"),
    ]
    with pytest.raises(SystemExit):
        module.main(args)
    assert not (source / "report.json").exists()
