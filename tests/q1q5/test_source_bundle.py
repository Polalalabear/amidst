"""Source reconstruction must fail on tampered bytes or unsafe destinations."""

from types import SimpleNamespace

import pytest

from amidst.q1q5.source_bundle import digest, rebuild


def composition():
    return {
        "scope": "ENGINEERING_COMPOSITION_NOT_INTEGRATED_PRODUCT",
        "base": "a" * 40,
        "files": {"src/example.py": {"commit": "a" * 40, "sha256": digest(b"print(1)\n")}},
    }


def test_reconstruction_exact_and_never_overwrites(tmp_path):
    doc = composition()
    output = tmp_path / "new"
    assert rebuild(tmp_path / "repo", doc, output, loader=lambda *a: b"print(1)\n")["files"] == 1
    assert (output / "src/example.py").read_bytes() == b"print(1)\n"
    with pytest.raises(ValueError):
        rebuild(tmp_path / "repo", doc, output)


@pytest.mark.parametrize(
    "name",
    [
        "../other.py",
        "/tmp/other.py",
        ".git/config",
        "data/gt.json",
        "src/a/../../escape.py",
        "src/a.png",
        "src/ground_truth/labels.json",
    ],
)
def test_invalid_paths_are_rejected_before_creating_destination(tmp_path, name):
    doc = composition()
    doc["files"][name] = doc["files"].pop("src/example.py")
    output = tmp_path / "new"
    with pytest.raises(ValueError):
        rebuild(tmp_path / "repo", doc, output)
    assert not output.exists()


def test_modified_git_bytes_cannot_return_complete(tmp_path):
    with pytest.raises(ValueError, match="PIN_MISMATCH"):
        rebuild(tmp_path / "repo", composition(), tmp_path / "new", loader=lambda *a: b"print(2)\n")


def test_css_reconstructs_only_pinned_append_only_inputs(tmp_path):
    values = {
        "a" * 40: b"base",
        "b" * 40: b"base1",
        "c" * 40: b"base2",
        "d" * 40: b"base3",
        "e" * 40: b"base4",
    }
    row = {
        "commit": None,
        "derivation": "BASE_PLUS_T1_T2_T3_T4_APPEND_ONLY_SUFFIXES",
        "inputs": [
            dict(commit=k, path="frontend/workbench-v2/style.css", sha256=digest(v))
            for k, v in list(values.items())[1:]
        ],
        "sha256": digest(b"base1234"),
    }
    doc = composition()
    doc["files"] = {"frontend/workbench-v2/style.css": row}
    rebuild(
        tmp_path / "repo", doc, tmp_path / "yes", loader=lambda repo, commit, path: values[commit]
    )
    assert (tmp_path / "yes/frontend/workbench-v2/style.css").read_bytes() == b"base1234"
    values["e" * 40] = b"changed"
    with pytest.raises(ValueError, match="APPEND_ONLY"):
        rebuild(
            tmp_path / "repo",
            doc,
            tmp_path / "no",
            loader=lambda repo, commit, path: values[commit],
        )


@pytest.mark.parametrize("name", ["pyproject.toml", "uv.lock"])
def test_explicit_root_dependency_files_are_supported(tmp_path, name):
    doc = composition()
    doc["files"][name] = doc["files"].pop("src/example.py")
    rebuild(tmp_path / "repo", doc, tmp_path / "new", loader=lambda *a: b"print(1)\n")
    assert (tmp_path / "new" / name).read_bytes() == b"print(1)\n"


def test_low_disk_does_not_create_destination(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.disk_usage", lambda _: SimpleNamespace(free=8 * 1024**3 - 1))
    with pytest.raises(ValueError, match="DISK"):
        rebuild(tmp_path / "repo", composition(), tmp_path / "new")
    assert not (tmp_path / "new").exists()
