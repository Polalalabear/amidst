"""Deterministic, index-ticked Q2/Q5 controller; no media, GT, model or PG reads.

The server supplies pinned metadata and a Q4 evidence port. RULE_ONLY uses source
index ticks and never truncates work by wall time. Subclasses may implement the
separate Agent policy; all execution still passes the shared observation guard.
"""
import json
import math
import threading
import time
from copy import deepcopy
from dataclasses import dataclass

from amidst.q1q5.candidates import transition_candidates
from amidst.q1q5.clock_mapping import (
    ClockMapping,
    ClockMappingError,
    resolve_source_range,
    resolve_wall_range,
)
from amidst.q1q5.graphs import GraphBundle, GraphError, load_graphs
from amidst.q1q5.linker import LinkError, LinkParameters, LocalLinker, _box, _iou
from amidst.q1q5.reasons import ordered_reasons
from amidst.q1q5.store import DetectionSnapshot, _safe_content, canonical_hash


class SessionCancelled(RuntimeError):
    pass


class ControllerError(ValueError):
    def __init__(self,message,code='DataIntegrityError'):
        super().__init__(message);self.code=code


def require(ok,message,code='DataIntegrityError'):
    if not ok:raise ControllerError(message,code)


def jsonl(records):
    return b''.join(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()+b'\n' for row in records)


