# Author-side: writes the players' build scripts (build_pvs27.py, build_utc.py), one per mod whose model is not
# shipped. Each is a single file, so a player runs just the one in that mod's folder: its own header (what it
# needs, the purchase's files and their SHA-256, its bundles), then the shared parts (parts/common.py: reading the
# purchase, writing the templates) and the clip-on model part (parts/clipon.py). The header also carries the mod's
# version and reference.json: the SHA-256 of each bundle the script made from the author's own purchases (update it
# after changing a template or the processing), which the log compares a player's result with.
# Usage: python converter/make_scripts.py
import json, re
from pathlib import Path

W = Path(__file__).resolve().parent

BASE_DEPS = "['shaders', 'cubemaps', 'assets/systems/effects/opticsight/opticsightsmasks.bundle']"
THERMAL_DEPS = (BASE_DEPS[:-1] + ", 'assets/content/items/mods/scopes/scope_base_trijicon_reap-ir.bundle',\n"
                "        'assets/systems/effects/nightvision.bundle', 'assets/systems/effects/nightvision/mask_nv_textures']")

USAGE = '''Requirements: Python 3.10 or newer with `pip install UnityPy numpy Pillow`{extra}.

Usage, with the SPT server and the game closed, from this mod's folder (SPT_Runtime/user/mods/{folder}):
  python {script} <the path of the model's zip>{options}
The easiest way to give the path: type "python {script} " and drag the zip into the window. The folder holding
the zip works too, and without a path the script looks in this mod's folder. The zip may be renamed, not unzipped.
It writes the bundles into bundles/ and lists them in bundles.json; start the server and the item is there.
Everything it does goes into {log} next to it: attach that file to an issue if it fails.
'''

