"""Eight scoped #529 RGB comparisons; reads one existing PNG per camera."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--rgb-root',type=Path,required=True)
    args = parser.parse_args()
    rows = []
    verification = args.assets/'verification'
    cameras = json.loads((args.assets/'cameras.three.json').read_text())['cameras']
    for camera in cameras:
        name = camera['camera_id']
        source = args.rgb_root/name/'000000.png'
        actual = verification/(name+'.png')
        with Image.open(source) as image:
            rgb = image.convert('RGB')
        with Image.open(actual) as image:
            live = image.convert('RGB')
        assert rgb.size==live.size==(960,540)
        a,b = np.asarray(rgb,dtype=float),np.asarray(live,dtype=float)
        luma = np.array([.2126,.7152,.0722])
        comparison = Image.new('RGB',(1920,580),(20,24,30))
        comparison.paste(rgb,(0,40));comparison.paste(live,(960,40))
        draw = ImageDraw.Draw(comparison)
        draw.text((12,12),name+' | #529 A4-1 / source frame 0',fill='white')
        draw.text((972,12),name+' | three.js / static baked scene (no recorded actors)',fill='white')
        out = verification/(name+'_comparison.png')
        comparison.save(out)
        rows.append(dict(camera_id=name,reference_relative_path='data/r004-4actor-natural-walk-eightcam-20261114/A4-1/'+name+'/000000.png',
                         reference_sha256=sha(source),viewer_path=actual.relative_to(args.assets).as_posix(),
                         comparison_path=out.relative_to(args.assets).as_posix(),
                         reference_mean_rgb_srgb8=a.mean((0,1)).tolist(),viewer_mean_rgb_srgb8=b.mean((0,1)).tolist(),
                         reference_mean_luma_srgb8=float((a@luma).mean()),viewer_mean_luma_srgb8=float((b@luma).mean()),
                         mean_luma_delta_srgb8=float(((b-a)@luma).mean()),mae_rgb_srgb8=float(np.abs(b-a).mean())))
    report = dict(schema='amidst.n6-rgb-comparison.v1',reference_pr=529,reference_run='A4-1',frame_index=0,
                  scope='Full-frame display sRGB statistics, not radiometric error or acceptance; source actors are absent from static viewer',
                  differences=['Cycles 32-sample bake versus #529 EEVEE 16-sample RGB',
                               'Diffuse irradiance and combined AgX appearance are fixed to static geometry; no dynamic actor shadows',
                               '4096 atlas interpolation/UV seams and reduced runtime noise; specular/view-dependent response is frozen',
                               'Character uses runtime PBR approximation; its source linear material colors are exact, camera HSV is not certified'],cameras=rows)
    (verification/'RGB_COMPARISON.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.assets/'REVIEW.html').write_text('<!doctype html><meta charset="utf-8"><title>N6 asset review</title><style>body{background:#18202a;color:white;font:16px system-ui;margin:24px}img{max-width:100%}section{margin-bottom:32px}</style><h1>N6 asset review</h1><p>Articulated source mannequin; static source scene with baked lighting. Local engineering evidence.</p>'
       +''.join('<section><h2>'+name+'</h2><img src="verification/character_'+name+'.png"></section>' for name in ('walk','run','idle'))
       +'<h2>v2.3 material variants</h2>'+''.join('<img style="width:49%" src="verification/variant_'+v+'.png">' for v in ('T','A','B','C'))
       +'<h2>Eight camera comparisons</h2><p>Left: existing #529 RGB. Right: static three.js scene. No video was rerendered.</p>'
       +''.join('<section><h3>'+r['camera_id']+'</h3><img src="'+r['comparison_path']+'"><p>Mean display luma delta: '+f"{r['mean_luma_delta_srgb8']:+.2f}"+' / 255.</p></section>' for r in rows))
    print(json.dumps([dict(camera_id=r['camera_id'],mean_luma_delta_srgb8=r['mean_luma_delta_srgb8']) for r in rows],indent=2))


if __name__=='__main__':
    main()
