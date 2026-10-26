"""Source-pinned index-only Q1 search; no query-time media/inference or GT reads."""
import math
import re
from copy import deepcopy
from functools import wraps

from amidst.q1q5.clock_mapping import ClockMappingError, resolve_source_range, resolve_wall_range
from amidst.q1q5.store import DetectionSnapshot, _safe_content, canonical_hash


class SearchError(ValueError):
    def __init__(self,message,code='DataIntegrityError'):
        self.code=code
        super().__init__(message)


def _require(ok,message,code='DataIntegrityError'):
    if not ok:raise SearchError(message,code)


def _guard(fn):
    @wraps(fn)
    def guarded(*args,**kwargs):
        try:return fn(*args,**kwargs)
        except SearchError:raise
        except (KeyError,TypeError,ValueError,IndexError,AttributeError,OverflowError) as exc:
            raise SearchError('Malformed Q1 metadata') from exc
    return guarded


def _ranges(ranges):
    _require(isinstance(ranges,list),'Ranges required');last=-1
    for r in ranges:
        _require(isinstance(r,list) and len(r)==2 and all(type(v) is int and v>=0 for v in r)
                 and last<=r[0]<r[1],'Invalid source ranges');last=r[1]
    return ranges


def _overlap(ranges,left,right):
    return [[max(a,left),min(b,right)] for a,b in ranges if max(a,left)<min(b,right)]


