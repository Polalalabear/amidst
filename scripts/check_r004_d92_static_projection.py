"""D92 planning-only projection and explicitly authorized static mesh intersections.

No Blender, RGB, renderer visibility/depth, GT, actor or recorded route input.
The proposed polyline and witness heights are declared here, not extracted from
an actor. Results are static witness times, never measured person visibility.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

PINS = {
    'catalog':'3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f',
    'geometry':'bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a',
    'patches':'17dbae08de96a65b8cc9710b5a8cb4a945d466362f17d41a7e6a0b3108285151',
    'cards':'015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd',
}
CARDS_HEAD='e99743dec9da690b237c8f85ed5e6bdb28ed464d'
HEIGHTS=[0.0,0.425,0.85,1.275,1.5,1.7,1.9]
EPS=1e-9


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def sub(a,b):return [x-y for x,y in zip(a,b,strict=True)]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def dot(a,b):return sum(x*y for x,y in zip(a,b,strict=True))


def interval(values_a,values_b):
    """Closed intersection of linear halfspaces on one proposed segment."""
    lo,hi=0.0,1.0
    for a,b in zip(values_a,values_b,strict=True):
        if a < -EPS and b < -EPS:return None
        if a < -EPS:lo=max(lo,-a/(b-a))
        elif b < -EPS:hi=min(hi,a/(a-b))
    return [lo,hi] if lo<=hi else None


def merge(intervals):
    out=[]
    for a,b in sorted(intervals):
        if out and a<=out[-1][1]+EPS:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return out


def unblocked(frustum,shadows):
    if frustum is None:return []
    lo,hi=frustum;cursor=lo;out=[]
    for a,b in merge(shadows):
        if b<lo or a>hi:continue
        a,b=max(a,lo),min(b,hi)
        if cursor<a-EPS:out.append([cursor,a])
        cursor=max(cursor,b)
    if cursor<hi-EPS:out.append([cursor,hi])
    return out


def frustum_values(camera,p):
    matrix=camera['camera_to_world'];delta=[p[i]-matrix[i][3] for i in range(3)]
    x,y,z=[sum(matrix[j][i]*delta[j] for j in range(3)) for i in range(3)]
    depth=-z
    return [depth-camera['clip_start'],camera['clip_end']-depth,
            camera['fx']*x+camera['cx']*depth,
            (camera['width']-camera['cx'])*depth-camera['fx']*x,
            camera['cy']*depth-camera['fy']*y,
            (camera['height']-camera['cy'])*depth+camera['fy']*y]


def shadow_values(origin,triangle,p):
    """A triangle's shadow is a four-halfspace convex cone beyond its face.

    Intersection with the planning segment is analytic; no time samples or
    renderer visibility API are used. Degenerate/camera-coplanar faces do not
    establish a positive-length blocking segment.
    """
    a,b,c=triangle;normal=cross(sub(b,a),sub(c,a));side=dot(normal,sub(origin,a))
    if abs(side)<EPS:return None
    values=[-math.copysign(1,side)*dot(normal,sub(p,a))]
    for left,right,other in [(a,b,c),(b,c,a),(c,a,b)]:
        edge_normal=cross(sub(left,origin),sub(right,origin))
        inside=dot(edge_normal,sub(other,origin))
        if abs(inside)<EPS:return None
        values.append(math.copysign(1,inside)*dot(edge_normal,sub(p,origin)))
    return values


def make_shadow_planes(origin,triangles):
    result=[]
    for triangle in triangles:
        # shadow_values is affine in p. Recover coefficients once per triangle.
        zero=shadow_values(origin,triangle,[0,0,0])
        if zero is None:continue
        axes=[shadow_values(origin,triangle,p) for p in ([1,0,0],[0,1,0],[0,0,1])]
        result.append([([axes[k][i]-zero[i] for k in range(3)],zero[i]) for i in range(4)])
    return result


def visible_intervals(camera,triangles,points,height,shadow_planes=None,
                      time_range_s=(36.0,39.0),offset_xy=(0.0,0.0)):
    origin=[camera['camera_to_world'][i][3] for i in range(3)]
    if shadow_planes is None:shadow_planes=make_shadow_planes(origin,triangles)
    lengths=[math.dist(a,b) for a,b in zip(points,points[1:],strict=False)]
    total=sum(lengths);distance=0;visible=[];projected=[]
    if total<=0 or time_range_s[0]>=time_range_s[1]:
        raise ValueError('positive route length and increasing clock range required')
    for start,end,length in zip(points,points[1:],lengths,strict=False):
        a=[start[0]+offset_xy[0],start[1]+offset_xy[1],start[2]+height]
        b=[end[0]+offset_xy[0],end[1]+offset_xy[1],end[2]+height]
        projected_part=interval(frustum_values(camera,a),frustum_values(camera,b))
        shadows=[]
        for planes in shadow_planes:
            part=interval([dot(n,a)+offset for n,offset in planes],
                          [dot(n,b)+offset for n,offset in planes])
            if part:shadows.append(part)
        def clock(part,distance=distance,length=length):
            return [time_range_s[0]+(time_range_s[1]-time_range_s[0])*(distance+v*length)/total for v in part]
        if projected_part:projected.append(clock(projected_part))
        visible.extend(clock(part) for part in unblocked(projected_part,shadows))
        distance+=length
    return dict(frustum_intervals_s=merge(projected),unoccluded_witness_intervals_s=merge(visible))


def speed_time_bounds(distance,total,time_range_s=(36.0,39.0),speed_limits=(0.8,1.5)):
    """Possible passage time at one fixed arc distance; no physical authority."""
    left,right=time_range_s;slow,fast=speed_limits
    if not 0<slow<=fast or not 0<=distance<=total or total<=0 or left>=right:
        raise ValueError('invalid distance, clock or speed limits')
    if not slow*(right-left)<=total<=fast*(right-left):return None
    lower=max(left+distance/fast,right-(total-distance)/slow)
    upper=min(left+distance/slow,right-(total-distance)/fast)
    return [lower,upper] if lower<=upper+EPS else None


def intersect_interval_sets(groups):
    """All declared samples must be unoccluded at the same time."""
    result=None
    for group in groups:
        result=group if result is None else merge([
            [max(a,c),min(b,d)] for a,b in result for c,d in group
            if max(a,c)<min(b,d)-EPS])
    return result or []


def body_sample_check(camera,triangles,points,planes):
    # Declared planning cage, not a measured actor silhouette or approved body policy.
    samples=[]
    for x in [-0.2,0.0,0.2]:
        for y in [-0.2,0.0,0.2]:
            for h in HEIGHTS:
                row=visible_intervals(camera,triangles,points,h,planes,offset_xy=(x,y))
                samples.append({'offset_xy_m':[x,y],'height_m':h,**row})
    common=intersect_interval_sets(row['unoccluded_witness_intervals_s'] for row in samples)
    return {'role':'DECLARED_UPRIGHT_SAMPLE_CAGE_NOT_ACTOR_GEOMETRY',
            'width_xy_m':[0.4,0.4],'height_m':1.9,'sample_count':len(samples),
            'samples':samples,'all_sampled_witness_intervals_s':common,
            'necessary_condition':'FAIL' if not common else 'NOT_SUFFICIENT_FOR_PASS',
            'whole_surface_visibility':'UNKNOWN',
            'limits':'Finite samples can disprove full visibility of this declared cage; '
                     'they cannot prove the complete body surface or detector visibility.'}


def audit(static_root,patches_path,cards):
    paths={'catalog':static_root/'safe_static/cameras.json',
           'geometry':static_root/'safe_static/static_geometry.PROPOSED.json',
           'patches':patches_path,'cards':cards}
    before={k:sha(p) for k,p in paths.items()}
    if before!=PINS:raise ValueError('input SHA-256 pin mismatch: '+','.join(k for k in PINS if before[k]!=PINS[k]))
    cameras={c['camera_id']:c for c in json.loads(paths['catalog'].read_bytes())['cameras']}
    geometry=json.loads(paths['geometry'].read_bytes());patches=json.loads(patches_path.read_bytes())
    exterior=patches['CAM_EXT_CLEAR:EXIT_V3:E_OUT_VEST']['polygon_world_m']
    target=patches['CAM_W1:ENTRY_V3:E_VEST_CORR']['polygon_world_m']
    # Boundary witnesses: leave CLEAR at t=36; first touch W1 entry at t=39.
    start=[max(p[0] for p in exterior),min(p[1] for p in exterior),exterior[0][2]]
    end=[min(p[0] for p in target),min(p[1] for p in target),target[0][2]]
    vest=next(o for o in geometry['objects'] if o['object_ref']=='WALK_VEST_W')
    west=min(p[0] for p in vest['vertices_world_m'])
    top=max(p[2] for p in vest['vertices_world_m'])
    points=[start,[west,start[1],start[2]],[west,start[1],top],end]
    triangles=[]
    for obj in geometry['objects']:
        vertices=obj['vertices_world_m']
        for face in obj['triangles_or_polygons']:
            triangles.extend(tuple(vertices[i] for i in (face[0],face[k],face[k+1]))
                             for k in range(1,len(face)-1))
    results={};cones={}
    for cid in ['CAM_EXT_CAR','CAM_EXT_CLEAR','CAM_W1']:
        origin=[cameras[cid]['camera_to_world'][i][3] for i in range(3)]
        cones[cid]=make_shadow_planes(origin,triangles)
        heights={str(h):visible_intervals(cameras[cid],triangles,points,h,cones[cid])
                 for h in HEIGHTS}
        union=merge([part for row in heights.values() for part in row['unoccluded_witness_intervals_s']])
        results[cid]={'by_witness_height_m':heights,'any_witness_intervals_s':union,
                      'last_static_witness_s':union[-1][1] if union else None,
                      'first_static_witness_s':union[0][0] if union else None}
    last=results['CAM_EXT_CAR']['last_static_witness_s']
    alternatives=[]
    for y in [min(p[1] for p in exterior),0.0,max(p[1] for p in exterior)]:
        route=[[start[0],y,start[2]],[west,y,start[2]],[west,y,top],end]
        length=sum(math.dist(a,b) for a,b in zip(route,route[1:],strict=False))
        intervals=merge([part for height in [1.5,1.7,1.9]
                         for part in visible_intervals(cameras['CAM_EXT_CAR'],triangles,route,height,
                                                       cones['CAM_EXT_CAR'])['unoccluded_witness_intervals_s']])
        loss=intervals[-1][1] if intervals else None
        before_distance=(loss-36)/3*length if loss is not None else None
        after_distance=length-before_distance if loss is not None else None
        bounds=speed_time_bounds(before_distance,length) if loss is not None else None
        lower=bounds[0] if bounds else None
        upper=min(38,bounds[1]) if bounds else None
        alternatives.append(dict(points_world_m=route,length_m=length,
            constant_arc_speed_m_s=length/3,constant_speed_t_L_s=loss,
            distance_to_last_visible_witness_m=before_distance,distance_after_loss_m=after_distance,
            feasibility_bounds_s={'lower':lower,'upper':upper},
            possible_t_L_range_under_0_8_to_1_5_m_s=[lower,upper] if lower is not None and lower<=upper else None,
            static_condition='FEASIBLE' if lower is not None and lower<=upper else 'INFEASIBLE'))
    body_checks={cid:body_sample_check(cameras[cid],triangles,points,cones[cid])
                 for cid in ['CAM_EXT_CAR','CAM_W1']}
    route_search=[]
    for start_y in [min(p[1] for p in exterior),0.0,max(p[1] for p in exterior)]:
        for end_y in sorted({min(p[1] for p in target),sum(p[1] for p in target)/len(target),max(p[1] for p in target)}):
            route=[[start[0],start_y,start[2]],[west,start_y,start[2]],[west,start_y,top],
                   [end[0],end_y,end[2]]]
            route_length=sum(math.dist(a,b) for a,b in zip(route,route[1:],strict=False))
            camera_rows={}
            for cid in ['CAM_EXT_CAR','CAM_W1']:
                heights={str(h):visible_intervals(cameras[cid],triangles,route,h,cones[cid])
                         for h in HEIGHTS}
                union=merge([part for row in heights.values() for part in row['unoccluded_witness_intervals_s']])
                camera_rows[cid]={'by_witness_height_m':heights,'any_witness_intervals_s':union,
                                 'all_centerline_witness_intervals_s':intersect_interval_sets(
                                     row['unoccluded_witness_intervals_s'] for row in heights.values())}
            car=camera_rows['CAM_EXT_CAR']['any_witness_intervals_s']
            w1=camera_rows['CAM_W1']['any_witness_intervals_s']
            loss=car[-1][1] if car else None;first=w1[0][0] if w1 else None
            loss_bounds=speed_time_bounds((loss-36)/3*route_length,route_length) if loss else None
            first_bounds=speed_time_bounds((first-36)/3*route_length,route_length) if first else None
            # Each bound is necessary separately; do not claim joint sufficiency.
            loss_possible=bool(loss_bounds and max(35,loss_bounds[0])<=min(38,loss_bounds[1]))
            first_possible=bool(first_bounds and first_bounds[1]>=38.4)
            route_search.append({'points_world_m':route,'length_m':route_length,
                'constant_speed_t_L_s':loss,'constant_speed_t_V_s':first,
                't_L_speed_bounds_s':loss_bounds,'t_V_speed_bounds_s':first_bounds,
                't_L_necessary_time_condition':loss_possible,'t_V_necessary_time_condition':first_possible,
                'both_time_conditions_not_refuted':loss_possible and first_possible,
                'cameras':camera_rows})
    after={k:sha(p) for k,p in paths.items()}
    if before!=after:raise ValueError('input bytes changed during static audit')
    length=sum(math.dist(a,b) for a,b in zip(points,points[1:],strict=False))
    return {'schema_version':'q-demo.r004-d92-static-projection.v1','input_sha256':before,
            'cards_file_sha256':before['cards'],'cards_head':CARDS_HEAD,'cards_pin_verified':True,'input_bytes_unchanged':True,
            'source_sha256':geometry['source_sha256'],'proposal_role':'DECLARED_PLANNING_POLYLINE_NOT_ACTOR_TRACK',
            'points_world_m':points,'source_range_s':[36,39],'arc_length_m':length,'speed_m_s':length/3,
            't_N_s':39,'required_t_L_range_s':[35,38],'t_L_static_witness_s':last,
            'static_witness_condition':'FEASIBLE' if last is not None and 35<=last<=38 else 'INFEASIBLE',
            'bounded_alternatives':alternatives,'cameras':results,'triangle_count':len(triangles),
            'method':'PINHOLE_FRUSTUM_AND_ANALYTIC_STATIC_TRIANGLE_SHADOW_INTERVALS',
            'actual_last_visible_time_s':None,'whole_person_visibility':'UNKNOWN',
            'declared_body_static_checks':body_checks,
            'D96_validation':{'scoring_status':'NONSCORING_PENDING_VALIDATION',
                'decision':'MAINTAIN_NONSCORING','required_t_V_earliest_s':38.4,
                'selected_t_V_necessary_condition':'FAIL',
                'bounded_route_search':route_search,'route_count':len(route_search),
                'routes_not_refuted_by_both_time_conditions':sum(row['both_time_conditions_not_refuted'] for row in route_search),
                'search_exhaustive':False,
                'limits':'Nine declared frozen-patch boundary/center polylines; no global route '
                         'impossibility, body surface, collision or actual observation claim.'},
            'actual_detector_or_tracking_last_observation':'UNKNOWN','collision':'UNKNOWN',
            'G4':'NOT_APPROVED_BY_THIS_CHECK','renderer_visibility_or_depth_read':False,
            'GT_or_actor_track_read':False,'render_performed':False,'product_inference_modified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-root',type=Path,required=True)
    parser.add_argument('--patches',type=Path,required=True)
    parser.add_argument('--cards',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit(args.static_root,args.patches,args.cards)
    with args.output.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
