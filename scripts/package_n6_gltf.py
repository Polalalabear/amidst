"""Add standard material variants and an explicitly described embedded lightmap."""
import argparse
import colorsys
import copy
import json
import struct
from pathlib import Path

from n6_gait import duration


def read_glb(path):
    raw = path.read_bytes()
    assert struct.unpack_from('<4sII',raw)==(b'glTF',2,len(raw))
    size,kind = struct.unpack_from('<I4s',raw,12)
    assert kind==b'JSON'
    document = json.loads(raw[20:20+size])
    offset = 20+size
    n,kind = struct.unpack_from('<I4s',raw,offset)
    assert kind==b'BIN\0'
    return document,bytearray(raw[offset+8:offset+8+n])


def write_glb(path,document,binary):
    assert not path.exists()
    document['buffers'][0]['byteLength'] = len(binary)
    j = json.dumps(document,separators=(',',':')).encode()
    j += b' '*((-len(j))%4)
    b = bytes(binary)+b'\0'*((-len(binary))%4)
    path.write_bytes(struct.pack('<4sII',b'glTF',2,28+len(j)+len(b))
                     +struct.pack('<I4s',len(j),b'JSON')+j
                     +struct.pack('<I4s',len(b),b'BIN\0')+b)


def material_variant(original,variant):
    result = copy.deepcopy(original)
    name = original['name']
    result['name'] = variant+'_'+name
    pbr = result['pbrMetallicRoughness']
    if name=='PRODUCTION_P1_R004_SHIRT' and variant in ('B','C'):
        pbr['baseColorFactor'] = [*colorsys.hsv_to_rgb(.012 if variant=='B' else .62,.75,.65),1]
    if name=='MAT_BOTH_PERSONS_NEUTRAL' and variant!='T':
        pbr['baseColorFactor'] = [*{'A':(.65,.65,.65),'B':(.035,.055,.14),'C':(.65,.58,.4)}[variant],1]
    hidden = (name.startswith('D124_') and variant!='T') or (name=='N6_BAG' and variant!='B')
    if hidden:
        pbr['baseColorFactor'][3] = 0
        result['alphaMode'] = 'MASK'
        result['alphaCutoff'] = .5
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--stage',choices=['character','scene'],required=True)
    args = parser.parse_args()
    d,b = read_glb(args.root/(args.stage+'.raw.glb'))
    # Source scene custom properties include a historical preview clock. Only
    # explicitly authored asset metadata belongs in this runtime simulation pack.
    for scene in d.get('scenes',[]):
        scene.pop('extras',None)
    if args.stage=='character':
        assert {a['name'] for a in d['animations']}=={'walk','run','idle'}
        original_materials = copy.deepcopy(d['materials'])
        d['materials'] = [material_variant(m,v) for v in ('T','A','B','C') for m in original_materials]
        count = len(original_materials)
        d.setdefault('extensionsUsed',[]).append('KHR_materials_variants')
        d.setdefault('extensions',{})['KHR_materials_variants'] = {'variants':[{'name':n} for n in ('T','A','B','C')]}
        for mesh in d['meshes']:
            for primitive in mesh['primitives']:
                index = primitive['material']
                primitive.setdefault('extensions',{})['KHR_materials_variants'] = {
                    'mappings':[{'material':index+i*count,'variants':[i]} for i in range(4)]}
        processed = set()
        for animation in d['animations']:
            accessors = {s['input'] for s in animation['samplers']}
            for index in accessors:
                assert index not in processed,'Unexpected shared animation time accessor'
                processed.add(index)
                accessor = d['accessors'][index]
                assert accessor['type']=='SCALAR' and accessor['componentType']==5126
                view = d['bufferViews'][accessor['bufferView']]
                offset = view.get('byteOffset',0)+accessor.get('byteOffset',0)
                times = list(struct.unpack_from('<'+'f'*accessor['count'],b,offset))
                factor = duration(animation['name'])/max(times)
                times = [t*factor for t in times]
                struct.pack_into('<'+'f'*len(times),b,offset,*times)
                accessor['min'],accessor['max'] = [min(times)],[max(times)]
        d['asset']['extras'] = dict(n6Locomotion='In-place; +X forward; controller uses meters per second',
                                    walkSpeed=1.2,runSpeed=2.5,materialVariants=['T','A','B','C'])
    else:
        assert not d.get('animations') and not d.get('skins') and len(d['meshes'])==15
        d.setdefault('extensionsUsed',[]).append('KHR_materials_unlit')
        for material in d['materials']:
            texture = material.pop('emissiveTexture')
            material.pop('emissiveFactor',None)
            material['pbrMetallicRoughness'] = dict(baseColorTexture=texture,
                 baseColorFactor=[1,1,1,1],metallicFactor=0,roughnessFactor=1)
            material.setdefault('extensions',{})['KHR_materials_unlit'] = {}
        payload = (args.root/'lightmap_irradiance.exr').read_bytes()
        b.extend(b'\0'*((-len(b))%4))
        index = len(d['bufferViews'])
        d['bufferViews'].append(dict(buffer=0,byteOffset=len(b),byteLength=len(payload)))
        b.extend(payload)
        d['asset']['extras'] = dict(n6Lighting={
            'appearance':'AgX display-baked RGB in standard KHR_materials_unlit baseColorTexture; no additional lighting',
            'linearIrradiance':dict(bufferView=index,mimeType='image/x-exr',texCoord=1,
                                    encoding='Linear Rec.709 float16',bake='Cycles DIFFUSE direct+indirect, color disabled'),
            'usage':'Irradiance is an alternative lighting input; do not multiply it onto the already baked appearance'})
    write_glb(args.root/(args.stage+'.glb'),d,b)
    print(json.dumps(dict(stage=args.stage,size_bytes=(args.root/(args.stage+'.glb')).stat().st_size)))


if __name__=='__main__':
    main()
