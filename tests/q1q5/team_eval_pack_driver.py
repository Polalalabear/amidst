"""TEST-ONLY mapping to native #293 builder/verifier; never simulates a result."""
import hashlib
import json
from pathlib import Path


def exercise(operation, *, implementation, **kwargs):
    profile = kwargs.get('test_profile')
    if operation == 'build':
        result = implementation.build_from_inputs(kwargs['inputs'], kwargs['output'], profile=profile)
        halves = result['manifest']['halves']
        result.update(entrypoint='tools/team_eval.py', entry_args=['--profile', profile,
                      '--manifest-sha256', result['manifest_sha256']], return_path=implementation.RETURN,
                      replayed_files={half.upper(): f'RETURN/outputs/{half}.json' for half in halves},
                      optional_template=implementation.TEMPLATE, immutable_probe_file='payload/baseline.json',
                      readme='README.txt')
    elif operation == 'verify':
        result = implementation.verify_pack(kwargs['root'], kwargs['manifest_sha256'], profile=profile)
    elif operation == 'validate_return':
        result = implementation.validate_return(kwargs['root'], kwargs['returned'], kwargs['manifest_sha256'], profile=profile)
    elif operation in {'return_missing_field', 'validate_unselected_return'}:
        doc = json.loads(Path(kwargs['example']).read_bytes())
        doc.setdefault('halves', ['baseline', 'complex'])
        if operation == 'return_missing_field':
            doc.pop(kwargs['missing_field'])
        result = implementation.validate_return_document(doc, manifest_sha256='0' * 64,
                    halves=['baseline', 'complex'], profile=profile)
    else:
        raise ValueError(operation)
    return {**result, 'implementation_file_sha256': hashlib.sha256(Path(implementation.__file__).read_bytes()).hexdigest(),
            'human_approval_verified': False}