def _ceil(v,step):return -(-v//step)


@_guard
def search_cameras(request,*,index,expected_index_sha256,aliases,expected_aliases_sha256,
                   clock_mapping,parameter_set,expected_parameter_sha256,
                   camera_catalog_ids,media_token_for_frame,graphs=None):
    """One explicit run, immutable metadata and a stable media-token issuer port.

    The HTTP adapter owns media grants/expiry/authorization; its token port must be
    deterministic for the supplied query session to preserve the current hash wire.
    This function does not mint a bearer grant or claim that a thumbnail was served.
    """
    required={'schema_version','session_ref','scene_id','run_ids','time','condition','camera_ids','region_ids','page_size','cursor','origin'}
    _require(isinstance(request,dict) and set(request)==required and request['schema_version']=='q-demo.q1-request.v1','Unexpected Q1 input','FORBIDDEN_INFERENCE_INPUT')
    _require(request['origin'] in {'MANUAL','PREFILL','Q3_PARSED'} and isinstance(request['session_ref'],str) and request['session_ref'],'Invalid origin/session','FORBIDDEN_INFERENCE_INPUT')
    _safe_content(request)
    q=deepcopy(request);condition=q['condition']
    _require(isinstance(condition,dict) and set(condition)=={'class_label','min_count_per_frame','color','query_min_score'},'Invalid condition','FORBIDDEN_INFERENCE_INPUT')
    _require(isinstance(condition['class_label'],str) and bool(condition['class_label']) and type(condition['min_count_per_frame']) is int and condition['min_count_per_frame']>0,'Explicit class/count required','FORBIDDEN_INFERENCE_INPUT')
    score=condition['query_min_score'];_require(type(score) in (int,float) and math.isfinite(score) and 0<=score<=1,'Explicit finite query score required','FORBIDDEN_INFERENCE_INPUT')
    color=condition['color']
    if color is not None:_require(isinstance(color,dict) and set(color)=={'label','min_verdict'} and isinstance(color['label'],str) and color['min_verdict'] in {'STRONG','WEAK'},'Invalid color condition','FORBIDDEN_INFERENCE_INPUT')
    _require(type(q['page_size']) is int and q['page_size']>0 and (q['cursor'] is None or isinstance(q['cursor'],str)),'Invalid pagination','FORBIDDEN_INFERENCE_INPUT')
    _require(isinstance(q['run_ids'],list) and q['run_ids'] and len(set(q['run_ids']))==len(q['run_ids']) and all(isinstance(v,str) and v for v in q['run_ids']),'Invalid run IDs','FORBIDDEN_INFERENCE_INPUT')
    for field in ['camera_ids','region_ids']:
        value=q[field];_require(value is None or (isinstance(value,list) and value and all(isinstance(v,str) and v for v in value) and len(set(value))==len(value)),'Invalid scope filter','FORBIDDEN_INFERENCE_INPUT')
    _require(canonical_hash(aliases,exclude=('content_sha256','stats'))==expected_aliases_sha256==aliases['content_sha256'],'Alias pin mismatch')
    _require(aliases['schema_version']=='q-demo.supported-classes.v1' and isinstance(aliases['class_labels'],list) and len(set(aliases['class_labels']))==len(aliases['class_labels']),'Invalid alias schema')
    _require(all(isinstance(k,str) and k and v in aliases['class_labels'] for k,v in aliases['aliases'].items()),'Alias points outside class map')
    _require(len({k.casefold() for k in aliases['aliases']})==len(aliases['aliases']),'Casefold alias collision')
    vocabulary=aliases['color_vocabulary']
    _require(isinstance(aliases['version'],str) and aliases['version'] and isinstance(vocabulary,dict)
             and isinstance(vocabulary['version'],str) and vocabulary['version']
             and isinstance(vocabulary['labels'],list) and all(isinstance(v,str) and v for v in vocabulary['labels'])
             and len(set(vocabulary['labels']))==len(vocabulary['labels'])
             and canonical_hash(vocabulary,exclude=('content_sha256','stats'))==vocabulary['content_sha256'],'Invalid color vocabulary pin')
    label=next((v for k,v in aliases['aliases'].items() if k.casefold()==condition['class_label'].casefold()),condition['class_label'])
    condition['class_label']=label
    scope={k:None for k in ['scene_id','scene_revision','run_ids','clock_ids','clock_mapping_sha256','requested_time','resolved_source_ranges_us','time_coverage','camera_ids','detection_index_id','detection_index_sha256','region_graph_sha256','camera_graph_sha256','class_map_sha256','color_method_version','parameter_set_id','parameter_set_sha256']}
    response={'schema_version':'q-demo.q1-response.v1','status':'UNKNOWN','reason':None,'query_id':None,'query_sha256':None,'normalized_condition':condition,'results':[],'no_match_cameras':[],'not_evaluated_cameras':[],'results_total':0,'returned_count':0,'next_cursor':None,'ranking_basis':['first_match_us_asc','camera_id'],'supported_classes_ref':'supported-classes:'+expected_aliases_sha256,'resolved_scope':scope,'identity_verdict':'UNCONFIRMED','llm_parse_used':False,'agent_attempted':False,'agent_used':False,'decision_source':None,'fallback_used':False,'fallback_reason':None,'provenance':{'producer':'q1-camera-search','producer_version':'1','gt_read':False,'input_refs':['supported-classes:'+expected_aliases_sha256]}}
    normalized={k:v for k,v in q.items() if k not in {'origin','cursor'}}
    bindings={'index':expected_index_sha256,'aliases':expected_aliases_sha256,'parameters':expected_parameter_sha256,'clock':clock_mapping.content_sha256 if clock_mapping else None}
    query_sha=canonical_hash({'request':normalized,'bindings':bindings});response['query_sha256']=query_sha;response['query_id']='q1-'+query_sha[:16]
    resolution=None;approved=None;graph_draft=False;partial=False
    def finish(status,reason=None):
        reasons=[reason] if reason else []
        if status=='PARTIAL':
            if resolution is not None and not resolution.coverage_complete:reasons.append('TIME_SCOPE_PARTIAL')
            if graph_draft:reasons.append('GRAPH_NOT_APPROVED')
            if approved is False:reasons.append('PARAMETERS_NOT_APPROVED')
            if partial:reasons.append('INCOMPLETE_EVIDENCE')
            order={'TIME_SCOPE_PARTIAL':10,'GRAPH_NOT_APPROVED':11,'PARAMETERS_NOT_APPROVED':12,'INCOMPLETE_EVIDENCE':13}
            reasons=sorted(set(reasons),key=lambda item:(order.get(item,0),item))
        response.update(status=status,reason=reasons[0] if reasons else None,reasons=reasons)
        response['output_sha256']=canonical_hash(response,exclude=('output_sha256','stats'))
        return response
    if len(q['run_ids'])!=1:return finish('UNKNOWN','MULTI_RUN_SCOPE_UNRESOLVED')
    if index is None:return finish('UNKNOWN','INDEX_NOT_AVAILABLE')
    _require(isinstance(index,DetectionSnapshot),'Pinned index snapshot required')
    m=deepcopy(index.manifest)
    _require(m['schema_version']=='q-demo.detection-index.v1' and canonical_hash(m,exclude=('index_id','content_sha256','stats'))==expected_index_sha256==m['content_sha256'],'Index pin mismatch')
    _require(q['scene_id']==m['scene_id'] and q['run_ids']==[m['run_id']],'Run/scene outside pinned index','FORBIDDEN_DATA_SCOPE')
    _require(aliases['class_map_sha256']==m['detector']['class_map']['content_sha256'] and canonical_hash({'version':m['detector']['class_map']['version'],'labels':aliases['class_labels']})==aliases['class_map_sha256'],'Alias/model class-map mismatch')
    _require(set(vocabulary['labels'])==set(m['color_method']['color_vocabulary']['labels']),'Alias/index color vocabulary mismatch')
    _require(score>=m['detector']['index_score_floor'],'Query score below index floor','FORBIDDEN_INFERENCE_INPUT')
    scope.update(scene_id=m['scene_id'],scene_revision=m['scene_revision'],run_ids=[m['run_id']],clock_ids=[m['clock_id']],detection_index_id=m['index_id'],detection_index_sha256=expected_index_sha256,class_map_sha256=aliases['class_map_sha256'],color_method_version=m['color_method']['version'])
    response['provenance']['input_refs'].append(m['index_id'])
    if label not in aliases['class_labels']:return finish('UNSUPPORTED_CLASS','CLASS_NOT_IN_CLASS_MAP')
    if color is not None and (label!='person' or color['label'] not in m['color_method']['color_vocabulary']['labels']):return finish('UNSUPPORTED_CONDITION','COLOR_CONDITION_UNSUPPORTED')
    if clock_mapping is None:return finish('UNKNOWN','CLOCK_MAPPING_MISSING')
    _require(clock_mapping.run_id==m['run_id'] and clock_mapping.clock_id==m['clock_id'],'Clock/index binding mismatch')
    scope['clock_mapping_sha256']=clock_mapping.content_sha256
    time=q['time'];_require(isinstance(time,dict),'Invalid time','FORBIDDEN_INFERENCE_INPUT')
    try:
        if time.get('kind')=='SOURCE':
            _require(set(time)=={'kind','run_id','range_us'} and time['run_id']==m['run_id'] and isinstance(time['range_us'],list) and len(time['range_us'])==2,'Invalid source query','FORBIDDEN_INFERENCE_INPUT')
            resolution=resolve_source_range(clock_mapping,*time['range_us'])
        else:
            _require(set(time)=={'kind','wall_range'} and time['kind']=='WALL' and isinstance(time['wall_range'],list) and len(time['wall_range'])==2,'Invalid wall query','FORBIDDEN_INFERENCE_INPUT')
            resolution=resolve_wall_range([clock_mapping],*time['wall_range'])
    except ClockMappingError as exc:raise SearchError(str(exc),'FORBIDDEN_INFERENCE_INPUT') from exc
    scope.update(resolution.to_scope())
    if resolution.status=='OUT_OF_RANGE':return finish('OUT_OF_RANGE')
    if parameter_set is None:return finish('UNKNOWN','PARAMETERS_NOT_APPROVED')
    ps=deepcopy(parameter_set);ph=canonical_hash(ps,exclude=('parameter_set_id','content_sha256','stats'))
    _require(ps['schema_version']=='q-demo.parameter-set.v1' and ph==expected_parameter_sha256==ps['content_sha256'] and ps['parameter_set_id']=='pset:q-demo:'+ph[:16],'Parameter pin mismatch')
    applies=ps['applies_to'];_require(applies['scene_revision']==m['scene_revision'] and m['run_id'] in applies['run_ids'] and m['index_id'] in applies['detection_index_ids'],'Parameter scope mismatch')
    values={p['name']:p for p in ps['parameters']};_require(len(values)==len(ps['parameters']),'Duplicate parameter')
    gap=(values.get('segment_merge_gap_us') or {}).get('value')
    if type(gap) is not int or gap<0:return finish('UNKNOWN','PARAMETERS_NOT_APPROVED')
    approved=ps['approval']['status']=='APPROVED' and bool(ps['approval'].get('approval_ref')) and values['segment_merge_gap_us']['status']=='APPROVED'
    scope.update(parameter_set_id=ps['parameter_set_id'],parameter_set_sha256=ph)
    _require(isinstance(camera_catalog_ids,list) and camera_catalog_ids and len(set(camera_catalog_ids))==len(camera_catalog_ids),'Explicit full camera catalog required')
    selected=set(q['camera_ids'] or camera_catalog_ids);_require(selected<=set(camera_catalog_ids),'Camera outside registered catalog','FORBIDDEN_DATA_SCOPE')
    graph_draft=False
    if q['region_ids'] is not None:
        if graphs is None:return finish('UNKNOWN','GRAPH_NOT_AVAILABLE')
        r,c=graphs.region,graphs.camera
        _require(r['scene_id']==m['scene_id'] and r['scene_revision']==m['scene_revision'],'Graph/index scene mismatch')
        _require(set(q['region_ids'])<={n['region_id'] for n in r['regions']},'Region outside graph','FORBIDDEN_DATA_SCOPE')
        selected&={cam['camera_id'] for cam in c['cameras'] if any(cover['region_id'] in q['region_ids'] for cover in cam['covered_regions'])}
        scope.update(region_graph_sha256=r['content_sha256'],camera_graph_sha256=c['content_sha256']);graph_draft=graphs.approval_status!='APPROVED'
    scope['camera_ids']=sorted(selected)
    if not selected:return finish('UNKNOWN','EMPTY_CAMERA_SCOPE')
    left,right=resolution.ranges[0].range_us
    metadata={c['camera_id']:c for c in m['sampling']['per_camera']};_require(len(metadata)==len(m['sampling']['per_camera']),'Duplicate camera metadata')
    partial=not resolution.coverage_complete;all_results=[]
    for camera in sorted(selected):
        meta=metadata.get(camera)
        if meta is None:response['not_evaluated_cameras'].append({'camera_id':camera,'reason':'NO_INDEX_BINDING'});partial=True;continue
        base,step,stride,origin=[meta[k] for k in ['source_frame_interval_us','index_interval_us','stride_samples','index_grid_origin_frame']]
        _require(all(type(v) is int and v>0 for v in [base,step,stride]) and type(origin) is int and origin>=0 and step==base*stride and stride==m['sampling']['stride_samples'],'Invalid index grid')
        ranges=_overlap(_ranges(meta['sampled_ranges_us']),left,right);full=sum(b-a for a,b in ranges)==right-left
        expected=sum(_ceil(b,base)-_ceil(a,base) for a,b in ranges)
        rows=[];seen=set()
        for row in index.records:
            if row['camera_id']!=camera:continue
            _safe_content(row)
            _require(row['frame_ref']==f"frame:{m['run_id']}:{camera}:{row['frame_index']}",'Frame reference mismatch')
            f,t=row['frame_index'],row['timestamp_us'];_require(type(f) is int and f>=0 and type(t) is int and t==f*base and f not in seen,'Invalid/duplicate frame grid');seen.add(f)
            if any(a<=t<b for a,b in ranges):rows.append(row)
        _require(len(rows)==expected,'Absent source row is integrity error')
        coverage=dict(evaluated_frames=0,not_sampled_frames=max(0,_ceil(right,base)-_ceil(left,base)-expected),not_inferred_frames=0,missing_frames=0);hits=[];evaluated=[]
        for row in sorted(rows,key=lambda r:r['timestamp_us']):
            state=row['frame_state'];on_grid=row['frame_index']>=origin and (row['frame_index']-origin)%stride==0
            _require(state in {'INFERRED','NOT_SAMPLED','NOT_INFERRED','MISSING'} and (state=='NOT_SAMPLED')==(not on_grid),'Frame/index state mismatch')
            coverage[{'INFERRED':'evaluated_frames','NOT_SAMPLED':'not_sampled_frames','NOT_INFERRED':'not_inferred_frames','MISSING':'missing_frames'}[state]]+=1
            if state!='INFERRED':_require(row['detections'] is None,'Uninferred row with detections');continue
            _require(isinstance(row['detections'],list),'Inferred row requires detections');evaluated.append(row)
            matched=[]
            for ordinal,d in enumerate(row['detections']):
                _require(d['observation_id']==f"obs:{m['index_id'].split(':')[-1]}:{camera}:{row['frame_index']}:{ordinal}",'Observation binding mismatch')
                _require(type(d['score']) in (int,float) and math.isfinite(d['score']) and 0<=d['score']<=1,'Invalid score')
                if d['class_label']!=label or d['score']<score:continue
                if color is not None:
                    verdict=(d.get('color') or {}).get('verdicts',{}).get(color['label']);_require(verdict in {'STRONG','WEAK','UNKNOWN','NONE'},'Missing color verdict')
                    if verdict not in ({'STRONG'} if color['min_verdict']=='STRONG' else {'STRONG','WEAK'}):continue
                matched.append(d)
            if len(matched)>=condition['min_count_per_frame']:hits.append((row,matched))
        complete=full and not coverage['not_inferred_frames'] and not coverage['missing_frames'] and bool(coverage['evaluated_frames'])
        partial|=not complete
        if not hits:
            if complete:response['no_match_cameras'].append({'camera_id':camera,'coverage':coverage})
            else:response['not_evaluated_cameras'].append({'camera_id':camera,'reason':'INCOMPLETE_COVERAGE'})
            continue
        _require(callable(media_token_for_frame),'Stable media issuer required')
        groups=[]
        for hit in hits:
            if not groups or hit[0]['timestamp_us']-min(right,groups[-1][-1][0]['timestamp_us']+step)>gap:groups.append([hit])
            else:groups[-1].append(hit)
        segments=[]
        for group in groups:
            start=group[0][0]['timestamp_us'];end=min(right,group[-1][0]['timestamp_us']+step)
            representative=max(group,key=lambda item:(max(d['score'] for d in item[1]),-item[0]['timestamp_us']))
            token=media_token_for_frame(representative[0]['frame_ref']);_require(isinstance(token,str) and token and not token.startswith(('/','file:')),'Invalid media token')
            segments.append({'range_us':[start,end],'matched_frames':len(group),'evaluated_frames':sum(start<=row['timestamp_us']<end for row in evaluated),'representative':{'frame_ref':representative[0]['frame_ref'],'observation_ids':[d['observation_id'] for d in representative[1]],'media_token':token}})
        all_results.append({'camera_id':camera,'matched_segments':segments,'coverage':coverage})
    all_results.sort(key=lambda x:(x['matched_segments'][0]['range_us'][0],x['camera_id']))
    for rank,result in enumerate(all_results,1):result['rank']=rank
    offset=0
    if q['cursor'] is not None:
        match=re.fullmatch(r'q1:([0-9a-f]{64}):(\d+)',q['cursor']);_require(match is not None and match[1]==query_sha,'Cursor scope mismatch','FORBIDDEN_INFERENCE_INPUT');offset=int(match[2]);_require(offset%q['page_size']==0 and offset<len(all_results),'Cursor outside results','FORBIDDEN_INFERENCE_INPUT')
    response.update(results_total=len(all_results),results=all_results[offset:offset+q['page_size']]);response['returned_count']=len(response['results'])
    if offset+q['page_size']<len(all_results):response['next_cursor']=f"q1:{query_sha}:{offset+q['page_size']}"
    if not resolution.coverage_complete:return finish('PARTIAL','TIME_SCOPE_PARTIAL')
    if graph_draft:return finish('PARTIAL','GRAPH_NOT_APPROVED')
    if not approved:return finish('PARTIAL','PARAMETERS_NOT_APPROVED')
    if partial:return finish('PARTIAL','INCOMPLETE_EVIDENCE')
    return finish('READY' if all_results else 'NO_MATCH')
