"""Q3 strict literal parsing and audited local-provider fallback.

Only closed catalogs, explicit caller parameters and declared clocks are inputs.
Returns a structured query; the HTTP orchestrator executes only PARSED responses.
"""
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import re

from amidst.q1q5.clock_mapping import ClockMapping, ClockMappingError, parse_wall_range
from amidst.q1q5.llm_provider import ProviderError
from amidst.q1q5.q3_rules import parse_rule, SPEC_SHA256, SOURCE_SHA256, VERSION
from amidst.q1q5.store import canonical_hash


class ParseError(ValueError):
    def __init__(self,message,code='FORBIDDEN_INFERENCE_INPUT'):
        self.code=code
        super().__init__(message)


@dataclass(frozen=True)
class ParseSettings:
    query_min_score: float
    min_count_per_frame: int
    min_verdict: str
    page_size: int
    switch_mode: str
    parameter_set_id: str
    parameter_set_sha256: str
    q3_max_llm_attempts: int | None
    q3_llm_timeout_ms: int | None

    def __post_init__(self):
        if (type(self.query_min_score) not in (int,float) or not math.isfinite(self.query_min_score)
                or not 0<=self.query_min_score<=1 or type(self.min_count_per_frame) is not int or self.min_count_per_frame<1
                or type(self.page_size) is not int or self.page_size<1 or self.min_verdict not in {'STRONG','WEAK'}
                or self.switch_mode not in {'RULE_ONLY','AGENT_SEQUENTIAL'}
                or not re.fullmatch(r'[0-9a-f]{64}',self.parameter_set_sha256)
                or self.parameter_set_id!='pset:q-demo:'+self.parameter_set_sha256[:16]):
            raise ParseError('Explicit parse settings required')
        for value in [self.q3_max_llm_attempts,self.q3_llm_timeout_ms]:
            if value is not None and (type(value) is not int or value<1):raise ParseError('Invalid provider bound')


def _catalog(catalog):
    c=deepcopy(catalog)
    expected={'scene_id','scene_revision','run_id','class_labels','color_labels','camera_ids','region_ids',
              'class_aliases','color_aliases','camera_aliases','region_aliases','class_map_sha256'}
    if not isinstance(c,dict) or set(c)!=expected:raise ParseError('Closed server catalog required')
    for aliases,values in [('class_aliases','class_labels'),('color_aliases','color_labels'),('camera_aliases','camera_ids'),('region_aliases','region_ids')]:
        if (not isinstance(c[aliases],dict) or not isinstance(c[values],list) or len(set(c[values]))!=len(c[values])
                or any(not isinstance(k,str) or not k or v not in c[values] for k,v in c[aliases].items())):
            raise ParseError('Alias outside closed catalog')
    if not re.fullmatch(r'[0-9a-f]{64}',c['class_map_sha256']):raise ParseError('Class-map pin required')
    return c


