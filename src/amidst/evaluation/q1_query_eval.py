"""Evaluation-only Q1 core scorer; expected answers must be supplied by humans.

No query implementation/model/index imports. Schemas and the audited stdlib
validator are read only from the hash-pinned #127 kit, never vendored or edited.
"""
import hashlib
import json
import sys
import types
from copy import deepcopy
from pathlib import Path

from amidst.evaluation.response_versions import (
    response_schema_key,scoring_exclusion,time_range_source,v2_schema_documents,V2_SCHEMA_SOURCE,
)

VERSION='q1-query-eval-v1.2'
KIT_SHA='994d34c8340855dbf0e28d0273851049df5e6c7d'


class EvaluationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def require(ok,message):
    if not ok:raise EvaluationError(message)


def decode(raw):
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'Duplicate JSON key');result[k]=v
        return result
    try:
        value=json.loads(raw,object_pairs_hook=pairs);canonical(value);return value
    except (ValueError,TypeError,UnicodeError) as exc:raise EvaluationError('Malformed JSON') from exc


def rows(raw):
    result=[decode(line) for line in raw.splitlines()]
    require(all(isinstance(r,dict) for r in result),'Object JSONL required');return result


_PINNED_FILES = {'mini_schema.py': '07b2fa8fe958e3a9beee02b3933ab9ed4c59d662664d67f52c888a74b4f338a4',
 'schemas/agent-decision.v1.schema.json': '22a75187165926a64b56737b14fee9d3b72b4812339f5cdeb94b661cec2d2401',
 'schemas/camera-transition-graph.v1.schema.json': '7fd9cf290420a15713c78203ce0d9bc9007cb913d77b50cf06936daa0545e7f1',
 'schemas/candidate-evidence.v1.schema.json': '53ce8d0a6d07c0dfd5390896911c505186a7b10fbee917cad0663cac0c14fca0',
 'schemas/candidate-snapshot.v1.schema.json': '56db1fe4217969373eb67460c9bd8ed45559b93ff7cc76f1ee091a74e3986b75',
 'schemas/clock-mapping.v1.schema.json': '00e8856105fee84acc8c43cfd2e8637238e839e2f145ae1f39c2d3f95bac1376',
 'schemas/common.schema.json': 'bfeab0531551039ce33570c94380a4012db40dae43389fbe5e91c3b0fb5a4645',
 'schemas/decision-record.v1.schema.json': 'ac6a9b3e1117e3ecebaa1709187c736ab42f8f2f1a23172edcb9b3ceecc627e3',
 'schemas/detection-index.v1.schema.json': '7b57ba14d5b62eb20593aa431acf5724eda3654fb6d5fe1a26f9938d5c7823e5',
 'schemas/detection-record.schema.json': '23e69782f3c38e2a441c32f5fe2671626cce5615ebc9cfe66c4cede8c55e9a75',
 'schemas/explanation.v1.schema.json': '0361661d041be467cafafb8e94b88c664db5443ee33d740b2c8af279fa801f16',
 'schemas/kit-supported-classes.v1.schema.json': '5b69f8b315279cab088534e9f4ba91c26280e4a768ccb940c186481dbd56729f',
 'schemas/link-record.schema.json': '0cce2b8a825b13d35402982196a51bb5f74075c48b51d5ec493b95321c1d0115',
 'schemas/parameter-set.v1.schema.json': '5d6b7022cb73d982707939861cb81579b253c8d38a5805031216ad9b9f9b80b6',
 'schemas/q1-request.v1.schema.json': '7426c14f5256939f51b3957471c38d7acd8f6db7c088871bf879150b23631aa6',
 'schemas/q1-response.v1.schema.json': '061d759e5e77c1031f18367d30d2f980be2c4eb85c740bb8aa01eed8da3008e2',
 'schemas/q2-request.v1.schema.json': '0011eb4392a003b024549e786ff1c347778ad1eb716387944eb92bccf0af4770',
 'schemas/q2-response.v1.schema.json': '11ed71d4cff91028aa915563ad91c0b90b505e5502e247b90443efefefcda1fe',
 'schemas/q3-llm-output.v1.schema.json': 'b54ea0ef9e760e07d600ab57c4eaacdfc130038c3b87ec9e3fd872432a0fdcdb',
 'schemas/q3-parse-request.v1.schema.json': 'd032caae1571f351102c23681e4682280e8bc6f796ad447fa52cca1fd74fcd24',
 'schemas/q3-parse-response.v1.schema.json': '67b385efa6a456b5fe36f3b62d183d1b54565b0bbb311aba0548a0aafe9bbbbf',
 'schemas/region-graph.v1.schema.json': '0fe44c062ef5fb8a6b9b20d58bf01caba242f7edb36a68c1234896a71109cd8e'}


