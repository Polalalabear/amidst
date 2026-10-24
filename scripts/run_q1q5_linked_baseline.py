"""Explicit stages; index process exits before isolated query/model workers start."""

import argparse
import subprocess
from pathlib import Path

from amidst.q1q5.baseline_runner import save
from amidst.q1q5.linked_runtime import build_inputs, materialize_rgb, query_inputs
from amidst.q1q5.production_preflight import read_pinned, strict_json


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=["rgb", "index", "cases"])
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--input-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model-config", type=Path)
    p.add_argument("--model-config-sha256")
    p.add_argument("--runtime", type=Path)
    p.add_argument("--runtime-sha256")
    p.add_argument("--selected-observation-id")
    p.add_argument("--allow-local-model-calls", action="store_true")
    a = p.parse_args(argv)
    before = subprocess.check_output(["df", "-k", str(a.output.parent)], text=True)
    if a.stage == "rgb":
        materialize_rgb(a.input, a.input_sha256, a.output)
    elif a.stage == "index":
        if not (a.allow_local_model_calls and a.model_config and a.model_config_sha256):
            p.error("explicit local model permission and pinned config required")
        config = strict_json(read_pinned(a.model_config, a.model_config_sha256))
        build_inputs(a.input, a.input_sha256, config, a.output)
    else:
        if not (a.selected_observation_id and a.runtime and a.runtime_sha256):
            p.error("explicit observed seed and pinned runtime required")
        runtime = strict_json(read_pinned(a.runtime, a.runtime_sha256))
        query_inputs(a.input.parent, a.input_sha256, a.selected_observation_id, runtime, a.output)
    save(a.output / "df-before.json", {"df_k": before})
    save(
        a.output / "df-after.json",
        {"df_k": subprocess.check_output(["df", "-k", str(a.output)], text=True)},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
