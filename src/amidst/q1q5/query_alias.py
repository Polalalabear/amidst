"""Exact aliases only; caller supplies canonical IDs from the selected source."""

class AliasError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def validate_aliases(aliases, valid_ids, *, allow_unavailable=False):
    if not isinstance(aliases, dict) or not isinstance(valid_ids, (list, tuple, set)):
        raise AliasError('ALIAS_CONFIG_INVALID')
    result = {}
    for alias, canonical in aliases.items():
        if not isinstance(alias, str) or not alias or not isinstance(canonical, str) or not canonical:
            raise AliasError('ALIAS_CONFIG_INVALID')
        key = alias.casefold()
        if key in result:
            raise AliasError('ALIAS_CONFLICT')
        if not allow_unavailable and canonical not in valid_ids:
            raise AliasError('ALIAS_TARGET_UNKNOWN')
        if key in {v.casefold() for v in valid_ids} and alias not in valid_ids:
            targets = [v for v in valid_ids if v.casefold() == key]
            if targets != [canonical]:
                raise AliasError('ALIAS_CONFLICT')
        if alias in valid_ids and canonical != alias:
            raise AliasError('ALIAS_CONFLICT')
        result[key] = canonical
    return result


def resolve_alias(value, aliases, valid_ids, *, allow_unavailable=False):
    mapping = validate_aliases(aliases, valid_ids, allow_unavailable=allow_unavailable)
    if not isinstance(value, str):
        raise AliasError('ALIAS_UNKNOWN')
    canonical = mapping.get(value.casefold(), value if value in valid_ids else None)
    if canonical is None:
        raise AliasError('ALIAS_UNKNOWN')
    if canonical not in valid_ids:
        raise AliasError('ALIAS_TARGET_UNKNOWN')
    return canonical


def region_aliases():
    # Repository-owned proposed vocabulary, never a request-selected path.
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / 'configs/q1q5/query_alias_v1.json'
    return json.loads(path.read_text(encoding='utf-8'))['region_aliases']


def region_catalog(run):
    from amidst.q1q5.store import canonical_hash
    binding = run.bindings
    if binding.graphs is None:
        return None
    graph = binding.graphs.region
    manifest = binding.index.manifest
    if (graph['scene_id'] != manifest['scene_id'] or graph['scene_revision'] != manifest['scene_revision']
            or graph['content_sha256'] != binding.region_graph_sha256
            or canonical_hash(graph, exclude=('graph_id', 'content_sha256', 'stats')) != binding.region_graph_sha256):
        raise AliasError('REGION_CATALOG_MISMATCH')
    aliases = region_aliases()
    ids = [r['region_id'] for r in graph['regions']]
    validate_aliases(aliases, ids, allow_unavailable=True)
    if len(ids) != len(set(ids)):
        raise AliasError('REGION_CATALOG_INVALID')
    return {'scene_id': graph['scene_id'], 'scene_revision': graph['scene_revision'],
            'region_graph_sha256': binding.region_graph_sha256,
            'regions': [{'region_id': value, 'label': next((k for k, v in aliases.items()
                         if v == value and any('\u3400' <= c <= '\u9fff' for c in k)), value)} for value in ids]}