def file_hash(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def ranges(value):
    require(isinstance(value,list),'Explicit source ranges required');last=-1
    for pair in value:
        require(isinstance(pair,list) and len(pair)==2 and all(type(x) is int and x>=0 for x in pair)
                and last<=pair[0]<pair[1],'Invalid source ranges');last=pair[1]
    return value


def intersect(a,b):
    result=[]
    for l,r in a:
        for x,y in b:
            start,end=max(l,x),min(r,y)
            if start<end:result.append([start,end])
    return sorted(result)


def complement(window,available):
    left,right=window;cursor=left;missing=[]
    for a,b in intersect([window],available):
        if cursor<a:missing.append([cursor,a])
        cursor=max(cursor,b)
    if cursor<right:missing.append([cursor,right])
    return missing


@dataclass(frozen=True)
class RuntimeBindings:
    index: DetectionSnapshot | None
    index_sha256: str | None
    graphs: GraphBundle | None
    region_graph_sha256: str | None
    camera_graph_sha256: str | None
    clock: ClockMapping | None
    clock_sha256: str | None
    parameter_set: dict | None
    parameter_sha256: str | None
    media_ranges_by_camera: dict
    media_scope_sha256: str


@dataclass(frozen=True)
class SessionResult:
    response: dict
    decisions_bytes: bytes
    links_bytes: bytes
    snapshots: tuple
    evidence: tuple
    seed_candidates: tuple
    diagnostics: tuple




class RuleController:
    """One run/session. Caller never supplies an execution script or hidden route.

    Non-executable/missing required parameters return UNKNOWN before seed choice.
    A separate seed-candidate port exposes choices without inventing response wire
    fields. Multi-candidate appearance seeds require an explicit user selection.
    """
    def __init__(self,request,*,bindings,evidence_provider,selected_observation_id=None,on_tick=None):
        require(isinstance(bindings,RuntimeBindings),'Pinned runtime bindings required')
        require(callable(evidence_provider),'Explicit Q4 evidence port required')
        self.request=deepcopy(request);self.bindings=bindings;self.evidence_provider=evidence_provider
        self.selected_observation_id=selected_observation_id
        require(on_tick is None or callable(on_tick),"Tick scheduler must be callable")
        self._cancelled=threading.Event();self._generation=0;self._manual_restart_agent=False
        self.on_tick=on_tick;self._control_lock=threading.RLock();self._manual_request=None;self._running=False
        self.decisions=[];self.links=[];self.snapshots=[];self.evidence=[];self.seeds=[];self.diagnostics=[]
        self.timeline=[];self.searching_index=0;self.session_agent_rounds_used=0
        self._episode_agent_rounds=0;self._episode_budget_ms=0;self.fallback_reason=None
        self.agent_attempted=False;self._cache={};self._latency_ms=0.0;self._ran=False
        self.scope={k:None for k in ['scene_id','scene_revision','run_ids','clock_ids','clock_mapping_sha256',
            'requested_time','resolved_source_ranges_us','time_coverage','camera_ids','detection_index_id',
            'detection_index_sha256','region_graph_sha256','camera_graph_sha256','class_map_sha256',
            'color_method_version','parameter_set_id','parameter_set_sha256','tracking_scope_sha256']}
        self.session_id='sess-'+canonical_hash({'request':self.request,'index':bindings.index_sha256,
            'region':bindings.region_graph_sha256,'camera':bindings.camera_graph_sha256,
            'tracking_scope':bindings.graphs.tracking_scope_sha256 if bindings.graphs else None,'clock':bindings.clock_sha256,'parameters':bindings.parameter_sha256,'media':bindings.media_scope_sha256,'selected_seed':selected_observation_id})[:16]
        self.cursor=0;self.current_camera=None;self.partial=False;self.graph_draft=False;self.time_partial=False;self.parameter_block_status="UNKNOWN"
        self.blocking_reasons=[]

    def _collect_blocking_reasons(self, manifest):
        """Collect independent missing prerequisites; corrupted pins still fail."""
        b=self.bindings;reasons=[]
        if b.clock is None:reasons.append('CLOCK_MAPPING_MISSING')
        if b.graphs is None:reasons.append('GRAPH_NOT_AVAILABLE')
        else:
            try:
                graph=load_graphs(b.graphs.region,b.graphs.camera,
                    region_sha256=b.region_graph_sha256,camera_sha256=b.camera_graph_sha256,
                    tracking_scope=b.graphs.tracking_scope,
                    tracking_scope_sha256=b.graphs.tracking_scope_sha256,tracking_scope_bytes=b.graphs.tracking_scope_bytes)
                self.scope['tracking_scope_sha256']=graph.tracking_scope_sha256
                index_cameras={x['camera_id'] for x in manifest['sampling']['per_camera']}
                graph_cameras={x['camera_id'] for x in graph.camera['cameras']}
                if graph.tracking_scope is None and not index_cameras<=graph_cameras:
                    reasons.append('TRACKING_SCOPE_MISSING')
                elif graph.tracking_scope is not None:
                    require(index_cameras<=set(graph.tracking_scope['query_camera_ids']),
                            'Index cameras outside declared query scope')
                    if graph.tracking_scope['G4_approved'] is not True or graph.approval_status!='APPROVED':
                        reasons.append('GRAPH_NOT_APPROVED')
            except GraphError as exc:
                if exc.code in {'EXIT_ZONES_MISSING','TRACKING_SCOPE_MISSING'}:reasons.append(exc.code)
                else:raise
        parameter=b.parameter_set;parameter_interval=None;items={}
        if parameter is None:reasons.append('PARAMETERS_NOT_APPROVED')
        else:
            p=deepcopy(parameter);_safe_content(p)
            ph=canonical_hash(p,exclude=('parameter_set_id','content_sha256','stats'))
            require(p['schema_version']=='q-demo.parameter-set.v1'
                    and ph==b.parameter_sha256==p['content_sha256']
                    and p['parameter_set_id']=='pset:q-demo:'+ph[:16]
                    and self.request['parameter_set_id']==p['parameter_set_id'],
                    'Parameter pin/request mismatch')
            scope=p['applies_to'];require(scope['scene_revision']==manifest['scene_revision']
                and manifest['run_id'] in scope['run_ids']
                and manifest['index_id'] in scope['detection_index_ids'],'Parameter scope mismatch')
            parameter_interval=scope['index_interval_us']
            items={x['name']:x for x in p['parameters']}
            require(len(items)==len(p['parameters']),'Duplicate parameter')
            names={'query_min_score','top_k','search_window_us','research_interval_us',
                   'session_max_research_rounds','switch_min_presence','evidence_max_observations',
                   'fallback_budget_ms','exit_rule'}
            link_names={'link_iou_min','link_center_dist_max_diag_ratio','link_max_gap_us',
                        'link_min_score','link_color_rule','link_ambiguity_margin'}
            if names|link_names<=items.keys() and all(items[n].get('value') is not None for n in names|link_names):
                self.parameter_block_status='PARTIAL'
            if (p['approval']['status']!='APPROVED' or not p['approval'].get('approval_ref')
                    or not p['approval'].get('approved_by') or not names|link_names<=items.keys()
                    or any(items[n].get('status')!='APPROVED' or items[n].get('value') is None
                           for n in names|link_names if n in items)
                    or any(not items[n].get('proposal_ref') for n in link_names if n in items)):
                reasons.append('PARAMETERS_NOT_APPROVED')
        active={m['camera_id'] for m in manifest['sampling']['per_camera']}
        if b.graphs is not None and b.graphs.tracking_scope is not None:
            active &= set(b.graphs.tracking_scope['tracking_camera_ids'])
        intervals=[]
        for meta in manifest['sampling']['per_camera']:
            if meta['camera_id'] not in active:continue
            base,step,stride,origin=[meta[k] for k in ['source_frame_interval_us','index_interval_us',
                                                    'stride_samples','index_grid_origin_frame']]
            if (not all(type(v) is int and v>0 for v in [base,step,stride])
                    or type(origin) is not int or origin<0
                    or stride!=manifest['sampling']['stride_samples'] or step!=base*stride
                    or (parameter_interval is not None and parameter_interval!=step)):
                reasons.append('PARAMETER_GRID_MISMATCH')
            intervals.append(step)
        if len(set(intervals))!=1:reasons.append('PARAMETER_GRID_MISMATCH')
        for interval in intervals:
            if type(interval) is not int or interval<=0:continue
            research=items.get('research_interval_us',{}).get('value')
            gap=items.get('link_max_gap_us',{}).get('value')
            if type(research) is int and research>0 and research%interval:
                reasons.append('PARAMETER_GRID_MISMATCH')
            if type(gap) is int and (gap<interval or gap%interval):
                reasons.append('PARAMETER_GRID_MISMATCH')
            samples=items.get('link_max_gap_samples')
            if samples is not None and type(gap) is int and gap>=interval and not gap%interval:
                if type(samples.get('value')) is not int or samples['value']!=gap//interval-1:
                    reasons.append('PARAMETER_GRID_MISMATCH')
        self.blocking_reasons=ordered_reasons(reasons)
        return self.blocking_reasons

    def _ensure_active(self):
        if self._cancelled.is_set():raise SessionCancelled("USER_STOPPED")

    def request_stop(self):
        """Freeze a USER stop journal before rejecting any late worker publication."""
        with self._control_lock:
            if not self._cancelled.is_set():
                self._generation+=1
                self._emit(self.decisions[-1]['state_after'] if self.decisions else None,
                           'ENDED',self.cursor,decided_by='USER',control_reason='USER_STOPPED')
                self._cancelled.set()
            decisions=jsonl(self.decisions);links=jsonl(self.links)
            return {'schema_version':'q-demo.stop-receipt.v1','session_id':self.session_id,
                'status':'STOP_REQUESTED','reason':'USER_STOPPED','generation':self._generation,
                'provider_cancelled':None,'decisions_sha256':file_hash(decisions),'links_sha256':file_hash(links),
                'decisions_jsonl':decisions.decode(),'links_jsonl':links.decode(),
                'session_agent_rounds_used':self.session_agent_rounds_used,'searching_index':self.searching_index,
                'gt_read':False,'identity_verdict':'UNCONFIRMED'}

    def _validate_mode(self):
        require(self.request['switch_mode']=='RULE_ONLY','Agent mode requires the separately authorized Agent controller','FORBIDDEN_INFERENCE_INPUT')

    def _prepare(self):
        q=self.request;b=self.bindings
        required={'schema_version','session_ref','scene_id','run_ids','time','seed','switch_mode','parameter_set_id'}
        require(isinstance(q,dict) and set(q)==required and q['schema_version']=='q-demo.q2-request.v1','Unexpected Q2 request','FORBIDDEN_INFERENCE_INPUT')
        _safe_content(q);self._validate_mode()
        require(isinstance(q['session_ref'],str) and q['session_ref'] and isinstance(q['run_ids'],list)
                and len(q['run_ids'])==1 and isinstance(q['run_ids'][0],str),'Explicit single run required','FORBIDDEN_DATA_SCOPE')
        if b.index is None:return 'INDEX_NOT_AVAILABLE'
        require(isinstance(b.index,DetectionSnapshot),'Index snapshot required')
        self.index=deepcopy(b.index);m=self.index.manifest;_safe_content(m)
        require(m['schema_version']=='q-demo.detection-index.v1' and canonical_hash(m,exclude=('index_id','content_sha256','stats'))==b.index_sha256==m['content_sha256'],'Index pin mismatch')
        require(q['scene_id']==m['scene_id'] and q['run_ids']==[m['run_id']],'Request/index scope mismatch','FORBIDDEN_DATA_SCOPE')
        self.manifest=m;self.scope.update(scene_id=m['scene_id'],scene_revision=m['scene_revision'],run_ids=[m['run_id']],clock_ids=[m['clock_id']],
            detection_index_id=m['index_id'],detection_index_sha256=b.index_sha256,class_map_sha256=m['detector']['class_map']['content_sha256'],color_method_version=m['color_method']['version'])
        blockers=self._collect_blocking_reasons(m)
        if blockers:return blockers[0]
        if b.clock is None:return 'CLOCK_MAPPING_MISSING'
        require(isinstance(b.clock,ClockMapping) and b.clock.content_sha256==b.clock_sha256
                and (b.clock.run_id,b.clock.clock_id)==(m['run_id'],m['clock_id']),'Clock pin/scope mismatch')
        self.scope['clock_mapping_sha256']=b.clock_sha256
        t=q['time'];require(isinstance(t,dict),'Explicit time required','FORBIDDEN_INFERENCE_INPUT')
        try:
            if t.get('kind')=='SOURCE':
                require(set(t)=={'kind','run_id','range_us'} and t['run_id']==m['run_id'] and isinstance(t['range_us'],list) and len(t['range_us'])==2,'Source time scope mismatch','FORBIDDEN_INFERENCE_INPUT')
                resolved=resolve_source_range(b.clock,*t['range_us'])
            else:
                require(set(t)=={'kind','wall_range'} and t['kind']=='WALL' and len(t['wall_range'])==2,'Wall time required','FORBIDDEN_INFERENCE_INPUT')
                resolved=resolve_wall_range([b.clock],*t['wall_range'])
        except ClockMappingError as exc:raise ControllerError(str(exc),'FORBIDDEN_INFERENCE_INPUT') from exc
        self.scope.update(resolved.to_scope())
        if not resolved.ranges:return 'TIME_OUT_OF_RANGE'
        self.left,self.right=resolved.ranges[0].range_us;self.cursor=self.left;self.time_partial=not resolved.coverage_complete
        if b.graphs is None:return 'GRAPH_NOT_AVAILABLE'
        try:self.graphs=load_graphs(b.graphs.region,b.graphs.camera,region_sha256=b.region_graph_sha256,camera_sha256=b.camera_graph_sha256,
            tracking_scope=b.graphs.tracking_scope,tracking_scope_sha256=b.graphs.tracking_scope_sha256,tracking_scope_bytes=b.graphs.tracking_scope_bytes)
        except GraphError as exc:
            if exc.code=='EXIT_ZONES_MISSING':return 'EXIT_ZONES_MISSING'
            raise
        r,c=self.graphs.region,self.graphs.camera
        require((r['scene_id'],r['scene_revision'])==(m['scene_id'],m['scene_revision']),'Graph/index scope mismatch')
        self.scope.update(region_graph_sha256=b.region_graph_sha256,camera_graph_sha256=b.camera_graph_sha256);self.graph_draft=self.graphs.approval_status!='APPROVED'
        self.all_metadata={x['camera_id']:x for x in m['sampling']['per_camera']};require(len(self.all_metadata)==len(m['sampling']['per_camera']),'Duplicate index camera')
        tracking=set(self.graphs.tracking_scope['tracking_camera_ids']) if self.graphs.tracking_scope else {x['camera_id'] for x in c['cameras']}
        self.metadata={cid:meta for cid,meta in self.all_metadata.items() if cid in tracking}
        self.cameras=sorted(self.metadata)
        self.scope['camera_ids']=self.cameras
        require(canonical_hash(b.media_ranges_by_camera)==b.media_scope_sha256 and set(b.media_ranges_by_camera)==set(self.all_metadata),'Media scope pin mismatch')
        self.available={camera:intersect(ranges(b.media_ranges_by_camera[camera]),intersect(ranges(meta['sampled_ranges_us']),[[self.left,self.right]])) for camera,meta in self.metadata.items()}
        if b.parameter_set is None:return 'PARAMETERS_NOT_APPROVED'
        p=deepcopy(b.parameter_set);_safe_content(p);ph=canonical_hash(p,exclude=('parameter_set_id','content_sha256','stats'))
        require(p['schema_version']=='q-demo.parameter-set.v1' and ph==b.parameter_sha256==p['content_sha256'] and p['parameter_set_id']=='pset:q-demo:'+ph[:16] and q['parameter_set_id']==p['parameter_set_id'],'Parameter pin/request mismatch')
        scope=p['applies_to'];require(scope['scene_revision']==m['scene_revision'] and m['run_id'] in scope['run_ids'] and m['index_id'] in scope['detection_index_ids'],'Parameter scope mismatch')
        self.scope.update(parameter_set_id=p['parameter_set_id'],parameter_set_sha256=ph)
        intervals=[]
        for meta in self.all_metadata.values():
            base,step,stride,origin=[meta[k] for k in ['source_frame_interval_us','index_interval_us','stride_samples','index_grid_origin_frame']]
            if (not all(type(v) is int and v>0 for v in [base,step,stride]) or type(origin) is not int or origin<0
                or stride!=m['sampling']['stride_samples'] or step!=base*stride or scope['index_interval_us']!=step):return 'PARAMETER_GRID_MISMATCH'
            intervals.append(step)
        if len(set(intervals))!=1:return 'PARAMETER_GRID_MISMATCH'
        self.interval=intervals[0]
        items={x['name']:x for x in p['parameters']};require(len(items)==len(p['parameters']),'Duplicate parameter')
        names={'query_min_score','top_k','search_window_us','research_interval_us','session_max_research_rounds',
               'switch_min_presence','evidence_max_observations','fallback_budget_ms','exit_rule'}
        link_names={'link_iou_min','link_center_dist_max_diag_ratio','link_max_gap_us','link_min_score','link_color_rule','link_ambiguity_margin'}
        if names|link_names<=items.keys() and all(items[n].get('value') is not None for n in names|link_names):self.parameter_block_status='PARTIAL'
        if (p['approval']['status']!='APPROVED' or not p['approval'].get('approval_ref') or not p['approval'].get('approved_by')
            or not names<=items.keys() or any(items[n].get('status')!='APPROVED' or items[n].get('value') is None for n in names)):return 'PARAMETERS_NOT_APPROVED'
        self.values={name:items[name]['value'] for name in names}
        for name in ['top_k','search_window_us','research_interval_us','session_max_research_rounds','evidence_max_observations','fallback_budget_ms']:
            require(type(self.values[name]) is int and self.values[name]>0,'Explicit positive parameter required: '+name)
        require(self.values['research_interval_us']%self.interval==0,'Research interval not representable by index grid','PARAMETER_GRID_MISMATCH')
        score=self.values['query_min_score'];require(type(score) in (int,float) and math.isfinite(score) and m['detector']['index_score_floor']<=score<=1,'Query score below index floor','FORBIDDEN_INFERENCE_INPUT')
        # Weak/unknown evidence never causes an automatic cut in this profile.
        if self.values['switch_min_presence']!='MATCH_STRONG':return 'PARAMETERS_NOT_APPROVED'
        rule=self.values['exit_rule']
        if not (isinstance(rule,dict) and set(rule)=={'method','boundary_inclusive'} and rule['method']=='BBOX_BOTTOM_MIDPOINT' and type(rule['boundary_inclusive']) is bool):return 'PARAMETERS_NOT_APPROVED'
        self.link_parameters={}
        try:
            for camera in self.cameras:self.link_parameters[camera]=LinkParameters.from_document(p,expected_sha256=ph,scene_revision=m['scene_revision'],run_id=m['run_id'],index_id=m['index_id'],index_interval_us=self.metadata[camera]['index_interval_us'])
        except LinkError as exc:
            if exc.code in {'PARAMETERS_NOT_APPROVED','PARAMETER_GRID_MISMATCH'}:return exc.code
            raise
        seed=q['seed'];require(isinstance(seed,dict) and seed.get('kind') in {'OBSERVATION','APPEARANCE'},'Explicit seed required','FORBIDDEN_INFERENCE_INPUT')
        if seed['kind']=='OBSERVATION':
            require(set(seed)=={'kind','observation_id'} and isinstance(seed['observation_id'],str),'Observation seed schema mismatch','FORBIDDEN_INFERENCE_INPUT');self.color_label=None
        else:
            require(set(seed)=={'kind','class_label','color'} and seed['class_label']=='person','Appearance seed schema mismatch','FORBIDDEN_INFERENCE_INPUT')
            color=seed['color'];require(color is None or (isinstance(color,dict) and set(color)=={'label','min_verdict'} and color['label'] in m['color_method']['color_vocabulary']['labels'] and color['min_verdict'] in {'STRONG','WEAK'}),'Unsupported seed color','FORBIDDEN_INFERENCE_INPUT')
            self.color_label=color['label'] if color else None
        self.records={};self.observations={}
        for original_row in self.index.records:
            row=deepcopy(original_row)
            require(row.get('run_id',m['run_id'])==m['run_id'] and row.get('clock_id',m['clock_id'])==m['clock_id'],'Record source mismatch')
            row.update(run_id=m['run_id'],clock_id=m['clock_id'])
            _safe_content(row);camera=row['camera_id'];frame=row['frame_index'];timestamp=row['timestamp_us']
            require(camera in self.all_metadata and (row['run_id'],row['clock_id'])==(m['run_id'],m['clock_id']),'Record source mismatch')
            meta=self.all_metadata[camera];require(type(frame) is int and frame>=0 and timestamp==frame*meta['source_frame_interval_us'] and type(timestamp) is int,'Frame grid mismatch')
            require(row['frame_ref']==f"frame:{m['run_id']}:{camera}:{frame}" and (camera,frame) not in self.records,'Frame ref/duplicate mismatch')
            state=row['frame_state'];on_grid=frame>=meta['index_grid_origin_frame'] and (frame-meta['index_grid_origin_frame'])%meta['stride_samples']==0
            require(state in {'INFERRED','NOT_SAMPLED','NOT_INFERRED','MISSING'} and (state=='NOT_SAMPLED')==(not on_grid),'Record/grid state mismatch')
            require(isinstance(row['detections'],list) if state=='INFERRED' else row['detections'] is None,'Record detections/state mismatch')
            self.records[(camera,frame)]=deepcopy(row)
            for ordinal,observation in enumerate(row['detections'] or []):
                oid=observation['observation_id'];require(oid==f"obs:{m['index_id'].split(':')[-1]}:{camera}:{frame}:{ordinal}" and oid not in self.observations,'Observation binding mismatch')
                _box(observation);require(type(observation['score']) in (int,float) and math.isfinite(observation['score']) and 0<=observation['score']<=1,'Invalid score')
                self.observations[oid]=(deepcopy(row),deepcopy(observation))
        selected=self.selected_observation_id or (seed['observation_id'] if seed['kind']=='OBSERVATION' else None)
        if selected in self.observations and self.observations[selected][0]['camera_id'] not in self.metadata:
            self.blocking_reasons=['SEED_CAMERA_NOT_TRACKED']
            return 'SEED_CAMERA_NOT_TRACKED'
        for camera,meta in self.metadata.items():
            base=meta['source_frame_interval_us']
            for left,right in intersect(meta['sampled_ranges_us'],[[self.left,self.right]]):
                for frame in range(-(-left//base),-(-right//base)):require((camera,frame) in self.records,'Absent source row is an integrity error')
            self.partial|=bool(complement([self.left,self.right],self.available[camera]))
        self.partial|=any(r['camera_id'] in self.metadata and self.left<=r['timestamp_us']<self.right and r['frame_state'] in {'MISSING','NOT_INFERRED'} for r in self.records.values())
        return None

    def _seed_candidates(self):
        seed=self.request['seed'];choices=[]
        for oid,(row,observation) in self.observations.items():
            if not (row['camera_id'] in self.available and self.left<=row['timestamp_us']<self.right and row['frame_state']=='INFERRED'
                    and any(a<=row['timestamp_us']<b for a,b in self.available[row['camera_id']])
                    and observation['class_label']=='person' and observation['score']>=self.values['query_min_score']):continue
            if seed['kind']=='OBSERVATION':
                if oid!=seed['observation_id']:continue
            elif self.color_label is not None:
                verdict=(observation.get('color') or {}).get('verdicts',{}).get(self.color_label)
                allowed={'STRONG'} if seed['color']['min_verdict']=='STRONG' else {'STRONG','WEAK'}
                if verdict not in allowed:continue
            choices.append({'observation_id':oid,'camera_id':row['camera_id'],'timestamp_us':row['timestamp_us'],
                            'frame_ref':row['frame_ref'],'score':observation['score']})
        choices.sort(key=lambda x:(x['timestamp_us'],x['camera_id'],x['observation_id']));self.seeds=choices
        selected=self.selected_observation_id or (seed['observation_id'] if seed['kind']=='OBSERVATION' else None)
        if selected is not None:
            require(isinstance(selected,str) and selected in {x['observation_id'] for x in choices},'Selected seed outside query/candidate scope','FORBIDDEN_DATA_SCOPE')
            return self.observations[selected]
        if len(choices)==1:return self.observations[choices[0]['observation_id']]
        return None

    def _new_linker(self,row,observation):
        camera=row['camera_id'];meta=self.metadata[camera]
        return LocalLinker(row,observation['observation_id'],parameters=self.link_parameters[camera],
            stride_samples=meta['stride_samples'],index_grid_origin_frame=meta['index_grid_origin_frame'],color_label=self.color_label)

    def _gap(self,end,states,camera):
        end=min(end,self.right)
        if end<=self.cursor:return
        if self.timeline and self.timeline[-1]['kind']=='GAP' and self.timeline[-1]['camera_shown']==camera and self.timeline[-1]['range_us'][1]==self.cursor:
            segment=self.timeline[-1];segment['range_us'][1]=end
            for state in states:
                if state not in segment['gap_states']:segment['gap_states'].append(state)
        else:self.timeline.append({'segment_id':self.session_id+':seg:'+str(len(self.timeline)),'kind':'GAP','range_us':[self.cursor,end],
                                   'gap_states':list(states),'camera_shown':camera,'position':None})
        self.cursor=end

    def _observe(self,row,observation,entered_by,decided_by='USER',decision_id=None):
        timestamp=row['timestamp_us'];camera=row['camera_id'];self._gap(timestamp,[],self.current_camera or camera)
        require(timestamp>=self.cursor,'Observation would backdate playback')
        end=min(self.right,timestamp+self.metadata[camera]['index_interval_us'])
        require(timestamp<end,'Empty/out-of-query observation cell')
        if (entered_by=='LINK' and self.timeline and self.timeline[-1]['kind']=='ON_CAMERA'
            and self.timeline[-1]['camera_id']==camera and self.timeline[-1]['range_us'][1]==timestamp):
            self.timeline[-1]['range_us'][1]=end;self.timeline[-1]['observation_ids'].append(observation['observation_id'])
        else:
            segment={'segment_id':self.session_id+':seg:'+str(len(self.timeline)),'kind':'ON_CAMERA','camera_id':camera,
                     'range_us':[timestamp,end],'entered_by':entered_by,'decided_by':decided_by,
                     'observation_ids':[observation['observation_id']],'presence_at_entry':'MATCH_STRONG' if self.color_label is None or (observation.get('color') or {}).get('verdicts',{}).get(self.color_label)=='STRONG' else 'MATCH_WEAK'}
            if decision_id is not None:segment['decision_id']=decision_id
            self.timeline.append(segment)
        self.cursor=end;self.current_camera=camera

    def _decider(self):return 'RULE_ONLY'

    def _emit(self,before,after,source_time,*,decision_time=None,snapshot=None,considered=(),tool_calls=(),
              submitted=None,accepted=True,rejection_code=None,action=None,candidate_ref=None,entry_id=None,decided_by=None,llm_calls=(),cause_decision_id=None,control_reason=None):
        self._ensure_active()
        require(type(source_time) is int and (decision_time is None or source_time>=decision_time),'Decision would backdate source')
        record={'schema_version':'q-demo.decision-record.v1','decision_id':self.session_id+'-dec-'+str(len(self.decisions)),
                'session_id':self.session_id,'input_pins':{'tracking_scope_sha256':self.scope['tracking_scope_sha256']},'step_index':len(self.decisions),'state_before':before,'state_after':after,
                'source_time_us':source_time,'decision_time_us':decision_time,'switch_mode':self.request['switch_mode'],
                'candidate_snapshot_sha256':snapshot['candidate_snapshot_sha256'] if snapshot else None,
                'exit_resolution':snapshot['exit_resolution'] if snapshot else None,'candidates_considered':list(deepcopy(considered)),
                'tool_calls':list(deepcopy(tool_calls)),'llm_calls':list(deepcopy(llm_calls)),
                'submitted':deepcopy(submitted),'accepted':accepted,'rejection_code':rejection_code,'executed_action':action,
                'executed_candidate_ref':candidate_ref,'entry_observation_id':entry_id,'decided_by':decided_by or self._decider(),
                'fallback_reason':self.fallback_reason,'rounds_used':self._episode_agent_rounds,'budget_used_ms':self._episode_budget_ms,
                'searching_index':self.searching_index,'session_agent_rounds_used':self.session_agent_rounds_used}
        if cause_decision_id is not None:record['cause_decision_id']=cause_decision_id
        if control_reason is not None:record['control_reason']=control_reason
        record['content_sha256']=canonical_hash(record);self.decisions.append(record);return record

    def _link_log(self,link,row,segment_id,ambiguous_ids=(),previous=None):
        ambiguous=None
        if link['decision']=='AMBIGUOUS_LINK':
            allowed=set(ambiguous_ids);ambiguous=[{'observation_id':o['observation_id'],'iou':_iou(link.get('matching_audit',{}).get('reference_bbox_xyxy_px',_box(previous)),_box(o))}
                for o in row['detections'] if o['observation_id'] in allowed]
            ambiguous.sort(key=lambda item:(-item['iou'],item['observation_id']))
        record={'schema_version':'q-demo.link-record.v1','session_id':self.session_id,'link_index':len(self.links),
                'run_id':self.manifest['run_id'],'camera_id':row['camera_id'],'frame_ref':row['frame_ref'],
                'local_segment_id':segment_id,'ambiguous_candidates':ambiguous,**deepcopy(link)}
        self.links.append(record)

    def _snapshot(self,camera,observation,window_start):
        snapshot=transition_candidates(self.graphs,from_camera_id=camera,last_bbox_xyxy_px=observation['bbox_xyxy_px'],
            session_id=self.session_id,top_k=self.values['top_k'],window_us=[window_start,window_start+self.values['search_window_us']],
            exit_boundary_inclusive=self.values['exit_rule']['boundary_inclusive'],allowed_camera_ids=self.cameras)
        snapshot.pop('candidate_snapshot_sha256')
        for candidate in snapshot['candidates']:
            candidate.pop('candidate_ref');candidate['window_truncated_us']=complement(candidate['window_us'],self.available[candidate['camera_id']])
        digest=canonical_hash(snapshot);snapshot['candidate_snapshot_sha256']=digest
        for candidate in snapshot['candidates']:candidate['candidate_ref']=f"cand:{digest[:16]}:{candidate['rank']}"
        self.snapshots.append(deepcopy(snapshot));return snapshot

    def _guard_observations(self,candidate,decision_time):
        choices=[]
        for row,observation in self.observations.values():
            timestamp=row['timestamp_us']
            if (row['camera_id']!=candidate['camera_id'] or not candidate['window_us'][0]<=timestamp<candidate['window_us'][1]
                or timestamp<decision_time or not any(a<=timestamp<b for a,b in self.available[row['camera_id']])
                or observation['class_label']!='person' or observation['score']<self.values['query_min_score']):continue
            if self.color_label is not None and (observation.get('color') or {}).get('verdicts',{}).get(self.color_label)!='STRONG':continue
            choices.append((row,observation))
        choices.sort(key=lambda pair:(pair[0]['timestamp_us'],-pair[1]['score'],pair[1]['observation_id']));return choices

    def get_evidence(self,snapshot,candidate_ref,decision_time):
        require(any(canonical_hash(s)==canonical_hash(snapshot) for s in self.snapshots),'Unknown or altered session snapshot','FORBIDDEN_DATA_SCOPE')
        candidates=[c for c in snapshot['candidates'] if c['candidate_ref']==candidate_ref]
        require(len(candidates)==1,'Candidate ref not in current snapshot','FORBIDDEN_DATA_SCOPE');candidate=candidates[0]
        key=(candidate_ref,decision_time,self.bindings.parameter_sha256)
        if key in self._cache:return deepcopy(self._cache[key])
        context={'expected_index_sha256':self.bindings.index_sha256,'query_min_score':self.values['query_min_score'],
                 'color_label':self.color_label,'evidence_max_observations':self.values['evidence_max_observations'],
                 'switch_min_presence':self.values['switch_min_presence'],'decision_time_us':decision_time,
                 'available_ranges_us':deepcopy(self.available[candidate['camera_id']])}
        self._ensure_active()
        evidence=self.evidence_provider(deepcopy(self.index),deepcopy(snapshot),candidate_ref,deepcopy(context));self._ensure_active();_safe_content(evidence)
        require(isinstance(evidence,dict) and evidence.get('schema_version')=='q-demo.candidate-evidence.v1'
                and canonical_hash(evidence,exclude=('evidence_sha256','stats'))==evidence.get('evidence_sha256'),'Evidence schema/hash mismatch')
        require(evidence.get('candidate_ref')==candidate_ref and evidence.get('camera_id')==candidate['camera_id']
                and evidence.get('window_us')==candidate['window_us'] and evidence.get('decision_time_us')==decision_time,'Evidence snapshot/window/time mismatch')
        presence=evidence.get('target_presence');require(presence in {'MATCH_STRONG','MATCH_WEAK','PERSON_COLOR_UNKNOWN','PERSON_NO_COLOR_MATCH','NO_PERSON_DETECTED','PARTIAL_EVIDENCE','NOT_EVALUATED'},'Invalid evidence presence')
        frames=evidence.get('frames');require(isinstance(frames,dict) and set(frames)=={'evaluated','not_sampled','not_inferred','missing'}
            and all(type(v) is int and v>=0 for v in frames.values()) and type(evidence.get('coverage_complete')) is bool,'Invalid evidence coverage')
        n=frames['evaluated']+frames['not_inferred']+frames['missing']
        require(evidence['coverage_complete']==(n>0 and frames['evaluated']==n),'False evidence coverage')
        require((presence=='NOT_EVALUATED')==(frames['evaluated']==0),'Evidence evaluation/presence mismatch')
        require(presence!='PARTIAL_EVIDENCE' or 0<frames['evaluated']<n,'False partial evidence')
        require(self.color_label is not None or presence in {'MATCH_STRONG','NO_PERSON_DETECTED','PARTIAL_EVIDENCE','NOT_EVALUATED'},'No-color evidence invented a color verdict')
        require(presence not in {'PERSON_NO_COLOR_MATCH','NO_PERSON_DETECTED'} or evidence['coverage_complete'],'Incomplete evidence cannot be negative')
        best=evidence.get('best_observations');require(isinstance(best,list) and len(best)<=self.values['evidence_max_observations'],'Evidence cap mismatch')
        require(len({item['observation_id'] for item in best})==len(best),'Duplicate evidence observation')
        for item in best:
            require(type(item['timestamp_us']) is int and type(item['score']) in (int,float)
                    and isinstance(item['bbox_xyxy_px'],list) and all(type(v) in (int,float) and math.isfinite(v) for v in item['bbox_xyxy_px']),'Malformed evidence observation')
            pair=self.observations.get(item['observation_id']);require(pair is not None,'Evidence observation not in pinned index');row,observation=pair
            require(row['camera_id']==candidate['camera_id'] and row['frame_ref']==item['frame_ref'] and row['timestamp_us']==item['timestamp_us']
                    and observation['class_label']=='person' and observation['score']==item['score'] and observation['bbox_xyxy_px']==item['bbox_xyxy_px']
                    and observation['score']>=self.values['query_min_score'] and candidate['window_us'][0]<=row['timestamp_us']<candidate['window_us'][1]
                    and any(a<=row['timestamp_us']<b for a,b in self.available[row['camera_id']]),'Evidence observation fields outside source scope')
            require(item['color_verdict']==(None if self.color_label is None else (observation.get('color') or {}).get('verdicts',{}).get(self.color_label)),'Evidence color mismatch')
        entry=evidence.get('entry_observation_id');timestamp=evidence.get('entry_timestamp_us')
        require((entry is None)==(timestamp is None) and (entry is None or (isinstance(entry,str) and type(timestamp) is int)),'Incomplete entry binding')
        if presence=='MATCH_STRONG':
            choices=self._guard_observations(candidate,decision_time);expected=choices[0] if choices else None
            require(entry==(expected[1]['observation_id'] if expected else None) and timestamp==(expected[0]['timestamp_us'] if expected else None),'Entry is not earliest legal guarded observation')
        else:require(entry is None,'Below-guard evidence cannot supply an entry')
        self.partial|=not evidence['coverage_complete']
        self._cache[key]=deepcopy(evidence);self.evidence.append(deepcopy(evidence));return evidence

    def _select(self,snapshot,decision_time):
        considered=[];calls=[];selected=None;started=time.perf_counter()
        for candidate in snapshot['candidates']:
            if selected is None:
                e=self.get_evidence(snapshot,candidate['candidate_ref'],decision_time);presence=e['target_presence']
                if presence=='MATCH_STRONG' and e['entry_observation_id'] is not None:
                    selected=(candidate,e);reason=None;action='SWITCH'
                else:
                    action='NEXT_CANDIDATE'
                    reason=('NO_ALIGNABLE_OBSERVATION' if presence=='MATCH_STRONG' else
                            'CONDITION_MISMATCH' if presence=='PERSON_NO_COLOR_MATCH' else
                            'BELOW_SWITCH_GUARD' if presence in {'MATCH_WEAK','PERSON_COLOR_UNKNOWN'} else
                            'INSUFFICIENT_COVERAGE' if presence in {'PARTIAL_EVIDENCE','NOT_EVALUATED'} else 'NO_PERSON_DETECTED')
                request={'session_id':self.session_id,'candidate_ref':candidate['candidate_ref'],'decision_time_us':decision_time}
                calls.append({'tool':'get_candidate_evidence','request_sha256':canonical_hash(request),'response_sha256':e['evidence_sha256']})
                digest=e['evidence_sha256']
            else:
                # Untouched ranks remain visible in the frozen snapshot. They
                # are audit facts, not NEXT_CANDIDATE actions after a SWITCH.
                self.diagnostics.append({'searching_index':self.searching_index,'candidate_ref':candidate['candidate_ref'],
                    'target_presence':'NOT_EVALUATED','evidence_sha256':None,'reason':'NOT_QUERIED_AFTER_ACCEPTED_SWITCH'})
                continue
            considered.append({'candidate_ref':candidate['candidate_ref'],'rank':candidate['rank'],'evidence_sha256':digest,
                'target_presence':presence,'exclusion_reason':reason,'action':action,'decided_by':self._decider()})
        elapsed=(time.perf_counter()-started)*1000;self._latency_ms+=elapsed
        self.diagnostics.append({'searching_index':self.searching_index,'stats':{'latency_ms':{'fallback':elapsed}}})
        # fallback_budget_ms is deliberately never a cutoff or domain branch.
        return selected,considered,calls

    def _selection_metadata(self):return {'decided_by':self._decider(),'llm_calls':[]}

    def _search(self,tracker,decision_time,window_start,before):
        if self.searching_index>=self.values['session_max_research_rounds']:
            self._emit(before,'ENDED',decision_time,decided_by=self._decider());return 'LIMIT',None
        self.searching_index+=1;self._episode_agent_rounds=0;self._episode_budget_ms=0
        snapshot=self._snapshot(self.current_camera,tracker.last,window_start)
        self._emit(before,'SEARCHING',decision_time,decision_time=decision_time,snapshot=snapshot)
        selected,considered,calls=self._select(snapshot,decision_time)
        with self._control_lock:
            self._ensure_active()
            if self._manual_request is not None:
                self._emit('SEARCHING','SEARCHING',decision_time,decision_time=decision_time,snapshot=snapshot,
                           accepted=False,rejection_code='USER_OVERRIDE',decided_by='USER')
                return 'MANUAL',tracker
            return self._commit_selection(snapshot,decision_time,selected,considered,calls,tracker)

    def _commit_selection(self,snapshot,decision_time,selected,considered,calls,tracker):
        if selected is not None:
            candidate,evidence=selected
            registered=[c for c in snapshot['candidates'] if c['candidate_ref']==candidate.get('candidate_ref')]
            require(len(registered)==1 and canonical_hash(candidate)==canonical_hash(registered[0]),'Policy selected an altered/noncandidate ref')
            require((candidate['candidate_ref'],decision_time,self.bindings.parameter_sha256) in self._cache,'Policy attempted a cut without fetched evidence')
            # Re-check the actual observed entry independently of a policy choice.
            checked=self.get_evidence(snapshot,candidate['candidate_ref'],decision_time)
            require(canonical_hash(evidence,exclude=('stats',))==canonical_hash(checked,exclude=('stats',)),'Policy altered evidence after validation')
            evidence=checked
            require(evidence['target_presence']=='MATCH_STRONG' and evidence['entry_observation_id'] is not None,'Policy attempted an unguarded cut')
            row,observation=self.observations[evidence['entry_observation_id']]
            require(row['timestamp_us']>=decision_time and self.left<=row['timestamp_us']<self.right,'Switch would backdate/outside query')
            new_tracker=self._new_linker(row,observation)
            decision=self._emit('SEARCHING','SWITCHING',decision_time,decision_time=decision_time,snapshot=snapshot,
                considered=considered,tool_calls=calls,submitted={'action':'SWITCH','candidate_ref':candidate['candidate_ref']},
                action='SWITCH',candidate_ref=candidate['candidate_ref'],entry_id=observation['observation_id'],**self._selection_metadata())
            self._emit('SWITCHING','PLAYING',row['timestamp_us'],decision_time=decision_time,snapshot=snapshot,
                entry_id=observation['observation_id'],candidate_ref=candidate['candidate_ref'],decided_by=decision['decided_by'],cause_decision_id=decision['decision_id'])
            self._gap(row['timestamp_us'],['SEARCHING','SWITCHING'],self.current_camera)
            self._observe(row,observation,'SWITCH',decision['decided_by'],decision['decision_id'])
            return 'SWITCH',new_tracker
        decision=self._emit('SEARCHING','RETURNED_TO_ORIGIN',decision_time,decision_time=decision_time,snapshot=snapshot,
            considered=considered,tool_calls=calls,submitted={'action':'RETURN_TO_ORIGIN','candidate_ref':None},
            action='RETURN_TO_ORIGIN',**self._selection_metadata())
        self._gap(min(self.right,decision_time+self.interval),['RETURNED_TO_ORIGIN'],self.current_camera)
        return 'RETURN',tracker

    def request_manual_seed(self,observation_id,*,restart_agent=False):
        """Server-only human action; queued atomically, never a hidden model tool.

        Called while a tick scheduler is running. Older observations require a new
        query/replay; a manual action cannot rewind source time or refund rounds.
        """
        with self._control_lock:
            require(self._running and self._manual_request is None,'No active session or manual selection already pending','FORBIDDEN_DATA_SCOPE')
            require(isinstance(observation_id,str) and observation_id in {s['observation_id'] for s in self.seeds},'Manual seed outside original query/condition','FORBIDDEN_DATA_SCOPE')
            row,_=self.observations[observation_id]
            require(row['timestamp_us']>=self.cursor,'Manual selection would backdate; start a separate query','FORBIDDEN_DATA_SCOPE')
            require(type(restart_agent) is bool,'Explicit boolean Agent restart required')
            self._ensure_active();self._manual_restart_agent=restart_agent
            self._manual_request=observation_id

    def _apply_manual(self,state):
        with self._control_lock:
            oid=self._manual_request;require(oid is not None,'No pending manual selection')
            row,observation=self.observations[oid];timestamp=row['timestamp_us']
            require(timestamp>=self.cursor,'Manual action cannot backdate playback')
            self._manual_request=None
            if self._manual_restart_agent and hasattr(self,'_metadata'):
                self.fallback_reason=None;self._metadata={'decided_by':'AGENT','llm_calls':[]}
            self._manual_restart_agent=False
            if self.searching_index>=self.values['session_max_research_rounds']:
                self._emit(state,'ENDED',timestamp,decided_by='USER');self._gap(self.right,['ENDED'],self.current_camera)
                return None
            tracker=self._new_linker(row,observation)
            # The old decision/journal stays intact. Only episode counters reset;
            # session search/Agent counters and the original query scope remain.
            self.searching_index+=1;self._episode_agent_rounds=0;self._episode_budget_ms=0
            self._gap(timestamp,['SEARCHING'],self.current_camera);self.current_camera=row['camera_id']
            snapshot=self._snapshot(self.current_camera,observation,timestamp)
            self._emit(state,'SEARCHING',timestamp,decision_time=timestamp,snapshot=snapshot,entry_id=oid,decided_by='USER')
            self._emit('SEARCHING','PLAYING',timestamp,decision_time=timestamp,snapshot=snapshot,entry_id=oid,decided_by='USER')
            self._observe(row,observation,'USER_SELECTION','USER')
            return tracker

    def _return_probe(self,row,tracker):
        """Fresh local segment on reacquisition; never resurrect an ended linker."""
        self._ensure_active()
        # The old segment has already ended. Use current real query-qualified
        # observations only; never compare them to an indefinitely frozen box.
        choices=[]
        if row['frame_state']=='INFERRED':
            for observation in row['detections']:
                if observation['class_label']!='person' or observation['score']<self.values['query_min_score']:continue
                if self.color_label is not None and (observation.get('color') or {}).get('verdicts',{}).get(self.color_label)!='STRONG':continue
                choices.append(observation)
        if len(choices)!=1:return None
        fresh=self._new_linker(row,choices[0])
        self.diagnostics.append({'event':'UNCONFIRMED_NEW_LOCAL_SEGMENT','method':'CURRENT_WINDOW_REAL_OBSERVATION_V1',
            'timestamp_us':row['timestamp_us'],'observation_id':choices[0]['observation_id'],
            'old_local_segment_id':tracker.segment_id,'local_segment_id':fresh.segment_id,'identity_verdict':'UNCONFIRMED'})
        return fresh

    def _execute(self,seed_row,seed_observation):
        tracker=self._new_linker(seed_row,seed_observation);self.current_camera=seed_row['camera_id']
        self._gap(seed_row['timestamp_us'],[],self.current_camera)
        self._emit(None,'PLAYING',seed_row['timestamp_us'],decided_by='USER')
        self._observe(seed_row,seed_observation,'SEED','USER')
        frame=seed_row['frame_index']+1;state='PLAYING';returned_at=None
        while self.cursor<self.right:
            self._ensure_active()
            camera=self.current_camera;meta=self.metadata[camera];timestamp=frame*meta['source_frame_interval_us']
            if timestamp>=self.right:break
            # The server may pace source ticks or accept a human selection here.
            # No control lock is held during scheduler/model/evidence waiting.
            if self.on_tick is not None:self.on_tick(timestamp,self)
            with self._control_lock:
                self._ensure_active()
                if self._manual_request is not None:
                    tracker=self._apply_manual(state)
                    if tracker is None:return 'ENDED_BY_LIMIT','SESSION_RESEARCH_ROUND_LIMIT'
                    state='PLAYING';returned_at=None;frame=tracker.last_frame+1;continue
                row=self.records.get((camera,frame))
                if row is None:
                    self._gap(self.right,['ENDED'],camera);return 'PARTIAL','INCOMPLETE_EVIDENCE'
                on_grid=frame>=meta['index_grid_origin_frame'] and (frame-meta['index_grid_origin_frame'])%meta['stride_samples']==0
                if not on_grid:
                    if state!='RETURNED_TO_ORIGIN':tracker.step(row)
                    frame+=1;continue
                if state=='RETURNED_TO_ORIGIN':
                    fresh=self._return_probe(row,tracker)
                    if fresh is not None:
                        tracker=fresh;self._emit(state,'PLAYING',timestamp,entry_id=tracker.last['observation_id'])
                        self._observe(row,tracker.last,'REACQUIRED',self._decider());state='PLAYING';frame+=1;continue
                    if timestamp-returned_at<self.values['research_interval_us']:
                        self._gap(timestamp+self.interval,[state],camera);frame+=1;continue
                    window_start=timestamp
                else:
                    previous=deepcopy(tracker.last);step=tracker.step(row)
                    if step is None:frame+=1;continue
                    self._link_log(step.link,row,step.local_segment_id,step.ambiguous_observation_ids,previous)
                    if step.state=='PLAYING':
                        if state!='PLAYING':self._emit(state,'PLAYING',timestamp,entry_id=tracker.last['observation_id'])
                        self._observe(row,tracker.last,'LINK',self._decider());state='PLAYING';frame+=1;continue
                    if step.state=='TEMP_LOST':
                        if state!='TEMP_LOST':self._emit(state,'TEMP_LOST',timestamp)
                        self._gap(timestamp+self.interval,['TEMP_LOST'],camera);state='TEMP_LOST';frame+=1;continue
                    if state=='PLAYING':self._emit(state,'TEMP_LOST',timestamp);state='TEMP_LOST'
                    window_start=step.first_missing_us
            result,new_tracker=self._search(tracker,timestamp,window_start,state)
            with self._control_lock:
                if result=='LIMIT':self._gap(self.right,['ENDED'],camera);return 'ENDED_BY_LIMIT','SESSION_RESEARCH_ROUND_LIMIT'
                if result=='MANUAL':
                    tracker=self._apply_manual('SEARCHING')
                    if tracker is None:return 'ENDED_BY_LIMIT','SESSION_RESEARCH_ROUND_LIMIT'
                    state='PLAYING';returned_at=None;frame=tracker.last_frame+1;continue
                if result=='SWITCH':tracker=new_tracker;state='PLAYING';returned_at=None;frame=tracker.last_frame+1;continue
                state='RETURNED_TO_ORIGIN';returned_at=timestamp;frame+=1
        self._gap(self.right,['ENDED'],self.current_camera)
        self._emit(state,'ENDED',self.right)
        if self.time_partial:return 'PARTIAL','TIME_SCOPE_PARTIAL'
        if self.graph_draft:return 'PARTIAL','GRAPH_NOT_APPROVED'
        if self.partial:return 'PARTIAL','INCOMPLETE_EVIDENCE'
        return 'COMPLETE',None

    def _finish(self,status,reason=None):
        self._running=False
        decisions=jsonl(self.decisions);links=jsonl(self.links)
        switching=[d for d in self.decisions if d['accepted'] and d['executed_action'] in {'SWITCH','RETURN_TO_ORIGIN'}]
        agent_used=any(d['accepted'] and d['decided_by']=='AGENT' for d in self.decisions)
        fallback_used=any(d['decided_by']=='RULE_FALLBACK' and d['executed_action'] is not None for d in self.decisions)
        reasons=self.blocking_reasons+([reason] if reason else [])
        if status in {'PARTIAL','COMPLETE'}:
            if self.time_partial:reasons.append('TIME_SCOPE_PARTIAL')
            if self.graph_draft:reasons.append('GRAPH_NOT_APPROVED')
        reasons=ordered_reasons(reasons)
        reason=reasons[0] if reasons else None
        response={'schema_version':'q-demo.q2-response.v1','status':status,'reason':reason,'reasons':reasons,'session_id':self.session_id,
                  'timeline':deepcopy(self.timeline),'decisions_ref':self.session_id+'.decisions.jsonl','decisions_sha256':file_hash(decisions),
                  'links_ref':self.session_id+'.links.jsonl','links_sha256':file_hash(links),'resolved_scope':deepcopy(self.scope),
                  'identity_verdict':'UNCONFIRMED','llm_parse_used':False,'agent_attempted':self.agent_attempted,'agent_used':agent_used,
                  'decision_source':switching[-1]['decided_by'] if switching else None,'fallback_used':fallback_used,
                  'fallback_reason':self.fallback_reason if fallback_used else None,
                  'provenance':{'producer':'q5-index-controller','producer_version':'1','gt_read':False,
                      'input_refs':[str(value) for value in [self.bindings.index_sha256,self.bindings.region_graph_sha256,self.bindings.camera_graph_sha256,
                                                           self.bindings.parameter_sha256,self.bindings.clock_sha256,self.bindings.media_scope_sha256,self.scope['tracking_scope_sha256']] if value is not None]},
                  'stats':{'latency_ms':{'fallback':self._latency_ms}}}
        response['output_sha256']=canonical_hash(response,exclude=('output_sha256','stats'))
        return SessionResult(response,decisions,links,tuple(deepcopy(self.snapshots)),tuple(deepcopy(self.evidence)),tuple(deepcopy(self.seeds)),tuple(deepcopy(self.diagnostics)))

    def run(self):
        require(not self._ran,'A controller instance is single-use');self._ran=True
        try:reason=self._prepare()
        except ControllerError:raise
        except (KeyError,TypeError,ValueError,AttributeError,IndexError,OverflowError) as exc:
            raise ControllerError('Malformed runtime metadata',getattr(exc,'code','DataIntegrityError')) from exc
        if reason is not None:return self._finish(self.parameter_block_status if reason=='PARAMETERS_NOT_APPROVED' else 'UNKNOWN',reason)
        seed=self._seed_candidates()
        if seed is None:
            if self.seeds:return self._finish('UNKNOWN','SEED_SELECTION_REQUIRED')
            return self._finish('PARTIAL' if self.partial or self.time_partial else 'NO_SEED','INCOMPLETE_EVIDENCE' if self.partial else 'TIME_SCOPE_PARTIAL' if self.time_partial else None)
        self._running=True
        try:status,reason=self._execute(*seed)
        except SessionCancelled:
            status,reason='PARTIAL','USER_STOPPED'
        except (ControllerError,LinkError,GraphError,KeyError,TypeError,ValueError,RuntimeError,OSError) as exc:
            self.diagnostics.append({'error_code':getattr(exc,'code','DataIntegrityError'),'message':str(exc)})
            source=max(self.left,min(self.cursor,self.right));self._emit(self.decisions[-1]['state_after'] if self.decisions else None,'ENDED',source)
            self._gap(self.right,['ENDED'],self.current_camera or seed[0]['camera_id']);status='UNKNOWN';reason=getattr(exc,'code','DataIntegrityError')
        return self._finish(status,reason)
