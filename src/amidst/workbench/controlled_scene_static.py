"""Exact URL-to-file map for the workbench-v2 static files (old UI retired, D268)."""

from pathlib import Path

from amidst.workbench.controlled_scene_data import read_regular

V2_FILES = (
    "index.html", "style.css", "tokens.mjs", "store.mjs", "clock.mjs", "api.mjs",
    "player-grid.mjs", "grid-view.mjs", "layout.mjs", "shell-view.mjs", "uncertainty.mjs",
    "plan-layers.mjs", "plan-view.mjs", "timeline-model.mjs",
    "timeline-view.mjs", "query.mjs", "inspector.mjs", "demo.mjs", "app.mjs",
    "demo-steps.controlled.json",
    "fixtures/synced_frames_3cams.json", "fixtures/synced_frames_4cams.json",
    "fixtures/synced_frames_8cams.json", "fixtures/synced_frames_11cams.json",
    "fixtures/synced_frames_integrity_error.json",
    "fonts/IBMPlexSans-Regular.woff2", "fonts/IBMPlexSansCondensed-SemiBold.woff2",
    "fonts/IBMPlexMono-Regular.woff2", "fonts/NotoSansTC-Regular.woff2",
    "fonts/OFL-IBMPlex.txt", "fonts/OFL-NotoSansTC.txt",
)
STATIC_FILES = {"/workbench-v2/": "frontend/workbench-v2/index.html"}
STATIC_FILES.update({"/workbench-v2/" + f: "frontend/workbench-v2/" + f for f in V2_FILES})


def read_static(repo: Path, path: str) -> bytes:
    return read_regular(repo, STATIC_FILES[path])
