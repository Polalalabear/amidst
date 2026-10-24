"""Reconstruct code-only, hash-pinned Draft composition from local Git objects."""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath


def require(value, reason):
    if not value:
        raise ValueError(reason)


def relative(value):
    require(isinstance(value, str) and value, "RELATIVE_SOURCE_PATH")
    path = PurePosixPath(value)
    require(
        not path.is_absolute() and path.as_posix() == value and ".." not in path.parts,
        "RELATIVE_SOURCE_PATH",
    )
    require(
        path.parts[0] in {"src", "scripts", "configs", "tests", "frontend", "docs"}
        and path.suffix not in {".blend", ".png", ".jpg", ".mp4", ".pt", ".pth", ".gguf"}
        and not {"gt", "ground_truth", "private_evaluation", ".git"}.intersection(path.parts),
        "CODE_ONLY_SOURCE_REQUIRED",
    )
    return value


def git_bytes(repo, commit, path):
    require(
        isinstance(commit, str) and re.fullmatch("[0-9a-f]{40}", commit), "FULL_GIT_COMMIT_REQUIRED"
    )
    relative(path)
    value = subprocess.check_output(["git", "show", commit + ":" + path], cwd=repo)
    require(len(value) <= 4_194_304, "SOURCE_FILE_TOO_LARGE")
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def rebuild(repo, composition, output, *, loader=git_bytes):
    require(
        composition.get("scope") == "ENGINEERING_COMPOSITION_NOT_INTEGRATED_PRODUCT",
        "COMPOSITION_SCOPE",
    )
    rows = composition.get("files")
    require(isinstance(rows, dict) and 0 < len(rows) <= 2000, "COMPOSITION_FILES")
    repo, output = Path(repo).resolve(), Path(output)
    require(
        output.is_absolute()
        and output.resolve() == output
        and output.parent.is_dir()
        and not output.exists()
        and not output.is_relative_to(repo),
        "NEW_EXTERNAL_CANONICAL_OUTPUT",
    )
    require(shutil.disk_usage(output.parent).free >= 8 * 1024**3, "DISK_SPACE_BELOW_8_GIB")
    # Validate every path and pin before creating a partial destination.
    for name, row in rows.items():
        relative(name)
        require(
            isinstance(row, dict) and re.fullmatch("[0-9a-f]{64}", row.get("sha256", "")),
            "SOURCE_PIN_REQUIRED",
        )
    output.mkdir(mode=0o700)
    for name, row in rows.items():
        if row.get("commit"):
            raw = loader(repo, row["commit"], name)
        else:
            require(
                row.get("derivation") == "BASE_PLUS_T1_T2_T3_T4_APPEND_ONLY_SUFFIXES"
                and name == "frontend/workbench-v2/style.css",
                "EXPLICIT_DERIVATION_REQUIRED",
            )
            base = loader(repo, composition["base"], name)
            raw = base
            require(len(row["inputs"]) == 4, "CSS_INPUTS")
            for item in row["inputs"]:
                value = loader(repo, item["commit"], item["path"])
                require(
                    item["path"] == name
                    and digest(value) == item["sha256"]
                    and value.startswith(base),
                    "CSS_APPEND_ONLY_PIN",
                )
                raw += value[len(base) :]
        require(digest(raw) == row["sha256"], "SOURCE_FILE_PIN_MISMATCH:" + name)
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    return {
        "status": "COMPLETE",
        "files": len(rows),
        "integrated_product": False,
        "git_checkout_changed": False,
        "model_calls": 0,
    }
