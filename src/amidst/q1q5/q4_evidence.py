"""Index-only candidate evidence. No RGB, inference, clock guessing or GT access."""
from copy import deepcopy
from functools import wraps
import math
import re

from amidst.q1q5.store import DetectionSnapshot, canonical_hash


class EvidenceError(ValueError):
    def __init__(self,message,code='DataIntegrityError'):
        self.code=code
        super().__init__(message)


def _require(value,message):
    if not value:raise EvidenceError(message)


def _ranges(value):
    _require(isinstance(value,list),'Ranges must be arrays')
    last=-1;out=[]
    for pair in value:
        _require(isinstance(pair,list) and len(pair)==2 and all(type(x) is int and x>=0 for x in pair)
                 and last<=pair[0]<pair[1],'Invalid/overlapping source ranges')
        last=pair[1];out.append(pair[:])
    return out


def _intersection(a,b):
    return [[max(x0,y0),min(x1,y1)] for x0,x1 in a for y0,y1 in b if max(x0,y0)<min(x1,y1)]


def _complement(window,covered):
    out=[];cursor=window[0]
    for left,right in covered:
        if left>cursor:out.append([cursor,left])
        cursor=max(cursor,right)
    if cursor<window[1]:out.append([cursor,window[1]])
    return out


def _ceil(value,step):return -(-value//step)


def _integrity_boundary(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:return function(*args, **kwargs)
        except EvidenceError:raise
        except (KeyError, TypeError, IndexError, AttributeError, OverflowError, ValueError) as exc:
            raise EvidenceError('Malformed candidate/index evidence') from exc
    return guarded


@_integrity_boundary
def candidate_evidence(index: DetectionSnapshot, snapshot, candidate_ref, *, expected_index_sha256,
                       query_min_score, color_label, evidence_max_observations,
                       switch_min_presence, decision_time_us, available_ranges_us):
    """Consume a trusted store snapshot and a canonical static candidate snapshot.

    available_ranges_us comes from the registered media binding, never from a query.
    The snapshot must declare exactly the resulting clipped ranges. A missing index
    row is an integrity error; it is never invented as MISSING or a negative frame.
    """
    _require(isinstance(index,DetectionSnapshot),'Pinned DetectionSnapshot required')
    manifest=deepcopy(index.manifest);snap=deepcopy(snapshot)
    digest=canonical_hash(manifest,exclude=('index_id','content_sha256','stats'))
    _require(digest==expected_index_sha256==manifest.get('content_sha256'),'Index content pin mismatch')
    _require(manifest.get('schema_version')=='q-demo.detection-index.v1','Index schema required')
    pre={k:v for k,v in snap.items() if k not in {'candidate_snapshot_sha256','stats'}}
    for c in pre.get('candidates',[]):c.pop('candidate_ref',None)
    sh=canonical_hash(pre)
    _require(sh==snapshot.get('candidate_snapshot_sha256'),'Candidate snapshot hash mismatch')
    matches=[c for c in snapshot['candidates'] if c['candidate_ref']==candidate_ref]
    _require(len(matches)==1,'Candidate not in canonical snapshot')
    candidate=deepcopy(matches[0]);_require(candidate_ref==f"cand:{sh[:16]}:{candidate['rank']}",'Candidate ref mismatch')
    _require(type(evidence_max_observations) is int and evidence_max_observations>0,'Explicit display cap required')
    _require(switch_min_presence in {'MATCH_STRONG','MATCH_WEAK'},'Explicit switch guard required')
    _require(type(decision_time_us) is int and decision_time_us>=0,'Integer decision time required')
    _require(type(query_min_score) in (int,float) and math.isfinite(query_min_score) and 0<=query_min_score<=1,'Explicit score required')
    if query_min_score<manifest['detector']['index_score_floor']:raise EvidenceError('Query score below index floor','FORBIDDEN_INFERENCE_INPUT')
    if color_label is not None and color_label not in manifest['color_method']['color_vocabulary']['labels']:
        raise EvidenceError('Color not in pinned vocabulary','UNSUPPORTED_CONDITION')
    window=_ranges([candidate['window_us']])[0];available=_ranges(available_ranges_us)
    cameras=[c for c in manifest['sampling']['per_camera'] if c['camera_id']==candidate['camera_id']]
    _require(len(cameras)<=1,'Duplicate camera grid')
    meta=cameras[0] if cameras else None
    effective=_intersection([window],_intersection(available,_ranges(meta['sampled_ranges_us']))) if meta else []
    effective.sort()
    _require(candidate.get('window_truncated_us',[])==_complement(window,effective),'Snapshot/media/index clipping mismatch')
    counts=dict(evaluated=0,not_sampled=0,not_inferred=0,missing=0);observations=[]
    if meta:
        base,stride,step,origin=[meta[k] for k in ['source_frame_interval_us','stride_samples','index_interval_us','index_grid_origin_frame']]
        _require(all(type(v) is int and v>0 for v in [base,stride,step]) and type(origin) is int and origin>=0
                 and step==base*stride and stride==manifest['sampling']['stride_samples'],'Invalid source/index grid')
        expected_source=sum(_ceil(b,base)-_ceil(a,base) for a,b in effective)
        expected_grid=sum(max(0,max(0,_ceil(b-origin*base,step))-max(0,_ceil(a-origin*base,step))) for a,b in effective)
        rows=[];seen=set()
        for row in index.records:
            if row.get('camera_id')!=candidate['camera_id']:continue
            frame,ts=row.get('frame_index'),row.get('timestamp_us')
            _require(type(frame) is int and frame>=0 and type(ts) is int and ts==frame*base,'Record grid mismatch')
            _require(frame not in seen,'Duplicate source frame');seen.add(frame)
            if any(a<=ts<b for a,b in effective):rows.append(row)
        _require(len(rows)==expected_source,'Absent source record is an integrity error')
        for row in sorted(rows,key=lambda r:r['timestamp_us']):
            frame,ts,state=row['frame_index'],row['timestamp_us'],row['frame_state']
            on_grid=frame>=origin and (frame-origin)%stride==0
            _require((state=='NOT_SAMPLED')==(not on_grid),'Frame state/index grid mismatch')
            _require(state in {'INFERRED','NOT_SAMPLED','NOT_INFERRED','MISSING'},'Invalid frame state')
            counts[{'INFERRED':'evaluated','NOT_SAMPLED':'not_sampled','NOT_INFERRED':'not_inferred','MISSING':'missing'}[state]]+=1
            if state!='INFERRED':
                _require(row.get('detections') is None,'Uninferred record has detections');continue
            _require(isinstance(row.get('detections'),list),'Inferred record requires detections')
            expected_frame=f"frame:{manifest['run_id']}:{candidate['camera_id']}:{frame}"
            _require(row['frame_ref']==expected_frame,'Frame binding mismatch')
            for ordinal,detection in enumerate(row['detections']):
                _require(detection['observation_id']==f"obs:{manifest['index_id'].split(':')[-1]}:{candidate['camera_id']}:{frame}:{ordinal}",'Observation index/frame mismatch')
                score=detection['score'];box=detection['bbox_xyxy_px']
                _require(type(score) in (int,float) and math.isfinite(score) and 0<=score<=1,'Invalid detection score')
                _require(isinstance(box,list) and len(box)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in box) and box[0]<box[2] and box[1]<box[3],'Invalid detection bbox')
                if detection['class_label']!='person' or score<query_min_score:continue
                verdict=None if color_label is None else (detection.get('color') or {}).get('verdicts',{}).get(color_label)
                _require(color_label is None or verdict in {'STRONG','WEAK','UNKNOWN','NONE'},'Missing color evidence')
                observations.append({'observation_id':detection['observation_id'],'frame_ref':row['frame_ref'],'timestamp_us':ts,'score':score,'color_verdict':verdict,'bbox_xyxy_px':box[:]})
        _require(counts['evaluated']+counts['not_inferred']+counts['missing']==expected_grid,'Index row count mismatch')
    n=counts['evaluated']+counts['not_inferred']+counts['missing'];complete=n>0 and counts['evaluated']==n
    verdicts={o['color_verdict'] for o in observations};partial=None
    if counts['evaluated']==0:presence='NOT_EVALUATED'
    elif observations and (color_label is None or 'STRONG' in verdicts):presence='MATCH_STRONG'
    elif 'WEAK' in verdicts:presence='MATCH_WEAK'
    elif 'UNKNOWN' in verdicts:presence='PERSON_COLOR_UNKNOWN'
    elif not complete:presence='PARTIAL_EVIDENCE';partial='PERSON_NO_COLOR_MATCH' if observations else 'NO_PERSON_DETECTED'
    else:presence='PERSON_NO_COLOR_MATCH' if observations else 'NO_PERSON_DETECTED'
    order={None:0,'STRONG':0,'WEAK':1,'UNKNOWN':2,'NONE':3}
    best=sorted(observations,key=lambda o:(order[o['color_verdict']],-o['score'],o['timestamp_us'],o['observation_id']))[:evidence_max_observations]
    supporting=[o for o in observations if color_label is None or o['color_verdict'] in {'STRONG','WEAK'}]
    eligible=[o for o in supporting if o['timestamp_us']>=decision_time_us and (color_label is None or o['color_verdict']=='STRONG' or switch_min_presence=='MATCH_WEAK')]
    eligible.sort(key=lambda o:(o['timestamp_us'],-o['score'],o['observation_id']));entry=eligible[0] if eligible else None
    result={'schema_version':'q-demo.candidate-evidence.v1','candidate_ref':candidate_ref,'camera_id':candidate['camera_id'],'window_us':window,'target_presence':presence,'frames':counts,'coverage_complete':complete,'partial_basis':partial,'decision_time_us':decision_time_us,'entry_observation_id':entry['observation_id'] if entry else None,'entry_timestamp_us':entry['timestamp_us'] if entry else None,'best_observations':best,'matching_observation_count':len(supporting),'first_match_us':min((o['timestamp_us'] for o in supporting),default=None)}
    result['evidence_sha256']=canonical_hash(result)
    return result
