"""Contract B #237: a total order, independent of discovery order."""
PRIORITY = (
    'MULTI_RUN_SCOPE_UNRESOLVED', 'INDEX_NOT_AVAILABLE', 'CLOCK_MAPPING_MISSING',
    'TRACKING_SCOPE_MISSING', 'GRAPH_NOT_AVAILABLE', 'PARAMETER_GRID_MISMATCH',
    'EXIT_ZONES_MISSING', 'SEED_CAMERA_NOT_TRACKED', 'EMPTY_CAMERA_SCOPE', 'USER_STOPPED',
)
DEGRADATION = ('TIME_SCOPE_PARTIAL', 'GRAPH_NOT_APPROVED', 'PARAMETERS_NOT_APPROVED', 'INCOMPLETE_EVIDENCE')


def ordered_reasons(values):
    first = {value: i for i, value in enumerate(PRIORITY)}
    last = {value: i for i, value in enumerate(DEGRADATION)}
    def key(value):
        if value in first:return (0, first[value], '')
        if value in last:return (2, last[value], '')
        return (1, 0, value)
    return sorted(set(values), key=key)
