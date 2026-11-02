"""Q3 evaluator for human annotations, frozen predictions and explicit clocks.

--schemas is readonly #127 994d34c src/amidst/contracts/q_demo; --clocks is
{schema_version:q-demo.eval-clock-catalog.v1,mappings:[clock-mapping.v1 documents]}.
Literal metrics need an optional llm_output beside response in id-wrapper mode.
"""
import argparse
from pathlib import Path
from amidst.evaluation.q1_query_eval import (
    EvaluationError,PinnedSchemas,canonical,decode,rows,sha,dataset_eligibility,
)
from amidst.evaluation.q3_parse_eval import clock_catalog,prediction_rows,evaluate


def pinned(path,pin):
    raw=Path(path).read_bytes()
    if sha(raw)!=pin:raise EvaluationError('Input file pin mismatch')
    return raw


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['queries','queries-sha256','predictions','predictions-sha256','clocks','clocks-sha256',
                 'dataset-receipt','dataset-receipt-sha256','schemas','output']:
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--prediction-layout',choices=['id-wrapper','dataset-order'],required=True)
    a=parser.parse_args(argv)
    try:
        cases=rows(pinned(a.queries,a.queries_sha256));preds=rows(pinned(a.predictions,a.predictions_sha256))
        preds=prediction_rows(cases,preds,a.prediction_layout)
        receipt=decode(pinned(a.dataset_receipt,a.dataset_receipt_sha256))
        eligible=dataset_eligibility(receipt,cases_sha256=a.queries_sha256,filename='queries_v1.jsonl')
        clocks=clock_catalog(decode(pinned(a.clocks,a.clocks_sha256)))
        report=evaluate(cases,preds,cases_sha256=a.queries_sha256,predictions_sha256=a.predictions_sha256,
                        schemas=PinnedSchemas(a.schemas),clocks=clocks,clocks_sha256=a.clocks_sha256,
                        evaluation_eligible=eligible,authority_sha256=a.dataset_receipt_sha256)
        with Path(a.output).open('xb') as stream:stream.write(canonical(report)+b'\n')
    except (EvaluationError,OSError,ValueError,TypeError,KeyError) as exc:parser.exit(2,str(exc)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
