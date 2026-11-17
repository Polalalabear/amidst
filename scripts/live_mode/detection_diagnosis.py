"""Evaluation-only contact sheet and box-luminance proxy, using historical sweep labels."""
import argparse
import json,statistics
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--work',type=Path,required=True)
ap.add_argument('--historical-rows',type=Path,required=True)
a=ap.parse_args()
root=a.work
rows=json.loads((root/'recording/evaluation_labels.json').read_text())
hist=json.loads(a.historical_rows.read_text())
lookup={(r['cam'],round(r['x'],2),round(r['y'],2),r['heading']):r for r in hist}
canvas=Image.new('RGB',(960,660),'#222222'); draw=ImageDraw.Draw(canvas)
stats={}; examples=[]
for j,cam in enumerate(['CAM_ENTRY','CAM_R101_IN','CAM_EXT_CAR']):
 a=[{**r,**{'old':lookup[(r['cam'],round(r['x'],2),round(r['y'],2),r['heading'])]}} for r in rows if r['cam']==cam and round(r['inside'],2)>=.6 and round(r['gt_h_px'],1)>=16]
 vals=[]
 for r in a:
  im=Image.open(root/'recording/rgb'/f"{r['id']}.jpg"); ar=np.asarray(im); x0,y0,x1,y1=[int(v) for v in r['bbox']]; crop=ar[max(0,y0):min(180,y1+1),max(0,x0):min(320,x1+1)]
  lum=crop@np.array([.2126,.7152,.0722]); vals.append(float(np.median(lum))); r['median_luma']=float(np.median(lum))
 stats[cam]={'n':len(a),'bbox_luma_p50':statistics.median(vals),'bbox_luma_range':[min(vals),max(vals)],'h_px_range':[min(r['gt_h_px'] for r in a),max(r['gt_h_px'] for r in a)]}
 for i,(lo,hi,name) in enumerate([(0,.05,'unrecovered'),(.05,.35,'threshold loss'),(.35,1.01,'detected')]):
  b=[r for r in a if lo<=r['old']['score']<hi and (r['old']['iou']>=.3 or lo==0)]
  name=name if b else 'lowest scored'; b=b or sorted(a,key=lambda r:r['old']['score'])[:1]; r=sorted(b,key=lambda r:abs(r['gt_h_px']-50))[0]; im=Image.open(root/'recording/rgb'/f"{r['id']}.jpg"); d=ImageDraw.Draw(im); d.rectangle(r['bbox'],outline='yellow',width=1)
  canvas.paste(im,(i*320,j*220)); draw.text((i*320+4,j*220+182),f"{cam} {name} s={r['old']['score']:.3f}",fill='white'); draw.text((i*320+4,j*220+197),f"{r['id']} H={r['gt_h_px']:.1f} Y={r['median_luma']:.1f}",fill='white'); examples.append({k:r[k] for k in ['id','cam','bbox','gt_h_px','median_luma','old']})
canvas.save(root/'diagnosis_frames.jpg')
(root/'diagnosis_frame_stats.json').write_text(json.dumps({'stats':stats,'examples':examples},indent=2))
print(json.dumps(stats,indent=2))
