"""D92 response provenance; never part of a domain request or D80 preimage."""


def time_range_source(time, *, default_selected_run=False):
    """Classify a time request after its normal clock resolver validates it.

    Only the adapter may assert a default, using a matching saved parse receipt.
    An explicit full-run range alone is not evidence of a parser default.
    """
    if default_selected_run:
        if time.get('kind') != 'SOURCE':
            raise ValueError('DEFAULT_SELECTED_RUN_REQUIRES_SOURCE_TIME')
        return 'DEFAULT_SELECTED_RUN'
    return {'SOURCE': 'EXPLICIT_SOURCE', 'WALL': 'EXPLICIT_WALL'}[time['kind']]
