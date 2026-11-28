"""E8 Mac scoring, one command (#780; design E8_DESIGN_V1.md §6.4). Final numbers; reads GT on the Mac only.

  python scripts/evaluation/e8_score_run.py --run <e8-run-*.zip | dir> --pack <e8-colab-pack dir> --mac-index <mac_index.json> --out <dir>

Part 1: GT regime per decision point (TRUE_DEPARTURE / FULL_BLIND / VISIBLE from the a-log; E6 cross-checked with the frozen
gt_regime), OWN_BOX answers judged with e3_scoring.judge_box, then e8_score.summary (H1, S1, S2, selection, position bias).
Part 2: every closed-loop b-log (and the frozen B1) through e3_f4_score.run_scores (pinned scorer acacce39...), E6-style segment
and decision-point rows (e6_verdict_run.window_ticks + full_track_dp_correct), H2 / S3 / S4, early switch.
Writes E8_RESULTS_<date>.json / .md and unified_e8_section.json; ``--unified`` also runs generate_unified_analysis + build_figures.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_e7_colab_pack as E7  # noqa: E402
import e3_f4_score as F4  # noqa: E402
from e6_verdict_run import window_ticks  # noqa: E402

from amidst.evaluation import e6_verdict as V  # noqa: E402
from amidst.evaluation import e8_score as S8  # noqa: E402
from amidst.evaluation.e3_scoring import judge_box  # noqa: E402

TICK_US = 200_000
SCORER = ROOT / 'src' / 'amidst' / 'evaluation' / 'e3_scoring.py'
MODEL_GROUP = re.compile(r'^B1\+([a-z0-9_]+)@(L\w+)$')     # zero-latency model groups (MEASURED ends in '+MEASURED')
EXIT_SELECTED_GROUP_MISSING = 3


def part2_hypotheses(group: str, segments: list[dict], points: list[dict], classes: dict, dps: list[dict], regime_of: dict,
                     family_of_case: dict) -> dict:
    """H2 / S3 / S4 for one Part-2 group against B1 (rows relabelled SELECTED, as e8_score expects)."""
    rows = [dict(r, group='SELECTED') for r in segments if r['group'] == group] + [r for r in segments if r['group'] == 'B1']
    pts = [dict(p, group='SELECTED') for p in points if p['group'] == group] + [p for p in points if p['group'] == 'B1']
    items = [(family_of_case[d['case_id']], S8.early_switch_s(classes[group][d['case_id']], classes['B1'][d['case_id']], d['tick']))
             for d in dps if regime_of[d['base_id']] == 'VISIBLE']
    return {'H2': S8.h2_test(rows, pts), 'S3': S8.s3_test(rows), 'S4': S8.s4_test(items)}


def missing_selected(sel: dict | None, groups) -> list[dict]:
    """O2 (#785, option A): the Mac-selected (model, level) must have Part-2 results; list what is missing."""
    if not sel:
        return []
    base = f"B1+{sel['model']}@{sel['level']}"
    return [{'model': sel['model'], 'level': sel['level'], 'latency': lat, 'group': g}
            for lat, g in (('ZERO_LATENCY', base), ('MEASURED', base + '+MEASURED')) if g not in groups]


def rerun_hint(missing: list[dict]) -> str:
    """Colab re-run for the missing group: notebook and pin unchanged; one override cell between cells 7 and 8."""
    if not missing:
        return ''
    m, lv = missing[0]['model'], missing[0]['level']
    return (f'In Cell 1 set RUN_MODELS = ["{m}"] and RUN_PART2 = True; insert after Cell 7: '
            f'SELECTION["per_model"]["{m}"] = {{"level": "{lv}"}}; SELECTION["selected"] = {{"model": "{m}", "level": "{lv}"}}; '
            'then Run All (finished groups resume from checkpoints) and score the new e8-run zip.')


def load_checkpoints(run: Path) -> tuple[list[dict], dict[str, dict]]:
    """-> (part-1 records, {group: part-2 result}) from the packaged run's checkpoints/ folder."""
    cps = next((p for p in [run / 'checkpoints', *run.glob('*/checkpoints')] if p.is_dir()), None)
    if cps is None:
        raise SystemExit(f'NO_CHECKPOINTS in {run}')
    recs, part2 = [], {}
    for f in sorted(cps.glob('*.json')):
        doc = json.loads(f.read_text())
        res = doc['result']
        if doc['mode'].startswith('part2_'):
            part2[f"{res['group']}|{res['latency']}"] = res
        else:
            recs += res['records']
    return recs, part2


def gt_actors(gt_root: Path, cid: str) -> tuple[dict, dict]:
    raw = (Path(gt_root) / 'gt-boxes' / f'{cid}.a-log.json').read_bytes()
    doc = json.loads(raw)
    return doc, {t['tick']: next((a for a in t['actors'] if a['id'] == doc['actor_id']), None) for t in doc['ticks']}


def own_box_hits(records: list[dict], actors_by_case: dict) -> dict:
    out = {}
    for r in records:
        d = r['display']
        if d['kind'] != 'NEEDS_MAC':
            continue
        a = actors_by_case[r['case_id']].get(int(r['base_id'].rsplit('|t', 1)[1]))
        body = ((a or {}).get('gt_boxes') or {}).get(d.get('camera_id'))
        vis = d.get('camera_id') in ((a or {}).get('gt_visible') or [])
        out[r['request_id']] = bool(vis and body and d.get('box_xyxy') and judge_box(d['box_xyxy'], body, E7.SIZE)['primary'])
    return out


def score(run: Path, pack: Path, mac_index: Path) -> dict:
    idx = json.loads(mac_index.read_text())
    reqs = [json.loads(x) for x in (pack / 'requests' / 'e8_part1.jsonl').read_text().splitlines() if x.strip()]
    table = json.loads((pack / 'scoring_only' / 'answer_table.json').read_text())
    cases = json.loads((pack / 'part2' / 'cases.json').read_text())
    records, part2 = load_checkpoints(run)
    dps = idx['decision_points']
    family_of = {d['base_id']: d['family'] for d in dps}
    alogs, actors = {}, {}
    for cid, root in idx['gt_roots'].items():
        alogs[cid], actors[cid] = gt_actors(Path(root), cid)
    regime_of, regime_mismatch = {}, []
    for d in dps:
        reg = S8.regime_from_gt(actors[d['case_id']].get(d['tick']))
        if d.get('gt_regime_frozen') and d['gt_regime_frozen'] != reg:
            regime_mismatch.append({'base_id': d['base_id'], 'frozen': d['gt_regime_frozen'], 'a_log': reg})
            reg = d['gt_regime_frozen']          # E6 frozen spec is authoritative (E6 verdict convention)
        regime_of[d['base_id']] = reg

    # ---------------- Part 2
    Sc = F4.load_scorer(SCORER)
    dps_by_case = defaultdict(list)
    for d in dps:
        dps_by_case[d['case_id']].append(d)
    groups = {'B1': {cid: json.loads((pack / m['b1_frozen']).read_text()) for cid, m in cases.items()}}
    for key, res in part2.items():
        groups[key.replace('|ZERO_LATENCY', '').replace('|MEASURED', '')] = res['blogs']
    segments, points, per_group, classes = [], [], {}, defaultdict(dict)
    for g, blogs in groups.items():
        tot = defaultdict(float)
        for cid, doc in blogs.items():
            case = {'case_id': cid, 'decision_points': [{'tick': d['tick'], 'type': d['type'], 'timestamp_us': d['tick'] * TICK_US,
                                                         'evaluation_window_us': [d['tick'] * TICK_US, (d['tick'] + 15) * TICK_US]}
                                                        for d in dps_by_case[cid]]}
            sc = F4.run_scores(Sc, case, alogs[cid], doc)
            pr = sc['primary']
            classes[g][cid] = sc['classes']
            fam = cases[cid]['family']
            segments.append({'case_id': cid, 'family_id': fam, 'group': g, 'wrong_person_s': pr['wrong_person_s'],
                             'blind_false_lock_s': pr['false_lock_s'], 'lost_s': pr['lost_s'], 'follow_rate': pr['follow_rate'],
                             'visible_ticks': pr['visible_ticks']})
            for k in ('wrong_person_s', 'wrong_person_only_s', 'wrong_camera_s', 'lost_s', 'false_lock_s', 'visible_ticks'):
                tot[k] += pr[k] or 0
            tot['follow_num'] += (pr['follow_rate'] or 0) * pr['visible_ticks']
            for d in dps_by_case[cid]:
                ok = V.full_track_dp_correct(regime_of[d['base_id']], window_ticks(sc['classes'], d['tick']))
                points.append({'base_id': d['base_id'], 'case_id': cid, 'family_id': fam, 'group': g, 'full_track_correct': ok})
                tot['dp_correct'] += ok
            tot['asks'] += len((doc.get('e8') or {}).get('log') or [])
        tot['follow_rate'] = tot.pop('follow_num') / tot['visible_ticks'] if tot['visible_ticks'] else None
        tot['dp_n'] = len(dps)
        per_group[g] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in tot.items()}

    # ---------------- Part 1 + selection -> SELECTED
    pre = S8.summary(records, reqs, table, regime_of, family_of, own_box=own_box_hits(records, actors))
    sel = pre['selection'].get('selected')
    h2 = s3 = s4 = None
    fam_case = {cid: m['family'] for cid, m in cases.items()}
    sel_group = f"B1+{sel['model']}@{sel['level']}" if sel else None
    missing = missing_selected(sel, groups)
    if sel_group in groups:
        hyp = part2_hypotheses(sel_group, segments, points, classes, dps, regime_of, fam_case)
        h2, s3, s4 = hyp['H2'], hyp['S3'], hyp['S4']
    early = {}
    for g in groups:
        if g != 'B1':
            vals = sorted(S8.early_switch_s(classes[g][d['case_id']], classes['B1'][d['case_id']], d['tick'])
                          for d in dps if regime_of[d['base_id']] == 'VISIBLE')
            early[g] = {'n': len(vals), 'median_s': vals[len(vals) // 2] if vals else None, 'values': vals}
    # O3 (#785): every zero-latency model group, reported as sensitivity only (uncorrected; not used by the conclusion)
    sensitivity = {g: {'model': MODEL_GROUP.match(g).group(1), 'level': MODEL_GROUP.match(g).group(2), 'is_selected': g == sel_group,
                       'role': 'SENSITIVITY_NOT_IN_CONCLUSION', 'metrics': per_group[g],
                       **part2_hypotheses(g, segments, points, classes, dps, regime_of, fam_case)}
                   for g in sorted(groups) if MODEL_GROUP.match(g)}
    p1 = S8.summary(records, reqs, table, regime_of, family_of, own_box=own_box_hits(records, actors), h2=h2, s3=s3, s4=s4)
    first = {k: v for k, v in p1['position_bias']['first_option_rate'].items() if k.split('|')[1] in ('L2', 'L3')}
    results = {'schema': 'e8_results_v1', 'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'scorer_sha256': F4.SCORER_SHA, 'mac_index_sha256': hashlib.sha256(mac_index.read_bytes()).hexdigest(),
               'answer_table_sha256': hashlib.sha256((pack / 'scoring_only' / 'answer_table.json').read_bytes()).hexdigest(),
               'regime_counts': p1['regimes'], 'regime_mismatch_e6': regime_mismatch, 'part1': p1,
               'part2': {'per_group': per_group, 'selected_group': sel_group, 'H2': h2, 'S3': s3, 'S4': s4, 'early_switch_s': early,
                         'sensitivity_model_groups': sensitivity, 'decision_points': points},
               'limitations': LIMITATIONS, 'identity_status': 'UNCONFIRMED'}
    results['conclusion'] = S8.conclusion(p1['primary'], p1['secondary'], union_answerable=p1['union_answerable'], first_option=first)
    if any(m['latency'] == 'ZERO_LATENCY' for m in missing):
        results.update(status='SELECTED_GROUP_MISSING', conclusion='SELECTED_GROUP_MISSING', selected_group_missing=missing,
                       rerun_hint=rerun_hint(missing))
    else:
        results['status'] = 'OK'
        if missing:
            results['selected_group_missing'] = missing      # MEASURED only: exploratory, the conclusion does not use it
    return results


LIMITATIONS = [
    'Part 2 groups are chosen from tentative Part-1 scores on Colab (label table only; O1, D417 trade-off); the Mac re-selects with '
    'GT regimes and stops with SELECTED_GROUP_MISSING if that group was not run.',
    'SELECTED is chosen from Part-1 accuracy on the same decision points that Part 2 tests, which biases it towards passing H2 '
    '(selection bias, O3); all model groups are reported as uncorrected sensitivity, and only SELECTED enters the conclusion.',
    'A merged option shows the detector score of its representative member (the tallest box, design §2.4), which can be lower '
    'than another member\'s score in a different camera; it is not a low-confidence signal about the person (N1).',
]


def render_md(r: dict) -> str:
    p1, p2 = r['part1'], r['part2']
    out = ['# E8 results', '']
    if r.get('status') == 'SELECTED_GROUP_MISSING':
        out += ['> **SELECTED_GROUP_MISSING** — the Mac-selected group has no Part-2 results, so H2 / S3 / S4 and the conclusion are '
                'not available. Missing: ' + ', '.join(f"{m['model']} @ {m['level']} ({m['latency']})" for m in r['selected_group_missing']),
                f"> Re-run: {r['rerun_hint']}", '']
    out += [f"- conclusion: **{r['conclusion']}** (design §5.5)", f"- regimes: {r['regime_counts']}",
           f"- selected (Part 2 primary): {p2['selected_group']}", '', '## Part 1 accuracy (majority over 3 orders)', '',
           '| group / level | majority | mean | n | needs_mac |', '| --- | ---: | ---: | ---: | ---: |']
    for k, v in p1['accuracy'].items():
        out.append(f"| {k} | {v['majority_acc']} | {v['mean_acc']} | {v['n']} | {v['needs_mac']} |")
    out += ['', '## Hypotheses', '', '| id | status | diff | p | p_holm | M | n_dp |', '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for k, v in {**p1['primary'], **p1['secondary']}.items():
        if isinstance(v, dict):
            out.append(f"| {k} | {v.get('status')} | {v.get('diff')} | {v.get('p')} | {v.get('p_holm')} | {v.get('M')} | {v.get('n_dp')} |")
    out += ['', '## Part 2 (closed loop, totals over all segments)', '',
            '| group | follow | wrong person s | of which wrong camera s | lost s | false lock s | dp correct / n | asks |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for g, v in p2['per_group'].items():
        out.append(f"| {g} | {v.get('follow_rate')} | {v.get('wrong_person_s')} | {v.get('wrong_camera_s')} | {v.get('lost_s')} | "
                   f"{v.get('false_lock_s')} | {int(v.get('dp_correct', 0))} / {v.get('dp_n')} | {int(v.get('asks', 0))} |")
    out += ['', '## Part 2 sensitivity: every model group vs B1 (uncorrected; not in the conclusion)', '',
            '| group | selected | follow | wrong person s | H2 p | S3 p | S4 median s |', '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for g, v in (p2.get('sensitivity_model_groups') or {}).items():
        out.append(f"| {g} | {'yes' if v['is_selected'] else ''} | {v['metrics'].get('follow_rate')} | {v['metrics'].get('wrong_person_s')} | "
                   f"{(v['H2'] or {}).get('p')} | {(v['S3'] or {}).get('p')} | {(v['S4'] or {}).get('median')} |")
    out += ['', '## Limitations', ''] + [f'- {x}' for x in r.get('limitations', [])]
    out += ['', 'Identity stays UNCONFIRMED.', '']
    return '\n'.join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', type=Path, required=True, help='e8-run-<date>.zip or its extracted folder')
    ap.add_argument('--pack', type=Path, required=True)
    ap.add_argument('--mac-index', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--unified', action='store_true', help='also write unified_analysis.json (e8 section) and the report figures')
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        run = a.run
        if run.suffix == '.zip':
            with zipfile.ZipFile(run) as zf:
                zf.extractall(tmp)
            run = Path(tmp)
        res = score(run, a.pack, a.mac_index)
    a.out.mkdir(parents=True, exist_ok=True)
    tag = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')
    (a.out / f'E8_RESULTS_{tag}.json').write_text(json.dumps(res, indent=1, sort_keys=True, allow_nan=False, default=str) + '\n')
    (a.out / f'E8_RESULTS_{tag}.md').write_text(render_md(res))
    sec = S8.unified_section(res)
    (a.out / 'unified_e8_section.json').write_text(json.dumps(sec, indent=1, sort_keys=True) + '\n')
    if a.unified:
        import generate_unified_analysis as GU
        sys.path.insert(0, str(ROOT / 'report' / 'figures'))
        import build_figures as BF
        GU.main(['--e8-results', str(a.out / 'unified_e8_section.json'), '--out-dir', str(a.out / 'unified'), '--no-charts',
                 '--platform', 'Mac'])
        BF.build_all_figures(a.out / 'unified' / 'unified_analysis.json', a.out / 'figures')
    print(json.dumps({'conclusion': res['conclusion'], 'selected': res['part2']['selected_group'],
                      'primary': {k: v.get('status') for k, v in res['part1']['primary'].items() if isinstance(v, dict)}}, indent=1))
    if res.get('status') == 'SELECTED_GROUP_MISSING':
        print(f"SELECTED_GROUP_MISSING: {res['selected_group_missing']}\n{res['rerun_hint']}", file=sys.stderr)
        return EXIT_SELECTED_GROUP_MISSING
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
