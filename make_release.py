# Author-side: packs the four public mods, one zip each, laid out like the game folder. The AN/PVS-22 and AN/PVS-30
# ship their bundles; the AN/PVS-27 and UTC XII ship model-free templates and their build script instead, which
# players run on their own purchase. Every zip carries the same shared client plugin.
# Usage: python make_release.py  ->  dist/JustachaesClipOnSight-<mod>-<version>.zip
import json, re, zipfile
from pathlib import Path
from mods import MODS, PLUGIN_DLL, PLUGIN_FOLDER, TOP_RAILS, W, server_files, manifest

VERSION = re.search(r'Version \{ get; init; \} = new\("([^"]+)"\)', (W / 'pvs22/ServerSource/PVS22Mod.cs').read_text(encoding='utf-8')).group(1)
CONVERTER = W / 'converter'


def package(key, mod):
    folder = f'SPT_Runtime/user/mods/{mod["folder"]}/'
    files = {f'BepInEx/plugins/{PLUGIN_FOLDER}/{PLUGIN_DLL.name}': PLUGIN_DLL.read_bytes()}
    for name, src in server_files(key).items(): files[folder + name] = src.read_bytes()
    for src, name in mod['items'].items(): files[folder + 'db/items/' + name] = src.read_bytes()
    files[folder + 'db/top_rails.json'] = TOP_RAILS.read_bytes()
    if mod['shipped']:
        for bundle, (src, _) in mod['bundles'].items(): files[folder + 'bundles/' + bundle] = src.read_bytes()
        files[folder + 'bundles.json'] = json.dumps(manifest(key, mod['bundles']), indent=2).encode()
    else:
        files[folder + mod['script']] = (CONVERTER / mod['script']).read_bytes()
        for bundle in mod['bundles']:
            template = CONVERTER / 'templates' / (Path(bundle).stem + '.bundle.template')
            files[folder + 'templates/' + template.name] = template.read_bytes()
    return files


def main():
    out_dir = W / 'dist'
    out_dir.mkdir(exist_ok=True)
    for key, mod in MODS.items():
        files = package(key, mod)
        out = out_dir / f'JustachaesClipOnSight-{mod["server"]}-{VERSION}.zip'
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in sorted(files.items()): z.writestr(name, data)
        print('RELEASE', out.name, f'{out.stat().st_size / 1e6:.1f} MB')
        for name in sorted(files): print('  ', name)


if __name__ == '__main__':
    main()
