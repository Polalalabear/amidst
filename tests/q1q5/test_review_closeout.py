import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
spec = importlib.util.spec_from_file_location("closeout", SCRIPTS / "closeout_q1q5_review.py")
closeout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closeout)


def test_timeout_audit_preserves_repeated_calls_and_unknowns(tmp_path):
    p = tmp_path / "record.json"
    record = {
        "timeout_ms": 2000,
        "validation": "PROVIDER_TIMEOUT",
        "stats": {"latency_ms": 2003},
        "timed_out": True,
    }
    closeout.save(
        p, {"recorded_at": "2026-10-25T00:00:00+00:00", "q3_provider_audit": [record, record]}
    )
    config = {
        "expected_calls": 2,
        "files": [
            {
                "path": str(p),
                "sha256": closeout.sha(p.read_bytes()),
                "round": 1,
                "role": "api_recording",
            }
        ],
    }
    result = closeout.timeouts(config, tmp_path / "audit")
    assert result["summary"]["q3"]["calls"] == 2
    assert result["summary"]["q3"]["latency_p95_nearest_rank_ms"] == 2003
    assert all(r["load_duration_ms"] is None for r in result["calls"])
    config["expected_calls"] = 3
    with pytest.raises(ValueError, match="CALL_COUNT_MISMATCH"):
        closeout.timeouts(config, tmp_path / "wrong-count")


def test_pin_rejects_corruption_and_symlink(tmp_path):
    p = tmp_path / "source"
    p.write_bytes(b"original")
    expected = closeout.sha(p.read_bytes())
    assert closeout.pinned(p, expected) == b"original"
    p.write_bytes(b"changed")
    with pytest.raises(ValueError, match="FILE_HASH_MISMATCH"):
        closeout.pinned(p, expected)
    link = tmp_path / "link"
    link.symlink_to(p)
    with pytest.raises(ValueError, match="REGULAR_FILE_REQUIRED"):
        closeout.pinned(link, closeout.sha(p.read_bytes()))


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../../escape"])
def test_path_escape_rejected(name):
    with pytest.raises(ValueError, match="RELATIVE_PATH_REQUIRED"):
        closeout.relative(name)


def test_output_rejects_overwrite_and_low_disk(tmp_path, monkeypatch):
    p = tmp_path / "new"
    closeout.fresh(p)
    with pytest.raises(ValueError, match="OUTPUT_ALREADY_EXISTS"):
        closeout.fresh(p)
    from collections import namedtuple

    usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(closeout.shutil, "disk_usage", lambda _: usage(10, 9, 1))
    with pytest.raises(ValueError, match="DISK_BELOW_8_GIB"):
        closeout.fresh(tmp_path / "too-low")


def test_context_supplement_preserves_original_and_checks_binding(tmp_path):
    import json

    recording = tmp_path / "original"
    recording.mkdir()
    docs = {
        "case.request.json": {"schema_version": "q-demo.q1-request.v1"},
        "case.response.json": {"supported_classes_ref": "supported-classes:alias-pin"},
        "detection_index.json": {"detector": {"class_map": {"content_sha256": "class-pin"}}},
    }
    for name, value in docs.items():
        closeout.save(recording / name, value)
    hashes = {n: closeout.sha((recording / n).read_bytes()) for n in docs}
    aliases = tmp_path / "aliases.json"
    closeout.save(
        aliases,
        {
            "class_map_sha256": "class-pin",
            "content_sha256": "alias-pin",
            "class_labels": ["person"],
            "aliases": {"人": "person"},
            "color_vocabulary": {"labels": ["red"]},
        },
    )
    config = {
        "alias_sources": {
            "example": {"path": str(aliases), "sha256": closeout.sha(aliases.read_bytes())}
        },
        "cases": [
            {"id": "example-0", "pack": "example", "recorded": str(recording), "files": hashes}
        ],
    }
    result = closeout.context(config, tmp_path / "supplement")
    assert result["supplemented_q1_recordings"] == 1
    assert all(closeout.sha((recording / n).read_bytes()) == pin for n, pin in hashes.items())
    supported = json.loads((tmp_path / "supplement/example-0/supported_classes.json").read_text())
    assert supported["class_labels"] == ["person"]
    docs["detection_index.json"]["detector"]["class_map"]["content_sha256"] = "wrong"
    closeout.save(recording / "detection_index.json", docs["detection_index.json"])
    hashes["detection_index.json"] = closeout.sha((recording / "detection_index.json").read_bytes())
    with pytest.raises(ValueError, match="CLASS_MAP_BINDING_MISMATCH"):
        closeout.context(config, tmp_path / "wrong-scope")