class PinnedSchemas:
    """Load only audited 994d34c bytes; refs resolve in an in-memory allowlist."""
    KEYS={'q-demo.q1-request.v1':'q1-request.v1.schema.json',
          'q-demo.q1-response.v1':'q1-response.v1.schema.json',
          'q-demo.q1-response.v2':'q1-response.v2.schema.json',
          'q-demo.q2-response.v1':'q2-response.v1.schema.json',
          'q-demo.q2-response.v2':'q2-response.v2.schema.json',
          'q-demo.q2-request.v1':'q2-request.v1.schema.json',
          'q-demo.q3-llm-output.v1':'q3-llm-output.v1.schema.json',
          'q-demo.q3-parse-response.v1':'q3-parse-response.v1.schema.json',
          'q-demo.q3-parse-response.v2':'q3-parse-response.v2.schema.json'}

    def __init__(self,root):
        root=Path(root).absolute();require(root.resolve()==root,'Canonical readonly schema root required')
        blobs={}
        for rel,pin in _PINNED_FILES.items():
            file=root/rel;require(file.resolve()==file and file.is_file(),'Schema/validator path rejected')
            raw=file.read_bytes();require(sha(raw)==pin,'Schema/validator differs from fixed kit '+KIT_SHA);blobs[rel]=raw
        name='_amidst_eval_frozen_schema_'+KIT_SHA
        module=types.ModuleType(name);sys.modules[name]=module
        # Execute the exact audited bytes already hashed, avoiding a second file
        # open/TOCTOU and never importing arbitrary code from the external root.
        exec(compile(blobs['mini_schema.py'],'frozen-kit@'+KIT_SHA+'/mini_schema.py','exec'),module.__dict__)
        self.documents={name.removeprefix('schemas/'):decode(raw) for name,raw in blobs.items() if name.startswith('schemas/')}
        full=self.documents['q1-response.v1.schema.json'];keys=['status','reason','results','no_match_cameras','not_evaluated_cameras']
        self.documents['q1-core-evaluation.schema.json']={'type':'object','properties':deepcopy(full['properties']),
                                                       'required':keys,'additionalProperties':False}
        self.validator=module.Validator(self._load)

    def _load(self,name):
        require(name in self.documents,'Schema ref outside frozen allowlist');return deepcopy(self.documents[name])

    def errors(self,value,key):
        if key.endswith('-response.v2') and 'common.v2.schema.json' not in self.documents:
            self.documents.update(v2_schema_documents())
        file='q1-core-evaluation.schema.json' if key=='Q1_CORE' else self.KEYS.get(key)
        require(file is not None,'Unsupported evaluation schema key')
        return [str(error) for error in self.validator.validate(value,file)]


def metric(n,d):return {'numerator':n,'denominator':d,'value':n/d if d else None}


def identity_map(items):
    result={}
    for row in items:
        require(isinstance(row,dict) and isinstance(row.get('id'),str) and row['id'] and row['id'] not in result,'Missing/duplicate evaluation ID')
        result[row['id']]=row
    return result


