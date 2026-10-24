"""One engineering acceptance command, optionally serving the same outputs."""

import argparse
import json
import os
from pathlib import Path

from amidst.q1q5.linked_acceptance import recipe, server_command
from amidst.q1q5.production_preflight import read_pinned, strict_json


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["config", "composition"]:
        p.add_argument("--" + name, type=Path, required=True)
        p.add_argument("--" + name + "-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--allow-local-model-calls", action="store_true")
    p.add_argument("--ollama-service-pid", type=int)
    p.add_argument("--serve", action="store_true")
    a = p.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    result = recipe(
        repo,
        strict_json(read_pinned(a.config, a.config_sha256)),
        a.composition,
        a.composition_sha256,
        a.output,
        permit=a.allow_local_model_calls,
        service_pid=a.ollama_service_pid,
    )
    print(json.dumps(result), flush=True)
    command = server_command(repo, a.output)
    if a.serve:
        os.execv(command[0], command)
    print(json.dumps({"workbench_command": command}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
