"""Non-formal association hypotheses from local tracks and static transitions.

This module accepts closed value objects only and performs no file or network I/O.
Camera connectivity permits a hypothesis; it never establishes identity or motion.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import groupby


@dataclass(frozen=True)
class Observation:
    camera_id: str
    timestamp_us: int
    observation_id: str
    score: float
    colors: frozenset[str]


@dataclass(frozen=True)
class Track:
    camera_id: str
    track_ref: str
    observations: tuple[Observation, ...]


@dataclass(frozen=True)
class Parameters:
    sample_interval_us: int = 200_000
    handoff_max_gap_us: int = 6_000_000
    min_score: float = 0.4
    color_rule: str = 'NOT_NONE'
    parameter_mode: str = 'DEMO_DEFAULT'

    def __post_init__(self):
        if (type(self.sample_interval_us) is not int or self.sample_interval_us <= 0
                or type(self.handoff_max_gap_us) is not int or self.handoff_max_gap_us < 0
                or type(self.min_score) not in (int, float) or not 0 <= self.min_score <= 1
                or self.color_rule != 'NOT_NONE' or self.parameter_mode != 'DEMO_DEFAULT'):
            raise ValueError('DEMO_PARAMETERS_INVALID')


def single_view_sequence(sightings, *, as_of_us):
    """#410 section 3.5, including adjacent/overlapping same-camera normalization."""
    by_camera = {}
    for item in sightings:
        start, end = item['range_us']
        end = min(end, as_of_us)
        if start < end:
            by_camera.setdefault(item['camera_id'], []).append([start, end])
    valid = []
    for camera, intervals in by_camera.items():
        merged = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        valid.extend({'camera_id': camera, 'range_us': pair} for pair in merged)
    if not valid:
        return []
    first_key = lambda item: (item['range_us'][0], -item['range_us'][1], item['camera_id'])
    chosen = min(valid, key=first_key)
    result = []
    def append(kind, camera, start, end):
        if (result and kind == 'ON_CAMERA' and result[-1]['kind'] == kind
                and result[-1]['camera_id'] == camera and result[-1]['range_us'][1] == start):
            result[-1]['range_us'][1] = end
        else:
            result.append({'kind': kind, 'camera_id': camera, 'range_us': [start, end],
                           'evidence_state': 'OBSERVED' if kind == 'ON_CAMERA' else 'UNKNOWN'})
    append('ON_CAMERA', chosen['camera_id'], *chosen['range_us'])
    time = chosen['range_us'][1]
    while time < as_of_us:
        active = [item for item in valid if item['range_us'][0] <= time < item['range_us'][1]]
        if active:
            chosen = min(active, key=lambda item: (-item['range_us'][1], item['camera_id']))
            append('ON_CAMERA', chosen['camera_id'], time, chosen['range_us'][1])
        else:
            future = [item for item in valid if item['range_us'][0] > time]
            if not future:
                append('LOST', None, time, as_of_us)
                break
            chosen = min(future, key=first_key)
            append('GAP', None, time, chosen['range_us'][0])
            append('ON_CAMERA', chosen['camera_id'], *chosen['range_us'])
        time = chosen['range_us'][1]
    return result


