"""Evaluation-only comparison of frozen Q5 decisions to externally authored scripts.

No inference, model, RGB or production-script imports. Script matching is a
reported measurement; a PROPOSED script never becomes an approved answer here.
"""
from dataclasses import dataclass
import hashlib
import json

VERSION = 'q5-switch-eval-v1'


class EvaluationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=True,allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(document,field):
    return sha(canonical({k:v for k,v in document.items() if k not in {field,'stats'}}))


def require(ok,message):
    if not ok:
        raise EvaluationError(message)


def load_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON key');result[key]=value
        return result
    try:
        value=json.loads(raw,object_pairs_hook=pairs);canonical(value);return value
    except (ValueError,TypeError,UnicodeError) as exc:
        raise EvaluationError('Malformed frozen JSON') from exc


@dataclass(frozen=True)
class FrozenOutput:
    # Canonical bytes prevent a caller mutating a previously verified dictionary.
    response_bytes: bytes
    decisions_bytes: bytes
    response_file_sha256: str
    decisions_file_sha256: str


def freeze_output(response_raw,decisions_raw,*,expected_response_sha256,expected_decisions_sha256):
    require(sha(response_raw)==expected_response_sha256 and sha(decisions_raw)==expected_decisions_sha256,
            'Frozen output file hash mismatch')
    response=load_json(response_raw)
    require(isinstance(response,dict) and response.get('schema_version')=='q-demo.q2-response.v1','Q2 response required')
    require(digest(response,'output_sha256')==response.get('output_sha256'),'Response content hash mismatch')
    require(response.get('decisions_sha256')==expected_decisions_sha256,'Response/decisions file binding mismatch')
    scope=response.get('resolved_scope',{})
    require(isinstance(scope,dict) and len(scope.get('run_ids') or [])==1 and len(scope.get('clock_ids') or [])==1,
            'Explicit single run/clock required for evaluation')
    decisions=[load_json(line) for line in decisions_raw.splitlines()];seen=set();last_step=-1;last_time=-1
    for record in decisions:
        require(isinstance(record,dict) and record.get('schema_version')=='q-demo.decision-record.v1', 'Invalid decision record')
        require(record.get('session_id')==response.get('session_id') and isinstance(record.get('decision_id'),str)
                and record['decision_id'] not in seen,'Decision/session binding mismatch');seen.add(record['decision_id'])
        require(digest(record,'content_sha256')==record.get('content_sha256'),'Decision hash mismatch')
        step=record.get('step_index');source=record.get('source_time_us');time=record.get('decision_time_us')
        require(type(step) is int and step>last_step and type(source) is int and source>=last_time,
                'Unordered decision step/source time');last_step=step;last_time=source
        require(time is None or (type(time) is int and 0<=time<=source),'Decision time backdating')
        action=record.get('executed_action')
        require(action in {None,'SWITCH','NEXT_CANDIDATE','CONTINUE_SEARCH','RETURN_TO_ORIGIN'},'Unknown executed action')
        if action is not None:require(time is not None,'Executed action needs decision time')
        if action=='SWITCH':
            require(record.get('accepted') is True and isinstance(record.get('entry_observation_id'),str)
                    and isinstance(record.get('executed_candidate_ref'),str),'Rejected/unbound switch')
    return FrozenOutput(canonical(response),canonical(decisions),expected_response_sha256,expected_decisions_sha256)


def _range(value):
    return isinstance(value,list) and len(value)==2 and all(type(x) is int and x>=0 for x in value) and value[0]<value[1]


