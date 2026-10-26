"""Scope documents for explicitly synthetic engineering graphs; no real G4 grant."""
import hashlib
import json
from copy import deepcopy

from amidst.q1q5.store import canonical_hash


def bind_engineering_scope(region, camera):
    """Return new pinned documents without altering existing frozen inputs.

    The existing scope schema names its approval bit G4_approved. It is true here
    only in the rSYN namespace, following the explicit synthetic graph approval;
    this function cannot approve or convert an r004 graph.
    """
    region, camera = deepcopy(region), deepcopy(camera)
    if any(doc.get('scene_revision') != 'rSYN'
           or doc.get('approval_status') != 'APPROVED'
           or not str(doc.get('approval_ref', '')).startswith('SYNTHETIC')
           for doc in (region, camera)):
        raise ValueError('EXPLICIT_SYNTHETIC_ENGINEERING_GRAPHS_REQUIRED')
    cameras = sorted(row['camera_id'] for row in camera['cameras'])
    transitions = {(t['from_camera_id'], t['to_camera_id']): t['transition_id']
                   for t in camera['transitions']}
    pairs = []
    for source in cameras:
        for target in cameras:
            if source == target:
                continue
            row = dict(from_camera_id=source, to_camera_id=target)
            tid = transitions.get((source, target))
            row.update(disposition='TRANSITION', transition_id=tid) if tid else row.update(
                disposition='EXCLUDED', reason='SYNTHETIC_ENGINEERING_NO_DECLARED_TRANSITION')
            pairs.append(row)
    scope = dict(schema_version='q-demo.r004-tracking-scope.v3', status='APPROVED',
                 G4_approved=True, query_camera_ids=cameras, tracking_camera_ids=cameras,
                 query_only_camera_ids=[], directed_pairs=pairs,
                 north_floor_y_gt_12='NOT_APPLICABLE_SYNTHETIC_ENGINEERING_ONLY',
                 overlap_pairs_deferred='NOT_APPLICABLE_SYNTHETIC_ENGINEERING_ONLY')
    raw = json.dumps(scope, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                     allow_nan=False).encode()
    pin = hashlib.sha256(raw).hexdigest()
    for doc, prefix in ((region, 'rgraph'), (camera, 'cgraph')):
        doc['inputs'] = [row for row in doc['inputs'] if not row['ref'].startswith('tracking-scope:')]
        doc['inputs'].append(dict(ref='tracking-scope:SYNTHETIC:engineering:v1', sha256=pin))
        if prefix == 'cgraph':
            doc['region_graph_sha256'] = region['content_sha256']
        doc['content_sha256'] = canonical_hash(doc, exclude=('graph_id', 'content_sha256', 'stats'))
        doc['graph_id'] = f"{prefix}:rSYN:static:{doc['content_sha256'][:16]}"
    return region, camera, scope, raw
