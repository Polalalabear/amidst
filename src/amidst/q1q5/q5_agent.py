"""Bounded sequential Q5 policy and pin-checked, model-free recorded replay."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import re
import time

from amidst.q1q5.agent_tools import AgentTools,ToolRejected
from amidst.q1q5.llm_provider import CallResult,ProviderError
from amidst.q1q5.q3_parse import _strict_object
from amidst.q1q5.q5_controller import RuleController,ControllerError,require
from amidst.q1q5.store import canonical_hash,_safe_content


@dataclass(frozen=True)
class AgentSettings:
    model: str
    model_digest: str
    options: dict
    template: str
    template_sha256: str
    template_version: str
    authorization_ref: str | None

    def __post_init__(self):
        require(isinstance(self.model,str) and re.fullmatch(r'[A-Za-z0-9_.:/-]+',self.model),'Explicit model required')
        require(isinstance(self.model_digest,str) and re.fullmatch(r'[0-9a-f]{64}',self.model_digest),'Pinned model digest required')
        require(isinstance(self.template,str) and self.template and hashlib.sha256(self.template.encode()).hexdigest()==self.template_sha256,'Prompt template pin mismatch')
        require(isinstance(self.template_version,str) and bool(self.template_version),'Versioned template required')
        require(isinstance(self.options,dict) and self.options.keys()<={'temperature','seed','top_k','top_p','num_predict','repeat_penalty'}
            and all(type(v) in (int,float) and math.isfinite(v) for v in self.options.values()),'Explicit sampling options required')
        require(self.authorization_ref is None or isinstance(self.authorization_ref,str) and bool(self.authorization_ref),'Invalid server authorization ref')
        _safe_content({'template':self.template,'options':self.options})


class ReplayMismatch(ControllerError):pass


class ReplayClock:
    def __init__(self,ticks):
        require(isinstance(ticks,list) and all(type(t) in (int,float) and math.isfinite(t) for t in ticks)
            and all(a<=b for a,b in zip(ticks,ticks[1:])),'Invalid recorded clock')
        self.ticks=tuple(ticks);self.cursor=0
    def __call__(self):
        if self.cursor>=len(self.ticks):raise ReplayMismatch('Recorded clock exhausted')
        value=self.ticks[self.cursor];self.cursor+=1;return value


class RecordedProvider:
    """Only replays exact previously audited calls. No transport/file access.

    The caller supplies an independently trusted expected trace hash. A changed
    request, template, timeout, model or scope is rejected rather than repaired.
    """
    def __init__(self,trace,*,expected_sha256):
        require(isinstance(trace,dict) and trace.get('schema_version')=='q-demo.q5-agent-trace.v1'
            and set(trace)=={'schema_version','session_id','events','clock_ticks','content_sha256'}
            and canonical_hash(trace,exclude=('content_sha256',))==trace['content_sha256']==expected_sha256,'Replay trace pin mismatch')
        self.trace=deepcopy(trace);self.clock=ReplayClock(trace['clock_ticks']);self.cursor=0
    def generate(self,**request):
        if self.cursor>=len(self.trace['events']):raise ReplayMismatch('Recorded provider exhausted')
        event=self.trace['events'][self.cursor]
        if canonical_hash(request)!=event['request_sha256'] or request!=event['request']:raise ReplayMismatch('Recorded provider input mismatch')
        self.cursor+=1
        if event['error_code'] is not None:raise ProviderError(event['error_code'],deepcopy(event['record']))
        return CallResult(event['text'],deepcopy(event['record']))
    def assert_consumed(self):
        require(self.cursor==len(self.trace['events']) and self.clock.cursor==len(self.clock.ticks),'Unused replay events or clock ticks')


class AgentController(RuleController):
    """Agent chooses only; shared Controller guards and executes all cuts.

    Live callers must supply a round scheduler (the server's polling cadence).
    Synthetic/replay callers may explicitly supply a no-wait scheduler. No model
    is called during RULE_ONLY or after the first session fallback trigger.
    """
    def __init__(self,*args,provider,agent_settings,round_scheduler,clock=time.monotonic,**kwargs):
        require(isinstance(agent_settings,AgentSettings) and callable(round_scheduler) and callable(clock),'Explicit Agent settings/scheduler/clock required')
        super().__init__(*args,**kwargs);self.provider=provider;self.settings=deepcopy(agent_settings)
        self.round_scheduler=round_scheduler;self.clock=clock;self.events=[];self.clock_ticks=[];self._metadata=None
        self._pending_calls=[];self._agent_started=None
        if isinstance(provider,RecordedProvider):require(provider.trace['session_id']==self.session_id,'Replay session mismatch')

    def trace(self):
        data={'schema_version':'q-demo.q5-agent-trace.v1','session_id':self.session_id,'events':deepcopy(self.events),'clock_ticks':list(self.clock_ticks)}
        data['content_sha256']=canonical_hash(data);return data

    def _now(self):
        value=self.clock();require(type(value) in (int,float) and math.isfinite(value)
            and (not self.clock_ticks or value>=self.clock_ticks[-1]),'Invalid Agent budget clock')
        self.clock_ticks.append(value);return value

    def _validate_mode(self):
        require(self.request['switch_mode'] in {'RULE_ONLY','AGENT_SEQUENTIAL'},'Unsupported switch mode','FORBIDDEN_INFERENCE_INPUT')

    def _prepare(self):
        reason=super()._prepare()
        if reason is not None or self.request['switch_mode']=='RULE_ONLY':return reason
        if not self.settings.authorization_ref:
            self.fallback_reason='MODE_NOT_AUTHORIZED';return None
        names={'agent_max_rounds','agent_total_budget_ms','agent_call_timeout_ms','agent_max_illegal_submissions','session_max_agent_rounds'}
        items={x['name']:x for x in self.bindings.parameter_set['parameters']}
        if not names<=items.keys() or any(items[n].get('status')!='APPROVED' or type(items[n].get('value')) is not int or items[n]['value']<=0 for n in names):return 'PARAMETERS_NOT_APPROVED'
        self.agent_values={n:items[n]['value'] for n in names};return None

    def _decider(self):return 'RULE_FALLBACK' if self.fallback_reason else 'RULE_ONLY'
    def _selection_metadata(self):return self._metadata or super()._selection_metadata()

    def _search(self,tracker,*args,**kwargs):
        self._search_last_observation=tracker.last['observation_id'];self._metadata=None
        return super()._search(tracker,*args,**kwargs)

    def _spent(self):
        self._episode_budget_ms=math.ceil(max(0,self._now()-self._agent_started)*1000)
        return self._episode_budget_ms

    def _call_record(self,event,validation):
        record=event['record']
        return {'model':record.get('model',self.settings.model),'model_digest':record.get('model_digest'),
                'prompt_sha256':record.get('prompt_sha256',hashlib.sha256(event['request']['prompt'].encode()).hexdigest()),
                'prompt_ref':'prompt:q5:'+self.settings.template_sha256,'raw_output_sha256':record.get('raw_output_sha256'),'validation':validation}

    def _rejected(self,snapshot,decision_time,code,submitted,tools):
        self._emit('SEARCHING','SEARCHING',decision_time,decision_time=decision_time,snapshot=snapshot,
            submitted=submitted,accepted=False,rejection_code=code,decided_by='AGENT',llm_calls=self._pending_calls,
            tool_calls=tools.history)
        self._pending_calls=[];tools.history=[]

    def _emit(self,*args,**kwargs):
        full=kwargs.pop('full_submitted',None)
        if full is not None:kwargs['submitted']=full
        submitted=kwargs.get('submitted')
        if kwargs.get('accepted',True) and kwargs.get('decided_by')=='AGENT' and kwargs.get('action') is not None:
            require(isinstance(submitted,dict) and submitted.get('decision_id')==self.session_id+'-dec-'+str(len(self.decisions)),'Agent decision-slot mismatch')
        return super()._emit(*args,**kwargs)

    def _remaining(self):
        return {'rounds':max(0,self.agent_values['agent_max_rounds']-self._episode_agent_rounds),
                'session_rounds':max(0,self.agent_values['session_max_agent_rounds']-self.session_agent_rounds_used),
                'budget_ms':max(0,self.agent_values['agent_total_budget_ms']-self._episode_budget_ms)}

    def _fallback(self,reason,snapshot,decision_time,tools=None):
        if not self.fallback_reason:self.fallback_reason=reason
        self._metadata={'decided_by':'RULE_FALLBACK','llm_calls':[]}
        if tools is None:return super()._select(snapshot,decision_time)
        # Already accepted NEXTs retain their journal and cursor. The rule only
        # visits the remaining suffix; current fetched evidence is reused.
        suffix=deepcopy(snapshot);suffix['candidates']=suffix['candidates'][tools.cursor:]
        # Base selection uses the original snapshot to validate refs, not a fake
        # suffix snapshot with the original hash.
        considered=[];calls=[];selected=None;started=time.perf_counter()
        for candidate in suffix['candidates']:
            if selected is not None:
                self.diagnostics.append({'searching_index':self.searching_index,'candidate_ref':candidate['candidate_ref'],
                    'target_presence':'NOT_EVALUATED','evidence_sha256':None,'reason':'NOT_QUERIED_AFTER_ACCEPTED_SWITCH'});continue
            e=self.get_evidence(snapshot,candidate['candidate_ref'],decision_time);presence=e['target_presence']
            if presence=='MATCH_STRONG' and e['entry_observation_id'] is not None:selected=(candidate,e);action='SWITCH';exclusion=None
            else:
                action='NEXT_CANDIDATE';exclusion=('NO_ALIGNABLE_OBSERVATION' if presence=='MATCH_STRONG' else
                    'CONDITION_MISMATCH' if presence=='PERSON_NO_COLOR_MATCH' else 'BELOW_SWITCH_GUARD' if presence in {'MATCH_WEAK','PERSON_COLOR_UNKNOWN'}
                    else 'INSUFFICIENT_COVERAGE' if presence in {'PARTIAL_EVIDENCE','NOT_EVALUATED'} else 'NO_PERSON_DETECTED')
            considered.append({'candidate_ref':candidate['candidate_ref'],'rank':candidate['rank'],'evidence_sha256':e['evidence_sha256'],
                'target_presence':presence,'exclusion_reason':exclusion,'action':action,'decided_by':'RULE_FALLBACK'})
            calls.append({'tool':'get_candidate_evidence','request_sha256':canonical_hash({'session_id':self.session_id,'candidate_ref':candidate['candidate_ref'],'decision_time_us':decision_time}),'response_sha256':e['evidence_sha256']})
        self._latency_ms+=(time.perf_counter()-started)*1000
        return selected,considered,calls

    def _select(self,snapshot,decision_time):
        if self.request['switch_mode']=='RULE_ONLY':return super()._select(snapshot,decision_time)
        if self.fallback_reason:return self._fallback(self.fallback_reason,snapshot,decision_time)
        self._pending_calls=[];self._agent_started=self._now();self._episode_budget_ms=0;illegal=0
        tools=AgentTools(self,snapshot,decision_time,self.session_id+'-dec-'+str(len(self.decisions)),self._remaining)
        base={'session_id':self.session_id,'decision_id':tools.decision_id}
        context=tools.dispatch('get_search_context',base);last_result=context
        if not snapshot['candidates']:
            self._metadata={'decided_by':'RULE_ONLY','llm_calls':[]};return None,[],[]
        while True:
            # The server's scheduler runs outside the manual-selection lock.
            self.round_scheduler(self.searching_index,self._episode_agent_rounds,self.values['research_interval_us'])
            if self._manual_request is not None:return None,[],[]
            spent=self._spent()
            reason=('ROUND_LIMIT' if self._episode_agent_rounds>=self.agent_values['agent_max_rounds'] or self.session_agent_rounds_used>=self.agent_values['session_max_agent_rounds']
                    else 'TIME_BUDGET' if spent>=self.agent_values['agent_total_budget_ms'] else None)
            if reason:
                if self._pending_calls:self._rejected(snapshot,decision_time,'SCHEMA_INVALID',None,tools)
                return self._fallback(reason,snapshot,decision_time,tools)
            context['remaining']=self._remaining()
            payload={'context':context,'last_tool_result':last_result,'remaining':self._remaining()}
            if self.settings.template_version=='q5-agent-v2':
                from amidst.q1q5.llm_guidance import workflow
                payload['workflow']=workflow(context,tools.fetched,tools.history)
            prompt=self.settings.template+'\n'+json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
            args={'model':self.settings.model,'prompt':prompt,'template':self.settings.template,'template_version':self.settings.template_version,
                'options':deepcopy(self.settings.options),'timeout_ms':min(self.agent_values['agent_call_timeout_ms'],self.agent_values['agent_total_budget_ms']-spent),'expected_digest':self.settings.model_digest}
            self.agent_attempted=True;self._episode_agent_rounds+=1;self.session_agent_rounds_used+=1
            error=None
            try:result=self.provider.generate(**args);text=result.text;record=result.record
            except ProviderError as exc:text=None;record=exc.record;error=exc.code
            except ReplayMismatch:raise
            except Exception:
                # Unexpected provider faults are operational unavailability. Do
                # not leak exception prose or invent a model digest/output.
                text=None;error='PROVIDER_UNAVAILABLE'
                record={'model':args['model'],'model_digest':None,'prompt':args['prompt'],
                    'prompt_sha256':hashlib.sha256(args['prompt'].encode()).hexdigest(),
                    'prompt_template_version':args['template_version'],'prompt_template_sha256':self.settings.template_sha256,
                    'sampling':deepcopy(args['options']),'raw_output':None,'raw_output_sha256':None,
                    'validation':'PROVIDER_UNAVAILABLE','validation_errors':['UNEXPECTED_PROVIDER_FAILURE'],'timeout_ms':args['timeout_ms'],'timed_out':False}
                record['content_sha256']=canonical_hash(record)
            require(isinstance(record,dict) and record.get('model')==args['model']
                and record.get('prompt')==args['prompt'] and record.get('prompt_sha256')==hashlib.sha256(args['prompt'].encode()).hexdigest()
                and record.get('content_sha256')==canonical_hash(record,exclude=('content_sha256','stats')),'Provider audit pin mismatch')
            if error is None:
                require(isinstance(text,str) and record.get('raw_output')==text
                    and record.get('raw_output_sha256')==hashlib.sha256(text.encode()).hexdigest()
                    and record.get('model_digest')==self.settings.model_digest and record.get('validation')=='PROVIDER_VALIDATED','Provider output/digest mismatch')
            event={'searching_index':self.searching_index,'request':deepcopy(args),'request_sha256':canonical_hash(args),'text':text,'record':deepcopy(record),'error_code':error}
            self.events.append(event);self._spent()
            self._pending_calls.append(self._call_record(event,'PASS' if error is None else error))
            if self._manual_request is not None:
                self._rejected(snapshot,decision_time,'USER_OVERRIDE',None,tools);return None,[],[]
            if error is not None:
                self._rejected(snapshot,decision_time,'SCHEMA_INVALID',None,tools)
                return self._fallback(error,snapshot,decision_time,tools)
            if self._episode_budget_ms>=self.agent_values['agent_total_budget_ms']:
                self._rejected(snapshot,decision_time,'SCHEMA_INVALID',None,tools)
                return self._fallback('TIME_BUDGET',snapshot,decision_time,tools)
            try:
                output=_strict_object(text)
                if isinstance(output,dict) and output.get('schema_version')=='q-demo.agent-decision.v1':
                    name='submit_decision';arguments=output
                else:
                    require(isinstance(output,dict) and set(output)=={'tool','arguments'} and output['tool'] in {'get_search_context','get_candidate_evidence','get_observation_summary'} and isinstance(output['arguments'],dict),'Invalid Agent tool envelope')
                    name=output['tool'];arguments=output['arguments']
                response=tools.dispatch(name,arguments)
            except ReplayMismatch:raise
            except (ValueError,TypeError,KeyError) as exc:
                self._pending_calls[-1]['validation']='SCHEMA_INVALID';self._rejected(snapshot,decision_time,'SCHEMA_INVALID',None,tools)
                return self._fallback('INVALID_RESPONSE',snapshot,decision_time,tools)
            last_result=response
            if self._spent()>=self.agent_values['agent_total_budget_ms']:
                self._rejected(snapshot,decision_time,'SCHEMA_INVALID',None,tools);return self._fallback('TIME_BUDGET',snapshot,decision_time,tools)
            if response.get('accepted') is False:
                illegal+=1;self._pending_calls[-1]['validation']=response['rejection_code']
                self._rejected(snapshot,decision_time,response['rejection_code'],arguments if name=='submit_decision' else None,tools)
                if illegal>=self.agent_values['agent_max_illegal_submissions']:return self._fallback('ILLEGAL_CANDIDATE',snapshot,decision_time,tools)
                tools.decision_id=self.session_id+'-dec-'+str(len(self.decisions));base={'session_id':self.session_id,'decision_id':tools.decision_id}
                context=tools.dispatch('get_search_context',base);continue
            if name!='submit_decision':
                # Evidence lookup is part of the same total wall-time budget.
                if self._spent()>=self.agent_values['agent_total_budget_ms']:
                    self._rejected(snapshot,decision_time,'SCHEMA_INVALID',None,tools);return self._fallback('TIME_BUDGET',snapshot,decision_time,tools)
                continue
            action=arguments['action'];candidate=next((c for c in snapshot['candidates'] if c['candidate_ref']==arguments['candidate_ref']),None)
            evidence=tools.fetched.get(arguments['candidate_ref']);considered=[]
            if candidate is not None:
                considered=[{'candidate_ref':candidate['candidate_ref'],'rank':candidate['rank'],'evidence_sha256':evidence['evidence_sha256'],
                    'target_presence':evidence['target_presence'],'exclusion_reason':arguments['rationale'] if action=='NEXT_CANDIDATE' else None,'action':action,'decided_by':'AGENT'}]
            if action=='NEXT_CANDIDATE':
                with self._control_lock:
                    if self._manual_request is not None:return None,[],[]
                    self._emit('SEARCHING','SEARCHING',decision_time,decision_time=decision_time,snapshot=snapshot,
                        submitted=arguments,considered=considered,tool_calls=tools.history,decided_by='AGENT',llm_calls=self._pending_calls,
                        action='NEXT_CANDIDATE',candidate_ref=candidate['candidate_ref'])
                self._pending_calls=[];tools.history=[]
                if tools.current() is None:
                    # Exhaustion is normal, not a provider failure or fake limit.
                    self._metadata={'decided_by':'RULE_ONLY','llm_calls':[]};return None,[],[]
                tools.decision_id=self.session_id+'-dec-'+str(len(self.decisions));base={'session_id':self.session_id,'decision_id':tools.decision_id}
                context=tools.dispatch('get_search_context',base);continue
            for other in snapshot['candidates']:
                if other['rank']<tools.cursor+1 or (candidate is not None and other['candidate_ref']==candidate['candidate_ref']):continue
                observed=tools.fetched.get(other['candidate_ref'])
                self.diagnostics.append({'searching_index':self.searching_index,'candidate_ref':other['candidate_ref'],
                    'target_presence':observed['target_presence'] if observed else 'NOT_EVALUATED',
                    'evidence_sha256':observed['evidence_sha256'] if observed else None,'reason':'NOT_SELECTED_AFTER_AGENT_DECISION'})
            self._metadata={'decided_by':'AGENT','llm_calls':deepcopy(self._pending_calls),'full_submitted':deepcopy(arguments)}
            return ((candidate,evidence) if action=='SWITCH' else None),considered,tools.history
