"""Non-formal association hypotheses from local tracks and static transitions.

This module accepts closed value objects only and performs no file or network I/O.
Camera connectivity permits a hypothesis; it never establishes identity or motion.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Observation:
    camera_id: str
    timestamp_us: int
    observation_id: str
    score: float
    colors: frozenset[str]
    class_label: str = "person"
    evidence_kind: str = "PERSON_DETECTION"


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
    """D147 display sequence: bridge only same-camera gaps up to 0.6 s."""
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
            if merged and start <= merged[-1][1] + 600_000:
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
    """Causal DEMO_DEFAULT associations, rescanning every indexed time after loss.

    Keep ambiguities in the audit and continue. A graph edge plus a <=6 s gap
    labels a handoff; later or edge-free matches are unconfirmed reacquisitions.
    Colour is taken only from past evaluated person observations of a local track.
    """
    if type(as_of_us) is not int or as_of_us < 0:
        raise ValueError('AS_OF_INVALID')
    available = []
    for track in tracks:
        observations = tuple(o for o in track.observations if o.timestamp_us < as_of_us)
        if observations:
            if (any(o.camera_id != track.camera_id or o.score < .3 for o in observations)
                    or any(a.timestamp_us >= b.timestamp_us for a, b in zip(observations, observations[1:]))):
                raise ValueError('LOCAL_TRACK_INVALID')
            available.append(Track(track.camera_id, track.track_ref, observations))
    if len({t.track_ref for t in available}) != len(available):
        raise ValueError('LOCAL_TRACK_INVALID')
    available.sort(key=lambda t: (t.observations[0].timestamp_us, t.camera_id, t.track_ref))
    samples = {t.track_ref: {o.timestamp_us: o for o in t.observations} for t in available}
    times = sorted({o.timestamp_us for t in available for o in t.observations})
    chain, events, audit = [], [], []
    current = None

    def known_colors(track, stamp):
        return next((o.colors for o in reversed(track.observations)
                     if o.timestamp_us <= stamp and o.colors and o.evidence_kind != 'BOX_CONTINUATION'), frozenset())

    for timestamp in times:
        if current is not None and timestamp in samples[current.track_ref]:
            for candidate in available:
                if candidate.track_ref != current.track_ref and candidate.observations[0].timestamp_us == timestamp:
                    audit.append({'reason': 'CURRENT_CAMERA_STILL_OBSERVED', 'timestamp_us': timestamp,
                                  'from_track_ref': current.track_ref, 'to_track_ref': candidate.track_ref,
                                  'identity_verdict': 'UNCONFIRMED'})
            continue
        eligible = []
        for candidate in available:
            if timestamp not in samples[candidate.track_ref]:
                continue
            if current is None:
                # A local continuation cannot become an initial person seed.
                if samples[candidate.track_ref][timestamp].colors and samples[candidate.track_ref][timestamp].class_label == 'person':
                    eligible.append((candidate, None))
                continue
            if candidate.track_ref == current.track_ref:
                continue
            past = [o for o in current.observations if o.timestamp_us <= timestamp]
            last = past[-1]
            gap = timestamp - (last.timestamp_us + parameters.sample_interval_us)
            same_camera = current.camera_id == candidate.camera_id
            edge = transitions.get((current.camera_id, candidate.camera_id))
            link_kind = ('SAME_CAMERA_REACQUISITION' if same_camera else
                         'CROSS_CAMERA_HANDOFF' if edge is not None and gap <= parameters.handoff_max_gap_us
                         else 'CROSS_CAMERA_REACQUISITION')
            reason = ('CURRENT_CAMERA_STILL_OBSERVED' if gap < 0 else
                      None if known_colors(current, timestamp).intersection(known_colors(candidate, timestamp))
                      else 'COLOR_NOT_COMPATIBLE')
            row = {'from_camera_id': current.camera_id, 'to_camera_id': candidate.camera_id,
                   'timestamp_us': timestamp, 'transition_id': edge if link_kind == 'CROSS_CAMERA_HANDOFF' else None,
                   'gap_us': gap, 'link_kind': link_kind,
                   'from_track_ref': current.track_ref, 'to_track_ref': candidate.track_ref,
                   'reason': reason, 'evidence_state': 'INFERRED', 'confidence': 'LOW',
                   'identity_verdict': 'UNCONFIRMED'}
            audit.append(row)
            if reason is None:
                eligible.append((candidate, row))
        if len(eligible) > 1:
            if current is None:
                audit.append({'reason': 'AMBIGUOUS_FIRST_SEED', 'timestamp_us': timestamp,
                              'identity_verdict': 'UNCONFIRMED'})
            else:
                for _, row in eligible:
                    row['reason'] = 'AMBIGUOUS_HANDOFF'
            continue
        if eligible:
            current, row = eligible[0]
            chain.append((current, timestamp))
            if row is not None:
                row['reason'] = 'DEMO_ASSOCIATION_HYPOTHESIS'
                events.append(dict(row, first_grid_as_of_us=timestamp + parameters.sample_interval_us))
    sightings = []
    for i, (track, start) in enumerate(chain):
        cutoff = chain[i + 1][1] if i + 1 < len(chain) else as_of_us
        for obs in track.observations:
            if not start <= obs.timestamp_us < cutoff:
                continue
            end = min(obs.timestamp_us + parameters.sample_interval_us, cutoff, as_of_us)
            if obs.evidence_kind == 'BOX_CONTINUATION':
                audit.append({'camera_id': track.camera_id, 'timestamp_us': obs.timestamp_us,
                              'track_ref': track.track_ref, 'observation_id': obs.observation_id,
                              'reason': 'BOX_CONTINUATION', 'evidence_kind': obs.evidence_kind,
                              'class_label': obs.class_label, 'color_verdict': 'NOT_EVALUATED',
                              'identity_verdict': 'UNCONFIRMED'})
            if (sightings and sightings[-1]['camera_id'] == track.camera_id
                    and sightings[-1]['range_us'][1] == obs.timestamp_us
                    and sightings[-1]['track_ref'] == track.track_ref):
                sightings[-1]['range_us'][1] = end
                sightings[-1]['observation_ids'].append(obs.observation_id)
            else:
                sightings.append({'camera_id': track.camera_id, 'range_us': [obs.timestamp_us, end],
                                  'evidence_state': 'OBSERVED', 'observation_ids': [obs.observation_id],
                                  'track_ref': track.track_ref,
                                  'link_kind': events[i - 1]['link_kind'] if i else 'LOCAL_SEED'})
    # D150: simultaneous camera-local evidence must survive a single-view choice.
    # A local candidate is explicitly unassociated; retaining its boxes is not an
    # identity merge. The selected chain alone drives causal single-view playback.
    selected = {(s['track_ref'], oid) for s in sightings for oid in s['observation_ids']}
    selected_links = {s['track_ref']: s['link_kind'] for s in sightings}
    if chain:
        anchor, first_time = chain[0]
        anchor_colors = known_colors(anchor, first_time)
        all_sightings = []
        for track in available:
            seed = track.observations[0]
            if seed.timestamp_us < first_time or not seed.colors.intersection(anchor_colors):
                continue
            for obs in track.observations:
                chosen = (track.track_ref, obs.observation_id) in selected
                if obs.evidence_kind == 'BOX_CONTINUATION' and not chosen:
                    audit.append({'camera_id': track.camera_id, 'timestamp_us': obs.timestamp_us,
                                  'track_ref': track.track_ref, 'observation_id': obs.observation_id,
                                  'reason': 'BOX_CONTINUATION', 'evidence_kind': obs.evidence_kind,
                                  'class_label': obs.class_label, 'color_verdict': 'NOT_EVALUATED',
                                  'identity_verdict': 'UNCONFIRMED'})
                end = min(obs.timestamp_us + parameters.sample_interval_us, as_of_us)
                if (all_sightings and all_sightings[-1]['track_ref'] == track.track_ref
                        and all_sightings[-1]['selected_for_single_view'] == chosen
                        and all_sightings[-1]['range_us'][1] == obs.timestamp_us):
                    all_sightings[-1]['range_us'][1] = end
                    all_sightings[-1]['observation_ids'].append(obs.observation_id)
                else:
                    all_sightings.append({'camera_id': track.camera_id, 'range_us': [obs.timestamp_us, end],
                        'evidence_state': 'OBSERVED', 'observation_ids': [obs.observation_id],
                        'track_ref': track.track_ref, 'link_kind': selected_links.get(track.track_ref, 'LOCAL_SEED') if chosen else 'LOCAL_SEED',
                        'selected_for_single_view': chosen,
                        'association_state': 'SELECTED_HYPOTHESIS' if chosen else 'UNASSOCIATED_LOCAL_CANDIDATE'})
        sightings = sorted(all_sightings, key=lambda item: (item['range_us'][0], item['camera_id'], item['track_ref']))
    return sightings, events, audit


def response(tracks, transitions, *, as_of_us, parameters, clock_mapping_sha256):
    sightings, events, audit = associate(tracks, transitions, as_of_us=as_of_us, parameters=parameters)
    single = single_view_sequence([s for s in sightings if s.get('selected_for_single_view', True)], as_of_us=as_of_us)
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
              'sightings': sightings, 'association_audit': audit, 'multi_view': sorted(cameras.values(), key=lambda c: (c['first_us'], c['camera_id'])),
              'single_view': single,
              'blind': {'status': 'UNAVAILABLE', 'reason': 'PREDICTION_UNAVAILABLE', 'estimate': None}
                       if single and single[-1]['kind'] in {'GAP', 'LOST'} else None,
              'identity_verdict': 'UNCONFIRMED', 'physical_navigation': 'UNKNOWN'}
    if any(event['link_kind'] == 'SAME_CAMERA_REACQUISITION' for event in events):
        result['reasons'].append('SAME_CAMERA_REACQUISITION')
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
