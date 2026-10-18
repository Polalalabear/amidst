"""Exact URL-to-file maps for v2 and six reusable pure legacy modules."""

from pathlib import Path

from amidst.workbench.controlled_scene_data import read_regular

V2_FILES = (
    "index.html", "style.css", "tokens.mjs", "store.mjs", "clock.mjs", "api.mjs",
    "player-grid.mjs", "grid-view.mjs", "plan-layers.mjs", "plan-view.mjs", "timeline-model.mjs",
    "timeline-view.mjs", "query.mjs", "inspector.mjs", "demo.mjs", "app.mjs",
    "demo-steps.controlled.json",
    "fixtures/synced_frames_3cams.json", "fixtures/synced_frames_4cams.json",
    "fixtures/synced_frames_8cams.json", "fixtures/synced_frames_11cams.json",
    "fixtures/synced_frames_integrity_error.json",
    "fonts/IBMPlexSans-Regular.woff2", "fonts/IBMPlexSansCondensed-SemiBold.woff2",
    "fonts/IBMPlexMono-Regular.woff2", "fonts/NotoSansTC-Regular.woff2",
    "fonts/OFL-IBMPlex.txt", "fonts/OFL-NotoSansTC.txt",
)
PURE_MODULES = ("presentation-data.mjs", "ground-estimate.mjs", "geometry.mjs",
                "blind-hypothesis.mjs", "demo-mode.mjs", "observation-selection.mjs")
VENDOR_LINES = ("Line2.js", "LineMaterial.js", "LineGeometry.js", "LineSegments2.js",
                "LineSegmentsGeometry.js")
STATIC_FILES = {"/workbench-v2/": "frontend/workbench-v2/index.html"}
STATIC_FILES.update({"/workbench-v2/" + f: "frontend/workbench-v2/" + f for f in V2_FILES})
STATIC_FILES.update({"/workbench/" + f: "frontend/workbench/" + f for f in PURE_MODULES})
LINE_FILES = {"/vendor/examples/jsm/lines/" + f: "examples/jsm/lines/" + f for f in VENDOR_LINES}


def read_static(repo: Path, path: str) -> bytes:
    return read_regular(repo, STATIC_FILES[path])
