"""Response-version and time-origin boundaries for offline consumers only."""
import hashlib
import json
from pathlib import Path

RESPONSE_SCHEMAS = {
    kind: {f'q-demo.{name}-response.v{version}' for version in (1, 2)}
    for kind, name in [('q1', 'q1'), ('q2', 'q2'), ('q3', 'q3-parse')]
}
TIME_SOURCES = {'EXPLICIT_SOURCE', 'EXPLICIT_WALL', 'DEFAULT_SELECTED_RUN'}
V2_SCHEMA_SOURCE = '82798fbd100cdad230ca8eb8469dc51a0b91f842'
V2_SCHEMA_PINS = {
    'common.v2.schema.json': 'bbc998ed811cd1678e4e1544b8eed0e0183a45f43bd14711165c358604d65283',
    'q1-response.v2.schema.json': '664005cf267f3bf6e32f8e1d4b3441c21135948b5bc3a6703a45004e3b260f10',
    'q2-response.v2.schema.json': '718fa14a785fab6a107aa9e3e73fff5ba44f4c156229fd38b87d8682466b82eb',
    'q3-parse-response.v2.schema.json': '16cee077d86ddf2f32a88c9f6c1859352be4f54b28603496c97e0fd614e74483',
}


def response_schema_key(value, kind):
    """Unknown versions still reach a closed v1 schema and fail validation."""
    version = value.get('schema_version') if isinstance(value, dict) else None
    if isinstance(version, str) and version in RESPONSE_SCHEMAS[kind]:
        return version
    return f"q-demo.{'q3-parse' if kind == 'q3' else kind}-response.v1"


def v2_schema_documents(root=None):
    """Read data only from the paired #278 schema bytes; no external code/ref loads."""
    root = Path(root) if root is not None else Path(__file__).parents[1] / 'contracts/q_demo/schemas'
    documents = {}
    for name, pin in V2_SCHEMA_PINS.items():
        path = root / name
        if path.resolve() != path or not path.is_file():
            raise ValueError('Paired #278 v2 schema unavailable: ' + name)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError('Paired #278 v2 schema SHA mismatch: ' + name)
        documents[name] = json.loads(raw)
    return documents


def time_range_source(response):
    version = response.get('schema_version') if isinstance(response, dict) else None
    if not isinstance(version, str) or version not in set().union(*RESPONSE_SCHEMAS.values()):
        raise ValueError('Unsupported response schema version')
    if version.endswith('.v1'):
        return None  # Do not infer lineage from a historical full-run time range.
    scope = response.get('resolved_scope')
    if not isinstance(scope, dict) or not {'time_range_source', 'requested_time'} <= scope.keys():
        raise ValueError('v2 time_range_source is required')
    source = scope['time_range_source']
    if source is not None and not isinstance(source, str):
        raise ValueError('v2 time_range_source must be a string or null')
    time = scope.get('requested_time')
    kind = time.get('kind') if isinstance(time, dict) else None
    valid = (time is None and source is None
             or kind == 'SOURCE' and source in {'EXPLICIT_SOURCE', 'DEFAULT_SELECTED_RUN'}
             or kind == 'WALL' and source == 'EXPLICIT_WALL')
    if not valid:
        raise ValueError('v2 time_range_source/requested_time mismatch')
    return source


def scoring_exclusion(case, response):
    """An owner annotation also keeps missing/invalid default-run predictions unscored."""
    expected = case.get('expected_time_range_source')
    if expected is not None and (not isinstance(expected, str) or expected not in TIME_SOURCES):
        raise ValueError('Invalid expected_time_range_source annotation')
    source = time_range_source(response) if response is not None else None
    if expected == 'DEFAULT_SELECTED_RUN' or expected is None and source == 'DEFAULT_SELECTED_RUN':
        return 'DEFAULT_SELECTED_RUN'
    return None
