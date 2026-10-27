# Points each built clip-on's materials at the game's own p0 reflective shader and cubemap (Armasight Vulcan
# materials as property templates), copies the REAP-IR's thermal data into thermal sights, then writes
# package/bundles and the bundles.json entries. Usage: python finalize_clipons.py
import copy, json, sys
from pathlib import Path
import UnityPy
from items import ITEMS

W = Path(__file__).resolve().parent
sys.path.insert(0, str(W.parent / 'common'))
import game_refs as refs

GAME = Path(r'D:/games/SPT-4.1.6/EscapeFromTarkov_Data/StreamingAssets/Windows')
VULCAN = 'assets/content/items/mods/scopes/scope_base_armasight_vulcan_gen3_bravo_mg_3,5x.bundle'
REAP = 'assets/content/items/mods/scopes/scope_base_trijicon_reap-ir.bundle'
SHADER = 6014991791773097075  # p0/Reflective/Bumped Specular SMap, in the shaders bundle
TEMPLATES = {'body': 'scope_base_armasight_vulcan_gen3_bravo_mg_3,5x_LOD0',
             'linza': 'scope_base_armasight_vulcan_gen3_bravo_mg_3,5x_LOD0_linza'}
# Textured body: the maps carry colour, so the tint stays white; spec colour, _Glossness, _Specularness
# like the PVS-22's tuned body (glossier than the Vulcan's 0.71 / 1.82 / 1.09).
# Body: the Nightforce ATACR 7-35x56's body settings (tint, spec colour, _Glossness, _Specularness, reflection),
# on each model's own textures.
BODY = ((0.838, 0.838, 0.838), (1.0, 1.0, 1.0), 2.0, 1.0)
BODY_REFLECT = (0.471, 0.471, 0.471, 0.5)
# Objective glass: opaque, near black, strong cubemap reflection (same as the PVS-22).
GLASS = ((0.02, 0.02, 0.022), (1.0, 1.0, 1.0), 3.2, 2.4)
GLASS_REFLECT = (0.80, 0.85, 1.0, 1.0)
THERMAL_FIELDS = ['ThermalVisionIsGlitch', 'ThermalVisionIsPixelated', 'ThermalVisionIsNoisy', 'ThermalVisionIsMotionBlurred',
                  'ThermalVisionIsFpsStuck', 'ThermalVisionUtilities', 'StuckFPSUtilities', 'MotionBlurUtilities',
                  'GlitchUtilities', 'PixelationUtilities', 'ChromaticAberrationThermalShift', 'UnsharpBias', 'UnsharpRadiusBlur']
DEPENDENCIES = ['shaders', 'cubemaps', 'assets/systems/effects/opticsight/opticsightsmasks.bundle']
THERMAL_DEPENDENCIES = [REAP, 'assets/systems/effects/nightvision.bundle', 'assets/systems/effects/nightvision/mask_nv_textures']

env = UnityPy.Environment()
vulcan = env.load_file((GAME / VULCAN).read_bytes(), name='vulcan')
templates = {}
for o in refs.objects(vulcan):
    if o.type.name == 'Material':
        t = o.read_typetree()
        for kind, name in TEMPLATES.items():
            if t['m_Name'] == name: templates[kind] = (t, o.assets_file)
assert set(templates) == set(TEMPLATES)

reap = env.load_file((GAME / REAP).read_bytes(), name='reap')
reap_thermal = None
for o in refs.objects(reap):
    if o.type.name == 'MonoBehaviour' and o.read().m_Script.read().m_ClassName == 'ScopeThermalVisionData':
        reap_thermal = (o.read_typetree(), o.assets_file)
        break
assert reap_thermal

def rgba(c): return {'r': c[0], 'g': c[1], 'b': c[2], 'a': c[3]}

def remap(value, source, target):
    """Deep copy of a type tree value with every PPtr re-pointed from the source file at the target file."""
    if isinstance(value, dict):
        if set(value) == {'m_FileID', 'm_PathID'}:
            if not value['m_PathID']: return {'m_FileID': 0, 'm_PathID': 0}
            path = f'archive:/{source.name}/{source.name}' if value['m_FileID'] == 0 else source.externals[value['m_FileID'] - 1].path
            return {'m_FileID': refs.external_id(target, path), 'm_PathID': value['m_PathID']}
        return {k: remap(v, source, target) for k, v in value.items()}
    if isinstance(value, list): return [remap(v, source, target) for v in value]
    return copy.deepcopy(value)