def associate(tracks, transitions, *, as_of_us, parameters):
    """Choose the earliest seed, then evaluate each later seed using its past only.

    At a candidate seed, the current camera must lack a contemporaneous sample.
    Direct graph edge, bounded sample gap and a shared non-NONE color are required.
    Multiple eligible seeds at the same timestamp stop with UNKNOWN, never a rank.
    """
    if type(as_of_us) is not int or as_of_us < 0:
        raise ValueError('AS_OF_INVALID')
    available = []
    for track in tracks:
        observations = tuple(o for o in track.observations if o.timestamp_us < as_of_us)
        if observations:
            if (any(o.camera_id != track.camera_id or o.score < parameters.min_score for o in observations)
                    or any(a.timestamp_us >= b.timestamp_us for a, b in zip(observations, observations[1:]))):
                raise ValueError('LOCAL_TRACK_INVALID')
            available.append(Track(track.camera_id, track.track_ref, observations))
    available.sort(key=lambda t: (t.observations[0].timestamp_us, t.camera_id))
    if not available:
        return [], [], []
    first_time = available[0].observations[0].timestamp_us
    first = [t for t in available if t.observations[0].timestamp_us == first_time]
    if len(first) != 1:
        return [], [], [{'reason': 'AMBIGUOUS_FIRST_SEED', 'timestamp_us': first_time}]
    chain, events, audit = [first[0]], [], []
    for timestamp, group in groupby(available[len(first):], lambda t: t.observations[0].timestamp_us):
        current = chain[-1]
        # No sample after this candidate's source time participates in association.
        past = [o for o in current.observations if o.timestamp_us <= timestamp]
        last = past[-1]
        eligible = []
        for candidate in group:
            seed = candidate.observations[0]
            edge = transitions.get((current.camera_id, candidate.camera_id))
            gap = timestamp - (last.timestamp_us + parameters.sample_interval_us)
            reason = ('NO_DIRECT_TRANSITION' if edge is None else
                      'CURRENT_CAMERA_STILL_OBSERVED' if gap < 0 else
                      'HANDOFF_WINDOW_EXCEEDED' if gap > parameters.handoff_max_gap_us else
                      'COLOR_NOT_COMPATIBLE' if not last.colors.intersection(seed.colors) else None)
            row = {'from_camera_id': current.camera_id, 'to_camera_id': candidate.camera_id,
                   'timestamp_us': timestamp, 'transition_id': edge, 'gap_us': gap,
                   'reason': reason, 'evidence_state': 'INFERRED', 'confidence': 'LOW',
                   'identity_verdict': 'UNCONFIRMED'}
            audit.append(row)
            if reason is None:
                eligible.append((candidate, row))
        if len(eligible) > 1:
            for _, row in eligible:
                row['reason'] = 'AMBIGUOUS_HANDOFF'
            break
        if eligible:
            candidate, row = eligible[0]
            row['reason'] = 'DEMO_ASSOCIATION_HYPOTHESIS'
            chain.append(candidate)
            events.append(dict(row, first_grid_as_of_us=timestamp + parameters.sample_interval_us))
    sightings = []
    for i, track in enumerate(chain):
        cutoff = chain[i + 1].observations[0].timestamp_us if i + 1 < len(chain) else as_of_us
        for obs in track.observations:
            if obs.timestamp_us >= cutoff:
                continue
            end = min(obs.timestamp_us + parameters.sample_interval_us, cutoff, as_of_us)
            if (sightings and sightings[-1]['camera_id'] == track.camera_id
                    and sightings[-1]['range_us'][1] == obs.timestamp_us):
                sightings[-1]['range_us'][1] = end
                sightings[-1]['observation_ids'].append(obs.observation_id)
            else:
                sightings.append({'camera_id': track.camera_id, 'range_us': [obs.timestamp_us, end],
                                  'evidence_state': 'OBSERVED', 'observation_ids': [obs.observation_id],
                                  'track_ref': track.track_ref})
    return sightings, events, audit


def response(tracks, transitions, *, as_of_us, parameters, clock_mapping_sha256):
    sightings, events, audit = associate(tracks, transitions, as_of_us=as_of_us, parameters=parameters)
    single = single_view_sequence(sightings, as_of_us=as_of_us)
    status = 'NO_SIGHTING' if not single else 'LOST' if single[-1]['kind'] == 'LOST' else 'TRACKING'
    cameras = {}
    for item in sightings:
        camera = cameras.setdefault(item['camera_id'], {'camera_id': item['camera_id'],
                                    'first_us': item['range_us'][0], 'last_us': item['range_us'][1]})
        camera['last_us'] = max(camera['last_us'], item['range_us'][1])
    result = {'schema_version': 'q-core.track-response.v1', 'status': status,
              'reasons': ['DEMO_DEFAULT', 'GRAPH_NOT_APPROVED', 'ASSOCIATION_IDENTITY_UNCONFIRMED'],
              'as_of_us': as_of_us,
              'resolved_time': {'kind': 'PLAYBACK_NOW', 'source_range_us': [0, as_of_us],
                                'clock_mapping_sha256': clock_mapping_sha256},
              'sightings': sightings, 'multi_view': sorted(cameras.values(), key=lambda c: (c['first_us'], c['camera_id'])),
              'single_view': single,
              'blind': {'status': 'UNAVAILABLE', 'reason': 'PREDICTION_UNAVAILABLE', 'estimate': None}
                       if single and single[-1]['kind'] in {'GAP', 'LOST'} else None,
              'identity_verdict': 'UNCONFIRMED', 'physical_navigation': 'UNKNOWN'}
    if any(row['reason'].startswith('AMBIGUOUS') for row in audit):
        result['reasons'].append('ASSOCIATION_AMBIGUOUS')
    return result, events, audit


def declared_wall(clock, timestamp_us):
    if clock['timezone'] != 'Asia/Taipei' or clock['rate'] != 1 or clock['t0_us'] != 0:
        raise ValueError('DECLARED_CLOCK_UNSUPPORTED')
    origin = datetime.fromisoformat(clock['wall_origin'])
    if origin.utcoffset() != timedelta(hours=8):
        raise ValueError('DECLARED_CLOCK_OFFSET')
    return (origin + timedelta(microseconds=timestamp_us)).isoformat(timespec='microseconds')
