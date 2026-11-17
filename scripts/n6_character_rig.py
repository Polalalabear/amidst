"""Producer-only articulated r004 mannequin; no scenario/route/GT inputs."""
import math

import bpy
from mathutils import Matrix, Vector


def neutral():
    legs, arms = {}, {}
    for s in (1, -1):
        legs[s] = dict(hip=(0,s*.09,.88), knee=(0,s*.09,.48),
                       ankle=(0,s*.09,.10), foot=(.015,s*.09,.05), yaw=0)
        arms[s] = dict(shoulder=(0,s*.19,1.36), elbow=(0,s*.19,1.10), wrist=(0,s*.19,.86))
    return dict(root=(0,0,0), yaw=0, body_z=0, body_pitch=0, legs=legs, arms=arms)


def build():
    from render_r004_natural_walk_sample import Person
    bpy.context.view_layer.update()
    root = bpy.data.objects['PRODUCTION_P1_ROOT']
    objects = [root] + list(root.children_recursive)
    for obj in objects:
        obj.animation_data_clear()
    adapter = Person(dict(root=root, objects=objects))
    adapter.apply(neutral())
    bpy.context.view_layer.update()
    data = bpy.data.armatures.new('N6_Skeleton')
    rig = bpy.data.objects.new('N6_Character', data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    definitions = [('root',(0,0,0),(0,0,.1),None),
                   ('pelvis',(0,0,.88),(0,0,1.03),'root'),
                   ('spine',(0,0,1.03),(0,0,1.36),'pelvis'),
                   ('neck',(0,0,1.36),(0,0,1.50),'spine'),
                   ('head',(0,0,1.50),(0,0,1.70),'neck')]
    for side,s in [('L',1),('R',-1)]:
        definitions += [
            (side+'_thigh',(0,s*.09,.88),(0,s*.09,.48),'pelvis'),
            (side+'_shin',(0,s*.09,.48),(0,s*.09,.10),side+'_thigh'),
            (side+'_foot',(0,s*.09,.10),(.15,s*.09,.10),side+'_shin'),
            (side+'_upper_arm',(0,s*.19,1.36),(0,s*.19,1.10),'spine'),
            (side+'_forearm',(0,s*.19,1.10),(0,s*.19,.86),side+'_upper_arm'),
            (side+'_hand',(0,s*.19,.86),(0,s*.19,.80),side+'_forearm')]
    for name,head,tail,parent in definitions:
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    mapping = {'HEAD':'head','NECK':'neck','TORSO':'spine','PELVIS':'pelvis'}
    for side in ('L','R'):
        for part,bone in [('THIGH','thigh'),('SHIN','shin'),('SHOE','foot'),
                          ('UPPER_ARM','upper_arm'),('FOREARM','forearm'),('HAND','hand')]:
            mapping[side+'_'+part] = side+'_'+bone
    meshes = [(obj,mapping[part]) for part,obj in adapter.parts.items()]
    meshes += [(obj,part[0]+('_shin' if 'KNEE' in part else '_forearm'))
               for part,obj in adapter.joints.items()]
    meshes += [(obj,'head' if obj.name.startswith(('D124_eye','D124_pupil','D124_nose')) else 'spine')
               for obj in objects if obj.type=='MESH' and obj.name.startswith('D124_')]
    for obj,bone in meshes:
        matrix = obj.matrix_world.copy()
        obj.parent = rig
        obj.matrix_world = matrix
        group = obj.vertex_groups.new(name=bone)
        group.add(list(range(len(obj.data.vertices))),1,'REPLACE')
        modifier = obj.modifiers.new('N6_Skin','ARMATURE')
        modifier.object = rig
        obj.name = 'N6_'+obj.name.split('PRODUCTION_P1_')[-1]
    bpy.context.view_layer.update()
    return rig,[obj for obj,_ in meshes]


def segment(rig,name,start,end):
    bone = rig.data.bones[name]
    direction = Vector(end)-Vector(start)
    assert abs(direction.length-bone.length)<1e-5,(name,direction.length,bone.length)
    rotation = (bone.tail_local-bone.head_local).normalized().rotation_difference(direction.normalized())
    rig.pose.bones[name].matrix = (Matrix.Translation(Vector(start)) @ rotation.to_matrix().to_4x4()
                                  @ bone.matrix_local.to_3x3().to_4x4())
    bpy.context.view_layer.update()


def apply(rig,pose):
    z = pose['body_z']
    for name in ('root','pelvis','spine','neck','head'):
        pb = rig.pose.bones[name]
        pb.matrix = Matrix.Translation((0,0,z if name!='root' else 0)) @ pb.bone.matrix_local
        bpy.context.view_layer.update()
    for side,s in [('L',1),('R',-1)]:
        leg,arm = pose['legs'][s],pose['arms'][s]
        for suffix,a,b in [('thigh','hip','knee'),('shin','knee','ankle')]:
            segment(rig,side+'_'+suffix,leg[a],leg[b])
        ankle = Vector(leg['ankle'])
        segment(rig,side+'_foot',ankle,ankle+Vector((.15,0,0)))
        for suffix,a,b in [('upper_arm','shoulder','elbow'),('forearm','elbow','wrist')]:
            segment(rig,side+'_'+suffix,arm[a],arm[b])
        wrist = Vector(arm['wrist'])
        segment(rig,side+'_hand',wrist,wrist+Vector((0,0,-.06)))


def articulation_probe(rig,meshes):
    rows = []
    for name,angles in [('L_upper_arm',(45,75)),('L_thigh',(35,55)),
                         ('L_shin',(60,110)),('L_forearm',(70,100))]:
        for degrees in angles:
            for pb in rig.pose.bones:
                pb.matrix_basis = Matrix.Identity(4)
            pb = rig.pose.bones[name]
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Matrix.Rotation(math.radians(degrees),4,'X').to_quaternion()
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            maximum = 0.
            for obj in meshes:
                evaluated = obj.evaluated_get(depsgraph)
                mesh = evaluated.to_mesh()
                for vertex in obj.data.vertices:
                    group = obj.vertex_groups[vertex.groups[0].group].name
                    transform = rig.pose.bones[group].matrix @ rig.data.bones[group].matrix_local.inverted()
                    expected = transform @ obj.matrix_world @ vertex.co
                    actual = evaluated.matrix_world @ mesh.vertices[vertex.index].co
                    maximum = max(maximum,(actual-expected).length)
                evaluated.to_mesh_clear()
            rows.append(dict(bone=name,flexion_degrees=degrees,max_skin_error_m=maximum))
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return rows
