"""Compare procedural-gait root positions to the unchanged D124 route sampler."""
import argparse
import json
import math
from pathlib import Path

from r004_natural_walk import WalkPlan,norm,sub
from render_r004_d124 import ProducerError,route_pose


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scenario',type=Path,required=True)
    p.add_argument('--geometry',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    scenario=json.loads(a.scenario.read_text())
    geo=json.loads(a.geometry.read_text())
    count,maxerr,counts,failures=0,0.,{},[]
    for run in scenario['runs']:
        for actor in run['actors']:
            points=[]
            for w in actor['waypoints']:
                heights=[f['top_z_m'] for f in geo['floors'] if min(f['x_m'])<=w['xy'][0]<=max(f['x_m'])
                         and min(f['y_m'])<=w['xy'][1]<=max(f['y_m'])]
                points.append({**w,'z_m':w.get('z_m',max(heights) if heights else 0)})
            plan=WalkPlan(points)
            old=[{'planned_source_time_us':w['t_us'],'foot_anchor_world_m':[*w['xy'],w['z_m']]} for w in points]
            num=0
            for n in range(math.ceil(plan.times[0]*15),math.floor(plan.times[-1]*15)+1):
                # Float seconds at an exact endpoint can exceed integer source
                # microseconds by <1e-8us. Apply the same route endpoint clamp.
                us=min(old[-1]['planned_source_time_us'],max(old[0]['planned_source_time_us'],n*1e6/15))
                try:
                    pose=plan.pose(us/1e6)
                    pos,_=route_pose(old,us)
                    maxerr=max(maxerr,norm(sub(pos,pose['root'])))
                    num+=1
                    count+=1
                except (ValueError,ProducerError) as exc:
                    failures.append({'run':run['scenario'],'actor':actor['actor_id'],'source_time_us':us,'error':str(exc)})
            counts[run['scenario']+'/'+actor['actor_id']]=num
    result={'result':'PASS' if not failures and maxerr<1e-8 else 'FAIL','poses_checked':count,
            'per_actor_counts':counts,'max_root_position_delta_m':maxerr,'failures':failures,
            'scope':'Numerical root/IK feasibility only; not full-route mesh/clearance or gait aesthetic acceptance.'}
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return result['result']!='PASS'


if __name__=='__main__':
    raise SystemExit(main())
