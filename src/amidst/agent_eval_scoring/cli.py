"""Subprocess CLI for Agent evaluation scoring (WP4, Gate 4).

Contract: docs/contracts/AGENT_EVAL_TOOLCHAIN_GATES_V1.md §5.
Usage:
    python -m amidst.agent_eval_scoring.cli --questions Q.jsonl --decisions D.jsonl \\
        --candidate-observations O.json --gt-fixture G.json --params P.json --out DIR
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys

from amidst.agent_eval_scoring import mapping, metrics

DP1_NAMES = ('DP1', 'DP1_HANDOFF_ADJUDICATION')
DP3_NAMES = ('DP3', 'DP3_CONTINUATION_ACCEPTANCE')


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def _build_gt_source(gt_fixture: Mapping):
    index: dict[tuple[str, int], dict[str, list[float]]] = {}
    actors: set[str] = set()
    target = str(gt_fixture['target'])
    actors.add(target)
    for frame in gt_fixture.get('frames', []):
        cam = str(frame['camera_id'])
        ts = int(frame['timestamp_us'])
        boxes = {str(k): [float(x) for x in v] for k, v in frame.get('boxes', {}).items()}
        actors.update(boxes.keys())
        index[(cam, ts)] = boxes

    def gt_source(camera_id: str, timestamp_us: int) -> dict[str, list[float]]:
        return dict(index.get((str(camera_id), int(timestamp_us)), {}))

    return gt_source, target, actors


def _score_dp1_question(
    sha: str,
    obs_entry: Mapping,
    gt_source,
    target_actor: str,
    params: Mapping,
    decision_answer: str | None,
) -> bool | None:
    cand_obs_map = obs_entry.get('candidates', {})
    if not cand_obs_map:
        return None
    iou_match = float(params.get('iou_match', 0.5))
    iou_manual_low = float(params.get('iou_manual_low', 0.3))
    majority_fraction = float(params.get('majority_fraction', 0.6))

    mapped: dict[str, dict] = {}
    for cid, obs_list in sorted(cand_obs_map.items()):
        res = mapping.map_track_to_actor(
            obs_list,
            gt_source,
            iou_match=iou_match,
            iou_manual_low=iou_manual_low,
            majority_fraction=majority_fraction,
        )
        if res['needs_manual']:
            return None
        mapped[str(cid)] = res

    gold_ids = {cid for cid, m in mapped.items() if m['actor'] == target_actor}
    if not gold_ids:
        gold_ids = {'ABSTAIN'}
    if decision_answer is None:
        return False
    return bool(decision_answer in gold_ids)


def _score_dp3_question(
    obs_entry: Mapping,
    gt_source,
    target_actor: str,
    params: Mapping,
    decision_answer: str | None,
) -> bool | None:
    seg_obs: Sequence[Mapping] = obs_entry.get('segment', [])
    if not seg_obs:
        return None
    iou_match = float(params.get('iou_match', 0.5))
    iou_manual_low = float(params.get('iou_manual_low', 0.3))
    target_thresh = float(params.get('dp3_target_frame_fraction', 0.5))

    target_hits = 0
    for obs in seg_obs:
        gt_boxes = gt_source(str(obs['camera_id']), int(obs['timestamp_us']))
        best_actor = None
        best_val = -1.0
        for actor_name, gt_box in sorted(gt_boxes.items()):
            val = mapping.iou(obs['box'], gt_box)
            if val > best_val:
                best_val = val
                best_actor = actor_name
        if best_actor is not None and iou_manual_low <= best_val < iou_match:
            return None
        if best_actor == target_actor and best_val >= iou_match:
            target_hits += 1

    gold = 'ACCEPT_SEGMENT' if (target_hits / len(seg_obs)) >= target_thresh else 'REJECT_SEGMENT'
    if decision_answer is None:
        return False
    return bool(decision_answer == gold)


def _assert_no_actor_leak(text: str, actors: set[str]) -> None:
    for actor in actors:
        if actor and actor in text:
            raise ValueError('actor identifier leaked into scoring output')


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Score Agent decisions against GT fixture in an isolated process.')
    parser.add_argument('--questions', required=True, type=Path)
    parser.add_argument('--decisions', required=True, type=Path)
    parser.add_argument('--candidate-observations', required=True, type=Path)
    parser.add_argument('--gt-fixture', required=True, type=Path)
    parser.add_argument('--params', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)

    questions = _load_jsonl(args.questions)
    decisions_rows = _load_jsonl(args.decisions)
    observations = json.loads(args.candidate_observations.read_text(encoding='utf-8'))
    gt_fixture = json.loads(args.gt_fixture.read_text(encoding='utf-8'))
    params = json.loads(args.params.read_text(encoding='utf-8'))

    decisions_by_sha = {
        str(d['request_sha256']): str(d.get('answer', d.get('final_answer', '')))
        for d in decisions_rows
    }
    gt_source, target_actor, all_actors = _build_gt_source(gt_fixture)

    per_question_out: list[dict] = []
    by_dp: dict[str, list[bool]] = {}
    n_scored = 0
    n_needs_manual = 0

    for q in questions:
        sha = str(q['request_sha256'])
        raw_dp = str(q.get('decision_point') or q.get('request', {}).get('decision_point', 'DP1'))
        short_dp = 'DP1' if raw_dp in DP1_NAMES else ('DP3' if raw_dp in DP3_NAMES else raw_dp)
        obs_entry = observations.get(sha, {})
        ans = decisions_by_sha.get(sha)

        if short_dp == 'DP1':
            correct = _score_dp1_question(sha, obs_entry, gt_source, target_actor, params, ans)
        else:
            correct = _score_dp3_question(obs_entry, gt_source, target_actor, params, ans)

        per_question_out.append({'request_sha256': sha, 'correct': correct})
        if correct is None:
            n_needs_manual += 1
        else:
            n_scored += 1
            by_dp.setdefault(short_dp, []).append(bool(correct))

    acc_dp = {
        dp_key: float(sum(1 for c in vals if c) / len(vals))
        for dp_key, vals in sorted(by_dp.items())
        if vals
    }
    if 'DP1' not in acc_dp:
        acc_dp['DP1'] = 0.0

    summary = {
        'Acc_dp': acc_dp,
        'n_scored': n_scored,
        'n_total': len(questions),
        'n_needs_manual': n_needs_manual,
        'params_status': str(params.get('status', 'PROPOSED')),
        'sample_sufficiency': 'INSUFFICIENT' if n_scored < 20 else 'SUFFICIENT',
    }

    args.out.mkdir(parents=True, exist_ok=True)
    pq_bytes = b''.join(metrics.canonical_bytes(r) + b'\n' for r in per_question_out)
    m_bytes = metrics.canonical_bytes(summary) + b'\n'

    _assert_no_actor_leak(pq_bytes.decode('utf-8'), all_actors)
    _assert_no_actor_leak(m_bytes.decode('utf-8'), all_actors)

    (args.out / 'per_question.jsonl').write_bytes(pq_bytes)
    (args.out / 'metrics.json').write_bytes(m_bytes)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
