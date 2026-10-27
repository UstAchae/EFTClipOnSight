# Writes package/db/pvs22.json: the item template (a 1x night-vision special scope), locales and the trader listing.
import json, copy
from pathlib import Path

W = Path(__file__).resolve().parent
DB = Path(r'D:/games/SPT-4.1.6/SPT_Runtime/SPT_Data/database/templates/items.json')
ITEM_ID = '67a0c0de5056532200000001'
BASE = '5b3b6e495acfc4330140bd88'  # Armasight Vulcan: a night-vision special scope
BUNDLE = 'ustachae_pvs22/an_pvs22.bundle'

items = json.loads(DB.read_text(encoding='utf-8-sig'))
t = copy.deepcopy(items[BASE])
t['_id'] = ITEM_ID
t['_name'] = 'ustachae_mount_an_pvs22'
t['_proto'] = BASE
p = t['_props']
p.update({
    'Name': 'AN/PVS-22', 'ShortName': 'PVS-22', 'Description': 'AN/PVS-22',
    'Prefab': {'path': BUNDLE, 'rcid': ''},
    'Weight': 0.86, 'Width': 2, 'Height': 1, 'Ergonomics': -9,
    'BackgroundColor': 'blue', 'RarityPvE': 'Superrare', 'CanSellOnRagfair': True,
    'Slots': [], 'ConflictingItems': [], 'ExamineExperience': 10, 'LootExperience': 10,
    # On its own it is a 1x night sight.
    'Zooms': [[1]], 'AimSensitivity': [[0.65]], 'CalibrationDistances': [[100]], 'SightingRange': 300,
    'ModesCount': [1], 'ScopesCount': 1, 'sightModType': 'optic',
})

locales = {
    'en': {'name': 'AN/PVS-22 Universal Night Sight',
           'shortName': 'AN/PVS-22',
           'description': 'A clip-on night sight for day scopes up to 12x. Mounted in line in front of the scope, '
                          'it turns the view through it into night vision while the scope keeps its own '
                          'magnification.'},
    'ch': {'name': 'AN/PVS-22 通用夜视瞄具',
           'shortName': 'AN/PVS-22',
           'description': '夹式夜视瞄具，适配最高 12 倍的白光瞄具。同轴装在白光瞄具前方后，'
                          '通过该瞄具看到的画面会变成夜视，倍率仍由白光瞄具提供。'},
}

catalog = {
    'item': t,
    'locales': locales,
    'handbookParentId': '5b5f749986f774094242f199',  # Special scopes (night vision / thermal)
    'price': 165000,
    'listing': {'traderId': '5935c25fb3acc3127c3d8cd9',  # Peacekeeper
                'currency': '5696686a4bdc2da3298b456a',  # USD
                'price': 1150, 'loyalty': 1, 'assortId': '67a0c0de5056532200000002'},
}
out = W / 'package/db'
out.mkdir(parents=True, exist_ok=True)
(out / 'pvs22.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding='utf-8')
print('wrote', out / 'pvs22.json')
