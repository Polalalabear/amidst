"""Versioned decoding guidance only. Existing task validators remain authoritative.

No images, GT, evaluation labels or inferred candidates; all refs come from the
current server context and previously returned evidence.
"""
from copy import deepcopy

Q3_MARKER='版本 q3-parse.v2。'
Q5_MARKER='Q5 sequential camera decision. Version q5-agent-v2.'

def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}

def const(value):return {'const':value}

def q3_schema(catalog=None,text=None):
    literal={'type':['string','null'],'minLength':1}
    terms={'type':'array','items':{'type':'string','minLength':1}}
    schema = obj({'schema_version':const('q-demo.q3-llm-output.v1'),
        'intent':{'enum':['FIND_CAMERAS','FIND_PERSON','EXPLAIN','UNSUPPORTED']},
        'class_term':deepcopy(literal),'color_term':deepcopy(literal),
        'time_literal':obj({k:deepcopy(literal) for k in ['start','end','date']}),
        'camera_terms':deepcopy(terms),'region_terms':deepcopy(terms),
        'needs_clarification':{'type':'boolean'},'clarification_question':deepcopy(literal)})
    if catalog is not None and text is not None:
        import re
        def matches_in_text(aliases):
            return sorted({m.group() for alias in aliases for m in re.finditer(re.escape(alias),text,re.I)})
        # Lexical grounding, not human answers: use the same versioned token
        # patterns and closed aliases already available to the runtime parser.
        from amidst.q1q5.q3_rules import DATE_PATTERN, TIME_PATTERN
        props=schema['properties']
        for field,aliases in [('class_term','class_aliases'),('color_term','color_aliases')]:
            if aliases in catalog:
                matches=matches_in_text(catalog[aliases])
                if matches:props[field]={'enum':matches}
                elif field=='color_term':props[field]=const(None)
        for field,aliases in [('camera_terms','camera_aliases'),('region_terms','region_aliases')]:
            if aliases in catalog:
                matches=matches_in_text(catalog[aliases])
                props[field]={'type':'array','items':{'enum':matches},'minItems':1} if matches else {'type':'array','maxItems':0}
        times=sorted({m.group() for m in TIME_PATTERN.finditer(text)})
        dates=sorted({m.group() for m in DATE_PATTERN.finditer(text)})
        for field,values in [('start',times),('end',times),('date',dates)]:
            props['time_literal']['properties'][field]={'enum':[None,*values]} if values else const(None)
    return schema

def workflow(context,fetched,history):
    rank=context['next_candidate_rank'];current=next((x for x in context['candidates'] if x['rank']==rank),None)
    evidence=fetched.get(current['candidate_ref']) if current else None
    refs=[]
    if evidence:
        refs=[x['observation_id'] for x in evidence['best_observations']]
        if evidence['entry_observation_id'] is not None:refs.append(evidence['entry_observation_id'])
        if not refs:refs.append(evidence['evidence_sha256'])
    actions=['RETURN_TO_ORIGIN']
    if evidence and refs:
        actions.append('NEXT_CANDIDATE')
        if evidence['target_presence']=='MATCH_STRONG' and evidence['entry_observation_id'] is not None:actions.append('SWITCH')
    return {'phase':'RETURN_TO_ORIGIN' if current is None else 'SUBMIT_DECISION' if evidence else 'FETCH_CANDIDATE_EVIDENCE',
        'current_candidate_ref':current['candidate_ref'] if current else None,
        'allowed_next_outputs':actions+(['get_candidate_evidence'] if current and not evidence else []),
        'candidate_citation_refs':sorted(set(refs)),
        'completed_tools':sorted({'get_search_context',*[x['tool'] for x in history]}),
        'context_already_contains_last_observation':True,
        'guidance_only_guards_unchanged':True}

def q5_schema(payload):
    c=payload['context'];w=payload['workflow'];branches=[]
    base={'schema_version':const('q-demo.agent-decision.v1'),'session_id':const(c['session_id']),
          'decision_id':const(c['decision_id']),'candidate_snapshot_sha256':const(c['candidate_snapshot_sha256'])}
    for action in w['allowed_next_outputs']:
        if action=='get_candidate_evidence':
            branches.append(obj({'tool':const(action),'arguments':obj({'session_id':const(c['session_id']),
                'decision_id':const(c['decision_id']),'candidate_ref':const(w['current_candidate_ref'])})}))
        else:
            refs=w['candidate_citation_refs']
            if action not in {'RETURN_TO_ORIGIN','NEXT_CANDIDATE','SWITCH'}:raise ValueError('Unsupported guidance action')
            citations={'type':'array','maxItems':0} if action=='RETURN_TO_ORIGIN' else {'type':'array','items':{'enum':refs},'minItems':1,'maxItems':1}
            branches.append(obj({**base,'action':const(action),'candidate_ref':const(None if action=='RETURN_TO_ORIGIN' else w['current_candidate_ref']),
                'cited_observation_ids':citations,'rationale':const({'RETURN_TO_ORIGIN':'Stop without a cut.','NEXT_CANDIDATE':'Continue to next candidate.','SWITCH':'Strong observed evidence.'}[action])}))
    if not branches:raise ValueError('No guided output branch')
    return branches[0] if len(branches)==1 else {'anyOf':branches}
