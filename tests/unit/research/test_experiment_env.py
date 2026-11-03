"""amidst.experiment-env.v1 schema and validator. SYNTHETIC manifests only; no real run is read."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'scripts/research'))
import experiment_env as env  # noqa: E402

EXAMPLE = REPO / 'docs/contracts/examples/amidst.experiment-env.v1.example.json'


@pytest.fixture
def manifest():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


def test_example_is_valid_and_hash_is_stable(manifest):
    assert env.validate(manifest) == []
    assert env.canonical_sha256(manifest) == env.canonical_sha256(json.loads(json.dumps(manifest, sort_keys=True)))
    assert manifest['source_class'] == 'SYNTHETIC' and manifest['parameter_set']['status'] == 'PROPOSED'


def mutate(manifest, path, value):
    m = copy.deepcopy(manifest)
    node = m
    for key in path[:-1]:
        node = node[key]
    if value is KeyError:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return m


@pytest.mark.parametrize('path,value', [
    (('gt_isolation', 'inference_read_gt'), True),
    (('gt_isolation', 'inference_read_gt'), KeyError),
    (('run', 'git_commit'), 'main'),
    (('parameter_set', 'status'), 'MAYBE'),
    (('source_class',), 'REAL'),
    (('seeds', 'random_seed'), '20261102'),
    (('seeds',), KeyError),
    (('runtime', 'node_version'), KeyError),
    (('data_sources', 0, 'locator'), '/Users/someone/data.json'),
    (('data_sources', 0, 'locator'), 'gt_private/x.json'),
    (('data_sources', 0, 'locator'), '../x.json'),
    (('data_sources', 0, 'sha256'), 'abc'),
    (('run', 'started_at_utc'), '2026-01-01 00:00:00'),
    (('hardware', 'accelerator'), 'tpu'),
])
def test_schema_rejects(manifest, path, value):
    assert env.validate(mutate(manifest, path, value)) != []


def test_unknown_is_allowed_where_defined_never_for_gt_declaration(manifest):
    m = mutate(manifest, ('hardware', 'ram_gib'), 'UNKNOWN')
    assert env.validate(m) == []
    assert env.validate(mutate(manifest, ('gt_isolation', 'inference_read_gt'), 'UNKNOWN')) != []


def test_approved_needs_reference_and_hash(manifest):
    m = mutate(manifest, ('parameter_set', 'status'), 'APPROVED')
    assert any('approval_ref' in e for e in env.validate(m))
    m['parameter_set']['approval_ref'] = '#93'
    assert env.validate(m) == []
    m['parameter_set']['parameter_set_sha256'] = 'UNKNOWN'
    assert any('parameter_set_sha256' in e for e in env.validate(m))


def test_formal_requires_known_commit_hash_and_passed_gt_scan(manifest):
    m = mutate(manifest, ('source_class',), 'FORMAL')
    assert any('gt_path_scan PASS' in e for e in env.validate(m))
    m['gt_isolation']['gt_path_scan'] = 'PASS'
    assert env.validate(m) == []
    m['run']['git_commit'] = 'UNKNOWN'
    assert any('git_commit' in e for e in env.validate(m))


def test_failed_gt_scan_and_time_order_are_rejected(manifest):
    assert any('FAIL' in e for e in env.validate(mutate(manifest, ('gt_isolation', 'gt_path_scan'), 'FAIL')))
    assert any('before' in e for e in env.validate(mutate(manifest, ('run', 'finished_at_utc'), '2025-01-01T00:00:00Z')))


def test_cli_prints_hash(tmp_path):
    out = subprocess.run([sys.executable, str(REPO / 'scripts/research/experiment_env.py'), str(EXAMPLE)],
                         capture_output=True, text=True, check=True).stdout
    assert out.startswith('VALID env_manifest_sha256=') and 'PROPOSED' in out