def dataset_eligibility(receipt,*,cases_sha256,filename):
    """Trusted #147 receipt, or explicit synthetic-only external dataset record."""
    require(isinstance(receipt,dict),'Dataset authority record required')
    if receipt.get('schema_version')=='team-review-import.v1':
        pins=receipt.get('output_files_sha256')
        require(isinstance(pins,dict),'Importer output pins must be an object')
        require(pins.get(filename)==cases_sha256,'Importer output pin mismatch')
        require(type(receipt.get('evaluation_eligible')) is bool,'Importer eligibility missing')
        version=receipt.get('pack_version');require(version in {'v0-pilot','v1'} and receipt['evaluation_eligible']==(version=='v1'),'Pilot/formal receipt mismatch')
        return receipt['evaluation_eligible']
    require(receipt.get('schema_version')=='q-demo.synthetic-evaluation-dataset.v1'
            and receipt.get('kind')=='SYNTHETIC' and receipt.get('cases_sha256')==cases_sha256,
            'Only explicit SYNTHETIC record or verified #147 import receipt accepted')
    return False


def dataset_kind_from_receipt(receipt):
    if receipt.get('schema_version')=='team-review-import.v1':
        return 'FORMAL' if receipt['pack_version']=='v1' else 'PILOT'
    return 'SYNTHETIC'



def core_errors(core,schemas):
    errors=schemas.errors(core,'Q1_CORE')
    if errors:return errors
    cameras=[x['camera_id'] for k in ['results','no_match_cameras','not_evaluated_cameras'] for x in core[k]]
    if len(cameras)!=len(set(cameras)):errors.append('Camera categories must be disjoint and unique')
    keys=[]
    for result in core['results']:
        last=-1
        for segment in result['matched_segments']:
            left,right=segment['range_us']
            if left>=right or left<last or segment['matched_frames']>segment['evaluated_frames']:errors.append('Invalid expected segments/counts')
            last=right
        keys.append((result['matched_segments'][0]['range_us'][0],result['camera_id']))
    ranks=[x['rank'] for x in core['results']]
    if keys!=sorted(keys) or (ranks and ranks!=list(range(ranks[0],ranks[0]+len(ranks)))):errors.append('Invalid expected order/ranks')
    if core['status']=='READY' and not core['results']:errors.append('READY needs results')
    incomplete=bool(core['not_evaluated_cameras']) or any(x['coverage']['not_inferred_frames'] or x['coverage']['missing_frames'] for k in ['results','no_match_cameras'] for x in core[k])
    if core['status'] in {'READY','NO_MATCH'} and incomplete:errors.append('Complete status hides incomplete coverage')
    if core['status']=='NO_MATCH' and (core['results'] or core['not_evaluated_cameras'] or not core['no_match_cameras']):errors.append('NO_MATCH categories inconsistent')
    if core['status'] in {'UNSUPPORTED_CLASS','UNSUPPORTED_CONDITION','OUT_OF_RANGE','UNKNOWN'} and core['results']:
        errors.append('Nonexecuting expected status cannot contain results')
    return errors


