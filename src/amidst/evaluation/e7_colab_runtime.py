"""E7 Colab runtime helpers (#766): version consistency, zip pack, resumable checkpoints, run packaging.

Pure-Python (stdlib only), no model/GT access. The notebook calls these so the logic is unit-tested on Mac.
Decider code never reads answer tables; this module only moves files and records provenance.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import zipfile
from importlib import metadata
from pathlib import Path
from typing import Any

from amidst.evaluation.e7_decider_eval import sha256_file

CHECKPOINT_SCHEMA = "e7_group_checkpoint_v1"

# pip distribution name -> importable module name
_IMPORT_NAME = {"huggingface_hub": "huggingface_hub", "safetensors": "safetensors", "torch": "torch",
                "torchvision": "torchvision", "transformers": "transformers", "accelerate": "accelerate"}


def _norm_version(v: str) -> str:
    """``2.7.1+cu126`` -> ``2.7.1`` (local build tag is not a different release)."""
    return str(v).split("+", 1)[0].strip()


def parse_pins(pinned_deps: list[str]) -> dict[str, str]:
    """``["torch==2.7.1", ...]`` -> ``{"torch": "2.7.1"}``. Only exact ``==`` pins are allowed."""
    pins: dict[str, str] = {}
    for spec in pinned_deps:
        m = re.fullmatch(r"\s*([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.!+\-]+)\s*", spec)
        if not m:
            raise ValueError(f"PIN_NOT_EXACT: {spec!r} (only name==version pins are allowed)")
        pins[m.group(1).replace("-", "_")] = m.group(2)
    return pins


def check_runtime_versions(
    pins: dict[str, str],
    *,
    disk_versions: dict[str, str | None],
    loaded_versions: dict[str, str | None],
) -> list[str]:
    """Return human-readable problems; empty list == memory and disk both match the pins.

    * disk != pin  -> pip did not install the pin (stop).
    * loaded in memory != pin (module already imported before the install) -> restart required.
    """
    problems: list[str] = []
    for name, want in sorted(pins.items()):
        disk = disk_versions.get(name)
        if disk is None or _norm_version(disk) != want:
            problems.append(f"{name}: installed on disk={disk!r}, pinned={want!r} (pip install did not produce the pin)")
        mem = loaded_versions.get(name)
        if mem is not None and _norm_version(mem) != want:
            problems.append(
                f"{name}: already imported in this runtime as {mem!r}, pinned={want!r}. "
                "重啟 runtime 後再 Run All (Runtime > Restart session, then Run All)."
            )
    return problems


def collect_versions(pins: dict[str, str]) -> tuple[dict[str, str | None], dict[str, str | None]]:
    """(disk_versions, loaded_versions) for each pinned package, read from importlib.metadata / sys.modules."""
    disk: dict[str, str | None] = {}
    loaded: dict[str, str | None] = {}
    for name in pins:
        try:
            disk[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            disk[name] = None
        mod = sys.modules.get(_IMPORT_NAME.get(name, name))
        loaded[name] = getattr(mod, "__version__", None) if mod is not None else None
    return disk, loaded


def assert_runtime_consistent(pinned_deps: list[str]) -> dict[str, Any]:
    """CELL 2 gate. Raises RuntimeError with the restart instruction on any mismatch."""
    pins = parse_pins(pinned_deps)
    disk, loaded = collect_versions(pins)
    problems = check_runtime_versions(pins, disk_versions=disk, loaded_versions=loaded)
    if problems:
        raise RuntimeError("STOP: runtime/package version mismatch:\n  - " + "\n  - ".join(problems))
    return {"pins": pins, "disk": disk, "loaded": loaded}


def check_min_versions(minimums: dict[str, str]) -> dict[str, str | None]:
    """Record (never change) numpy/Pillow-style runtime packages; raise if below a minimum."""
    def key(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in re.findall(r"\d+", _norm_version(v))[:3])

    seen: dict[str, str | None] = {}
    for name, floor in minimums.items():
        try:
            v = metadata.version(name)
        except metadata.PackageNotFoundError:
            v = None
        seen[name] = v
        mod = sys.modules.get({"Pillow": "PIL"}.get(name, name))
        mem = getattr(mod, "__version__", None) if mod is not None else None
        if v is not None and mem is not None and _norm_version(mem) != _norm_version(v):
            raise RuntimeError(f"STOP: {name} in memory {mem} != installed {v}. 重啟 runtime 後再 Run All (restart, then Run All).")
        if v is None or key(v) < key(floor):
            raise RuntimeError(f"STOP: {name}=={v} is below the required minimum {floor} (runtime is left unchanged on purpose).")
    return seen


# --------------------------------------------------------------------------- zip upload pack
def make_pack_zip(pack_root: Path, zip_path: Path) -> dict[str, str]:
    """Mac side: zip ``pack_root`` (stored, no compression; PNG already compressed) and write ``<zip>.sha256``.

    ``PACK_INFO.json`` cannot hold the zip's own SHA-256 (circular), so the digest goes to the sidecar file
    ``<zip name>.sha256`` (``<hex>  <zip name>``) and into the run's RUN_NOTES.
    """
    root = Path(pack_root)
    if not (root / "MANIFEST.sha256").is_file():
        raise FileNotFoundError(f"MANIFEST_MISSING: {root / 'MANIFEST.sha256'}")
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(root).as_posix())
    digest = sha256_file(zip_path)
    side = zip_path.with_name(zip_path.name + ".sha256")
    side.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return {"zip": str(zip_path), "zip_sha256": digest, "sidecar": str(side)}


def extract_pack_zip(zip_path: Path, dest: Path, *, expected_sha256: str | None = None) -> dict[str, Any]:
    """Colab side: verify the zip (sidecar or given digest), unzip into ``dest`` (local disk), return the pack root.

    Refuses path traversal. The caller then runs ``verify_manifest_sha256(pack_root)`` (file-level check on fast local disk).
    """
    zip_path, dest = Path(zip_path), Path(dest)
    if not zip_path.is_file():
        raise FileNotFoundError(f"PACK_ZIP_MISSING: {zip_path}")
    actual = sha256_file(zip_path)
    exp = expected_sha256
    side = zip_path.with_name(zip_path.name + ".sha256")
    if exp is None and side.is_file():
        exp = side.read_text(encoding="utf-8").split()[0].lower()
    if exp is not None and exp.lower() != actual:
        raise RuntimeError(f"PACK_ZIP_SHA_MISMATCH: expected={exp} actual={actual}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            try:
                (dest / name).resolve().relative_to(dest_resolved)
            except ValueError as exc:
                raise RuntimeError(f"PACK_ZIP_PATH_TRAVERSAL: {name!r}") from exc
        zf.extractall(dest)
    root = dest
    if not (root / "MANIFEST.sha256").is_file():
        subs = [d for d in dest.iterdir() if d.is_dir() and (d / "MANIFEST.sha256").is_file()]
        if len(subs) != 1:
            raise FileNotFoundError(f"MANIFEST_MISSING_IN_ZIP: {zip_path.name}")
        root = subs[0]
    return {"pack_root": root, "zip_sha256": actual, "sha256_checked_against": "sidecar/argument" if exp else "NONE (no sidecar)"}


# --------------------------------------------------------------------------- resumable checkpoints
def run_fingerprint(*, git_commit: str, dataset_scope: str, n_requests: int, smoke_mode: bool,
                    cpu_sample_cap: int | None, pinned_deps: list[str], run_unaccelerated: bool = True,
                    pack_manifest_sha256: str | None = None) -> dict[str, Any]:
    """Everything that must be equal for a checkpoint to be reusable."""
    fp = {"git_commit": git_commit, "dataset_scope": dataset_scope, "n_requests": n_requests,
          "smoke_mode": bool(smoke_mode), "cpu_sample_cap": cpu_sample_cap, "pinned_deps": sorted(pinned_deps)}
    if not run_unaccelerated:  # keys added only when non-default so earlier checkpoints stay valid
        fp["run_unaccelerated"] = False
    if pack_manifest_sha256:
        fp["pack_manifest_sha256"] = pack_manifest_sha256
    return fp


def checkpoint_path(output_dir: Path, party_id: str, mode: str) -> Path:
    return Path(output_dir) / "checkpoints" / f"{party_id}__{mode}.json"


def save_group_checkpoint(output_dir: Path, party_id: str, mode: str, result: dict[str, Any],
                          fingerprint: dict[str, Any]) -> Path:
    """Atomic write (tmp + rename) so a runtime that dies mid-write never leaves a half checkpoint."""
    path = checkpoint_path(output_dir, party_id, mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema_version": CHECKPOINT_SCHEMA, "party_id": party_id, "mode": mode,
           "saved_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "fingerprint": fingerprint, "result": result}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def load_group_checkpoint(output_dir: Path, party_id: str, mode: str, fingerprint: dict[str, Any]) -> dict[str, Any] | None:
    """Return the saved result if it exists, is readable and has the same fingerprint; else None (re-run the group)."""
    path = checkpoint_path(output_dir, party_id, mode)
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if doc.get("schema_version") != CHECKPOINT_SCHEMA or doc.get("fingerprint") != fingerprint:
        return None
    if doc.get("party_id") != party_id or doc.get("mode") != mode or not isinstance(doc.get("result"), dict):
        return None
    return doc["result"]


# --------------------------------------------------------------------------- RUN_NOTES + packaging
def build_run_notes(*, notebook_version: str, git_commit: str, python_version: str, pinned_deps: list[str],
                    versions: dict[str, Any], pack_zip_sha256: str | None, manifest_verification: dict[str, Any],
                    smoke_mode: bool, completed_groups: list[str], resumed_groups: list[str],
                    skipped_models: list[dict[str, Any]], hf_provenance: dict[str, Any],
                    deviations: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "e7_run_notes_v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notebook_version": notebook_version,
        "git_commit": git_commit,
        "python_version": python_version,
        "smoke_mode": bool(smoke_mode),
        "pinned_deps": list(pinned_deps),
        "package_versions": versions,
        "pack_zip_sha256": pack_zip_sha256 or "UNKNOWN",
        "manifest_verification": manifest_verification,
        "completed_groups": completed_groups,
        "resumed_from_checkpoint": resumed_groups,
        "skipped_models": skipped_models,
        "hf_provenance": hf_provenance,
        "deviations": list(deviations),
        "identity_status": "UNCONFIRMED",
    }


def package_run(output_dir: Path, run_name: str, notes: dict[str, Any], extra_files: list[Path] | None = None) -> dict[str, Any]:
    """Collect outputs + checkpoints + RUN_NOTES into ``<output_dir>/<run_name>/`` (with MANIFEST.sha256) and zip it."""
    out = Path(output_dir)
    run_dir = out / run_name
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    (run_dir / "RUN_NOTES.json").write_text(json.dumps(notes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cps = out / "checkpoints"
    if cps.is_dir():
        shutil.copytree(cps, run_dir / "checkpoints")
    for f in extra_files or []:
        f = Path(f)
        if f.is_file():
            shutil.copy2(f, run_dir / f.name)
    lines = [f"{sha256_file(p)}  {p.relative_to(run_dir).as_posix()}" for p in sorted(run_dir.rglob("*")) if p.is_file()]
    (run_dir / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    zip_path = out / f"{run_name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(run_dir.rglob("*")):
            if p.is_file():
                zf.write(p, f"{run_name}/{p.relative_to(run_dir).as_posix()}")
    return {"run_dir": str(run_dir), "zip": str(zip_path), "zip_sha256": sha256_file(zip_path), "files": len(lines)}


def main(argv: list[str] | None = None) -> int:
    """Mac CLI: ``python -m amidst.evaluation.e7_colab_runtime make-zip --pack-root P --zip Z`` (verifies the pack first)."""
    import argparse

    ap = argparse.ArgumentParser(description="E7 Colab upload-pack zip builder (#766).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("make-zip", help="gate the pack (verify-pack), zip it, write <zip>.sha256")
    z.add_argument("--pack-root", required=True, type=Path)
    z.add_argument("--zip", dest="zip_path", required=True, type=Path)
    z.add_argument("--requests-only", action="store_true", help="per-tick pack (#767): gate with verify_requests_only_pack (no answer table allowed)")
    args = ap.parse_args(argv)
    from amidst.evaluation.e7_scoring_bridge import verify_colab_pack_pre_upload, verify_requests_only_pack

    (verify_requests_only_pack if args.requests_only else verify_colab_pack_pre_upload)(args.pack_root)  # D385/D392 gate before anything leaves the Mac
    print(json.dumps(make_pack_zip(args.pack_root, args.zip_path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
