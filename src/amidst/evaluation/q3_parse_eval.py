"""Evaluation-only Q3 scorer; no parser/provider or answer-generation imports."""
from amidst.evaluation.q1_query_eval import (
    EvaluationError,KIT_SHA,canonical,sha,require,identity_map,metric,
)
from amidst.q1q5.clock_mapping import ClockMapping,ClockMappingError

VERSION='q3-parse-eval-v1'
STATUSES={'PARSED','NEEDS_CLARIFICATION','UNSUPPORTED_CLASS','UNSUPPORTED_CONDITION','PARSE_FAILED','TIME_EXPRESSION_INVALID'}
REFUSALS=STATUSES-{'PARSED'}
FIELDS=['intent','class','color','time_us','camera','region']
LITERALS=['intent','class_term','color_term','time_literal','camera_terms','region_terms']


def clock_catalog(document):
    require(isinstance(document,dict) and document.get('schema_version')=='q-demo.eval-clock-catalog.v1'
            and isinstance(document.get('mappings'),list),'Explicit clock catalog required')
    result={}
    for row in document['mappings']:
        mapping=ClockMapping(row);require(mapping.run_id not in result,'Duplicate clock mapping run')
        result[mapping.run_id]=mapping
    return result


def project(query,schemas,clocks):
    require(isinstance(query,dict),'Structured query required')
    key=query.get('schema_version');require(key in {'q-demo.q1-request.v1','q-demo.q2-request.v1'},'Unexpected structured query schema')
    errors=schemas.errors(query,key);require(not errors,'Structured query schema: '+str(errors))
    run_ids=query['run_ids'];require(len(run_ids)==1 and run_ids[0] in clocks,'Explicit single-run clock mapping required')
    run=run_ids[0];mapping=clocks[run];time=query['time']
    require(isinstance(mapping,ClockMapping) and mapping.run_id==run,'Clock binding mismatch')
    try:
        if time['kind']=='SOURCE':
            require(time['run_id']==run,'Source time/run mismatch');left,right=time['range_us']
        else:
            left,right=[mapping.wall_to_source(value) for value in time['wall_range']]
    except ClockMappingError as exc:raise EvaluationError('Time conversion failed: '+str(exc)) from exc
    require(type(left) is int and type(right) is int and left<right,'Invalid half-open source range')
    condition=query.get('condition') if key=='q-demo.q1-request.v1' else query.get('seed')
    color=condition.get('color')
    return {'intent':'FIND_CAMERAS' if key=='q-demo.q1-request.v1' else 'FIND_PERSON',
            'class':condition.get('class_label'),'color':color.get('label') if color else None,
            'time_us':{'run_id':run,'clock_id':mapping.clock_id,'range_us':[left,right]},
            'camera':sorted(query['camera_ids']) if query.get('camera_ids') is not None else None,
            'region':sorted(query['region_ids']) if query.get('region_ids') is not None else None}


def prediction_rows(cases,predictions,layout):
    require(layout in {'id-wrapper','dataset-order'},'Explicit prediction layout required')
    if layout=='id-wrapper':return predictions
    require(len(cases)==len(predictions),'Ordered predictions need exactly one response per case')
    return [{'id':case['id'],'response':response} for case,response in zip(cases,predictions)]


