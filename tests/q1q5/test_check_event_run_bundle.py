"""CX-7-T: artificial pixels/metadata only; no rendering or original assets.

The external TEST-ONLY contract is not a production schema or human approval.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_event_run_bundle.py"
FREEZE = ROOT / "docs/history/R004_CAMERA_CATALOG_FREEZE_D84_20261027.json"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(doc):
    return (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode()


def save(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(doc))


def png():
    def chunk(kind, raw):
        return struct.pack(">I", len(raw)) + kind + raw + struct.pack(">I", zlib.crc32(kind + raw))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + b"\x20\x40\x60" * 4) * 4))
            + chunk(b"IEND", b""))


def clock(run_id, clock_id, duration, hour):
    doc = dict(schema_version="q-demo.clock-mapping.v1", run_id=run_id, clock_id=clock_id,
               timezone="Asia/Taipei", wall_origin=f"2026-11-01T{hour}:00:00+08:00",
               mapping_kind="DECLARED_DEMO_CLOCK", mapping_version="SYNTHETIC_ONLY",
               t0_us=0, rate=1, source_duration_us=duration,
               declaration_source="SYNTHETIC_ONLY", declared_by="SYNTHETIC_ONLY",
               declared_at="2026-10-29T14:00:00+08:00")
    doc["content_sha256"] = digest(json.dumps(doc, sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=True).encode())
    return doc


def seal_clock(doc):
    doc = {k: v for k, v in doc.items() if k != "content_sha256"}
    doc["content_sha256"] = digest(json.dumps(doc, sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=True).encode())
    return doc


def fixture(tmp_path, profile="l2"):
    home = tmp_path / "SYNTHETIC"
    safe = home / "bundle/safe_bundle"
    safe.mkdir(parents=True)
    graph_hash = digest(b"SYNTHETIC graph bytes")
    scopes = []
    for n, (label, duration, cameras) in enumerate(
        [("A4-1", 50_000_000, ["CAM_A", "CAM_B"]),
         ("B4-1", 42_000_000, ["CAM_C", "CAM_D"])] if profile == "r004-a4b4"
        else [("L2", 1_000_000, ["CAM_L", "CAM_R"])], start=1
    ):
        run_id = f"SYNTHETIC_{label}"
        c = clock(run_id, "clock:" + run_id, duration, f"{13 + n:02d}")
        save(safe / f"clocks/{label}.json", c)
        frames = []
        for camera in cameras:
            for i in range(duration * 5 // 1_000_000):
                filename = f"rgb/{run_id}/{camera}/frame_{i:06d}.png"
                path = safe / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png())
                frames.append(dict(camera_id=camera, frame_index=i, filename=filename,
                                   file_sha256=digest(png())))
        run = dict(fixture_role="SYNTHETIC_ONLY", run_id=run_id, label=label,
                   catalog_sha256=json.loads(FREEZE.read_bytes())["catalog_sha256"],
                   clock_ref=f"clocks/{label}.json", sampling={"fps": 5},
                   camera_ids=cameras, frames=frames)
        save(safe / f"runs/{label}.json", run)
        scopes.append(dict(run_id=run_id, label=label, camera_ids=cameras,
                           source_duration_us=duration, fps=5))
    plan = dict(fixture_role="SYNTHETIC_ONLY", state="FROZEN_SYNTHETIC",
                profile=profile, runs=scopes, graph_sha256=graph_hash)
    save(home / "frozen.json", plan)
    save(home / "authorization.json", dict(fixture_role="SYNTHETIC_ONLY",
         reference="SYNTHETIC:D-CX7T", frozen_plan_sha256=digest(encode(plan))))
    save(home / "g4.json", dict(fixture_role="SYNTHETIC_ONLY", decision="APPROVED",
         graph_sha256=graph_hash, frozen_plan_sha256=digest(encode(plan))))
    df = "Filesystem 1024-blocks Used Available Capacity Mounted on\nSYNTHETIC 30000000 1000000 29000000 4% /SYNTHETIC\n"
    receipt = dict(fixture_role="SYNTHETIC_ONLY", profile=profile,
                   frozen_plan_sha256=digest(encode(plan)), authorization_ref="SYNTHETIC:D-CX7T",
                   graph_sha256=graph_hash, g4_receipt_sha256=digest((home / "g4.json").read_bytes()),
                   before_df_k=df, after_df_k=df)
    save(home / "receipt.json", receipt)
    contract = dict(fixture_role="SYNTHETIC_ONLY", projection="SYNTHETIC_EVENT_BUNDLE_V1",
                    profile=profile, frozen_plan={"filename": "frozen.json", "file_sha256": digest(encode(plan))},
                    authorization={"filename": "authorization.json", "file_sha256": digest((home / "authorization.json").read_bytes())},
                    g4={"filename": "g4.json", "file_sha256": digest((home / "g4.json").read_bytes())})
    save(home / "contract.json", contract)
    reseal(home)
    return home


def reseal(home):
    """Re-pin mechanical mutations so a negative does not pass only via old SHA."""
    safe = home / "bundle/safe_bundle"
    files = {p.relative_to(safe).as_posix(): digest(p.read_bytes())
             for p in safe.rglob("*") if p.is_file() and p.name != "manifest.json"}
    manifest = dict(fixture_role="SYNTHETIC_ONLY", files=files,
                    runs=[name for name in sorted(files) if name.startswith("runs/")])
    save(safe / "manifest.json", manifest)
    receipt = json.loads((home / "receipt.json").read_bytes())
    receipt["safe_manifest_sha256"] = digest(encode(manifest))
    save(home / "receipt.json", receipt)
    contract = json.loads((home / "contract.json").read_bytes())
    contract["receipt_file_sha256"] = digest(encode(receipt))
    save(home / "contract.json", contract)


def checker():
    if not SCRIPT.is_file():
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("CX7T_IMPLEMENTATION_MISSING")
        pytest.skip("CX7T_IMPLEMENTATION_MISSING")
    spec = importlib.util.spec_from_file_location("event_bundle_checker", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(home, **kwargs):
    return checker().inspect_bundle(
        home / "bundle", home / "receipt.json",
        profile=json.loads((home / "contract.json").read_bytes())["profile"],
        contract_path=home / "contract.json",
        contract_sha256=digest((home / "contract.json").read_bytes()), **kwargs)


def mutate(home, relative, change):
    path = home / relative
    doc = json.loads(path.read_bytes())
    change(doc)
    save(path, doc)
    reseal(home)


@pytest.mark.parametrize("profile,expected_frames", [("l2", 10), ("r004-a4b4", 920)])
def test_synthetic_positive_is_only_mechanical(profile, expected_frames, tmp_path):
    home = fixture(tmp_path, profile)
    result = inspect(home)
    assert result["status"] == "SYNTHETIC_VALID"
    assert result["frame_count"] == expected_frames
    assert result["authority_verified"] is False
    assert result["render_authorized"] is False
    assert result["formal_run_allowed"] is False


@pytest.mark.parametrize("field", ["contract_path", "contract_sha256"])
def test_no_selected_contract_fails_closed(tmp_path, field):
    home = fixture(tmp_path)
    args = dict(contract_path=home / "contract.json",
                contract_sha256=digest((home / "contract.json").read_bytes()))
    args[field] = None
    result = checker().inspect_bundle(home / "bundle", home / "receipt.json", profile="l2", **args)
    assert result["status"] == "FAIL" and result["code"] == "CONTRACT_UNSELECTED"


@pytest.mark.parametrize("change,code", [
    (lambda d: d["frames"].pop(), "FRAME_GRID_INCOMPLETE"),
    (lambda d: d["frames"][1].update(frame_index=0), "FRAME_GRID_INCOMPLETE"),
    (lambda d: d["sampling"].update(fps=4), "FROZEN_RUN_SCOPE_MISMATCH"),
    (lambda d: d["frames"][0].update(filename="../private/image.png"), "SAFE_PATH_REJECTED"),
])
def test_frame_grid_and_safe_references(tmp_path, change, code):
    home = fixture(tmp_path)
    mutate(home, "bundle/safe_bundle/runs/L2.json", change)
    assert inspect(home)["code"] == code


def test_missing_frame_and_wrong_file_bytes_fail(tmp_path):
    home = fixture(tmp_path)
    frame = next((home / "bundle/safe_bundle/rgb").rglob("*.png"))
    frame.unlink()
    assert inspect(home)["code"] == "FILE_MISSING"
    frame.write_bytes(png() + b"tamper")
    assert inspect(home)["code"] == "FILE_SHA256_MISMATCH"


@pytest.mark.parametrize("key", ["timezone", "wall_origin", "t0_us", "source_duration_us", "content_sha256"])
def test_clock_required_fields(tmp_path, key):
    home = fixture(tmp_path)
    mutate(home, "bundle/safe_bundle/clocks/L2.json", lambda d: d.pop(key))
    assert inspect(home)["code"] == "CLOCK_INVALID"


@pytest.mark.parametrize("change", [
    lambda d: d.update(content_sha256="0" * 64),
    lambda d: d.update(mapping_kind="WALL_GUESS"),
    lambda d: d.update(timezone="UNKNOWN"),
    lambda d: d.update(wall_origin="2026-11-01T14:00:00"),
])
def test_invalid_clock_declaration(tmp_path, change):
    home = fixture(tmp_path)
    mutate(home, "bundle/safe_bundle/clocks/L2.json", change)
    assert inspect(home)["code"] == "CLOCK_INVALID"


def test_two_runs_cannot_reuse_clock_id(tmp_path):
    home = fixture(tmp_path, "r004-a4b4")
    path = home / "bundle/safe_bundle/clocks/B4-1.json"
    doc = json.loads(path.read_bytes())
    doc["clock_id"] = "clock:SYNTHETIC_A4-1"
    save(path, seal_clock(doc))
    reseal(home)
    assert inspect(home)["code"] == "CLOCK_REUSED"


def test_r004_uses_full_d84_catalog_pin(tmp_path):
    home = fixture(tmp_path, "r004-a4b4")
    mutate(home, "bundle/safe_bundle/runs/A4-1.json", lambda d: d.update(catalog_sha256="3eba857"))
    assert inspect(home)["code"] == "CATALOG_FREEZE_MISMATCH"


def test_r004_duration_cannot_be_changed_even_with_resealed_plan(tmp_path):
    home = fixture(tmp_path, "r004-a4b4")
    doc = json.loads((home / "frozen.json").read_bytes())
    doc["runs"][0]["source_duration_us"] = 1_000_000
    save(home / "frozen.json", doc)
    repin_external(home, "frozen_plan", "frozen.json")
    assert inspect(home)["code"] == "R004_D89_SCOPE_MISMATCH"


def repin_external(home, key, filename):
    contract = json.loads((home / "contract.json").read_bytes())
    contract[key]["file_sha256"] = digest((home / filename).read_bytes())
    save(home / "contract.json", contract)


def test_l2_scope_is_read_from_frozen_plan(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "bundle/safe_bundle/runs/L2.json", lambda d: d.update(camera_ids=["CAM_L"]))
    assert inspect(home)["code"] == "FROZEN_RUN_SCOPE_MISMATCH"


def test_l2_duration_is_read_from_frozen_plan(tmp_path):
    home = fixture(tmp_path)
    path = home / "bundle/safe_bundle/clocks/L2.json"
    doc = json.loads(path.read_bytes())
    doc["source_duration_us"] = 2_000_000
    save(path, seal_clock(doc))
    reseal(home)
    assert inspect(home)["code"] == "FROZEN_RUN_SCOPE_MISMATCH"


def test_authorization_producer_declaration_cannot_replace_external_scope(tmp_path):
    home = fixture(tmp_path)
    doc = json.loads((home / "authorization.json").read_bytes())
    doc["frozen_plan_sha256"] = "0" * 64
    save(home / "authorization.json", doc)
    repin_external(home, "authorization", "authorization.json")
    assert inspect(home)["code"] == "AUTHORIZATION_SCOPE_MISMATCH"


def test_modified_d84_receipt_cannot_redefine_the_frozen_catalog(tmp_path, monkeypatch):
    home = fixture(tmp_path, "r004-a4b4")
    path = home / "modified_catalog_freeze.json"
    save(path, {"catalog_sha256": "0" * 64})
    module = checker()
    monkeypatch.setattr(module, "D84_RECEIPT", path)
    result = module.inspect_bundle(home / "bundle", home / "receipt.json", profile="r004-a4b4",
        contract_path=home / "contract.json", contract_sha256=digest((home / "contract.json").read_bytes()))
    assert result["code"] == "D84_RECEIPT_PIN_MISMATCH"


@pytest.mark.parametrize("name", ["trajectory.json", "visibility.json", "depth.png", "actor.json", "script.json", "GT.json"])
def test_prohibited_safe_filenames(tmp_path, name):
    home = fixture(tmp_path)
    save(home / "bundle/safe_bundle" / name, {})
    reseal(home)
    assert inspect(home)["code"] == "PRIVATE_CONTENT_IN_SAFE"


@pytest.mark.parametrize("key", ["trajectory", "visibility", "depth", "actor_id", "script_ref", "GT"])
def test_nested_private_json_keys_fail(tmp_path, key):
    home = fixture(tmp_path)
    mutate(home, "bundle/safe_bundle/runs/L2.json", lambda d: d.update(extra={key: []}))
    assert inspect(home)["code"] == "PRIVATE_CONTENT_IN_SAFE"


def test_unlisted_file_and_symlink_fail(tmp_path):
    home = fixture(tmp_path)
    extra = home / "bundle/safe_bundle/extra.json"
    save(extra, {})
    assert inspect(home)["code"] == "SAFE_FILE_SET_MISMATCH"
    extra.unlink()
    extra.symlink_to(home / "g4.json")
    assert inspect(home)["code"] == "SYMLINK_REJECTED"


def test_safe_manifest_private_reference_is_never_followed(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "bundle/safe_bundle/runs/L2.json", lambda d: d.update(clock_ref="../private/clock.json"))
    assert inspect(home)["code"] == "SAFE_PATH_REJECTED"


@pytest.mark.parametrize("extra", [
    {"extra_ref": "../private/secret.json"},
    {"nested": {"reference": "../private/secret.json"}},
    {"nested": {"paths": ["/SYNTHETIC/private/secret.json"]}},
    {"filename": "private/secret.json"},
])
def test_extra_safe_manifest_reference_cannot_escape(tmp_path, extra):
    home = fixture(tmp_path)
    manifest = home / "bundle/safe_bundle/manifest.json"
    doc = json.loads(manifest.read_bytes())
    doc.update(extra)
    save(manifest, doc)
    receipt = json.loads((home / "receipt.json").read_bytes())
    receipt["safe_manifest_sha256"] = digest(manifest.read_bytes())
    save(home / "receipt.json", receipt)
    contract = json.loads((home / "contract.json").read_bytes())
    contract["receipt_file_sha256"] = digest((home / "receipt.json").read_bytes())
    save(home / "contract.json", contract)
    assert inspect(home)["code"] == "SAFE_PATH_REJECTED"


def test_g4_missing_and_producer_approved_alone_fail(tmp_path):
    home = fixture(tmp_path, "r004-a4b4")
    (home / "g4.json").unlink()
    assert inspect(home)["code"] == "G4_RECEIPT_MISSING"
    save(home / "g4.json", {"decision": "APPROVED"})
    assert inspect(home)["code"] == "EXTERNAL_PIN_MISMATCH"


@pytest.mark.parametrize("field", ["graph_sha256", "frozen_plan_sha256"])
def test_g4_scope_mismatch_rejected_after_repin(tmp_path, field):
    home = fixture(tmp_path, "r004-a4b4")
    doc = json.loads((home / "g4.json").read_bytes())
    doc[field] = "0" * 64
    save(home / "g4.json", doc)
    repin_external(home, "g4", "g4.json")
    assert inspect(home)["code"] == "G4_SCOPE_MISMATCH"


@pytest.mark.parametrize("field,code", [("frozen_plan_sha256", "FROZEN_PLAN_REFERENCE_MISSING"),
                                       ("authorization_ref", "AUTHORIZATION_SOURCE_MISSING")])
def test_receipt_requires_freeze_and_authorization(tmp_path, field, code):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d.pop(field))
    assert inspect(home)["code"] == code


@pytest.mark.parametrize("field", ["before_df_k", "after_df_k"])
@pytest.mark.parametrize("available,expected", [(8 * 1024 * 1024, "SYNTHETIC_VALID"),
                                               (8 * 1024 * 1024 - 1, "DISK_BELOW_8_GIB")])
def test_disk_threshold_is_kib_not_decimal_gb(tmp_path, field, available, expected):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d.update({field:
        f"Filesystem 1024-blocks Used Available Capacity Mounted on\nSYNTHETIC 30000000 1000000 {available} 4% /SYNTHETIC\n"}))
    result = inspect(home)
    assert result.get("code", result["status"]) == expected


@pytest.mark.parametrize("text", ["", "Available 999999999", "Filesystem 512-blocks Used Available\nx 1 1 99999999", "Filesystem 1024-blocks Used Available\nx 1 1 -1", "Filesystem 1024-blocks Used Available\nx 1 1 99999999\ny 1 1 99999999"])
def test_missing_or_ambiguous_df_k_fails(tmp_path, text):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d.update(before_df_k=text))
    assert inspect(home)["code"] == "DF_K_INVALID"


def test_unknown_projection_or_production_role_fails_closed(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "contract.json", lambda d: d.update(projection="future-production-wire"))
    assert inspect(home)["code"] == "CONTRACT_UNSELECTED"
    mutate(home, "contract.json", lambda d: d.update(projection="SYNTHETIC_EVENT_BUNDLE_V1", fixture_role="ACTUAL_BLENDER"))
    assert inspect(home)["code"] == "CONTRACT_UNSELECTED"


def test_cli_exit_codes_and_plain_default_fail_closed(tmp_path):
    home = fixture(tmp_path)
    command = [sys.executable, str(SCRIPT), "--profile", "l2", "--bundle", str(home / "bundle"),
               "--receipt", str(home / "receipt.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1 and json.loads(result.stdout)["code"] == "CONTRACT_UNSELECTED"
    result = subprocess.run(command + ["--contract-options", str(home / "contract.json"),
                            "--contract-sha256", digest((home / "contract.json").read_bytes())],
                            capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)["authority_verified"] is False


def test_cli_accepts_relative_selected_paths_without_resolving_symlinks(tmp_path):
    home = fixture(tmp_path)
    command = [sys.executable, str(SCRIPT), "--profile", "l2", "--bundle", "bundle",
               "--receipt", "receipt.json", "--contract-options", "contract.json",
               "--contract-sha256", digest((home / "contract.json").read_bytes())]
    result = subprocess.run(command, cwd=home, capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)["status"] == "SYNTHETIC_VALID"
    (home / "linked-contract.json").symlink_to(home / "contract.json")
    command[command.index("contract.json")] = "linked-contract.json"
    result = subprocess.run(command, cwd=home, capture_output=True, text=True)
    assert result.returncode == 1 and json.loads(result.stdout)["code"] == "SYMLINK_REJECTED"


def test_duplicate_json_keys_are_rejected(tmp_path):
    home = fixture(tmp_path)
    path = home / "bundle/safe_bundle/extra.json"
    path.write_text('{"x": 1, "x": 2}')
    reseal(home)
    assert inspect(home)["code"] == "DUPLICATE_JSON_KEY"
