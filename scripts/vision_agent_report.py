#!/usr/bin/env python3
"""Aggregate vision-agent answer tables, scores and oracle into tables.md + two figures (repo venv: matplotlib).

Reads ``local/evidence/vision-agent-<date>/{answers_*.json,scores.json,oracle.json}`` (run ``run_vision_agent.py oracle`` and
``score`` first). Writes ``tables.md``, ``fig_summary.png``, ``fig_timeline.png`` next to them and, with --docs DIR, copies the
figures there. Prices: openai_gateway.PRICES (USD per Mtok)."""
import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from amidst.paths import local_dir  # noqa: E402
from amidst.q1q5.openai_gateway import PRICES  # noqa: E402

OUT = local_dir() / 'evidence/vision-agent-20261120'
API = {'terra': 'gpt-6.1-terra', 'sol': 'gpt-6.1-sol'}
EVENTS = ('A4-1', 'B4-1')
MODES = ('offline', 'realtime')
NAMES = {'terra_vision': 'terra 看圖', 'terra_text': 'terra 不看圖', 'sol_vision': 'sol 看圖', 'sol_text': 'sol 不看圖',
         'info_terra_vision': '[資訊] terra 看圖', 'info_terra_text': '[資訊] terra 不看圖', 'info_sol_vision': '[資訊] sol 看圖'}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--docs')
    args = ap.parse_args()
    scores = json.loads((OUT / 'scores.json').read_text())
    oracle = json.loads((OUT / 'oracle.json').read_text())
    md = []
    keys = [k for k in NAMES if k in scores]
    fields = [('follow_rate', '跟對率'), ('lost_s_while_visible', '失聯秒'), ('wrong_total_s', '錯人+盲區誤鎖秒'),
              ('combined_follow_rate', '含自畫框跟對率'), ('combined_lost_s_while_visible', '含自畫框失聯秒'),
              ('early_reconnect_s_total', '提早接回秒'), ('wrong_connections', '錯接次數'), ('own_box_wrong_s', '自畫框錯秒')]
    summary = {}
    for mode in MODES:
        md.append(f'\n### 時間模式：{mode}\n')
        md.append('| 事件 | 組 | ' + ' | '.join(n for _f, n in fields) + ' |')
        md.append('|---|---|' + '---:|' * len(fields))
        for ev in EVENTS:
            r = oracle[ev]['rule']
            md.append(f'| {ev} | 規則 | ' + ' | '.join(str(r.get(f)) if f in r else '0' for f, _ in fields) + ' |')
            summary[(ev, mode, 'rule')] = r
            for sk, sn in (('all', '上限·索引框·全鏡頭'), ('graph', '上限·索引框·圖鄰居'), ('own_all', '上限·自畫框·全鏡頭'), ('own_graph', '上限·自畫框·圖鄰居')):
                lat = 0.0 if mode == 'offline' else 2.0
                r = oracle[ev][f'oracle_{sk}_lat{lat:g}']
                md.append(f'| {ev} | {sn}{"" if mode == "offline" else "（延遲 2 s）"} | ' + ' | '.join(str(r.get(f)) for f, _ in fields) + ' |')
                summary[(ev, mode, 'oracle_' + sk)] = r
            for k in keys:
                runs = scores[k][ev][mode]
                vals = {f: mean([x['metrics'].get(f) for x in runs]) for f, _ in fields}
                rng = lambda f: (min(x['metrics'][f] for x in runs), max(x['metrics'][f] for x in runs))
                cells = []
                for f, _ in fields:
                    lo, hi = rng(f)
                    cells.append(f'{vals[f]} [{lo}–{hi}]' if lo != hi else f'{vals[f]}')
                md.append(f'| {ev} | {NAMES[k]}（K={len(runs)}） | ' + ' | '.join(cells) + ' |')
                summary[(ev, mode, k)] = vals
    md.append('\n### 呼叫統計\n')
    md.append('| 組 | 呼叫數 | 成功解析 | 找不到(present=false) | 解析失敗／傳輸錯誤 | 延遲 p50／p95 s | prompt／completion tokens 平均 | 估計花費 USD |')
    md.append('|---|---:|---:|---:|---:|---|---|---:|')
    total = 0.0
    for k in keys:
        model = k.replace('info_', '').split('_')[0]
        calls = []
        for f in sorted(OUT.glob(f'{"info_" if k.startswith("info_") else ""}answers_{k.replace("info_", "")}_k*.json')):
            calls += json.loads(f.read_text())['answers']
        ok = [c for c in calls if c.get('answer')]
        absent = [c for c in ok if not c['answer']['present']]
        bad = [c for c in calls if c.get('error')]
        lat = [c['latency_s'] for c in calls if c.get('latency_s') and not c.get('error')]
        pt = [c['prompt_tokens'] for c in calls if c.get('prompt_tokens')]
        ct = [c['completion_tokens'] for c in calls if c.get('completion_tokens')]
        cost = sum(c.get('prompt_tokens', 0) * PRICES[API[model]][0] / 1e6 + c.get('completion_tokens', 0) * PRICES[API[model]][1] / 1e6 for c in calls)
        total += cost
        md.append(f'| {NAMES[k]} | {len(calls)} | {len(ok)} | {len(absent)} | {len(bad)} | {pct(lat, .5)}／{pct(lat, .95)} | '
                  f'{round(mean(pt) or 0)}／{round(mean(ct) or 0)} | {cost:.4f} |')
    md.append(f'\n估計總花費（token × PRICES）：USD {total:.4f}')
    rec = json.loads((OUT / 'recognition.json').read_text())
    md.append('\n### 辨識對照（每個觸發 tick；GT 只在評分端）：看圖 Agent vs RT-DETR＋規則顯示\n')
    md.append('| 事件 | 組 | 範圍 | 評分 tick | Agent TP/FP/FN | Agent P／R | 規則 TP/FP/FN | 規則 P／R | Agent對規則錯 | 規則對Agent錯 | 兩者皆對 |')
    md.append('|---|---|---|---:|---|---|---|---|---:|---:|---:|')
    for k in [k for k in NAMES if k in rec and k.startswith('info_')] + [k for k in NAMES if k in rec and not k.startswith('info_')]:
        for ev in EVENTS:
            runs = [r['recognition'] for r in rec[k][ev]]
            for scope in ('all', 'gap', 'verify', 'no_person_box', 'score<0.45', 'score>=0.45'):
                def agg(who, f):
                    return mean([r.get(f'{who}/{scope}', {}).get(f, 0) for r in runs]) if any(f'{who}/{scope}' in r for r in runs) else None
                if agg('agent', 'ticks') is None:
                    continue
                ap_, rp_ = [mean([r.get(f'{w}/{scope}', {}).get(m) for r in runs]) for w, m in (('agent', 'precision'), ('rule', 'precision'))], None
                md.append(f'| {ev} | {NAMES[k]}（K={len(runs)}） | {scope} | {agg("agent", "ticks")} | '
                          f'{agg("agent", "TP")}/{agg("agent", "FP")}/{agg("agent", "FN")} | '
                          f'{mean([r.get(f"agent/{scope}", {}).get("precision") for r in runs])}／{mean([r.get(f"agent/{scope}", {}).get("recall") for r in runs])} | '
                          f'{agg("rule", "TP")}/{agg("rule", "FP")}/{agg("rule", "FN")} | '
                          f'{mean([r.get(f"rule/{scope}", {}).get("precision") for r in runs])}／{mean([r.get(f"rule/{scope}", {}).get("recall") for r in runs])} | '
                          f'{mean([r.get("cmp/" + scope, {}).get("agent_right_rule_wrong", 0) for r in runs]) if scope in ("all", "gap", "verify") else ""} | '
                          f'{mean([r.get("cmp/" + scope, {}).get("rule_right_agent_wrong", 0) for r in runs]) if scope in ("all", "gap", "verify") else ""} | '
                          f'{mean([r.get("cmp/" + scope, {}).get("both_right", 0) for r in runs]) if scope in ("all", "gap", "verify") else ""} |')
    (OUT / 'tables.md').write_text('\n'.join(md))
    print('\n'.join(md))
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang TC', 'Heiti TC', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        groups = [('rule', '規則'), ('oracle_all', '上限\n索引框'), ('oracle_own_all', '上限\n自畫框')] + [(k, NAMES[k].replace(' ', '\n')) for k in keys]
        fig, axes = plt.subplots(2, 2, figsize=(9, 5.2), sharey=False)
        for i, ev in enumerate(EVENTS):
            for j, mode in enumerate(MODES):
                ax = axes[i][j]
                xs, ys = [], []
                for g, name in groups:
                    s = summary.get((ev, mode, g))
                    if s is None:
                        continue
                    v = s.get('combined_lost_s_while_visible')
                    ys.append(s.get('lost_s_while_visible') if v is None else v)
                    xs.append(name)
                cols = ['#9a9a9a', '#2b6cb0', '#2b6cb0'] + ['#d97706' if 'vision' in k else '#6b8e23' for k in keys]
                ax.bar(range(len(xs)), ys, color=cols[:len(xs)])
                ax.set_xticks(range(len(xs)))
                ax.set_xticklabels(xs, fontsize=6.5)
                ax.set_title(f'{ev} · {mode}', fontsize=9)
                ax.set_ylabel('失聯秒（目標可偵測時，含自畫框）', fontsize=7)
                for x, y in zip(range(len(xs)), ys):
                    ax.text(x, y, f'{y:.1f}', ha='center', va='bottom', fontsize=7)
        fig.tight_layout()
        fig.savefig(OUT / 'fig_summary.png', dpi=100)
        print('figure ok')
    except Exception as exc:  # noqa: BLE001
        print('figure skipped:', exc)
    if args.docs and (OUT / 'fig_summary.png').exists():
        Path(args.docs).mkdir(parents=True, exist_ok=True)
        (Path(args.docs) / 'fig_summary.png').write_bytes((OUT / 'fig_summary.png').read_bytes())


if __name__ == '__main__':
    main()
