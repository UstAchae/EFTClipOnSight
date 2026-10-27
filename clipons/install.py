# The author's test install: the four clip-on mods with all their bundles (the author's own builds) and the shared
# client plugin. Refuses while the SPT server or the game is running, since both lock files in these folders.
# The earlier single-mod install (UstAchae-PVS22) holds the same items and is moved out of the way, into
# .codex-work/old_install_backup.
import json, shutil, subprocess, sys
from pathlib import Path

W = Path(__file__).resolve().parent
sys.path.insert(0, str(W.parent))
from mods import MODS, PLUGIN_DLL, PLUGIN_FOLDER, TOP_RAILS, server_files, manifest

ROOT = Path(r'D:/games/SPT-4.1.6')
MODS_DIR = ROOT / 'SPT_Runtime/user/mods'
PLUGINS = ROOT / 'BepInEx/plugins'
BACKUP = ROOT / '.codex-work/old_install_backup'

running = subprocess.run(['tasklist'], capture_output=True, text=True).stdout
for exe in ('SPT.Server.exe', 'EscapeFromTarkov.exe'):
    if exe in running: raise SystemExit(f'{exe} is running; close it first')

for old in (MODS_DIR / 'UstAchae-PVS22', PLUGINS / 'UstAchae-PVS22'):
    if old.exists():
        target = BACKUP / old.parent.name / old.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists(): shutil.rmtree(target)
        shutil.move(str(old), str(target))
        print('moved the old install', old.relative_to(ROOT), '->', target.relative_to(ROOT))


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    assert dst.read_bytes() == src.read_bytes()
    print('installed', dst.relative_to(ROOT))


for key, mod in MODS.items():
    folder = MODS_DIR / mod['folder']
    for name, src in server_files(key).items(): copy(src, folder / name)
    for src, name in mod['items'].items(): copy(src, folder / 'db/items' / name)
    copy(TOP_RAILS, folder / 'db/top_rails.json')
    for bundle, (src, _) in mod['bundles'].items(): copy(src, folder / 'bundles' / bundle)
    (folder / 'bundles.json').write_text(json.dumps(manifest(key, mod['bundles']), indent=2), encoding='utf-8')
copy(PLUGIN_DLL, PLUGINS / PLUGIN_FOLDER / PLUGIN_DLL.name)
