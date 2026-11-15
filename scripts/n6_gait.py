"""Periodic in-place gait, authored independently of all recorded trajectories."""
import math

from r004_natural_walk import two_link

PROFILES = {
    'walk': dict(speed_m_s=1.2, stride_m=1.05, duty=.60, lift_m=.065),
    'run': dict(speed_m_s=2.5, stride_m=1.60, duty=.38, lift_m=.24),
    'idle': dict(speed_m_s=0., stride_m=0., duty=1., lift_m=0.),
}


def duration(name):
    p = PROFILES[name]
    return p['stride_m']/p['speed_m_s'] if name!='idle' else 2.


def pose(name, phase):
    from n6_character_rig import neutral
    p = PROFILES[name]
    if name=='idle':
        result = neutral()
        result['body_z'] = .002*math.sin(2*math.pi*phase)
        for side in (1,-1):
            for point in ('shoulder','elbow','wrist'):
                a = result['arms'][side][point]
                result['arms'][side][point] = (a[0],a[1],a[2]+result['body_z'])
            result['legs'][side]['hip'] = (0,side*.09,.88+result['body_z'])
            hip, ankle = result['legs'][side]['hip'],result['legs'][side]['ankle']
            # Tiny breathing cannot extend a straight knee beyond its reach.
            result['legs'][side]['hip'] = (0,side*.09,min(hip[2],.879))
            result['legs'][side]['knee'] = two_link(result['legs'][side]['hip'],ankle,.40,.38)
        return result
    feet = {}
    for side,offset in ((1,0.),(-1,.5)):
        q = (phase+offset)%1.
        if q < p['duty']:
            x = p['stride_m']*(p['duty']/2-q)
            lift = 0.
        else:
            u = (q-p['duty'])/(1-p['duty'])
            # Hermite endpoint derivatives match the planted -speed slope.
            extent = p['stride_m']*p['duty']/2
            tangent = -p['stride_m']*(1-p['duty'])
            x = ((2*u**3-3*u**2+1)*(-extent)+(u**3-2*u**2+u)*tangent
                 +(-2*u**3+3*u**2)*extent+(u**3-u**2)*tangent)
            lift = p['lift_m']*math.sin(math.pi*u)**2
        feet[side] = dict(ankle=(x,side*.09,.10+lift),support=q<p['duty'])
    limit = min(f['ankle'][2]+math.sqrt(.78**2-f['ankle'][0]**2) for f in feet.values())
    height = min(.88 if name=='walk' else .90,limit-.008)
    legs,arms = {},{}
    for side in (1,-1):
        ankle = feet[side]['ankle']
        hip = (0,side*.09,height)
        knee = two_link(hip,ankle,.40,.38)
        legs[side] = dict(hip=hip,knee=knee,ankle=ankle,foot=(ankle[0]+.015,side*.09,ankle[2]-.05),yaw=0)
        shoulder = (.015 if name=='walk' else .045,side*.19,1.36+height-.88)
        angle = (.22 if name=='walk' else .55)*math.sin(2*math.pi*(phase+(.5 if side==1 else 0)))
        elbow = (shoulder[0]+.26*math.sin(angle),side*.19,shoulder[2]-.26*math.cos(angle))
        bend = .25 if name=='walk' else 1.35
        wrist = (elbow[0]+.24*math.sin(angle+bend),side*.19,elbow[2]-.24*math.cos(angle+bend))
        arms[side] = dict(shoulder=shoulder,elbow=elbow,wrist=wrist)
    return dict(root=(0,0,0),yaw=0,body_z=height-.88,body_pitch=0,legs=legs,arms=arms,
                supports={side:f['support'] for side,f in feet.items()})
