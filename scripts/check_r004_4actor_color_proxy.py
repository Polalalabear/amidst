"""No-render shader/illuminant proxy. This is not an RGB hue measurement."""
import argparse
import colorsys
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--scene-export', type=Path, required=True)
    p.add_argument('--scenario', type=Path, required=True)
    p.add_argument('--config-a4', type=Path, required=True)
    p.add_argument('--config-b4', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    scene = json.loads(args.scene_export.read_text())
    config = json.loads(args.config_a4.read_text())['hsv_config']
    assert config == json.loads(args.config_b4.read_text())['hsv_config']
    assert config['crop_ratio'] == .5 and config['value_min'] == .2
    raw = json.dumps(config, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    (args.out.parent / 'hsv_config.json').write_bytes(raw)
    shader = next(m['diffuse'][:3] for m in scene['materials'] if m['name'] == 'PRODUCTION_P1_R004_SHIRT')
    colors = {'T': shader, 'A': shader, 'B': colorsys.hsv_to_rgb(.012, .75, .65), 'C': colorsys.hsv_to_rgb(.62, .75, .65)}
    lights = {tuple(o['color']) for o in scene['objects'] if o['type'] == 'LIGHT'}
    assert lights == {(1., 1., 1.)}
    world = scene['world']['nodes'][0]['color'][:3]
    def srgb(v):
        return 12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055
    rows = []
    for run in json.loads(args.scenario.read_text())['runs']:
        for cam in run['render_camera_ids']:
            for actor, rgb in colors.items():
                variants = []
                for f in [0, .25, .5, 1.]:
                    linear = [v*((1-f)+f*w) for v, w in zip(rgb, world)]
                    for kind, value in [('linear', linear), ('simple_sRGB_not_AgX', list(map(srgb, linear)))]:
                        h,s,v = colorsys.rgb_to_hsv(*value)
                        margin = min(min(abs(h-e), 1-abs(h-e)) for e in [.95, .05])
                        in_band = h >= .95 or h <= .05
                        expected = in_band if actor != 'C' else .5 <= h <= .72
                        variants.append({'world_rgb_weight_assumed': f, 'space': kind, 'hsv': [h,s,v], 'red_margin': margin, 'expected_band': expected, 'sv_pass': s >= config['saturation_min'] and v >= config['value_min']})
                rows.append({'run_id': run['run_id'], 'camera_id': cam, 'actor_id': actor, 'variants': variants})
    b = [v for r in rows if r['actor_id'] == 'B' for v in r['variants']]
    result = {'schema': 'amidst.r004-v21-color-proxy.v1', 'method': 'source linear shader times white/world RGB hypotheses, optional simple sRGB transform',
              'boundary': 'MODEL_ONLY; no rendered B RGB; not a camera-specific irradiance solution; omits AgX, BRDF, indirect lighting, detector crops and occlusion',
              'source_blend_sha256': scene['sha256'], 'scene_export_sha256': hashlib.sha256(args.scene_export.read_bytes()).hexdigest(),
              'scenario_sha256': hashlib.sha256(args.scenario.read_bytes()).hexdigest(), 'hsv_config_sha256': hashlib.sha256(raw).hexdigest(),
              'shader_rgb': colors, 'shader_hsv': {a: colorsys.rgb_to_hsv(*c) for a,c in colors.items()},
              'all_lamps_rgb': list(lights), 'world_rgb': world, 'view_transform': scene['render'], 'rows': rows,
              'b_hue_proxy_range': [min(v['hsv'][0] for v in b), max(v['hsv'][0] for v in b)],
              'b_min_red_margin': min(v['red_margin'] for v in b), 'b_proxy_pass': all(v['expected_band'] and v['sv_pass'] and v['red_margin'] >= .02 for v in b),
              'all_proxy_expected_labels_pass': all(v['expected_band'] and v['sv_pass'] for r in rows for v in r['variants']), 'rendered': False}
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print({k: result[k] for k in ['hsv_config_sha256', 'b_hue_proxy_range', 'b_min_red_margin', 'b_proxy_pass', 'all_proxy_expected_labels_pass']})
    return 0 if result['b_proxy_pass'] and result['all_proxy_expected_labels_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