def evaluate(cases,predictions,*,cases_sha256,predictions_sha256,schemas,evaluation_eligible,authority_sha256,dataset_kind):
    require(type(evaluation_eligible) is bool,'Explicit dataset eligibility required')
    require(dataset_kind in {'FORMAL','SYNTHETIC','PILOT'} and evaluation_eligible==(dataset_kind=='FORMAL'),
            'Dataset kind/eligibility mismatch')
    by_id=identity_map(cases);preds=identity_map(predictions);details=[];invalid=[];origin_groups={}
    totals={k:0 for k in ['status','reason','camera_tp','camera_fp','camera_fn','segments','coverage','order','none_categories','schema','present','hash','request_binding']}
    groups={}
    for cid,case in sorted(by_id.items()):
        expected=case.get('expected_response_core');request=case.get('request')
        errors=schemas.errors(request,'q-demo.q1-request.v1')+core_errors(expected,schemas)
        if errors:
            invalid.append({'id':cid,'status':'INVALID','reason':'PRECISE_EXPECTED_OR_REQUEST_INVALID','errors':errors});continue
        results=expected['results']
        if (request.get('cursor') is not None or len(results)>request['page_size']
                or [x['rank'] for x in results]!=list(range(1,len(results)+1))):
            invalid.append({'id':cid,'status':'INVALID','reason':'PAGE_SCOPE_UNSUPPORTED','errors':[]});continue
        normalized_request={k:v for k,v in request.items() if k!='origin'}
        binding=case.get('query_binding')
        if (not isinstance(binding,dict) or 'query_sha256' not in binding
                or binding.get('request_sha256')!=sha(canonical(normalized_request))):
            invalid.append({'id':cid,'status':'INVALID','reason':'QUERY_BINDING_CONTEXT_MISSING','errors':[]});continue
        prediction=preds.get(cid,{}).get('response');validation=schemas.errors(prediction,response_schema_key(prediction,'q1'))
        measurements={k:False for k in ['status','reason','segments','coverage','order','none_categories','schema','present','hash','request_binding']}
        measurements['present']=cid in preds;measurements['schema']=not validation
        camera_tp=camera_fp=camera_fn=0
        actual=prediction if not validation else None
        measurements['hash']=actual is not None and actual.get('output_sha256')==sha(canonical({k:v for k,v in actual.items() if k not in {'output_sha256','stats'}}))
        integrity_errors=[] if actual is None or measurements['hash'] else ['Prediction output_sha256 mismatch']
        if integrity_errors:actual=None
        expected_cameras={x['camera_id'] for x in expected['results']}
        if actual is not None:
            actual_runs=(actual.get('resolved_scope') or {}).get('run_ids')
            measurements['request_binding']=(actual.get('normalized_condition')==request['condition']
                and (actual_runs is None or actual_runs==request['run_ids'])
                and actual.get('query_sha256')==binding['query_sha256'])
            if not measurements['request_binding']:
                integrity_errors.append('Prediction does not match frozen request/query binding')
                actual=None
            elif (actual['schema_version'].endswith('.v2') and case.get('expected_time_range_source') is not None
                  and time_range_source(actual) != case['expected_time_range_source']):
                integrity_errors.append('Prediction time source contradicts frozen annotation')
                actual=None
        if actual is not None:
            measurements['hash']=actual.get('output_sha256')==sha(canonical({k:v for k,v in actual.items() if k not in {'output_sha256','stats'}}))
            measurements['status']=actual['status']==expected['status'];measurements['reason']=actual['reason']==expected['reason']
            actual_cameras={x['camera_id'] for x in actual['results']};camera_tp=len(actual_cameras&expected_cameras);camera_fp=len(actual_cameras-expected_cameras);camera_fn=len(expected_cameras-actual_cameras)
            def segments(result):return {x['camera_id']:[(s['range_us'],s['matched_frames'],s['evaluated_frames']) for s in x['matched_segments']] for x in result['results']}
            measurements['segments']=segments(actual)==segments(expected)
            def coverage(result):return {x['camera_id']:x['coverage'] for group in ['results','no_match_cameras'] for x in result[group]}
            measurements['coverage']=coverage(actual)==coverage(expected)
            expected_order=[(x['camera_id'],x['rank']) for x in expected['results']]
            actual_order=[(x['camera_id'],x['rank']) for x in actual['results']]
            keys=[(x['matched_segments'][0]['range_us'][0],x['camera_id']) for x in actual['results']]
            measurements['order']=expected_order==actual_order and keys==sorted(keys)
            def categories(result):return [sorted(x['camera_id'] for x in result[k]) for k in ['results','no_match_cameras','not_evaluated_cameras']]
            categories_actual=categories(actual);flat=sum(categories_actual,[])
            measurements['none_categories']=categories_actual==categories(expected) and len(set(flat))==len(flat)
        else:camera_fn=len(expected_cameras)
        exclusion=scoring_exclusion(case,actual)
        eligible=evaluation_eligible and exclusion is None
        category=case.get('category','UNSPECIFIED');require(isinstance(category,str),'Category must be text')
        details.append({'id':cid,'category':category,'prediction_present':cid in preds,'eligible_for_formal_metrics':eligible,
                        'scoring_exclusion_reason':exclusion,'checks':measurements,
                        'camera_counts':{'TP':camera_tp,'FP':camera_fp,'FN':camera_fn},'schema_errors':validation,'integrity_errors':integrity_errors})
        if exclusion is None and (eligible or dataset_kind=='SYNTHETIC'):
            norm={k:v for k,v in request.items() if k!='origin'}
            origin_groups.setdefault(sha(canonical({'request':norm,'query_binding':binding})),[]).append((request['origin'],actual['output_sha256'] if actual else None))
            for k,v in measurements.items():totals[k]+=int(v)
            totals['camera_tp']+=camera_tp;totals['camera_fp']+=camera_fp;totals['camera_fn']+=camera_fn
            group=groups.setdefault(category,{'count':0,'correct':{k:0 for k in measurements}});group['count']+=1
            for k,v in measurements.items():group['correct'][k]+=int(v)
    n=sum(d['eligible_for_formal_metrics'] for d in details)
    measured_n=sum(d['scoring_exclusion_reason'] is None for d in details) if dataset_kind=='SYNTHETIC' else n
    origin_pairs=[v for v in origin_groups.values() if len({x[0] for x in v})>1]
    invariant=sum(all(x[1] is not None for x in values) and len({x[1] for x in values})==1 for values in origin_pairs)
    report={'schema_version':'q1-query-eval-report.v1','scorer_version':VERSION,'schema_kit_sha':KIT_SHA,
            'v2_schema_source_commit':V2_SCHEMA_SOURCE,
            'cases_sha256':cases_sha256,'predictions_sha256':predictions_sha256,'dataset_authority_sha256':authority_sha256,
            'evaluation_eligible':evaluation_eligible,'status':'MEASURED' if n else 'NO_FORMAL_CASES',
            'dataset_kind':dataset_kind,
            'case_count':len(cases),'valid_case_count':len(details),'formal_case_count':n,'invalid_cases':invalid,
            'unscored_default_run_ids':[d['id'] for d in details if d['scoring_exclusion_reason']=='DEFAULT_SELECTED_RUN'],
            'synthetic_case_count':measured_n if dataset_kind=='SYNTHETIC' else 0,
            'unspecified_category_count':sum(d['category']=='UNSPECIFIED' for d in details),
            'missing_prediction_ids':sorted(set(by_id)-set(preds)),'extra_prediction_ids':sorted(set(preds)-set(by_id)),
            'metrics':{k:metric(totals[k] if evaluation_eligible else 0,n) for k in ['status','reason','segments','coverage','order','none_categories','schema','present','hash','request_binding']},
            'camera_micro_precision':metric(totals['camera_tp'],totals['camera_tp']+totals['camera_fp']) if evaluation_eligible else metric(0,0),
            'camera_micro_recall':metric(totals['camera_tp'],totals['camera_tp']+totals['camera_fn']) if evaluation_eligible else metric(0,0),
            'origin_invariance':metric(invariant,len(origin_pairs)) if evaluation_eligible else metric(0,0),
            'by_category':{k:{'count':g['count'],'metrics':{m:metric(v,g['count']) for m,v in g['correct'].items()}} for k,g in sorted(groups.items())} if evaluation_eligible else {},
            'synthetic_metrics':({**{k:metric(totals[k],measured_n) for k in ['status','reason','segments','coverage','order','none_categories','schema','present','hash','request_binding']},
                                 'camera_micro_precision':metric(totals['camera_tp'],totals['camera_tp']+totals['camera_fp']),
                                 'camera_micro_recall':metric(totals['camera_tp'],totals['camera_tp']+totals['camera_fn']),
                                 'origin_invariance':metric(invariant,len(origin_pairs))} if dataset_kind=='SYNTHETIC' else None),
            'details':details,'acceptance_threshold':None,
            'limits':['Expected core is a schema projection; predictions use the full frozen response schema.',
                      'Invalid/missing human expected annotations never become model errors or fabricated answers.',
                      'PILOT and SYNTHETIC cases excluded from all formal metric denominators; no dataset-size acceptance claim.',
                      'query_binding must be frozen by the evaluation owner from trusted request context; the scorer never derives it from the prediction.',
                      'Request conditions must already use canonical frozen labels; alias normalization is not performed by the scorer.']}
    report['output_sha256']=sha(canonical(report));return report