def finalize_material(o, t, kind, look):
    template, source = templates['linza' if kind == 'linza' else 'body']
    own = dict(t['m_SavedProperties']['m_TexEnvs'])
    shader = template['m_Shader']
    t['m_Shader'] = {'m_FileID': refs.external_id(o.assets_file, source.externals[shader['m_FileID'] - 1].path), 'm_PathID': shader['m_PathID']}
    t['m_ValidKeywords'] = []; t['m_InvalidKeywords'] = []
    t['m_CustomRenderQueue'] = template['m_CustomRenderQueue']; t['stringTagMap'] = []; t['disabledShaderPasses'] = []
    props = copy.deepcopy(template['m_SavedProperties'])
    floats = dict(props['m_Floats']); colors = dict(props['m_Colors'])
    if look:
        color, spec, gloss, specular = look
        floats['_Glossness'] = gloss; floats['_Specularness'] = specular
        colors['_Color'] = rgba(color + (1.0,)); colors['_SpecColor'] = rgba(spec + (1.0,))
        if kind == 'glass': colors['_ReflectColor'] = rgba(GLASS_REFLECT)
        if kind == 'body': colors['_ReflectColor'] = rgba(BODY_REFLECT)
    props['m_Floats'] = list(floats.items()); props['m_Colors'] = list(colors.items())
    tex = []
    for slot, v in props['m_TexEnvs']:
        ref = v['m_Texture']; v = copy.deepcopy(v)
        mine = own.get(slot, {}).get('m_Texture', {'m_PathID': 0})
        if mine['m_PathID']: v['m_Texture'] = mine
        elif ref['m_FileID']:  # native shared texture (cubemap, optic masks): keep pointing at the game's copy
            v['m_Texture'] = {'m_FileID': refs.external_id(o.assets_file, source.externals[ref['m_FileID'] - 1].path), 'm_PathID': ref['m_PathID']}
        else: v['m_Texture'] = {'m_FileID': 0, 'm_PathID': 0}
        if slot == '_Cube' and kind == 'glass':
            # The game's crisp "metal" cubemap, as BRNVG's PVS-14 lenses use: a sharper reflection reads as glass.
            v['m_Texture'] = {'m_FileID': refs.external_id(o.assets_file, refs.CUBES), 'm_PathID': refs.METAL_CUBE}
        tex.append((slot, v))
    props['m_TexEnvs'] = tex
    t['m_SavedProperties'] = props
    o.save_typetree(t)


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

manifest = []
for key, cfg in ITEMS.items():
    bundle_key = f'ustachae_clipons/{key}.bundle'
    built = env.load_file((W / 'built' / bundle_key).read_bytes(), name=bundle_key)
    done = set()
    for o in refs.objects(built):
        if o.type.name == 'Material':
            t = o.read_typetree()
            kind = t['m_Name'].replace('mat_', '')  # CreateAsset renamed them after the asset file
            if kind in ('live', 'tube', 'blur'): continue  # keep their own shaders from the bundle
            if kind in ('glass', 'eyeglass', 'backstop'):  # our coated-lens shader
                point_lens_at_metal_cube(o, t); done.add(kind); continue
            finalize_material(o, t, kind, {'body': BODY, 'glass': GLASS}.get(kind))
            done.add(kind)
        elif o.type.name == 'MonoBehaviour' and cfg['thermal']:
            t = o.read_typetree()
            if 'ThermalVisionUtilities' not in t: continue
            source_tree, source_file = reap_thermal
            for field in THERMAL_FIELDS: t[field] = remap(source_tree[field], source_file, o.assets_file)
            t['ThermalVision'] = 1
            # The UTC XII against the REAP-IR it borrows from: 60 Hz (the REAP-IR is stuck at 35 fps), a quieter
            # sensor (NETD < 50 mK; half the noise), only a short microbolometer smear (motion blur 0.6 -> 0.2),
            # and none of the older sight's glitching. White hot (palette 2) stays as the REAP-IR has it.
            t['ThermalVisionIsFpsStuck'] = 0
            t['ThermalVisionIsGlitch'] = 0
            t['ThermalVisionUtilities']['NoiseParameters']['NoiseIntensity'] *= 0.5
            t['MotionBlurUtilities']['BlurAmount'] = 0.2
            assert t['ThermalVisionUtilities']['CurrentRampPalette'] == 2  # WhiteHot
            o.save_typetree(t)
            done.add('thermal')
    expected = {'body', 'glass', 'eyeglass', 'backstop'} | ({'thermal'} if cfg['thermal'] else set())  # no sight lens: not a sight
    assert done == expected, (key, done)

    out = W / 'package/bundles' / bundle_key
    out.parent.mkdir(parents=True, exist_ok=True)
    for name, f in list(built.files.items()):
        if str(name).endswith('.resS'): built.files[name] = refs.Stored(f.bytes, getattr(f, 'flags', 0))
    out.write_bytes(built.save(packer='lz4'))
    manifest.append({'key': bundle_key, 'dependencyKeys': DEPENDENCIES + (THERMAL_DEPENDENCIES if cfg['thermal'] else [])})

    check = UnityPy.Environment().load_file(out.read_bytes(), name=bundle_key)
    for o in refs.objects(check):
        if o.type.name == 'Material':
            t = o.read_typetree()
            if t['m_Name'] in ('mat_glass', 'mat_eyeglass', 'mat_backstop', 'mat_tube', 'mat_blur'):
                assert t['m_Shader']['m_FileID'] == 0 and t['m_Shader']['m_PathID'], 'own shader must be in the bundle'
            else:
                assert t['m_Shader']['m_FileID'] and o.assets_file.externals[t['m_Shader']['m_FileID'] - 1].path == refs.SHADERS
    print('CLIPON_FINALIZE_PASS', key, out.stat().st_size)

(W / 'package/bundles.json').write_text(json.dumps({'manifest': manifest}, indent=2), encoding='utf-8')
