"""Q1 scorer: human expected cores + frozen predictions; no answer generation.

Use --schemas with the readonly #127 994d34c src/amidst/contracts/q_demo directory.
--dataset-receipt is the #147 import receipt, or a SYNTHETIC-only dataset record.
Only a verified v1 importer receipt is FORMAL. SYNTHETIC/PILOT never contribute
to formal denominators. Each case needs evaluation-owner-frozen query_binding:
{request_sha256, query_sha256}; the request pin excludes origin. Capture this
from trusted request context, never infer it from the prediction being scored.
Conditions must already use canonical frozen labels. Missing context is INVALID.
"""
import argparse
from pathlib import Path

from amidst.evaluation.q1_query_eval import (
    EvaluationError,
    PinnedSchemas,
    canonical,
    dataset_eligibility,
    dataset_kind_from_receipt,
    decode,
    evaluate,
    rows,
    sha,
)


def pinned(path,pin):
    raw=Path(path).read_bytes()
    if sha(raw)!=pin:raise EvaluationError('Input file pin mismatch')
    return raw


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['cases','cases-sha256','predictions','predictions-sha256','dataset-receipt','dataset-receipt-sha256','schemas','output']:
        parser.add_argument('--'+name,required=True)
    a=parser.parse_args(argv)
    try:
        cases=rows(pinned(a.cases,a.cases_sha256));preds=rows(pinned(a.predictions,a.predictions_sha256))
        receipt=decode(pinned(a.dataset_receipt,a.dataset_receipt_sha256))
        eligible=dataset_eligibility(receipt,cases_sha256=a.cases_sha256,filename='cases_v1.jsonl')
        report=evaluate(cases,preds,cases_sha256=a.cases_sha256,predictions_sha256=a.predictions_sha256,
                        schemas=PinnedSchemas(a.schemas),evaluation_eligible=eligible,authority_sha256=a.dataset_receipt_sha256,
                        dataset_kind=dataset_kind_from_receipt(receipt))
        with Path(a.output).open('xb') as stream:stream.write(canonical(report)+b'\n')
    except (EvaluationError,OSError,ValueError,TypeError,KeyError) as exc:parser.exit(2,str(exc)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
