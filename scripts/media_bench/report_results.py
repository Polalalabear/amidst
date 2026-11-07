"""Summarize source-pinned browser measurements without pooling window modes."""
from pathlib import Path
import argparse,hashlib,json,math,statistics


def pin(path):
    raw=path.read_bytes();return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def summarize_values(values):
    values=sorted(v for v in values if v is not None)
    return {'n':len(values),'median_ms':statistics.median(values) if values else None,
            'p90_ms':values[math.ceil(.9*len(values))-1] if values else None}


def read_trials(root):
    rows=[];inputs=[]
    for kind in ['legacy','core']:
        for path in sorted(root.glob(kind+'-*.json')):
            rows.append(json.loads(path.read_text())['summary']);inputs.append(pin(path))
    return rows,inputs


def report(proxy_path,playback_path,legacy_path,headed_root,hidden_root,out):
    proxies=json.loads(proxy_path.read_text());playback=json.loads(playback_path.read_text())
    legacy=json.loads(legacy_path.read_text())
    assert len(playback['trials'])==27 and playback['headful'] is False
    assert all(not row['page_errors'] and not row['visibility_changes'] for row in playback['trials'])
    assert len({(r['case'],r['format'],r['speed']) for r in playback['trials']})==27
    assert all(r['native_last_frame_complete'] for r in playback['trials'])
    assert len(legacy['trials'])==9 and legacy['headful'] is False
    assert len({(r['format'],r['speed']) for r in legacy['trials']})==9
    assert all(r['native_last_frame_complete'] and not r['page_errors'] for r in legacy['trials'])
    sources=[pin(proxy_path),pin(playback_path),pin(legacy_path)];groups=[];all_trials={}
    for mode,root in [('HEADFUL_INTERRUPTED_SESSION',headed_root),('HEADLESS_COMPLETE_SESSION',hidden_root)]:
        rows,inputs=read_trials(root);sources+=inputs;all_trials[mode]=rows
        for kind in ['legacy','core']:
            current=[r for r in rows if r['kind']==kind]
            groups.append({'mode':mode,'profile':kind,'saved_trials':len(current),
                           'timeouts':sum(r['timeout'] for r in current),
                           'page_errors':sum(len(r['page_errors']) for r in current),
                           'decoded_visible':summarize_values([r['render_ready_latency_ms'] for r in current]),
                           'native_browser_paint':summarize_values([r['native_image_paint_latency_ms'] for r in current])})
    storage={'source_png_bytes':sum(r['source_bytes'] for r in proxies['rows']),
             'safe_png_playback_bytes':sum(r['png_public_bytes'] for r in proxies['rows']),
             'jpeg_bytes':sum(r['proxies']['jpeg']['bytes'] for r in proxies['rows']),
             'webp_bytes':sum(r['proxies']['webp']['bytes'] for r in proxies['rows'])}
    result={'scope':'LOCAL engineering browser measurements; no model, inference or research acceptance',
            'source_head':playback['source_head'],'proxy_manifest_sha256':hashlib.sha256(proxy_path.read_bytes()).hexdigest(),
            'browser':playback['browser'],'hardware':playback['hardware'],'headful_playback':False,
            'storage':storage,'playback_trials':playback['trials'],'legacy_playback_trials':legacy['trials'],'latency_groups':groups,
            'latency_trials':all_trials,'sources':sources,
            'not_measured':['physical display fps','live detector-to-switch latency','manual first-pixel target appearance','A4/B4 integrated core switch latency'],
            'latency_origin':'recorded first matching observation at B frame 103 / source 5.15s; source selection is not physical ground truth'}
    result['resource_timing_boundary']='27-case receipt used the default ResourceTiming buffer; http_* fields are first buffered entries, NOT total transfers. FPS/ElementTiming/decode observations are independent. Later script increases the buffer.'
    out.mkdir(exist_ok=False)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# D133 Mac playback format and switch latency measurements','',
           'Engineering only. No integration merge, model run, source write or formal acceptance.','',
           '## Storage (bytes)','',f"Original PNG: {storage['source_png_bytes']:,}; safe public PNG stream: {storage['safe_png_playback_bytes']:,}; JPEG90: {storage['jpeg_bytes']:,}; WebP90: {storage['webp_bytes']:,}.",'',
           '## Playback: complete 27-case matrix','',
           'Same clean #408 event-viewer; all source cameras shown. Mac Chrome **headless**. Native values are image ElementTiming render events, not physical screen Hz. Each case ran its full source duration once; no between-run confidence interval.','',
           '| Case | Format | Setting | Native fps/camera mean | Decoded-visible fps/camera mean | Actual source speed | decode() wait P90 ms |',
           '|---|---|---:|---:|---:|---:|---:|']
    for r in playback['trials']:
        native=statistics.mean(c['native_image_paint_fps'] for c in r['per_camera'].values())
        ready=statistics.mean(c['displayed_advances_fps'] for c in r['per_camera'].values())
        lines.append(f"|{r['case']}|{r['format']}|{r['speed']}x|{native:.3f}|{ready:.3f}|{r['actual_source_multiplier']:.3f}x|{r['decode_wait_p90_ms']:.3f}|")
    lines+=['','decode() promise wait may include pending loading; it is not isolated decoder CPU time. The 27-case raw receipt used the default ResourceTiming buffer, so its http_* fields cover only first buffered entries, not total transfer bytes. FPS/native image events are independent. Later script increases that buffer; this report does not relabel old executions.','',
            'Every original PNG retained its source byte pin. Its unsafe metadata was removed in memory before public PNG/codec decoding; the manifest preserves original and served hashes separately.','',
            '## B-05b recorded workbench: supplementary 9-case matrix','',
            'Single active camera in the same clean #408 player. LOCAL adapter preserves authorization and source-pin checks, replaces only served image bytes/hash/content type, and adapts the hard-coded PNG Blob MIME in the served JS response. Source checkout files are unchanged. This is a codec experiment, not product proxy integration.','',
            '| Format | Setting | Native fps | Decoded-visible fps | Actual source speed | decode() wait P90 ms |',
            '|---|---:|---:|---:|---:|---:|']
    for r in legacy['trials']:
        lines.append(f"|{r['format']}|{r['speed']}x|{r['native_image_paint_fps']:.3f}|{r['decoded_visible_fps']:.3f}|{r['actual_source_multiplier']:.3f}x|{r['decode_wait_p90_ms']:.3f}|")
    lines+=['','The event-viewer advances at most one source frame per 40 ms tick, so its B-05b high-speed ceiling is approximately 25 fps/camera. The single-view workbench uses a separate player and must be assessed from its own table.','',
            '## Switch baselines (ms)','',
            '| Mode | Profile | Saved n | Ready median / P90 | Native paint n | Native median / P90 |',
            '|---|---|---:|---|---:|---|']
    def pair(d):return 'UNKNOWN' if not d['n'] else f"{d['median_ms']:.3f} / {d['p90_ms']:.3f}"
    for g in groups:lines.append(f"|{g['mode']}|{g['profile']}|{g['saved_trials']}|{pair(g['decoded_visible'])}|{g['native_browser_paint']['n']}|{pair(g['native_browser_paint'])}|")
    lines+=['','HEADFUL session stopped after 30 B-05b and 11 synthetic core trials when the user reported popup disruption. Saved valid samples remain separate; missing repetitions were not filled. Headless complete-session samples are not pooled with those data.','',
            'Legacy = B-05b recorded first matched B frame available at replay clock 5.15s → actual B PNG ready/native render. Core = existing 8765 SYNTHETIC schematic state transition, not a real-camera/detector result.','',
            'The offline recording begins the new-camera sighting at 5.15s. Earlier unlabelled physical pixel appearance is UNKNOWN. No live model/inference time is included.','',
            '## Sources and methods','',
            '- Chrome headless uses the installed Mac Google Chrome executable, fresh isolated contexts and disabled HTTP cache. It does not display or focus windows: https://developer.chrome.com/docs/automation-and-testing/headless',
            '- Native image render timestamps: https://w3c.github.io/element-timing/',
            '- decode() is a decoding readiness promise, not physical display measurement: https://html.spec.whatwg.org/multipage/embedded-content.html#dom-img-decode',
            '- Compression/format background: https://developer.chrome.com/docs/performance/insights/image-delivery','',
            'All raw samples/screenshots and proxy images stay LOCAL. Source/code/tool/manifest pins are in the receipts; committed JSON contains only engineering measurement summaries.']
    (out/'results.md').write_text('\n'.join(lines)+'\n')
    plot_latency(all_trials,out)
    print(json.dumps({'status':'COMPLETE','latency':groups,'storage':storage,'results_sha256':pin(out/'results.json')['sha256']},indent=2))


