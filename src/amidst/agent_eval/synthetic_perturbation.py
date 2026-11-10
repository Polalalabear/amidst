"""S2 synthetic track-level perturbation generator (WP4, Gate 3).

Contract: docs/contracts/AGENT_EVAL_TOOLCHAIN_GATES_V1.md §2.
Design: docs/design/AGENT_DECISION_V1.md §4.3; D203 (episodes & >=8 clusters).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
import importlib
import json
from pathlib import Path
import random

from amidst.agent_eval import question_bank as qb

ad = importlib.import_module('amidst.q1q5.agent_decision')

LABEL_KEY = 'inserted_candidate_ids'


def _load_safe_index(safe_index_path: str | Path) -> list[dict]:
    raw = Path(safe_index_path).read_text(encoding='utf-8')
    doc = json.loads(raw)
    qb.scan_no_forbidden_keys(doc)
    if not isinstance(doc, Mapping) or not isinstance(doc.get('tracks'), list) or not doc['tracks']:
        raise ad.AgentDecisionError('REQUEST_INVALID', 'safe_index tracks')
    tracks: list[dict] = []
    for i, trk in enumerate(doc['tracks']):
        if not isinstance(trk, Mapping):
            raise ad.AgentDecisionError('REQUEST_INVALID', f'safe_index.tracks[{i}]')
        tracks.append(copy.deepcopy(dict(trk)))
    return tracks


def _build_distractor_candidate(
    src_track: Mapping,
    *,
    req: Mapping,
    rng: random.Random,
    slot_idx: int,
    q_idx: int,
) -> dict:
    as_of_us = int(req['as_of_us'])
    current = req['current']
    edges = {tuple(e) for e in req['topology']['edges']}

    cam = str(src_track['camera_id'])
    if not ad.CAMERA_ID.fullmatch(cam):
        cam = 'CAM_B'

    # Shift timestamps into the valid causal window [0, as_of_us - 1].
    orig_dur = max(0, int(src_track['last_seen_us']) - int(src_track['first_seen_us']))
    max_last = max(1, as_of_us - 100_000 - rng.randint(0, 5) * 50_000 - (q_idx % 5) * 10_000 - slot_idx * 5_000)
    last_seen_us = min(as_of_us - 1, max(0, max_last))
    dur = min(orig_dur, last_seen_us)
    first_seen_us = max(0, last_seen_us - dur)

    gap_choices = (150_000, 250_000, 350_000, 450_000, 550_000, 650_000, 750_000)
    gap_us = gap_choices[(rng.randint(0, len(gap_choices) - 1) + q_idx + slot_idx) % len(gap_choices)]

    has_edge = (current['camera_id'], cam) in edges
    if cam == current['camera_id']:
        link_kind = 'SAME_CAMERA_REACQUISITION'
    elif has_edge and gap_us <= 6_000_000:
        link_kind = 'CROSS_CAMERA_HANDOFF'
    else:
        link_kind = 'CROSS_CAMERA_REACQUISITION'

    # Colour: either keep source track colours or align with current track colours to create ambiguity.
    src_colors = [c for c in src_track.get('colors', []) if c in ad.COLORS]
    cur_colors = [c for c in current.get('colors', []) if c in ad.COLORS]
    if rng.random() < 0.7 and cur_colors:
        colors = list(dict.fromkeys(cur_colors))
    else:
        colors = list(dict.fromkeys(src_colors or cur_colors or ['red']))
    rule_eligible = bool(set(colors) & set(cur_colors))

    scores = copy.deepcopy(dict(src_track['scores']))
    cont = float(src_track.get('continuation_fraction', 0.1))
    cont = min(1.0, max(0.0, cont))

    return {
        'id': 'B1',  # placeholder, renumbered after shuffling
        'camera_id': cam,
        'first_seen_us': int(first_seen_us),
        'last_seen_us': int(last_seen_us),
        'colors': colors,
        'scores': scores,
        'continuation_fraction': cont,
        'gap_us': int(gap_us),
        'graph_edge': bool(has_edge),
        'link_kind': link_kind,
        'rule_eligible': bool(rule_eligible),
    }


def generate_synthetic(
    questions: Sequence[Mapping],
    *,
    safe_index_path: str | Path,
    seed: int,
    per_point: int,
    out_dir: str | Path,
) -> dict:
    """Generate S2 synthetic DP1 questions by inserting ``per_point`` distractor tracks per point.

    Reads ONLY ``safe_index_path``. Writes ``requests_s2_v1.jsonl`` and
    ``scoring_private/synthetic_labels_v1.json`` under ``out_dir``.
    """
    if type(per_point) is not int or not 1 <= per_point <= 3:
        raise ad.AgentDecisionError('REQUEST_INVALID', 'per_point must be int in 1..3')
    if type(seed) is not int:
        raise ad.AgentDecisionError('REQUEST_INVALID', 'seed must be int')

    safe_tracks = _load_safe_index(safe_index_path)
    dp1_questions = [copy.deepcopy(dict(q)) for q in questions if q.get('decision_point') == ad.DP1]
    for q in dp1_questions:
        qb.scan_no_forbidden_keys(q)
        ad.validate_request(q['request'])

    rng = random.Random(seed)
    out_questions: list[dict] = []
    labels: dict[str, dict[str, list[str]]] = {}
    first_inserted_positions: set[int] = set()

    for q_idx, q in enumerate(dp1_questions):
        req = copy.deepcopy(dict(q['request']))
        orig_cands = [(copy.deepcopy(dict(c)), False) for c in req['candidates']]
        if len(orig_cands) + per_point > ad.MAX_CANDIDATES:
            orig_cands = orig_cands[: ad.MAX_CANDIDATES - per_point]

        inserted_cands = []
        for s_idx in range(per_point):
            trk = safe_tracks[rng.randrange(len(safe_tracks))]
            cand = _build_distractor_candidate(trk, req=req, rng=rng, slot_idx=s_idx, q_idx=q_idx)
            inserted_cands.append((cand, True))

        combined = orig_cands + inserted_cands
        rng.shuffle(combined)

        # Guarantee that across a multi-question batch, inserted candidates do not sit at a single fixed position.
        if q_idx == len(dp1_questions) - 1 and len(dp1_questions) > 1 and len(first_inserted_positions) <= 1:
            cur_first_pos = next(idx for idx, (_, is_ins) in enumerate(combined) if is_ins)
            if not first_inserted_positions or cur_first_pos in first_inserted_positions:
                combined = combined[1:] + combined[:1]

        first_pos = next(idx for idx, (_, is_ins) in enumerate(combined) if is_ins)
        first_inserted_positions.add(first_pos)

        cur_id = str(req['current']['id'])
        prefix = 'C' if cur_id.startswith('B') else 'B'
        final_cands: list[dict] = []
        inserted_ids: list[str] = []
        for idx, (cand, is_ins) in enumerate(combined):
            opaque_id = f'{prefix}{idx + 1}'
            c_copy = dict(cand)
            c_copy['id'] = opaque_id
            final_cands.append(c_copy)
            if is_ins:
                inserted_ids.append(opaque_id)

        req['candidates'] = final_cands
        req['rule_answer'] = ad.RuleDecider().answer(req)
        ad.validate_request(req)
        sha = ad.request_sha256(req)

        syn_q = {
            'schema_version': qb.QUESTION_VERSION,
            'decision_point': ad.DP1,
            'source_run': q['source_run'],
            'commit': q['commit'],
            'params_sha256': q['params_sha256'],
            'scene_sha256': q['scene_sha256'],
            'request_sha256': sha,
            'candidate_order_seed': q.get('candidate_order_seed', 0),
            'question_class': 'SYNTHETIC_PERTURBATION',
            'allowed_answers': qb.allowed_answers_for_request(req),
            'request': req,
        }
        qb.scan_no_forbidden_keys(syn_q)
        out_questions.append(syn_q)
        labels[sha] = {LABEL_KEY: inserted_ids}

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    questions_file = out_path / 'requests_s2_v1.jsonl'
    questions_file.write_bytes(b''.join(ad.canonical(row) + b'\n' for row in out_questions))

    private_dir = out_path / 'scoring_private'
    private_dir.mkdir(parents=True, exist_ok=True)
    labels_file = private_dir / 'synthetic_labels_v1.json'
    labels_file.write_bytes(ad.canonical(labels) + b'\n')

    return {
        'questions_path': str(questions_file),
        'labels_path': str(labels_file),
        'n_synthetic': len(out_questions),
    }


def generate_synthetic_clusters(
    questions: Sequence[Mapping],
    *,
    safe_index_path: str | Path,
    seeds: Sequence[int] = (1, 2, 3, 4, 5, 6, 7, 8),
    per_point: int = 2,
    out_dir: str | Path,
) -> dict:
    """Generate >=8 S2 clusters ((source_run, seed) pairs) and count D203 ambiguity episodes."""
    if len(seeds) < 8:
        raise ad.AgentDecisionError('REQUEST_INVALID', 'S2 requires at least 8 cluster seeds')
    out_path = Path(out_dir)
    all_questions: list[dict] = []
    all_labels: dict[str, dict[str, list[str]]] = {}
    cluster_ids: list[str] = []

    for s in seeds:
        cluster_sub = out_path / f'cluster_s{s:02d}'
        res = generate_synthetic(
            questions,
            safe_index_path=safe_index_path,
            seed=s,
            per_point=per_point,
            out_dir=cluster_sub,
        )
        rows = [
            json.loads(line)
            for line in Path(res['questions_path']).read_text(encoding='utf-8').splitlines()
            if line.strip()
        ]
        lbls = json.loads(Path(res['labels_path']).read_text(encoding='utf-8'))
        for row in rows:
            cid = f"{row['source_run']}#s{s:02d}"
            row['source_run'] = cid
            if cid not in cluster_ids:
                cluster_ids.append(cid)
            all_questions.append(row)
        all_labels.update(lbls)

    combined_q_path = out_path / 'requests_s2_v1.jsonl'
    combined_q_path.write_bytes(b''.join(ad.canonical(r) + b'\n' for r in all_questions))
    private_dir = out_path / 'scoring_private'
    private_dir.mkdir(parents=True, exist_ok=True)
    combined_l_path = private_dir / 'synthetic_labels_v1.json'
    combined_l_path.write_bytes(ad.canonical(all_labels) + b'\n')

    episodes = qb.count_ambiguous_episodes(all_questions)
    return {
        'questions_path': str(combined_q_path),
        'labels_path': str(combined_l_path),
        'n_synthetic': len(all_questions),
        'n_clusters': len(cluster_ids),
        'clusters': cluster_ids,
        'ambiguous_episodes': episodes,
    }