def evaluate(cases,predictions,*,cases_sha256,predictions_sha256,schemas,clocks,
             clocks_sha256,evaluation_eligible,authority_sha256):
    require(type(evaluation_eligible) is bool,'Explicit dataset eligibility required')
    by_id=identity_map(cases);preds=identity_map(predictions);invalid=[];details=[]
    field_counts={k:[0,0] for k in FIELDS};literal_counts={k:[0,0] for k in LITERALS}
    counts=dict(status=0,schema=0,hash=0,present=0,valid_predictions=0,fallback=0,raw_available=0)
    tp=fp=fn=0;groups={}
    for cid,case in sorted(by_id.items()):
        status=case.get('expected_status');expected=case.get('expected_structured_query');llm=case.get('expected_llm_output')
        errors=schemas.errors(llm,'q-demo.q3-llm-output.v1')
        if status not in STATUSES:errors.append('Expected status missing/unsupported')
        if not isinstance(case.get('text'),str) or not case['text']:errors.append('Original text required')
        expected_projection=None
        if status=='PARSED':
            try:expected_projection=project(expected,schemas,clocks)
            except EvaluationError as exc:errors.append(str(exc))
        elif expected is not None:errors.append('Non-PARSED expected must not execute a query')
        if errors:
            invalid.append({'id':cid,'status':'INVALID','reason':'PRECISE_HUMAN_ANNOTATION_OR_CLOCK_INVALID','errors':errors});continue
        wrapper=preds.get(cid,{})
        response=wrapper.get('response');schema_errors=schemas.errors(response,'q-demo.q3-parse-response.v1')
        hash_ok=not schema_errors and response.get('output_sha256')==sha(canonical({k:v for k,v in response.items() if k not in {'output_sha256','stats'}}))
        actual=response if hash_ok else None;semantic_errors=[];actual_projection=None
        if actual is not None:
            if actual['status']=='PARSED':
                try:actual_projection=project(actual.get('structured_query'),schemas,clocks)
                except EvaluationError as exc:semantic_errors.append(str(exc));actual=None
            elif actual.get('structured_query') is not None:semantic_errors.append('Non-PARSED prediction has executable query');actual=None
        raw=wrapper.get('llm_output');raw_errors=schemas.errors(raw,'q-demo.q3-llm-output.v1') if raw is not None else None
        checks={k:actual_projection is not None and actual_projection[k]==expected_projection[k] for k in FIELDS} if expected_projection is not None else {}
        literals={k:raw[k]==llm[k] for k in LITERALS} if raw is not None and not raw_errors and actual is not None else {}
        status_ok=actual is not None and actual['status']==status
        detail={'id':cid,'eligible_for_formal_metrics':evaluation_eligible,'status_correct':status_ok,
                'schema_valid':not schema_errors,'hash_valid':hash_ok,'fields':checks,'literal_fields':literals,
                'raw_llm_output_available':raw is not None and not raw_errors,
                'schema_errors':schema_errors,'semantic_errors':semantic_errors,'raw_llm_schema_errors':raw_errors}
        details.append(detail)
        if not evaluation_eligible:continue
        counts['status']+=int(status_ok);counts['schema']+=int(not schema_errors);counts['hash']+=int(hash_ok);counts['present']+=int(cid in preds)
        counts['valid_predictions']+=int(actual is not None);counts['fallback']+=int(actual is not None and actual['fallback_used'])
        counts['raw_available']+=int(bool(literals))
        for k,v in checks.items():field_counts[k][0]+=int(v);field_counts[k][1]+=1
        # Missing raw intermediate output is unavailable, not an invented wrong label.
        for k,v in literals.items():literal_counts[k][0]+=int(v);literal_counts[k][1]+=1
        expected_refusal=status in REFUSALS;actual_refusal=actual is not None and actual['status'] in REFUSALS
        tp+=int(expected_refusal and actual_refusal);fp+=int(not expected_refusal and actual_refusal);fn+=int(expected_refusal and not actual_refusal)
        category=case.get('category','UNSPECIFIED');require(isinstance(category,str),'Category must be text')
        group=groups.setdefault(category,{'count':0,'status_correct':0,'fields':{k:[0,0] for k in FIELDS}});group['count']+=1;group['status_correct']+=int(status_ok)
        for k,v in checks.items():group['fields'][k][0]+=int(v);group['fields'][k][1]+=1
    n=sum(d['eligible_for_formal_metrics'] for d in details)
    report={'schema_version':'q3-parse-eval-report.v1','scorer_version':VERSION,'schema_kit_sha':KIT_SHA,
            'cases_sha256':cases_sha256,'predictions_sha256':predictions_sha256,'clocks_sha256':clocks_sha256,'dataset_authority_sha256':authority_sha256,
            'evaluation_eligible':evaluation_eligible,'status':'MEASURED' if n else 'NO_FORMAL_CASES',
            'case_count':len(cases),'valid_case_count':len(details),'formal_case_count':n,'invalid_cases':invalid,
            'missing_prediction_ids':sorted(set(by_id)-set(preds)),'extra_prediction_ids':sorted(set(preds)-set(by_id)),
            'status_accuracy':metric(counts['status'],n),'schema_validity':metric(counts['schema'],n),
            'hash_validity':metric(counts['hash'],n),'prediction_coverage':metric(counts['present'],n),
            'field_accuracy':{k:metric(*v) for k,v in field_counts.items()},'literal_field_accuracy':{k:metric(*v) for k,v in literal_counts.items()},
            'raw_llm_output_availability':metric(counts['raw_available'],n),'fallback_rate':metric(counts['fallback'],counts['valid_predictions']),
            'refusal':{'TP':tp,'FP':fp,'FN':fn,'precision':metric(tp,tp+fp),'recall':metric(tp,tp+fn)},
            'by_category':{k:{'count':v['count'],'status_accuracy':metric(v['status_correct'],v['count']),
                              'fields':{f:metric(*pair) for f,pair in v['fields'].items()}} for k,v in sorted(groups.items())},
            'details':details,'acceptance_threshold':None,
            'limits':['Semantic fields score PARSED expected cases only; original literal fields need an explicit validated llm_output sidecar.',
                      'Time uses uncut source microseconds and an explicitly pinned mapping, so clipping cannot hide a wrong time.',
                      'No parser, provider, question, answer or acceptance threshold is generated.']}
    report['output_sha256']=sha(canonical(report));return report
