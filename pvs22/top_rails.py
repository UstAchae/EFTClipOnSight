# Writes package/db/top_rails.json: for every vanilla item with rail slots, which of them sit straight on top,
# judged from the slot node positions in the item's prefab: {item: {slot: on top}}. Modded items (and vanilla
# items with slots other mods add) come from the server's unmeasured_rails.json, written at its last start,
# and are measured from their bundles in the mod folders; whatever still can't be measured falls back to
# name rules on the server.
# What a slot accepts is decided by the server at load time, after other mods have added their entries:
# handguard slots taking a red dot or a scope mount, and any slot taking the NcStar MPR45 backup rail, whose
# places the user chose as the reference for where a clip-on belongs. Slot names don't say where a rail is
# (the Zenit B-10's mod_tactical is a side rail), and slot nodes all share one rotation, so position is the
# only reliable signal. Modded items fall back to name rules on the server.
import json, collections
from pathlib import Path
import numpy as np
import UnityPy

W = Path(__file__).resolve().parent
ITEMS = Path(r'D:/games/SPT-4.1.6/SPT_Runtime/SPT_Data/database/templates/items.json')
GAME = Path(r'D:/games/SPT-4.1.6/EscapeFromTarkov_Data/StreamingAssets/Windows')
MODS = Path(r'D:/games/SPT-4.1.6/SPT_Runtime/user/mods')
UNMEASURED = MODS / 'UstAchae-PVS22/unmeasured_rails.json'
RAIL_SLOTS = ('mod_scope', 'mod_mount', 'mod_tactical', 'mod_sight')  # same prefixes as PVS22Mod.cs

items = json.loads(ITEMS.read_text(encoding='utf-8'))

def rotate(q, v):
    u, w = np.array(q[:3]), q[3]
    return 2 * u.dot(v) * u + (w * w - u.dot(u)) * v + 2 * w * np.cross(u, v)

def slot_positions(bundle, names):
    """Slot node positions in the prefab root's frame (x across, y up, z along the barrel)."""
    pos = {}
    for o in UnityPy.load(str(bundle)).objects:
        if o.type.name != 'Transform': continue
        t = o.read(); name = t.m_GameObject.read().m_Name
        if name not in names or name in pos: continue
        p = np.zeros(3)
        while True:
            q, lp, s = t.m_LocalRotation, t.m_LocalPosition, t.m_LocalScale
            p = rotate((q.x, q.y, q.z, q.w), p * np.array([s.x, s.y, s.z])) + np.array([lp.x, lp.y, lp.z])
            if not t.m_Father or t.m_Father.path_id == 0: break
            t = t.m_Father.read()
        pos[name] = p
    return pos

top, rejected = collections.defaultdict(dict), []

def measure(k, v, bundle):
    slots = v['_props']['Slots']
    rails = [s['_name'] for s in slots if s['_name'].startswith(RAIL_SLOTS)]
    pos = slot_positions(bundle, {s['_name'] for s in slots})
    highest = max((p[1] for p in pos.values() if abs(p[0]) < 0.006), default=None)
    for name in rails:
        p = pos.get(name)
        if p is None: continue  # no node for it in this model (a slot another mod added): left to the server's fallback
        # On the centreline and the highest rail level (within 1 cm of the top-most centred slot), and either
        # 2 cm above the lowest other slot (origins differ between items) or on an item whose slots all run
        # along that same top line (gas-tube rails, scout mounts, receiver top rails).
        others = [q for m, q in pos.items() if m != name]
        lowest = min((q[1] for q in others), default=-0.02)
        one_line = p is not None and all(abs(q[0]) < 0.006 and abs(q[1] - p[1]) < 0.01 for q in others)
        if p is not None and abs(p[0]) < 0.006 and p[1] > highest - 0.01 and (p[1] > lowest + 0.02 or one_line):
            top[k][name] = True
        else:
            top[k][name] = False
            rejected.append((v['_name'], name, p.round(3).tolist()))

def has_rails(v):
    return any(s['_name'].startswith(RAIL_SLOTS) for s in v['_props'].get('Slots') or [])

for k, v in items.items():
    if v.get('_type') != 'Item' or not has_rails(v): continue
    path = v['_props'].get('Prefab', {}).get('path')
    if path and (GAME / path).exists(): measure(k, v, GAME / path)
vanilla = len(top)

# Modded items, by the prefab path the server reported: a bundle in some mod's bundles folder, or the
# game's own when a clone reuses a vanilla model.
mod_bundles = {}
for b in MODS.glob('*/**/*.bundle'):
    rel = b.relative_to(MODS).as_posix()
    if '/bundles/' in rel: mod_bundles.setdefault(rel.split('/bundles/', 1)[1], b)
missing = []
if UNMEASURED.exists():
    for k, v in json.loads(UNMEASURED.read_text(encoding='utf-8')).items():
        if not has_rails(v): continue
        path = (v['_props'].get('Prefab') or {}).get('path')
        bundle = mod_bundles.get(path) or (GAME / path if path and (GAME / path).exists() else None)
        if bundle is None: missing.append((v.get('_name'), path)); continue
        try: measure(k, v, bundle)
        except Exception as e: missing.append((v.get('_name'), f'{path}: {e}'))

out = W / 'package/db/top_rails.json'
out.write_text(json.dumps(dict(sorted(top.items())), indent=1), encoding='utf-8')
for m in missing: print('UNMEASURED', *m)
print('TOP_RAILS', sum(sum(v.values()) for v in top.values()), 'top slots of', sum(map(len, top.values())), 'rail slots on',
      len(top), 'items', f'({vanilla} vanilla, {len(top) - vanilla} modded; {len(missing)} modded without a bundle) ->', out)