def _strict_object(text):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    def bad(_):raise ValueError('Non-finite JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=bad)


def validate_literal_output(output,text):
    keys={'schema_version','intent','class_term','color_term','time_literal','camera_terms','region_terms','needs_clarification','clarification_question'}
    if not isinstance(output,dict) or set(output)!=keys or output['schema_version']!='q-demo.q3-llm-output.v1':raise ValueError('Unexpected Q3 fields/schema')
    if output['intent'] not in {'FIND_CAMERAS','FIND_PERSON','EXPLAIN','UNSUPPORTED'} or type(output['needs_clarification']) is not bool:raise ValueError('Invalid intent/clarification')
    question=output['clarification_question']
    if output['needs_clarification']:
        if not isinstance(question,str) or not question.strip():raise ValueError('Clarification question missing')
    elif question is not None:raise ValueError('Unexpected clarification question')
    literals=[]
    for key in ['class_term','color_term']:
        value=output[key]
        if value is not None and (not isinstance(value,str) or not value):raise ValueError('Invalid literal')
        if value is not None:literals.append(value)
    time=output['time_literal']
    if not isinstance(time,dict) or set(time)!={'start','end','date'}:raise ValueError('Invalid time literal')
    for value in time.values():
        if value is not None:
            if not isinstance(value,str) or not value:raise ValueError('Invalid time literal')
            literals.append(value)
    for key in ['camera_terms','region_terms']:
        if not isinstance(output[key],list) or any(not isinstance(v,str) or not v for v in output[key]):raise ValueError('Invalid term list')
        literals+=output[key]
    if any(value not in text for value in literals):raise ValueError('LLM invented nonliteral term')
    return deepcopy(output)


def parse_query(request,*,catalog,settings: ParseSettings,clock_mapping: ClockMapping | None,
                provider=None,prompt_template=None,model=None,options=None,expected_digest=None,prompt_template_version="q3-parse.v1"):
    allowed={'schema_version','session_ref','text','locale','context','parser_mode'}
    if not isinstance(request,dict) or set(request)!=allowed or request['schema_version']!='q-demo.q3-parse-request.v1':raise ParseError('Unexpected Q3 input')
    if (request['locale']!='zh-TW' or not isinstance(request['session_ref'],str) or not request['session_ref']
            or not isinstance(request['text'],str) or not request['text'].strip()
            or request['parser_mode'] not in {'RULE_ONLY','LLM_WITH_RULE_FALLBACK'}):raise ParseError('Invalid Q3 request')
    ctx=request['context'];c=_catalog(catalog)
    if (not isinstance(ctx,dict) or set(ctx)!={'scene_id','run_ids','clock_mapping_sha256'}
            or ctx['scene_id']!=c['scene_id'] or ctx['run_ids']!=[c['run_id']]):raise ParseError('Select exactly one registered run')
    if clock_mapping is not None and (clock_mapping.run_id!=c['run_id'] or ctx['clock_mapping_sha256']!=clock_mapping.content_sha256):raise ParseError('Clock scope/pin mismatch')
    if clock_mapping is None and ctx['clock_mapping_sha256'] is not None:raise ParseError('Clock pin supplied without mapping')
    text=request['text'];rules=parse_rule(text,**{k:c[k] for k in ['class_aliases','color_aliases','camera_aliases','region_aliases']})
    output=rules.output;parsed_by='RULE';audit=[];fallback=None;last_record=None
    scope={key:None for key in ['scene_id','scene_revision','run_ids','clock_ids','clock_mapping_sha256','requested_time','resolved_source_ranges_us','time_coverage','camera_ids','detection_index_id','detection_index_sha256','region_graph_sha256','camera_graph_sha256','class_map_sha256','color_method_version','parameter_set_id','parameter_set_sha256']}
    scope.update(scene_id=c['scene_id'],scene_revision=c['scene_revision'],run_ids=[c['run_id']],clock_ids=[clock_mapping.clock_id] if clock_mapping else None,clock_mapping_sha256=clock_mapping.content_sha256 if clock_mapping else None,class_map_sha256=c['class_map_sha256'],parameter_set_id=settings.parameter_set_id,parameter_set_sha256=settings.parameter_set_sha256)
    response={'schema_version':'q-demo.q3-parse-response.v1','status':'PARSE_FAILED','reason':None,'parsed_by':parsed_by,'structured_query':None,'unresolved_terms':[],'clarification':None,'llm_call':None,'resolved_scope':scope,'identity_verdict':'UNCONFIRMED','llm_parse_used':False,'agent_attempted':False,'agent_used':False,'decision_source':None,'fallback_used':False,'fallback_reason':None,'provenance':{'producer':'q3-parser','producer_version':'1','gt_read':False,'input_refs':['rules-spec:'+SPEC_SHA256,'catalog:'+canonical_hash(c)],'rule_version':VERSION,'rule_spec_sha256':SPEC_SHA256,'rule_source_sha256':SOURCE_SHA256}}
    def finish(status,reason=None,question=None):
        response.update(status=status,reason=reason,parsed_by=parsed_by,llm_parse_used=parsed_by=='LLM',fallback_used=fallback is not None,fallback_reason=fallback)
        if question:response['clarification']={'question':question,'options':[]}
        response['output_sha256']=canonical_hash(response,exclude=('output_sha256','stats'))
        # Full provider audit is separate from the stable domain response.
        return response,tuple(audit)
    if rules.unsupported_condition:return finish('UNSUPPORTED_CONDITION','UNSUPPORTED_ATTRIBUTE')
    if request['parser_mode']=='LLM_WITH_RULE_FALLBACK':
        if settings.q3_max_llm_attempts is None or settings.q3_llm_timeout_ms is None:raise ParseError('Explicit approved Q3 bounds required')
        if provider is None:fallback='PROVIDER_UNAVAILABLE'
        else:
            if not all(isinstance(v,str) and v for v in [prompt_template,model]) or not isinstance(options,dict):raise ParseError('Explicit model/template/options required')
            from amidst.q1q5.llm_guidance import Q3_MARKER
            if prompt_template_version not in {'q3-parse.v1','q3-parse.v2'} or (prompt_template_version=='q3-parse.v2') != prompt_template.startswith(Q3_MARKER):
                raise ParseError('Q3 template version/framing mismatch')
            catalog_fields=['class_labels','color_labels','camera_ids','region_ids']+(['class_aliases','color_aliases','camera_aliases','region_aliases'] if prompt_template_version=='q3-parse.v2' else [])
            prompt=prompt_template+'\nCLOSED_CATALOG='+json.dumps({k:c[k] for k in catalog_fields},ensure_ascii=True,sort_keys=True)+'\nUSER_TEXT='+json.dumps(text,ensure_ascii=True)
            for attempt in range(1,settings.q3_max_llm_attempts+1):
                try:
                    result=provider.generate(model=model,prompt=prompt,template=prompt_template,template_version=prompt_template_version,options=options,timeout_ms=settings.q3_llm_timeout_ms,expected_digest=expected_digest)
                    last_record=result.record;audit.append({'provider_record':deepcopy(last_record),'task_validation_errors':[]})
                    output=validate_literal_output(_strict_object(result.text),text)
                    # A schema-valid model must not erase recognized user constraints.
                    for field,table in [('class_term','class_aliases'),('color_term','color_aliases')]:
                        literal=rules.output[field]
                        known={v for k,v in c[table].items() if literal is not None and k.casefold()==literal.casefold()}
                        proposed={v for k,v in c[table].items() if output[field] is not None and k.casefold()==output[field].casefold()}
                        if known and known!=proposed:raise ValueError('LLM dropped/changed explicit '+field)
                    for field,table in [('camera_terms','camera_aliases'),('region_terms','region_aliases')]:
                        expected={c[table][k] for k in c[table] if any(k.casefold()==v.casefold() for v in rules.output[field])}
                        actual={c[table][k] for k in c[table] if any(k.casefold()==v.casefold() for v in output[field])}
                        if expected!=actual:raise ValueError('LLM dropped/changed explicit scope')
                    if not rules.output['needs_clarification']:
                        if output['time_literal']!=rules.output['time_literal'] or output['intent']!=rules.output['intent']:
                            raise ValueError('LLM changed explicit intent/time')
                    parsed_by='LLM';fallback=None;break
                except ProviderError as exc:
                    last_record=exc.record;audit.append({'provider_record':deepcopy(last_record),'task_validation_errors':[]});fallback=exc.code;break
                except (ValueError,TypeError) as exc:
                    fallback='INVALID_RESPONSE'
                    if last_record is not None:audit[-1]['task_validation_errors']=[str(exc)]
            if parsed_by!='LLM':output=rules.output
            if last_record:
                response['llm_call']={k:last_record[k] for k in ['model','model_digest','prompt_sha256','raw_output_sha256']}
                response['llm_call']['model_digest']=response['llm_call']['model_digest'] or 'UNKNOWN'
                response['llm_call'].update(prompt_ref='prompt:'+last_record['prompt_sha256'],attempts=len(audit),validation_errors=[v for a in audit for v in a.get('task_validation_errors',[])])
    # Conservative residual guard prevents silently dropping unsupported user conditions.
    class_term=output['class_term'];lookup=lambda table,term:next((v for k,v in table.items() if term is not None and k.casefold()==term.casefold()),None)
    label=lookup(c['class_aliases'],class_term)
    if class_term is not None and label is None:
        if parsed_by=='RULE' and output['time_literal']['start'] is None:return finish('PARSE_FAILED','RULE_SYNTAX_UNSUPPORTED')
        response['unresolved_terms']=[class_term];return finish('UNSUPPORTED_CLASS','CLASS_NOT_IN_CLOSED_TABLE')
    if output['intent'] in {'EXPLAIN','UNSUPPORTED'}:return finish('UNSUPPORTED_CONDITION','INTENT_NOT_EXECUTABLE')
    color=lookup(c['color_aliases'],output['color_term'])
    if output['color_term'] is not None and color is None:return finish('UNSUPPORTED_CONDITION','COLOR_NOT_IN_CLOSED_TABLE')
    if color and label!='person':return finish('UNSUPPORTED_CONDITION','COLOR_REQUIRES_PERSON')
    if output['needs_clarification'] or label is None:return finish('NEEDS_CLARIFICATION','AMBIGUOUS_QUERY',output['clarification_question'] or '請補充查詢類別與起訖時間。')
    if rules.unparsed:
        response['unresolved_terms']=list(rules.unparsed);return finish('NEEDS_CLARIFICATION','UNPARSED_CONDITION','這些條件超出第一版語法，請改寫或使用表單。')
    cameras=[lookup(c['camera_aliases'],v) for v in output['camera_terms']];regions=[lookup(c['region_aliases'],v) for v in output['region_terms']]
    if any(v is None for v in cameras+regions):
        response['unresolved_terms']=[*output['camera_terms'],*output['region_terms']];return finish('NEEDS_CLARIFICATION','UNRESOLVED_SCOPE','請選擇目錄已有的鏡頭或區域。')
    if clock_mapping is None:return finish('NEEDS_CLARIFICATION','CLOCK_MAPPING_MISSING','請選擇有展示時鐘對應的 run。')
    try:
        literal=output['time_literal'];wall=parse_wall_range(clock_mapping,literal['start'],literal['end'],date_literal=literal['date'])
    except ClockMappingError as exc:return finish('TIME_EXPRESSION_INVALID',exc.code)
    time={'kind':'WALL','wall_range':list(wall)};scope['requested_time']=time;scope['camera_ids']=sorted(set(cameras)) or None
    common={'session_ref':request['session_ref'],'scene_id':c['scene_id'],'run_ids':[c['run_id']],'time':time}
    if output['intent']=='FIND_PERSON':
        if label!='person' or cameras or regions:return finish('UNSUPPORTED_CONDITION','Q2_SCOPE_FILTER_UNSUPPORTED')
        query={'schema_version':'q-demo.q2-request.v1',**common,'seed':{'kind':'APPEARANCE','class_label':'person','color':{'label':color,'min_verdict':settings.min_verdict} if color else None},'switch_mode':settings.switch_mode,'parameter_set_id':settings.parameter_set_id}
    else:
        query={'schema_version':'q-demo.q1-request.v1',**common,'condition':{'class_label':label,'min_count_per_frame':settings.min_count_per_frame,'color':{'label':color,'min_verdict':settings.min_verdict} if color else None,'query_min_score':settings.query_min_score},'camera_ids':sorted(set(cameras)) or None,'region_ids':sorted(set(regions)) or None,'page_size':settings.page_size,'cursor':None,'origin':'Q3_PARSED'}
    response['structured_query']=query
    return finish('PARSED')
