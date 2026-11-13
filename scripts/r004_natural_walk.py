"""Producer-only procedural walking. No detector, ranking or actor association imports.

Source-time/root positions remain piecewise linear. Gait is distance-driven;
planted feet have fixed world anchors, and limbs use two-link IK.
"""
from __future__ import annotations

import bisect
import math


def add(a, b):
    return tuple(x+y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x*s for x in a)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    length = norm(a)
    if length < 1e-12:
        raise ValueError('zero vector')
    return mul(a, 1/length)


def smooth(x):
    x = max(0., min(1., x))
    return x*x*(3-2*x)


def rotate(p, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return (c*p[0]-s*p[1], s*p[0]+c*p[1], p[2])


def two_link(start, end, upper, lower, pole=(1., 0., 0.)):
    """Exact two-link lengths; fail instead of silently stretching a limb."""
    delta = sub(end, start)
    length = norm(delta)
    if not abs(upper-lower)-1e-8 <= length <= upper+lower+1e-8:
        raise ValueError(f'unreachable limb: {length} outside {abs(upper-lower),upper+lower}')
    axis = unit(delta)
    perpendicular = sub(pole, mul(axis, dot(pole, axis)))
    if norm(perpendicular) < 1e-8:
        perpendicular = sub((0., 1., 0.), mul(axis, axis[1]))
    perpendicular = unit(perpendicular)
    along = (upper*upper-lower*lower+length*length)/(2*length)
    height = math.sqrt(max(0., upper*upper-along*along))
    return add(start, add(mul(axis, along), mul(perpendicular, height)))


class WalkPlan:
    stride_m = .95
    duty = .62

    # Preserve the first sample for later running design, without pretending its
    # double-support walking cycle is already a complete running gait.
    profiles = {
        'walk': {'stride_m': .85, 'duty': .55, 'foot_lift_m': .018, 'hip_flex_margin_m': .001,
                 'arm_swing_m': .080, 'body_pitch_rad': .012},
        'exaggerated_reference': {'stride_m': .95, 'duty': .62, 'foot_lift_m': .085, 'hip_flex_margin_m': .009,
                                 'arm_swing_m': .150, 'body_pitch_rad': .025},
    }

    def __init__(self, waypoints, profile='walk'):
        self.profile = self.profiles[profile]
        self.stride_m = self.profile['stride_m']
        self.duty = self.profile['duty']
        self.times = [w['t_us']/1e6 for w in waypoints]
        self.points = [(*map(float, w['xy']), float(w.get('z_m', 0))) for w in waypoints]
        if len(self.times) < 2 or any(b <= a for a,b in zip(self.times,self.times[1:])):
            raise ValueError('strictly increasing route times required')
        self.lengths = [norm(sub(b,a)) for a,b in zip(self.points,self.points[1:])]
        self.stations = [0.]
        for length in self.lengths:
            self.stations.append(self.stations[-1]+length)
        self.path_legs = [(self.stations[i], self.stations[i+1], self.points[i], self.points[i+1])
                          for i,length in enumerate(self.lengths) if length > 1e-9]
        if not self.path_legs:
            self.path_legs = [(0., 1., self.points[0], add(self.points[0], (1.,0.,0.)))]

    def at(self, time):
        time = max(self.times[0], min(self.times[-1], time))
        i = max(0, min(len(self.times)-2, bisect.bisect_right(self.times,time)-1))
        f = (time-self.times[i])/(self.times[i+1]-self.times[i])
        return add(self.points[i],mul(sub(self.points[i+1],self.points[i]),f)), self.stations[i]+f*self.lengths[i], i

    def path_at(self, station):
        for lo,hi,a,b in self.path_legs:
            if station <= hi:
                direction = unit(sub(b,a))
                return add(a,mul(direction,station-lo)), direction
        lo,hi,a,b = self.path_legs[-1]
        direction = unit(sub(b,a))
        return add(b,mul(direction,station-hi)), direction

    def yaw(self, time):
        # Symmetric heading blend only; never changes the route or event times.
        root,_,i = self.at(time)
        if self.lengths[i] < 1e-9:
            for j in range(i-1,-1,-1):
                if self.lengths[j] > 1e-9:
                    d = sub(self.points[j+1],self.points[j])
                    return math.atan2(d[1],d[0])
            return 0.
        before = self.at(time-.16)[0]
        after = self.at(time+.16)[0]
        d = sub(after,before)
        if norm(d) < 1e-9:
            d = sub(self.points[i+1],root)
        return math.atan2(d[1],d[0])

    def anchor(self, station, side):
        center,direction = self.path_at(station)
        yaw = math.atan2(direction[1],direction[0])
        return add(center, rotate((0., side*.09, .10),yaw)), yaw

    def pose(self, time):
        root,station,leg_index = self.at(time)
        yaw = self.yaw(time)
        speed = self.lengths[leg_index]/(self.times[leg_index+1]-self.times[leg_index])
        # Fade at route boundaries and actual holds; phase follows distance, not fps.
        lo,hi = leg_index,leg_index
        while lo > 0 and self.lengths[lo-1] > 1e-9:
            lo -= 1
        while hi+1 < len(self.lengths) and self.lengths[hi+1] > 1e-9:
            hi += 1
        fade = min(smooth((time-self.times[lo])/.28), smooth((self.times[hi+1]-time)/.28))
        weight = smooth(speed/.45)*fade if speed > 1e-9 else 0.
        cycle = station/self.stride_m
        feet = {}
        for side,offset in [(1,0.),(-1,.5)]:
            phase = cycle+offset
            step = math.floor(phase)
            fraction = phase-step
            contact = (step-offset)*self.stride_m+self.stride_m*self.duty/2
            first,fyaw = self.anchor(contact,side)
            support = fraction < self.duty
            if support:
                world = first
            else:
                u = (fraction-self.duty)/(1-self.duty)
                second,nyaw = self.anchor(contact+self.stride_m,side)
                s = u*u*u*(10-15*u+6*u*u)
                world = add(first,mul(sub(second,first),s))
                world = add(world,(0.,0.,self.profile['foot_lift_m']*math.sin(math.pi*u)**2))
                fyaw += math.atan2(math.sin(nyaw-fyaw),math.cos(nyaw-fyaw))*s
            local = rotate(sub(world,root),-yaw)
            neutral = (0.,side*.09,.10)
            local = add(neutral,mul(sub(local,neutral),weight))
            feet[side] = {'ankle':local,'yaw':math.atan2(math.sin(fyaw-yaw),math.cos(fyaw-yaw))*weight,
                          'support':support and weight > .999,'phase':fraction}
        # Rise over the planted leg, lower during double support. A constant low
        # pelvis would make both knees crouch throughout the cycle.
        hip_limits=[]
        for side,f in feet.items():
            x,y,z=f['ankle']
            horizontal_sq=x*x+(y-side*.09)**2
            if horizontal_sq>=.78**2:
                raise ValueError('gait horizontal reach exceeded')
            hip_limits.append(z+math.sqrt(.78**2-horizontal_sq))
        body_z=min(.88,min(hip_limits)-self.profile['hip_flex_margin_m']*weight)-.88
        legs,arms = {},{}
        for side,f in feet.items():
            hip = (0.,side*.09,.88+body_z)
            knee = two_link(hip,f['ankle'],.40,.38)
            foot = add(f['ankle'], rotate((.015,0.,-.05),f['yaw']))
            legs[side] = {**f,'hip':hip,'knee':knee,'foot':foot}
            phase = cycle+(0 if side==1 else .5)
            shoulder = (.014*weight,side*.19,1.36+body_z)
            wrist = (-self.profile['arm_swing_m']*math.sin(2*math.pi*phase)*weight,side*.20, .91+body_z)
            elbow = two_link(shoulder,wrist,.26,.24)
            arms[side] = {'shoulder':shoulder,'elbow':elbow,'wrist':wrist}
        return {'root':root,'yaw':yaw,'station':station,'speed':speed,'weight':weight,
                'body_z':body_z,'body_pitch':self.profile['body_pitch_rad']*weight,'legs':legs,'arms':arms}
