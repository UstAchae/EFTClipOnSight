# Installs the clip-on pack: the PVS-22 package (../pvs22/package) and this pipeline's package go into one
# server mod folder with a merged bundles.json, and the client plugin into BepInEx. Refuses while the SPT
# server or the game is running, since both lock files in these folders.
import json, shutil, subprocess
from pathlib import Path

W = Path(__file__).resolve().parent
ROOT = Path(r'D:/games/SPT-4.1.6')
MOD = ROOT / 'SPT_Runtime/user/mods/UstAchae-PVS22'
PLUGIN = ROOT / 'BepInEx/plugins/UstAchae-PVS22'
PVS22 = W.parent / 'pvs22'
CLIPONS = W / 'package'

running = subprocess.run(['tasklist'], capture_output=True, text=True).stdout
for exe in ('SPT.Server.exe', 'EscapeFromTarkov.exe'):
    if exe in running: raise SystemExit(f'{exe} is running; close it first')

def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    assert dst.read_bytes() == src.read_bytes()
    print('installed', dst.relative_to(ROOT))

for package in (PVS22 / 'package', CLIPONS):
    for f in (package / 'bundles').rglob('*.bundle'): copy(f, MOD / 'bundles' / f.relative_to(package / 'bundles'))
    for f in (package / 'db').rglob('*.json'): copy(f, MOD / 'db' / f.relative_to(package / 'db'))
for f in ('UstAchae.PVS22.dll', 'UstAchae.PVS22.deps.json', 'UstAchae.PVS22.runtimeconfig.json'):
    copy(PVS22 / 'ServerSource/bin/Release' / f, MOD / f)
copy(PVS22 / 'package/client/UstAchae.PVS22.Client.dll', PLUGIN / 'UstAchae.PVS22.Client.dll')

manifest = []
for package in (PVS22 / 'package', CLIPONS):
    manifest += json.loads((package / 'bundles.json').read_text(encoding='utf-8'))['manifest']
(MOD / 'bundles.json').write_text(json.dumps({'manifest': manifest}, indent=2), encoding='utf-8')
print('bundles.json', [m['key'] for m in manifest])
