"""Union coplanar source mesh faces into verified covered rectangles for conservative shadow proofs."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

p = argparse.ArgumentParser()
p.add_argument('--scene-export', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
s = json.loads(a.scene_export.read_text())
groups = defaultdict(list)
for obj in s['objects']:
    if obj['type'] != 'MESH' or obj['hide_render'] or obj['name'].startswith('PRODUCTION_'):
        continue
    for face in obj['polygons']:
        pts = [obj['vertices_world_m'][i] for i in face]
        axes = [i for i in range(3) if all(p[i] == pts[0][i] for p in pts)]
        if len(axes) != 1:
            continue
        axis = axes[0]
        uv = [i for i in range(3) if i != axis]
        poly = Polygon([(p[uv[0]], p[uv[1]]) for p in pts])
        if poly.is_valid and poly.area > 0:
            groups[(obj['name'], axis, pts[0][axis])].append(poly)
faces = []
for (name, axis, coord), polys in groups.items():
    combined = unary_union(polys)
    levels = sorted({v[1] for poly in polys for v in poly.exterior.coords})
    uv = [i for i in range(3) if i != axis]
    for lo, hi in zip(levels, levels[1:]):
        cut = combined.intersection(box(combined.bounds[0], lo, combined.bounds[2], hi))
        for part in getattr(cut, 'geoms', [cut]):
            if part.geom_type != 'Polygon' or part.area == 0:
                continue
            rect = box(*part.bounds)
            if not combined.covers(rect):
                continue
            u0,v0,u1,v1 = rect.bounds
            for lower in levels:
                if lower < v0 and combined.covers(box(u0,lower,u1,v1)):
                    v0 = lower
                    break
            for upper in reversed(levels):
                if upper > v1 and combined.covers(box(u0,v0,u1,upper)):
                    v1 = upper
                    break
            points = []
            for u,v in [(u0,v0),(u1,v0),(u1,v1),(u0,v1)]:
                pt = [0.,0.,0.]
                pt[axis],pt[uv[0]],pt[uv[1]] = coord,u,v
                points.append(pt)
            faces.append({'object_ref': name, 'vertices_world_m': points})
out = {'source_blend_sha256': s['sha256'], 'source_export_sha256': hashlib.sha256(a.scene_export.read_bytes()).hexdigest(),
       'method': 'exact-coordinate coplanar union; rectangle admitted only if Shapely union.covers(rectangle); no convex hull or AABB substitutes across holes', 'faces': faces}
a.out.write_text(json.dumps(out,indent=2)+'\n')
print('verified source-covered rectangles', len(faces))
