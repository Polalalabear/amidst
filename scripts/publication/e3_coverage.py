"""Static source-mesh visibility for publication only; never runtime/scoring.

Opaque source triangles cast shadows onto three horizontal body-sample planes.
The static visibility region requires >=2 of 3 samples inside the calibrated
frustum and unobstructed. Dynamic actors are intentionally outside this map.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SCENE_SHA = 'cf9ef5135774fd215090b8448c8757bcf241d29e9bfdf44fabde728a3be7d4f3'
BOUNDS = (-15., 23., -10., 18.)
CELL = 0.05
HEIGHTS = (0.15, 0.9, 1.6)


def load_triangles(path: Path):
    """Read unmodified baked GLB, honoring accessors and full node transforms."""
    raw = path.read_bytes()
    magic, version, length = struct.unpack_from('<III', raw)
    assert magic == 0x46546C67 and version == 2 and length == len(raw)
    chunks = {}; offset = 12
    while offset < len(raw):
        n, kind = struct.unpack_from('<II', raw, offset); offset += 8
        chunks[kind] = raw[offset:offset+n]; offset += n
    gltf = json.loads(chunks[0x4E4F534A]); binary = chunks[0x004E4942]
    assert all(m.get('alphaMode', 'OPAQUE') == 'OPAQUE' and m.get('doubleSided') for m in gltf['materials'])
    types = {5121:'<u1', 5123:'<u2', 5125:'<u4', 5126:'<f4'}
    widths = {'SCALAR':1, 'VEC2':2, 'VEC3':3, 'VEC4':4}
    def accessor(index):
        a=gltf['accessors'][index]; v=gltf['bufferViews'][a['bufferView']]
        assert 'sparse' not in a and not a.get('normalized',False)
        dtype=np.dtype(types[a['componentType']]); width=widths[a['type']]
        offset=v.get('byteOffset',0)+a.get('byteOffset',0)
        return np.ndarray((a['count'],width),dtype=dtype,buffer=binary,offset=offset,
                          strides=(v.get('byteStride',dtype.itemsize*width),dtype.itemsize)).copy()
    def transform(node):
        if 'matrix' in node:return np.array(node['matrix'],float).reshape(4,4).T
        x,y,z,w=node.get('rotation',[0,0,0,1])
        rot=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                      [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                      [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
        m=np.eye(4);m[:3,:3]=rot@np.diag(node.get('scale',[1,1,1]));m[:3,3]=node.get('translation',[0,0,0]);return m
    arrays=[]; components=[]
    def visit(index,parent):
        node=gltf['nodes'][index];m=parent@transform(node)
        if 'mesh' in node:
            count=0
            for primitive in gltf['meshes'][node['mesh']]['primitives']:
                assert primitive.get('mode',4)==4
                vertices=accessor(primitive['attributes']['POSITION'])
                vertices=np.c_[vertices,np.ones(len(vertices))]@m.T
                # glTF Y-up -> Blender Z-up.
                vertices=vertices[:,[0,2,1]]*np.array([1,-1,1])
                indices=accessor(primitive['indices']).reshape(-1,3)
                arrays.append(vertices[indices]);count+=len(indices)
            components.append({'name':node.get('name'),'triangles':count})
        for child in node.get('children',[]):visit(child,m)
    for root in gltf['scenes'][gltf.get('scene',0)]['nodes']:visit(root,np.eye(4))
    return np.concatenate(arrays),components


def clip3(poly, z, above):
    out=[]
    if not poly:return out
    for a,b in zip(poly,poly[1:]+poly[:1]):
        va=(a[2]-z)*(1 if above else -1);vb=(b[2]-z)*(1 if above else -1)
        if va>=0:out.append(a)
        if (va>=0)!=(vb>=0):out.append(a+(b-a)*(va/(va-vb)))
    return out


def frustum_mask(camera,height):
    width=round((BOUNDS[1]-BOUNDS[0])/CELL);height_px=round((BOUNDS[3]-BOUNDS[2])/CELL)
    x=BOUNDS[0]+(np.arange(width)+.5)*CELL
    y=BOUNDS[3]-(np.arange(height_px)+.5)*CELL
    xx,yy=np.meshgrid(x,y)
    world=np.stack([xx,np.full_like(xx,height),-yy,np.ones_like(xx)],axis=-1)
    clip=world@(np.array(camera['projection_matrix'])@np.array(camera['world_to_camera'])).T
    return (clip[:,:,3]>0)&np.all(np.abs(clip[:,:,:3])<=clip[:,:,3,None],axis=-1)


def camera_position(camera):
    m=np.array(camera['camera_to_world']);return np.array([m[0,3],-m[2,3],m[1,3]])


def coverage(triangles,camera):
    origin=camera_position(camera)
    width=round((BOUNDS[1]-BOUNDS[0])/CELL);height_px=round((BOUNDS[3]-BOUNDS[2])/CELL)
    masks=[]
    for height in HEIGHTS:
        shadow=Image.new('1',(width,height_px));draw=ImageDraw.Draw(shadow)
        eligible=triangles[(triangles[:,:,2].min(axis=1)<origin[2]-1e-6)&(triangles[:,:,2].max(axis=1)>height+1e-5)]
        for triangle in eligible:
            poly=clip3(list(triangle),height+1e-5,True)
            poly=clip3(poly,origin[2]-1e-5,False)
            if len(poly)<3:continue
            projected=[]
            for vertex in poly:
                factor=(height-origin[2])/(vertex[2]-origin[2]);p=origin+(vertex-origin)*factor
                # Pixel centers are sample coordinates; Pillow draws at integer pixel centers.
                projected.append(((p[0]-BOUNDS[0])/CELL-.5,(BOUNDS[3]-p[1])/CELL-.5))
            draw.polygon(projected,fill=1)
        masks.append(frustum_mask(camera,height)&~np.asarray(shadow,dtype=bool))
    return np.sum(masks,axis=0)>=2


def section_segments(triangles,height=.9):
    segments=[]
    for tri in triangles:
        points=[]
        for a,b in zip(tri,np.roll(tri,-1,axis=0)):
            if (a[2]<height)!=(b[2]<height):points.append(a+(b-a)*((height-a[2])/(b[2]-a[2])))
        if len(points)==2:segments.append([points[0][:2].tolist(),points[1][:2].tolist()])
    return segments


def segment_blocked(triangles,origin,destination):
    """Independent exact, double-sided Moller-Trumbore segment test."""
    direction=destination-origin
    edge1=triangles[:,1]-triangles[:,0];edge2=triangles[:,2]-triangles[:,0]
    pvec=np.cross(np.broadcast_to(direction,edge2.shape),edge2)
    det=np.einsum('ij,ij->i',edge1,pvec);good=np.abs(det)>1e-10
    inv=np.divide(1.,det,out=np.zeros_like(det),where=good)
    tvec=origin-triangles[:,0]
    u=np.einsum('ij,ij->i',tvec,pvec)*inv
    qvec=np.cross(tvec,edge1)
    v=qvec@direction*inv
    t=np.einsum('ij,ij->i',edge2,qvec)*inv
    return bool(np.any(good&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-6)&(t<1-1e-5)))
