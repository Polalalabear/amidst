"""Run fresh indexes once, then safe bundle and review encoding, after all RGB is complete."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--artifacts-root', type=Path, required=True)
    p.add_argument('--evidence-root', type=Path, required=True)
    p.add_argument('--data-root', type=Path, required=True)
    p.add_argument('--scenario', type=Path, required=True)
    p.add_argument('--ffmpeg', type=Path, required=True)
    a = p.parse_args()
    repo, art, evidence, data = (x.resolve() for x in [a.repo, a.artifacts_root, a.evidence_root, a.data_root])
    assert evidence.parent == art / 'evidence' and data.parent == art / 'data'
    assert json.loads((evidence / 'RENDER_FULL_COMPLETE.json').read_text())['status'] == 'PASS'
    doc = json.loads(a.scenario.read_text())
    for run in doc['runs']:
        assert len(run['render_camera_ids']) == 8
        for cam in run['render_camera_ids']:
            assert len(list((data / run['scenario'] / cam).glob('*.png'))) == run['duration_us'] // 200000
    # Exclusive creation prevents a second inference pass even if a second supervisor is launched.
    with (evidence / 'POSTPROCESS_LOCK.json').open('x') as f:
        json.dump({'pid': os.getpid(), 'code_git_sha': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()}, f)

    def run(script, args, name, extra_env=None):
        cmd = [sys.executable, '-B', str(repo / 'scripts' / script)] + list(map(str, args))
        (evidence / f'{name}_command.json').write_text(json.dumps(cmd, indent=2) + '\n')
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', **(extra_env or {})}
        with (evidence / f'{name}.log').open('x') as log:
            child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
            begin = time.monotonic()
            try:
                while child.poll() is None:
                    time.sleep(10)
                    print(json.dumps({'stage': name, 'elapsed_s': round(time.monotonic() - begin, 1)}), flush=True)
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
        if child.returncode:
            print((evidence / f'{name}.log').read_text()[-5000:], flush=True)
            raise RuntimeError(f'{name} exit {child.returncode}; do not rerun completed indexes')
        print(name, 'PASS', flush=True)

    common = ['--repo', repo, '--artifacts-root', art]
    run('prepare_r004_eight_camera_safe.py', common + ['--data-root', data, '--evidence-root', evidence], 'prepare_safe')
    safe = data / 'bundle/safe'
    pin = hashlib.sha256((safe / 'SAFE_MANIFEST.json').read_bytes()).hexdigest()
    model = art / 'data/demo-owned-v1/models/rtdetr'
    runtime = art / 'data/q1q5-dynamic-baseline-v1_20261025/runtime-deps'
    for label in ['A4-1', 'B4-1']:
        run('index_r004_4actor.py', ['--safe-root', safe, '--safe-manifest-sha256', pin,
            '--label', label, '--model-source', model / 'source/rtdetr_pytorch',
            '--weights', model / 'rtdetr_r18vd_dec3_6x_coco_from_paddle.pth'],
            'index_' + label, {'PYTHONPATH': str(runtime)})
    run('package_r004_4actor.py', common + ['--safe-root', safe], 'package_bundle', {'PYTHONPATH': str(repo / 'src')})
    run('package_r004_natural_walk_full.py', ['--artifacts-root', art, '--ffmpeg', a.ffmpeg,
        '--evidence-root', evidence, '--data-root', data, '--scenario', a.scenario.resolve()], 'encode_review')
    (evidence / 'POSTPROCESS_COMPLETE.json').write_text(json.dumps({'status': 'PASS',
        'model_calls_expected': {'A4-1': 2000, 'B4-1': 1680}, 'old_records_reused': False}, indent=2) + '\n')


if __name__ == '__main__':
    def stop(signum, frame):
        raise SystemExit(f'postprocessor stopped by signal {signum}')
    signal.signal(signal.SIGTERM, stop)
    main()
