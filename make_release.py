# Author-side: packs the public release. Only the AN/PVS-30's bundle ships (3DMA's licence allows free mods);
# the other items come as model-free templates plus build_models.py, which players run on their own purchases.
# Usage: python make_release.py  ->  dist/JustachaesClipOnSight-<version>.zip, laid out like the game folder.
import json, re, zipfile
from pathlib import Path

W = Path(__file__).resolve().parent
PVS22, CLIPONS, CONVERTER = W / 'pvs22', W / 'clipons', W / 'converter'
SHIPPED = 'ustachae_clipons/pvs30.bundle'
VERSION = re.search(r'Version \{ get; init; \} = new\("([^"]+)"\)', (PVS22 / 'ServerSource/PVS22Mod.cs').read_text(encoding='utf-8')).group(1)
MOD = 'SPT_Runtime/user/mods/UstAchae-PVS22/'
PLUGIN = 'BepInEx/plugins/UstAchae-PVS22/'


def main():
    files = {}
    for f in ('UstAchae.PVS22.dll', 'UstAchae.PVS22.deps.json', 'UstAchae.PVS22.runtimeconfig.json'):
        files[MOD + f] = (PVS22 / 'ServerSource/bin/Release' / f).read_bytes()
    files[PLUGIN + 'UstAchae.PVS22.Client.dll'] = (PVS22 / 'package/client/UstAchae.PVS22.Client.dll').read_bytes()
    manifest = []
    for package in (PVS22 / 'package', CLIPONS / 'package'):
        for f in (package / 'db').rglob('*.json'):
            files[MOD + 'db/' + f.relative_to(package / 'db').as_posix()] = f.read_bytes()
        listed = package / 'bundles.json'
        if listed.exists():
            manifest += [m for m in json.loads(listed.read_text(encoding='utf-8'))['manifest'] if m['key'] == SHIPPED]
    files[MOD + 'bundles/' + SHIPPED] = (CLIPONS / 'package/bundles' / SHIPPED).read_bytes()
    files[MOD + 'bundles.json'] = json.dumps({'manifest': manifest}, indent=2).encode()
    files[MOD + 'build_models.py'] = (CONVERTER / 'build_models.py').read_bytes()
    for f in sorted((CONVERTER / 'templates').glob('*.bundle.template')):
        files[MOD + 'templates/' + f.name] = f.read_bytes()
    assert len(manifest) == 1, manifest
    out = W / 'dist' / f'JustachaesClipOnSight-{VERSION}.zip'
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()): z.writestr(name, data)
    print('RELEASE', out, f'{out.stat().st_size / 1e6:.1f} MB')
    for name in sorted(files): print('  ', name)


if __name__ == '__main__':
    main()