def plot_latency(all_trials,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['svg.hashsalt']='amidst-d133'
    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    for mode,rows in all_trials.items():
        for kind in ['legacy','core']:
            vals=sorted(r['native_image_paint_latency_ms'] if kind=='legacy' else r['render_ready_latency_ms'] for r in rows if r['kind']==kind and (r['native_image_paint_latency_ms'] if kind=='legacy' else r['render_ready_latency_ms']) is not None)
            if vals:axes[0 if kind=='legacy' else 1].step(vals,[(i+1)/len(vals) for i in range(len(vals))],where='post',label=f"{mode.split('_')[0]} n={len(vals)}")
    for ax,title in zip(axes,['B-05b replay: native image paint','Synthetic core: decoded schematic ready']):
        ax.set_title(title);ax.set_xlabel('Latency (ms)');ax.set_ylabel('Empirical CDF');ax.set_ylim(0,1.02);ax.grid(alpha=.25);ax.legend()
    fig.suptitle('Browser replay baselines — no live detector latency')
    svg=out/'latency_ecdf.svg'
    fig.savefig(svg,metadata={'Date':None});fig.savefig(out/'latency_ecdf.png',dpi=160)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proxies',type=Path);p.add_argument('--playback',type=Path);p.add_argument('--legacy-playback',type=Path);p.add_argument('--headed',type=Path);p.add_argument('--hidden',type=Path);p.add_argument('--curated',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.curated:
        a.out.mkdir(exist_ok=False);plot_latency(json.loads(a.curated.read_text())['latency_trials'],a.out)
    else:
        if not all([a.proxies,a.playback,a.legacy_playback,a.headed,a.hidden]):p.error('provide --curated or all five source inputs')
        report(a.proxies,a.playback,a.legacy_playback,a.headed,a.hidden,a.out)
