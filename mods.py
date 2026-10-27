# The four mods the clip-ons are published as (one clip-on each, the user's choice): what goes into each server
# mod folder. Used by clipons/install.py (the author's own test install), make_release.py (the public packages)
# and converter/make_templates.py. All four share one client plugin, which every package carries at the same path.
from pathlib import Path

W = Path(__file__).resolve().parent
PVS22, CLIPONS = W / 'pvs22', W / 'clipons'

BASE_DEPS = ['shaders', 'cubemaps', 'assets/systems/effects/opticsight/opticsightsmasks.bundle']
THERMAL_DEPS = BASE_DEPS + ['assets/content/items/mods/scopes/scope_base_trijicon_reap-ir.bundle',
                            'assets/systems/effects/nightvision.bundle', 'assets/systems/effects/nightvision/mask_nv_textures']

PLUGIN_FOLDER = 'UstAchae-ClipOnSight'
PLUGIN_DLL = PVS22 / 'package/client/UstAchae.ClipOnSight.Client.dll'
TOP_RAILS = PVS22 / 'package/db/top_rails.json'

# key: the mod's folder and title; its items (catalog file -> name under db/items/), bundles (bundle key ->
# where the author's build puts it, and its dependencies), whether the bundle may be published (the AN/PVS-22's
# TurboSquid licence allows game mods in an engine's own format, the AN/PVS-30's 3DMA licence free mods; the
# CGTrader models' terms are read strictly), and, for the others, the player's build script.
MODS = {
    'pvs22': {'folder': 'UstAchae-ClipOnSight-PVS22', 'title': 'AN/PVS-22', 'server': 'PVS22',
              'items': {PVS22 / 'package/db/pvs22.json': 'pvs22.json'},
              'bundles': {'ustachae_pvs22/an_pvs22.bundle': (PVS22 / 'package/bundles/ustachae_pvs22/an_pvs22.bundle', BASE_DEPS)},
              'shipped': True, 'script': None},
    'pvs27': {'folder': 'UstAchae-ClipOnSight-PVS27', 'title': 'AN/PVS-27', 'server': 'PVS27',
              'items': {CLIPONS / 'package/db/items/pvs27.json': 'pvs27.json', CLIPONS / 'package/db/items/pvs27_fde.json': 'pvs27_fde.json'},
              'bundles': {'ustachae_clipons/pvs27.bundle': (CLIPONS / 'package/bundles/ustachae_clipons/pvs27.bundle', BASE_DEPS),
                          'ustachae_clipons/pvs27_fde.bundle': (CLIPONS / 'package/bundles/ustachae_clipons/pvs27_fde.bundle', BASE_DEPS)},
              'shipped': False, 'script': 'build_pvs27.py'},
    'pvs30': {'folder': 'UstAchae-ClipOnSight-PVS30', 'title': 'AN/PVS-30', 'server': 'PVS30',
              'items': {CLIPONS / 'package/db/items/pvs30.json': 'pvs30.json'},
              'bundles': {'ustachae_clipons/pvs30.bundle': (CLIPONS / 'package/bundles/ustachae_clipons/pvs30.bundle', BASE_DEPS)},
              'shipped': True, 'script': None},
    'utc': {'folder': 'UstAchae-ClipOnSight-UTC', 'title': 'UTC XII', 'server': 'UTC',
            'items': {CLIPONS / 'package/db/items/utc.json': 'utc.json', CLIPONS / 'package/db/items/utc_fde.json': 'utc_fde.json'},
            'bundles': {'ustachae_clipons/utc.bundle': (CLIPONS / 'package/bundles/ustachae_clipons/utc.bundle', THERMAL_DEPS),
                        'ustachae_clipons/utc_fde.bundle': (CLIPONS / 'package/bundles/ustachae_clipons/utc_fde.bundle', THERMAL_DEPS)},
            'shipped': False, 'script': 'build_utc.py'},
}


def server_files(key):
    """The server mod's assembly files: name in the mod folder -> built file."""
    out = PVS22 / 'ServerSource/bin/Release' / key
    name = f'UstAchae.ClipOnSight.{MODS[key]["server"]}'
    return {f'{name}{ext}': out / f'{name}{ext}' for ext in ('.dll', '.deps.json', '.runtimeconfig.json')}


def manifest(key, bundles):
    """bundles.json for the given bundle keys of a mod."""
    return {'manifest': [{'key': b, 'dependencyKeys': MODS[key]['bundles'][b][1]} for b in bundles]}
