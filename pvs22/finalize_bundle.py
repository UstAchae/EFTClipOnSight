# Points the built materials at the game's own p0 reflective shader and cubemap, using the Armasight
# Vulcan body material as the property template, then writes package/bundles and bundles.json.
import copy, json, sys
from pathlib import Path
import UnityPy

W = Path(__file__).resolve().parent
sys.path.insert(0, str(W.parent / 'common'))
import game_refs as refs

GAME = Path(r'D:/games/SPT-4.1.6/EscapeFromTarkov_Data/StreamingAssets/Windows')
KEY = 'ustachae_pvs22/an_pvs22.bundle'
SHADER = 6014991791773097075  # p0/Reflective/Bumped Specular SMap, in the shaders bundle

# Body-type materials: linear tint, spec colour, _Glossness, _Specularness (p0 reflective shader).
# Effective albedo (texture x tint, after baked AO) is about 0.14 linear: matching the Vulcan's 0.09 read
# much darker than other items in game (user feedback), since the baked AO already darkens this model.
LOOK = {
    # Own tint (its generated textures are near white); spec, gloss and reflection from the Nightforce ATACR body.
    # Tints set so the rendered brightness sits with the PVS-27/PVS-30/UTC XII (it came out 2.6x brighter).
    'an_pvs22_body':   ((0.131, 0.135, 0.127), (1.0, 1.0, 1.0), 2.0, 1.0),
    'an_pvs22_label':  ((0.70, 0.70, 0.70), (0.25, 0.25, 0.25), 1.2, 0.35),
    'an_pvs22_text':   ((0.70, 0.70, 0.67), (0.20, 0.20, 0.20), 1.2, 0.30),
    'an_pvs22_rubber': ((0.128, 0.128, 0.128), (0.25, 0.25, 0.25), 1.2, 0.40),
    'an_pvs22_black':  ((0.160, 0.160, 0.165), (0.30, 0.30, 0.30), 1.3, 0.45),  # objective's central plug: dark grey cap, lit deep in the shade
}
# Lens glass: opaque and near black so the cubemap reflection and a tight highlight carry the look, like
# coated glass in photos of the real objective; opaque so the hollow inside of the tube never shows.
GLASS = ((0.02, 0.02, 0.022), (1.0, 1.0, 1.0), 3.2, 2.4)
GLASS_REFLECT = (0.80, 0.85, 1.0, 1.0)
# Materials on our coated-lens shader: the objective, the eyepiece glass and the black disc behind it.
LENSES = ('an_pvs22_glass', 'an_pvs22_eyeglass', 'an_pvs22_backstop')
TEMPLATES = {'body': 'scope_base_armasight_vulcan_gen3_bravo_mg_3,5x_LOD0',
             'linza': 'scope_base_armasight_vulcan_gen3_bravo_mg_3,5x_LOD0_linza'}

env = UnityPy.Environment()
vulcan = env.load_file((GAME / 'assets/content/items/mods/scopes/scope_base_armasight_vulcan_gen3_bravo_mg_3,5x.bundle').read_bytes(), name='vulcan')
templates = {}
for o in refs.objects(vulcan):
    if o.type.name == 'Material':
        t = o.read_typetree()
        for kind, name in TEMPLATES.items():
            if t['m_Name'] == name: templates[kind] = (t, o.assets_file)
assert set(templates) == set(TEMPLATES)
assert templates['body'][0]['m_Shader']['m_PathID'] == SHADER

def rgba(c): return {'r': c[0], 'g': c[1], 'b': c[2], 'a': c[3]}


def point_lens_at_metal_cube(o, t):
    """The coated-lens material keeps its own shader from the bundle; only its _Cube goes to the game's crisp
    metal cubemap (the one BRNVG's lenses reflect)."""
    tex = []
    for slot, v in t['m_SavedProperties']['m_TexEnvs']:
        if slot == '_Cube':
            v = dict(v); v['m_Texture'] = {'m_FileID': refs.external_id(o.assets_file, refs.CUBES), 'm_PathID': refs.METAL_CUBE}
        tex.append((slot, v))
    assert any(slot == '_Cube' for slot, _ in tex), 'lens material without _Cube'
    t['m_SavedProperties']['m_TexEnvs'] = tex
    o.save_typetree(t)