def compare_script(frozen,script_raw,*,expected_script_sha256):
    require(isinstance(frozen,FrozenOutput),'Output must be frozen before script comparison')
    require(sha(script_raw)==expected_script_sha256,'Evaluation script pin mismatch')
    script=load_json(script_raw);response=load_json(frozen.response_bytes);records=load_json(frozen.decisions_bytes)
    require(isinstance(script,dict) and script.get('schema_version')=='q5-evaluation-script.v1','Explicit evaluation-script adapter required')
    require(script.get('status') in {'PROPOSED','APPROVED'} and (script['status']!='APPROVED' or (isinstance(script.get('approval_ref'),str) and bool(script['approval_ref']))),'Script approval reference missing')
    scope=response['resolved_scope']
    require(script.get('run_id')==scope['run_ids'][0] and script.get('clock_id')==scope['clock_ids'][0], 'Script/output run or clock mismatch')
    # Timeline maps executed SWITCH to camera and evidence entry time; neither
    # an actor ID nor a scripted trajectory can select a runtime destination.
    source_ranges=scope.get('resolved_source_ranges_us')
    require(isinstance(source_ranges,list) and source_ranges and all(isinstance(r,dict) and r.get('run_id')==script['run_id'] and _range(r.get('range_us')) for r in source_ranges),'Explicit resolved query ranges required')
    def in_scope(window):return any(r['range_us'][0]<=window[0]<window[1]<=r['range_us'][1] for r in source_ranges)
    entries={};timeline=response.get('timeline');require(isinstance(timeline,list),'Timeline required')
    timeline_end=-1
    for seg in timeline:
        require(isinstance(seg,dict) and _range(seg.get('range_us')),'Invalid timeline interval')
        require(seg['range_us'][0]>=timeline_end and in_scope(seg['range_us']),'Overlapping/out-of-scope timeline');timeline_end=seg['range_us'][1]
        if seg.get('kind')=='GAP':require(seg.get('position') is None,'GAP cannot contain a scripted position')
        if seg.get('entered_by')=='SWITCH':
            key=seg.get('decision_id');require(isinstance(key,str) and key not in entries,'Duplicate switch timeline binding')
            require(seg.get('kind')=='ON_CAMERA' and isinstance(seg.get('camera_id'),str)
                    and isinstance(seg.get('observation_ids'),list) and seg['observation_ids'],'Invalid switch entry')
            entries[key]=seg
    executed=[]
    for record in records:
        action=record['executed_action']
        if action not in {'SWITCH','RETURN_TO_ORIGIN'}:continue
        item={'decision_id':record['decision_id'],'decision_time_us':record['decision_time_us'],'action':action,'camera_id':None,'entry_time_us':None}
        if action=='SWITCH':
            entry=entries.pop(record['decision_id'],None);require(entry is not None,'Missing switch timeline entry')
            require(entry['range_us'][0]>=record['decision_time_us'] and entry['observation_ids'][0]==record['entry_observation_id'], 'Switch entry evidence/time mismatch')
            item.update(camera_id=entry['camera_id'],entry_time_us=entry['range_us'][0])
        executed.append(item)
    require(not entries,'Timeline switch has no executed decision')
    events=script.get('events');require(isinstance(events,list) and events,'Explicit nonempty script event list required')
    seen=set();last_end=-1;items=[];covered=set()
    for event in events:
        require(isinstance(event,dict) and isinstance(event.get('event_id'),str) and event['event_id'] not in seen,'Invalid/duplicate script event');seen.add(event['event_id'])
        window=event.get('decision_window_us');require(_range(window) and window[0]>=last_end and in_scope(window),'Decision windows must be disjoint, ordered and within query scope');last_end=window[1]
        action=event.get('action');require(action in {'SWITCH','RETURN_TO_ORIGIN','NO_SWITCH'},'Unknown script action')
        observed=[a for a in executed if window[0]<=a['decision_time_us']<window[1]]
        covered.update(a['decision_id'] for a in observed)
        if action=='SWITCH':
            cameras=event.get('allowed_camera_ids');entry_window=event.get('entry_window_us')
            require(isinstance(cameras,list) and cameras and all(isinstance(x,str) and x for x in cameras) and _range(entry_window) and in_scope(entry_window),'Explicit in-scope camera/entry window required')
            match=len(observed)==1 and observed[0]['action']=='SWITCH' and observed[0]['camera_id'] in cameras and entry_window[0]<=observed[0]['entry_time_us']<entry_window[1]
        elif action=='RETURN_TO_ORIGIN':
            match=len(observed)==1 and observed[0]['action']=='RETURN_TO_ORIGIN'
        else:
            match=not any(a['action']=='SWITCH' for a in observed)
        items.append({'event_id':event['event_id'],'expected_action':action,'match':bool(match),'observed':observed})
    unmatched=[a for a in executed if a['decision_id'] not in covered]
    matches=sum(item['match'] for item in items)
    report={'schema_version':'q5-switch-eval-report.v1','scorer_version':VERSION,
            'response_file_sha256':frozen.response_file_sha256,'decisions_file_sha256':frozen.decisions_file_sha256,
            'script_file_sha256':expected_script_sha256,'script_status':script['status'],'script_approval_ref':script.get('approval_ref'),
            'status':'MEASURED_APPROVED_SCRIPT' if script['status']=='APPROVED' else 'MEASURED_PROPOSED_SCRIPT',
            'run_id':script['run_id'],'clock_id':script['clock_id'],'event_count':len(items),'matched_events':matches,
            'event_match_ratio':{'numerator':matches,'denominator':len(items),'value':matches/len(items)},
            'by_expected_action':{action:{'count':sum(x['expected_action']==action for x in items),'matched':sum(x['expected_action']==action and x['match'] for x in items)} for action in ['SWITCH','RETURN_TO_ORIGIN','NO_SWITCH']},
            'uncovered_executed_actions':unmatched,'uncovered_executed_count':len(unmatched),'events':items,
            'agent_used_reported':response.get('agent_used'),'fallback_used_reported':response.get('fallback_used'),
            'acceptance_threshold':None,'limits':['Script comparison is evaluation-only; no identity or physical-validity claim.','Agent/fallback flags are reported, not independently validated by this metric.','Positive windows compare one executed action plus camera/entry time; NO_SWITCH measures absence within its declared window.']}
    report['output_sha256']=digest(report,'output_sha256');return report
