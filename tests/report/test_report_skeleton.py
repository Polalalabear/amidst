"""Focused tests for Track C (#734 / #730) report/ skeleton and figure pipeline."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "report"
FIGURES_DIR = REPORT_DIR / "figures"
SLIDES_DIR = REPORT_DIR / "slides"
POSTER_DIR = REPORT_DIR / "poster"
BUILD_SCRIPT = FIGURES_DIR / "build_figures.py"
SAMPLE_INPUT = FIGURES_DIR / "sample_placeholder_input.json"

EXPECTED_FIGURE_STEMS = (
    "fig1_e3_e5_summary",
    "fig2_five_way_comparison",
    "fig3_latency_breakdown",
)

DATAPACK_MANIFEST_SHA256 = "4eee05ba92ac954d4916f3000bd0d7c011297a75253ffe860605e74bca881b98"


def test_report_directory_structure() -> None:
    expected_paths = [
        REPORT_DIR / "README.md",
        POSTER_DIR / "poster_a0.html",
        POSTER_DIR / "README.md",
        SLIDES_DIR / "package.json",
        SLIDES_DIR / "README.md",
        SLIDES_DIR / "slides" / "amidst-q1q5" / "index.tsx",
        FIGURES_DIR / "FIGURES.md",
        BUILD_SCRIPT,
        SAMPLE_INPUT,
    ]
    for path in expected_paths:
        assert path.is_file(), f"Missing required report file: {path}"


def test_slides_package_json_pins_open_slide_cli_exact_version() -> None:
    pkg = json.loads((SLIDES_DIR / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "@open-slide/cli" in deps, "@open-slide/cli must be declared in package.json"
    version = deps["@open-slide/cli"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"@open-slide/cli must be pinned to an exact semver (no ^, ~, *, latest); got {version!r}"
    )

    scripts = pkg.get("scripts", {})
    assert "export:pdf" in scripts and "pdf" in scripts["export:pdf"].lower()
    assert "export:pptx" in scripts and "pptx" in scripts["export:pptx"].lower()


def test_slides_have_speaker_notes_transitions_and_reveals() -> None:
    deck_src = (SLIDES_DIR / "slides" / "amidst-q1q5" / "index.tsx").read_text(encoding="utf-8")

    # Verify all 8 slides exist and each has non-empty speaker notes and a transition
    slide_names = re.findall(r"const (Slide\d+\w+): AnnotatedPage", deck_src)
    assert len(slide_names) == 8, f"Expected 8 slides in storyline, found {len(slide_names)}: {slide_names}"

    for name in slide_names:
        assert re.search(rf"{name}\.notes\s*=\s*['\"`]", deck_src) or re.search(
            rf"{name}\.notes\s*=\s*\n\s*['\"`]", deck_src
        ), f"Slide {name} is missing speaker notes"
        assert re.search(rf"{name}\.transition\s*=\s*['\"][a-z-]+['\"]", deck_src), (
            f"Slide {name} is missing a page transition"
        )

    assert "export const speakerNotes" in deck_src
    assert "<Steps>" in deck_src and "<Step " in deck_src, "Deck must use progressive reveal (<Steps>/<Step>)"

    # Verify shared figures are referenced
    for stem in EXPECTED_FIGURE_STEMS:
        assert f"{stem}.svg" in deck_src, f"Slide deck must reference shared figure {stem}.svg"


def test_poster_is_a0_portrait_and_shares_figures() -> None:
    poster_html = (POSTER_DIR / "poster_a0.html").read_text(encoding="utf-8")
    assert "@page" in poster_html
    assert "841mm 1189mm" in poster_html, "Poster must target A0 portrait (841mm 1189mm)"
    for stem in EXPECTED_FIGURE_STEMS:
        assert f"../figures/{stem}.svg" in poster_html, f"Poster must reference ../figures/{stem}.svg"
    assert "UNCONFIRMED" in poster_html
    assert "PLACEHOLDER" in poster_html
    assert DATAPACK_MANIFEST_SHA256 in poster_html


def test_build_figures_runs_headlessly_on_sample_input(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--input", str(SAMPLE_INPUT), "--out-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"build_figures.py failed: {proc.stderr}\n{proc.stdout}"

    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "unified_analysis_v1"
    assert manifest["identity_status"] == "UNCONFIRMED"
    assert manifest["datapack_manifest_sha256"] == DATAPACK_MANIFEST_SHA256

    for stem in EXPECTED_FIGURE_STEMS:
        svg_file = tmp_path / f"{stem}.svg"
        png_file = tmp_path / f"{stem}.png"
        assert svg_file.is_file() and svg_file.stat().st_size > 1000
        assert png_file.is_file() and png_file.stat().st_size > 1000
        assert "<svg" in svg_file.read_text(encoding="utf-8")
        assert png_file.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_build_figures_handles_populated_synthetic_input(tmp_path: Path) -> None:
    data = json.loads(SAMPLE_INPUT.read_text(encoding="utf-8"))
    for entry in data["five_way_comparison"]["entries"]:
        if entry["status"] == "PLACEHOLDER":
            entry["status"] = "AVAILABLE"
            entry["metrics"]["correct_rate"] = 0.62
            entry["metrics"]["decision_point_accuracy"] = 0.35
    data["latency_breakdown"]["aol_zero_latency_approx"]["api_aol_zero_latency_correct_rate"] = 0.58
    for row in data["latency_breakdown"]["per_model_latency_ms"]:
        if row["p50_ms"] is None:
            row["p50_ms"] = 1800
            row["p95_ms"] = 3200
    data["e6_verdict"]["status"] = "AVAILABLE"
    data["e6_verdict"]["verbatim_verdict_text"] = "SYNTHETIC_TEST_VERDICT"

    custom_input = tmp_path / "synthetic_unified.json"
    custom_input.write_text(json.dumps(data), encoding="utf-8")
    out_dir = tmp_path / "out"

    proc = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--input", str(custom_input), "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"build_figures.py failed on populated synthetic input: {proc.stderr}"
    for stem in EXPECTED_FIGURE_STEMS:
        assert (out_dir / f"{stem}.svg").is_file()
        assert (out_dir / f"{stem}.png").is_file()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda d: d.pop("schema_version"),
        lambda d: d.__setitem__("schema_version", "wrong_v99"),
        lambda d: d.pop("five_way_comparison"),
        lambda d: d.pop("latency_breakdown"),
    ],
)
def test_build_figures_fails_cleanly_on_invalid_schema(tmp_path: Path, mutator) -> None:
    data = json.loads(SAMPLE_INPUT.read_text(encoding="utf-8"))
    mutator(data)
    bad_input = tmp_path / "bad.json"
    bad_input.write_text(json.dumps(data), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--input", str(bad_input), "--out-dir", str(tmp_path / "out")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0, "build_figures.py must fail cleanly on invalid schema"
    assert "ERROR:" in proc.stderr


def test_figures_md_and_readme_preserve_required_wording() -> None:
    figures_md = (FIGURES_DIR / "FIGURES.md").read_text(encoding="utf-8")
    report_readme = (REPORT_DIR / "README.md").read_text(encoding="utf-8")

    for stem in EXPECTED_FIGURE_STEMS:
        assert f"{stem}.svg" in figures_md
        assert f"{stem}.png" in figures_md

    for doc_name, text in (("FIGURES.md", figures_md), ("report/README.md", report_readme)):
        assert "UNCONFIRMED" in text, f"{doc_name} must state UNCONFIRMED identity"
        assert "PLACEHOLDER" in text, f"{doc_name} must mark E6/E7 as PLACEHOLDER"
        assert "Colab" in text and "local demo" in text, (
            f"{doc_name} must distinguish Colab latency from local demo latency"
        )
        assert DATAPACK_MANIFEST_SHA256 in text, f"{doc_name} must cite datapack MANIFEST SHA-256"
        for hyp in ("H8a", "H8b", "H8c", "H8d"):
            assert hyp in text, f"{doc_name} must preserve E5 verdict {hyp}"
