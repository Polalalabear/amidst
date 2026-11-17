"""Run existing update gates with checkout-local QA state and a read-only owned package.

Does not change production configuration, asset pins, validators, or I/O boundaries.
Only tempfile's state destination is redirected, within this checkout's local/evidence.
"""

import argparse
import os
from pathlib import Path
import runpy
import sys
import tempfile

from demo_dependency_config import REPO, configuration, owned_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state-parent", type=Path, required=True)
    ap.add_argument("gate", choices=["dependency", "serve"])
    args, forwarded = ap.parse_known_args()
    state = args.state_parent.resolve()
    if not state.is_relative_to((REPO / "local/evidence").resolve()):
        ap.error("QA_STATE_MUST_BE_IN_CHECKOUT_LOCAL_EVIDENCE")
    config, root = configuration()
    original_state = owned_path(root, config["state_root"])
    if not original_state.is_dir():
        ap.error("EXISTING_OWNED_STATE_PARENT_REQUIRED: QA never creates source directories")
    state.mkdir(parents=True, exist_ok=True)
    mkdir, mkdtemp = os.mkdir, tempfile.mkdtemp

    def state_mkdir(path, mode=0o777, *, dir_fd=None):
        if dir_fd is None and Path(path).resolve() == original_state:
            return  # existing directory: production mkdir(exist_ok=True) is a no-op
        return mkdir(path, mode, dir_fd=dir_fd)

    def state_temp(suffix=None, prefix=None, dir=None):
        if dir is not None and Path(dir).resolve() == original_state:
            dir = state
        return mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

    def readonly_owned(event, values):
        if event == "open" and values and not isinstance(values[0], int):
            target = Path(os.fsdecode(values[0])).resolve()
            flags = values[2] if len(values) > 2 and isinstance(values[2], int) else 0
            if target.is_relative_to(root) and flags & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            ):
                raise PermissionError("QA_SOURCE_PACKAGE_IS_READ_ONLY")
        if event in {
            "os.remove",
            "os.rename",
            "os.rmdir",
            "os.mkdir",
            "os.chmod",
            "os.link",
            "os.symlink",
            "os.truncate",
        }:
            for value in values[:2]:
                if isinstance(value, (str, bytes, os.PathLike)) and Path(
                    os.fsdecode(value)
                ).resolve().is_relative_to(root):
                    raise PermissionError("QA_SOURCE_PACKAGE_IS_READ_ONLY")

    os.mkdir, tempfile.mkdtemp = state_mkdir, state_temp
    sys.addaudithook(readonly_owned)
    script = (
        "check_demo_dependencies.py" if args.gate == "dependency" else "serve_demo_integration.py"
    )
    if args.gate == "serve" and (
        "--port" not in forwarded or forwarded[forwarded.index("--port") + 1] == "8785"
    ):
        ap.error("QA_REQUIRES_AN_EXPLICIT_NON_8785_PORT")
    sys.argv = [script, *forwarded]
    runpy.run_path(str(REPO / "scripts" / script), run_name="__main__")


if __name__ == "__main__":
    main()
