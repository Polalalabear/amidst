"""Q5 typed tools; session-owned refs only, without file, image or model access."""
from copy import deepcopy
from amidst.q1q5.q5_controller import ControllerError
from amidst.q1q5.store import canonical_hash,_safe_content


class ToolRejected(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)


def reject_unless(ok,code):
    if not ok:raise ToolRejected(code)


class AgentTools:
    """One immutable SEARCHING snapshot, one cursor and no authority to cut video.

    Successful submissions return a validated proposal to the controller. They
    never execute a cut themselves. Observation refs are scoped to this search.
    """
    def __init__(self,controller,snapshot,decision_time_us,decision_id,remaining):
        reject_unless(any(canonical_hash(s)==canonical_hash(snapshot) for s in controller.snapshots),'STALE_SNAPSHOT')
        self.controller=controller;self.snapshot=deepcopy(snapshot);self.decision_time_us=decision_time_us
        self.decision_id=decision_id;self.remaining=remaining;self.cursor=0;self.fetched={};self.exposed=set();self.closed=False
        self.history=[];self.proposals=[]
        last=controller._search_last_observation if hasattr(controller,'_search_last_observation') else None
        if last is not None:self.exposed.add(last)

    def _request(self,value,fields,*,decision=True):
        expected={'session_id',*fields}|({'decision_id'} if decision else set())
        reject_unless(isinstance(value,dict) and set(value)==expected,'SCHEMA_INVALID')
        reject_unless(value['session_id']==self.controller.session_id,'UNKNOWN_REF')
        if decision:reject_unless(value['decision_id']==self.decision_id,'STALE_SNAPSHOT')
        reject_unless(not self.closed,'ILLEGAL_ORDER')

    def current(self):
        return self.snapshot['candidates'][self.cursor] if self.cursor<len(self.snapshot['candidates']) else None

    def get_search_context(self,value):
        self._request(value,set());c=self.controller
        last=getattr(c,'_search_last_observation',None)
        observation=self._summary(last) if last is not None else None
        return {'session_id':c.session_id,'decision_id':self.decision_id,'candidate_snapshot_sha256':self.snapshot['candidate_snapshot_sha256'],
                'state':'SEARCHING','last_observation':observation,'exit_resolution':self.snapshot['exit_resolution'],
                'candidates':deepcopy(self.snapshot['candidates']),'next_candidate_rank':self.cursor+1 if self.current() else None,
                'remaining':deepcopy(self.remaining())}

    def get_candidate_evidence(self,value):
        self._request(value,{'candidate_ref'});ref=value['candidate_ref']
        reject_unless(isinstance(ref,str) and ref in {x['candidate_ref'] for x in self.snapshot['candidates']},'UNKNOWN_REF')
        current=self.current();reject_unless(current is not None and current['candidate_ref']==ref and ref not in self.fetched,'ILLEGAL_ORDER')
        evidence=self.controller.get_evidence(self.snapshot,ref,self.decision_time_us)
        self.fetched[ref]=deepcopy(evidence);self.exposed.update(x['observation_id'] for x in evidence['best_observations'])
        if evidence['entry_observation_id'] is not None:self.exposed.add(evidence['entry_observation_id'])
        return evidence

    def _summary(self,oid):
        row,observation=self.controller.observations[oid]
        return {'observation_id':oid,'frame_ref':row['frame_ref'],'timestamp_us':row['timestamp_us'],'camera_id':row['camera_id'],
                'class_label':observation['class_label'],'bbox_xyxy_px':deepcopy(observation['bbox_xyxy_px']),'score':observation['score'],
                'color_verdict':None if self.controller.color_label is None else (observation.get('color') or {}).get('verdicts',{}).get(self.controller.color_label)}

    def get_observation_summary(self,value):
        self._request(value,{'observation_id'},decision=False);oid=value['observation_id']
        reject_unless(isinstance(oid,str) and oid in self.exposed,'UNKNOWN_REF');return self._summary(oid)

    def submit_decision(self,value):
        keys={'schema_version','session_id','decision_id','candidate_snapshot_sha256','action','candidate_ref','cited_observation_ids','rationale'}
        reject_unless(isinstance(value,dict) and set(value)==keys and value['schema_version']=='q-demo.agent-decision.v1','SCHEMA_INVALID')
        reject_unless(value['session_id']==self.controller.session_id,'UNKNOWN_REF')
        reject_unless(value['decision_id']==self.decision_id and value['candidate_snapshot_sha256']==self.snapshot['candidate_snapshot_sha256'],'STALE_SNAPSHOT')
        reject_unless(not self.closed,'ILLEGAL_ORDER')
        action=value['action'];ref=value['candidate_ref'];cited=value['cited_observation_ids'];rationale=value['rationale']
        reject_unless(isinstance(action,str) and action in {'SWITCH','NEXT_CANDIDATE','RETURN_TO_ORIGIN'} and (ref is None or isinstance(ref,str))
            and isinstance(cited,list) and all(isinstance(x,str) and x for x in cited) and len(cited)==len(set(cited))
            and isinstance(rationale,str) and bool(rationale.strip()),'SCHEMA_INVALID')
        try:_safe_content({'rationale':rationale})
        except ValueError:raise ToolRejected('SCHEMA_INVALID') from None
        import re
        reject_unless(not re.search(r'same person|同一[個个]?人|identity confirmed|身分[已]?確認|/Users/|/private/|/tmp/|file://|ground_truth|renderer_trajectory|persons\\.sim',rationale,re.I),'SCHEMA_INVALID')
        if action=='RETURN_TO_ORIGIN':
            reject_unless(ref is None and set(cited)<=self.exposed,'UNCITED_OR_FOREIGN_REF')
            self.closed=True;self.proposals.append(deepcopy(value));return {'accepted':True,'rejection_code':None,'executed_action':action}
        reject_unless(ref in {x['candidate_ref'] for x in self.snapshot['candidates']},'UNKNOWN_REF')
        current=self.current();reject_unless(current is not None and current['candidate_ref']==ref,'ILLEGAL_ORDER')
        reject_unless(ref in self.fetched,'EVIDENCE_NOT_FETCHED');e=self.fetched[ref]
        allowed={x['observation_id'] for x in e['best_observations']}
        if e['entry_observation_id'] is not None:allowed.add(e['entry_observation_id'])
        # SWITCH/NEXT must cite a ref from this candidate's returned evidence.
        reject_unless(set(cited)<=allowed and bool(cited),'UNCITED_OR_FOREIGN_REF')
        if action=='SWITCH':
            reject_unless(e['target_presence']=='MATCH_STRONG' and e['entry_observation_id'] is not None,'INSUFFICIENT_EVIDENCE');self.closed=True
        else:self.cursor+=1
        self.proposals.append(deepcopy(value));return {'accepted':True,'rejection_code':None,'executed_action':action}

    def dispatch(self,name,value):
        reject_unless(isinstance(name,str) and name in {'get_search_context','get_candidate_evidence','get_observation_summary','submit_decision'},'SCHEMA_INVALID')
        try:response=getattr(self,name)(deepcopy(value))
        except ToolRejected as error:
            response={'accepted':False,'rejection_code':error.code,'executed_action':None}
        self.history.append({'tool':name,'request_sha256':canonical_hash(value),'response_sha256':canonical_hash(response)})
        return deepcopy(response)