built = env.load_file((W / 'built' / KEY).read_bytes(), name=KEY)
done = set()
for o in refs.objects(built):
    if o.type.name != 'Material':
        continue
    t = o.read_typetree()
    name = t['m_Name'].replace('mat_', 'an_pvs22_')  # CreateAsset renamed them after the asset file
    if name in ('an_pvs22_tube', 'an_pvs22_blur'): continue  # keep their own shaders from the bundle
    if name in LENSES:
        point_lens_at_metal_cube(o, t); done.add(name); continue
    t['m_Name'] = name
    kind = 'linza' if name == 'an_pvs22_linza' else 'body'
    template, source = templates[kind]
    own = dict(t['m_SavedProperties']['m_TexEnvs'])
    shader = template['m_Shader']
    t['m_Shader'] = {'m_FileID': refs.external_id(o.assets_file, source.externals[shader['m_FileID'] - 1].path), 'm_PathID': shader['m_PathID']}
    t['m_ValidKeywords'] = []; t['m_InvalidKeywords'] = []
    t['m_CustomRenderQueue'] = template['m_CustomRenderQueue']; t['stringTagMap'] = []; t['disabledShaderPasses'] = []
    props = copy.deepcopy(template['m_SavedProperties'])
    floats = dict(props['m_Floats']); colors = dict(props['m_Colors'])
    if kind == 'body':
        color, spec, gloss, specular = GLASS if name == 'an_pvs22_glass' else LOOK[name]
        floats['_Glossness'] = gloss; floats['_Specularness'] = specular
        colors['_Color'] = rgba(color + (1.0,)); colors['_SpecColor'] = rgba(spec + (1.0,))
        if name == 'an_pvs22_glass': colors['_ReflectColor'] = rgba(GLASS_REFLECT)
        if name == 'an_pvs22_body': colors['_ReflectColor'] = rgba((0.471, 0.471, 0.471, 0.5))  # Nightforce ATACR
    props['m_Floats'] = list(floats.items()); props['m_Colors'] = list(colors.items())
    tex = []
    for slot, v in props['m_TexEnvs']:
        ref = v['m_Texture']; v = copy.deepcopy(v)
        mine = own.get(slot, {}).get('m_Texture', {'m_PathID': 0})
        if mine['m_PathID']: v['m_Texture'] = mine
        elif ref['m_FileID']:  # native shared texture (cubemap, optic masks): keep pointing at the game's copy
            v['m_Texture'] = {'m_FileID': refs.external_id(o.assets_file, source.externals[ref['m_FileID'] - 1].path), 'm_PathID': ref['m_PathID']}
        else: v['m_Texture'] = {'m_FileID': 0, 'm_PathID': 0}
        if slot == '_Cube' and name == 'an_pvs22_glass':
            # The game's crisp "metal" cubemap, as BRNVG's PVS-14 lenses use: a sharper reflection reads as glass.
            v['m_Texture'] = {'m_FileID': refs.external_id(o.assets_file, refs.CUBES), 'm_PathID': refs.METAL_CUBE}
        tex.append((slot, v))
    props['m_TexEnvs'] = tex
    t['m_SavedProperties'] = props
    o.save_typetree(t)
    done.add(name)
assert done == set(LOOK) | set(LENSES), done  # no sight lens: the clip-on is not a sight

out = W / 'package/bundles' / KEY
out.parent.mkdir(parents=True, exist_ok=True)
for name, f in list(built.files.items()):
    if str(name).endswith('.resS'):
        built.files[name] = refs.Stored(f.bytes, getattr(f, 'flags', 0))
out.write_bytes(built.save(packer='lz4'))
(W / 'package/bundles.json').write_text(json.dumps({'manifest': [{'key': KEY, 'dependencyKeys': ['shaders', 'cubemaps', 'assets/systems/effects/opticsight/opticsightsmasks.bundle']}]}, indent=2), encoding='utf-8')

# Read the output back: every material must now resolve to the native shader and cubemap files.
check = UnityPy.Environment().load_file(out.read_bytes(), name=KEY)
for o in refs.objects(check):
    if o.type.name == 'Material':
        t = o.read_typetree()
        if t['m_Name'].replace('mat_', 'an_pvs22_') in ('an_pvs22_tube', 'an_pvs22_blur') + LENSES:
            assert t['m_Shader']['m_FileID'] == 0 and t['m_Shader']['m_PathID'], 'own shader must be in the bundle'
            continue
        assert t['m_Shader']['m_FileID'] and o.assets_file.externals[t['m_Shader']['m_FileID'] - 1].path == refs.SHADERS
print('PVS22_FINALIZE_PASS', out, out.stat().st_size)