HEADS = {
    'pvs27': ('build_pvs27.py', '''"""Justachae's Clip-on Sight: AN/PVS-27 (black and FDE). Builds this mod's bundles from your own purchase of the model.

The model's licence does not allow sharing it, so this mod ships model-free templates (templates/); this script
reads the model you bought, turns it into the mesh and textures the mod uses and writes them into the templates.

Input: the PVS27 Magnum Universal Night Sight model from CGTrader
(https://www.cgtrader.com/3d-models/military/other/pvs27-magnum-universal-night-sight), its download unchanged
(not unzipped, name as downloaded):
  pvs27-magnum-universal-night-sight.zip

''' + USAGE.format(extra='', folder='UstAchae-ClipOnSight-PVS27', script='build_pvs27.py', options='', log='build_pvs27.log') + '''"""
# The purchase: the files used from its download ("inner.zip/path" for a zip inside it) with their SHA-256 (the
# processing was measured on exactly these files, so other versions are refused).
SOURCE = {'title': 'AN/PVS-27 (CGTrader)', 'archives': ['pvs27-magnum-universal-night-sight.zip'], 'files': {
    'obj': ('PVS27_nightvision_UPDATE_01.zip/separated_glass/PVS27_nightvision.obj', '87fe11eb166acddf099e25ccc84e37e1f1b4fe95f0241a791acd2e2e64a51e96'),
    'base': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_BaseColor.png', '826319c82990a64ba9708704e02d41abae6a30b67569de92360b00e694113e8f'),
    'normal': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Normal.png', '98262df6b1075bc7390c4ed4b15f9e3d356203f421aa6ed6ed1387fc523df198'),
    'rough': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Roughness.png', '17681fd87e02856643e2f2490e16f104decd56d4381a7e33a4eb739a03840ab0'),
    'metal': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Metallic.png', '751473eafb107d338b7fd7bbae7087d188e51ef7873b58776e5390935bbf4104'),
    'ao': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_ambient_occlusion.png', '62ca62d4e4131542457d2819ee8d6116e04e86abcb9c204e33d07a2b7c67b65a'),
    'fde_base': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_BaseColor.png', '962dbdfcd87a8c824127111af2e11eec4376a2548b19fa7374d0507506339a5c'),
    'fde_rough': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_Roughness.png', 'b3a58a4b0c8baacd42737e413cb71c6106e6fcc5d87436f89d3a796926afaea1'),
    'fde_metal': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_Metallic.png', '66909ba674a99fbaa24418b9b631577ee2f6c4a9ecbd38f45a8cf292c40f7626')}}

# The bundles: key, the template's mesh and textures to fill, dependencies.
KEY = 'pvs27'
MODELS = {'pvs27': {'bundle': 'ustachae_clipons/pvs27.bundle', 'mesh': 'mesh_ustachae_pvs27', 'deps': ''' + BASE_DEPS + ''',
                    'textures': ['albedo', 'spec', 'normal']},
          'pvs27_fde': {'bundle': 'ustachae_clipons/pvs27_fde.bundle', 'mesh': 'mesh_ustachae_pvs27_fde', 'deps': ''' + BASE_DEPS + ''',
                        'textures': ['albedo', 'spec', 'normal']}}

# How the model maps into the EFT mod frame (+Z toward the muzzle, +Y up, origin on the rail top at the middle of
# the mount), in the OBJ's own units: figures read off the source mesh (as in the author's clipons/items.py).
CLIPON = {
    'length_axis': 0, 'objective': -1, 'scale': 1.0, 'rail_y': 0.003, 'mount_centre': 0.016,
    'eyepiece': {'along': 0.0772, 'y': 0.0374, 'radius': 0.0233},
    'materials': {'PVS27_nightvision': 'body', 'PVS27_front_glass': 'drop', 'PVS27_lense': 'drop'},
    'objective_lens': {'y': 0.0399, 'radius': 0.0442, 'depth': (0.011, 0.0125)},
    'drop_depth': 0.0, 'normal_dx': False,
    'albedo_target': 0.03, 'sheen': 0.6,  # its near-black paint, lifted to 3% so details read
}
''', 'clipon.py'),
    'utc': ('build_utc.py', '''"""Justachae's Clip-on Sight: Trijicon UTC XII (black and FDE). Builds this mod's bundles from your own purchase of the model.

The model's licence does not allow sharing it, so this mod ships model-free templates (templates/); this script
reads the model you bought, turns it into the mesh and textures the mod uses and writes them into the templates.

Input: the UTCx Thermal Weapon Sight model from CGTrader
(https://www.cgtrader.com/3d-models/military/other/utcx-thermal-weapon-sight), its download unchanged (not
unzipped, name as downloaded):
  utcx-thermal-weapon-sight.zip

''' + USAGE.format(extra='', folder='UstAchae-ClipOnSight-UTC', script='build_utc.py', options='', log='build_utc.log') + '''"""
# The purchase: the files used from its download ("inner.zip/path" for a zip inside it) with their SHA-256 (the
# processing was measured on exactly these files, so other versions are refused).
SOURCE = {'title': 'UTC XII (CGTrader)', 'archives': ['utcx-thermal-weapon-sight.zip'], 'files': {
    'obj': ('UTCX2_thermal_scope_PACK.zip/UTCX2.obj', 'a08d67bcc24e679f2ec4b4f4a4f0b7627f35fd3827ed7b7be3f1e77879daa0e7'),
    'base': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_BaseColor.png', 'caf6eab75c31866d131edb3306213fce0142e34ff1edc36322b7994a0ccf1ed3'),
    'normal': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_Normal.png', 'a5fa5f2a503f7836c1ea7cf6ec2734f435229e41d1c08860372eba980fcbea67'),
    'rough': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_Roughness.png', '7a0186f4ad38e454e908ca5805a92d6783c3d3a063c5e93ebb5a7c5e00f2ee8f'),
    'metal': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_Metallic.png', 'ca4bfbc924abcc4bb41be9e36ee2985d3f07f8db1ffae32894bdafef9991268d'),
    'ao': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_ambient_occlusion.png', 'f5e5b68ae404bb4869c34a035fc5db37a6ae1a3d14d2a6b298223e717cf93556'),
    'fde_base': ('UTCX2_thermal_scope_PACK.zip/textures/FDE/UTCX2_BaseColor.png', '23bddc11e42acd6548f67a4593235fa12d7766982740fee7fda2e9c16c3e9ce0'),
    'fde_rough': ('UTCX2_thermal_scope_PACK.zip/textures/FDE/UTCX2_Roughness.png', 'd22afec8cb766bb97fd9d7fcf5cb656d1767b20af67f72e511e82a2a7cd1f632'),
    'fde_metal': ('UTCX2_thermal_scope_PACK.zip/textures/FDE/UTCX2_Metallic.png', '067dc4e1640a932aaf04cdef88d79a21f750d8614d2c72ac019ba0d956ce38fb')}}

# The bundles: key, the template's mesh and textures to fill, dependencies (the thermal picture uses the game's
# REAP-IR and night-vision effects).
KEY = 'utc'
MODELS = {'utc': {'bundle': 'ustachae_clipons/utc.bundle', 'mesh': 'mesh_ustachae_utc', 'deps': ''' + THERMAL_DEPS + ''',
                  'textures': ['albedo', 'spec', 'normal']},
          'utc_fde': {'bundle': 'ustachae_clipons/utc_fde.bundle', 'mesh': 'mesh_ustachae_utc_fde', 'deps': ''' + THERMAL_DEPS + ''',
                      'textures': ['albedo', 'spec', 'normal']}}

# How the model maps into the EFT mod frame (+Z toward the muzzle, +Y up, origin on the rail top at the middle of
# the mount), in the OBJ's own units: figures read off the source mesh (as in the author's clipons/items.py).
S = 0.158 / 0.6031  # the source is not to scale; real length 158 mm
CLIPON = {
    'length_axis': 0, 'objective': -1, 'scale': S, 'rail_y': 0.003 / S, 'mount_centre': -0.0016 / S,
    'eyepiece': {'along': 0.244 - 0.004 / S, 'y': 0.035 / S, 'radius': 0.0134 / S},
    'materials': {'UTCX2': 'body'},
    # The lens's widest surface (r 30.9 mm) is 10 mm in; the barrel is narrower further out.
    'objective_lens': {'y': 0.0514 / S, 'radius': 0.0309 / S, 'depth': (0.0075 / S, 0.0105 / S), 'disc': 0.0099 / S},
    'drop_depth': 0.001 / S, 'normal_dx': False,
}
''', 'clipon.py'),
}

TAIL = '''

if __name__ == '__main__':
    main()
'''


def script(key):
    name, head, part = HEADS[key]
    common = (W / 'parts/common.py').read_text(encoding='utf-8')
    model = (W / 'parts' / part).read_text(encoding='utf-8')
    version = re.search(r'Version \{ get; init; \} = new\("([^"]+)"\)', (W.parent / 'pvs22/ServerSource/PVS22Mod.cs').read_text(encoding='utf-8')).group(1)
    reference = json.loads((W / 'reference.json').read_text(encoding='utf-8'))
    facts = (f"MOD_VERSION = '{version}'\n"
             "# SHA-256 of the bundles this script made from the author's own purchase (the log compares yours with them).\n"
             f"REFERENCE = {json.dumps({k: reference[k] for k in (key, key + '_fde')}, indent=1)}\n")
    return name, head + facts + '\n' + common + '\n' + model.rstrip('\n') + '\n' + TAIL


if __name__ == '__main__':
    for key in HEADS:
        name, text = script(key)
        (W / name).write_text(text, encoding='utf-8')
        print('SCRIPT', name, len(text.splitlines()), 'lines')
