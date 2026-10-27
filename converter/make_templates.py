# Author-side: turns the finished bundles into the model-free templates that ship with the mod. The model's
# mesh and textures are emptied (and the resource file that held the texture pixels is cleared); everything
# else (prefab, materials, shaders, markers, thermal data) is our own work and stays.
# Usage: python converter/make_templates.py  ->  converter/templates/<key>.bundle.template
import sys
from pathlib import Path
import UnityPy
from PIL import Image

W = Path(__file__).resolve().parent
sys.path.insert(0, str(W.parent / 'common'))
import game_refs as refs
from build_models import MODELS, write_texture

ROOT = W.parent


def strip(src, model):
    env = UnityPy.Environment()
    bundle = env.load_file(src.read_bytes(), name=model['bundle'])
    meshes = textures = 0
    for o in refs.objects(bundle):
        if o.type.name == 'Mesh' and o.read_typetree()['m_Name'] == model['mesh']:
            t = o.read_typetree()
            t['m_VertexData']['m_VertexCount'] = 0
            t['m_VertexData']['m_DataSize'] = b''
            t['m_IndexBuffer'] = []
            for s in t['m_SubMeshes']:
                s.update(firstByte=0, indexCount=0, firstVertex=0, vertexCount=0)
                s['localAABB'] = {'m_Center': {'x': 0.0, 'y': 0.0, 'z': 0.0}, 'm_Extent': {'x': 0.0, 'y': 0.0, 'z': 0.0}}
            o.save_typetree(t)
            meshes += 1
        elif o.type.name == 'Texture2D' and o.read().m_Name in model['textures']:
            write_texture(o, Image.new('RGBA', (4, 4), (128, 128, 128, 255)), size=4)
            textures += 1
    assert meshes == 1 and textures == len(model['textures']), (src, meshes, textures)
    # Every texture is now inline, so nothing reads the resource file any more: clear it.
    for name, f in list(bundle.files.items()):
        if str(name).endswith('.resS'):
            bundle.files[name] = refs.Stored(b'', getattr(f, 'flags', 0))
    return bundle.save(packer='lz4')


if __name__ == '__main__':
    out = W / 'templates'
    out.mkdir(exist_ok=True)
    for key, model in MODELS.items():
        src = ROOT / model['built']
        data = strip(src, model)
        (out / f'{key}.bundle.template').write_bytes(data)
        print('TEMPLATE', key, len(data))
