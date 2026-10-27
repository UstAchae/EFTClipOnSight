# Writes package/db/items/<key>.json for each clip-on: the item template (cloned from a native night-vision or
# thermal scope, then made a Mount: the clip-on is not a sight itself, the user's choice), locales and the trader
# listing. The server mod loads every file there.
import json, copy
from pathlib import Path
from items import ITEMS

W = Path(__file__).resolve().parent
DB = Path(r'D:/games/SPT-4.1.6/SPT_Runtime/SPT_Data/database/templates/items.json')
VULCAN = '5b3b6e495acfc4330140bd88'   # Armasight Vulcan: a night-vision special scope
REAP = '5a1eaa87fcdbcb001865f75e'     # Trijicon REAP-IR: a thermal special scope
PEACEKEEPER, USD = '5935c25fb3acc3127c3d8cd9', '5696686a4bdc2da3298b456a'
MOUNT = '55818b224bdc2dde698b456f'
SCOPE_ONLY = ['AdjustableOpticSensitivity', 'AdjustableOpticSensitivityMax', 'AimSensitivity', 'CalibrationDistances', 'CustomAimPlane', 'IsAdjustableOptic', 'MinMaxFov', 'ModesCount', 'ScopesCount', 'ZoomSensitivity', 'Zooms', 'sightModType']  # properties only sights have

CATALOG = {
    'pvs27': {
        'id': '67a0c0de5056532700000001', 'assort': '67a0c0de5056532700000002', 'base': VULCAN,
        'size': (2, 2), 'ergonomics': -13, 'price': 220000, 'usd': 1500,
        'en': ('AN/PVS-27 Magnum Universal Night Sight', 'AN/PVS-27',
               'A clip-on night sight with a fast F/1.0 catadioptric lens and a Gen 3 tube, built for sniper day '
               'scopes of 3x to 20x. Mounted in line in front of the scope, it turns the view through it into night '
               'vision while the scope keeps its own magnification.'),
        'ch': ('AN/PVS-27 MUNS 马格南通用夜视瞄具', 'AN/PVS-27',
               '夹式夜视瞄具，采用 F/1.0 折反射物镜和三代像增强管，适配 3 到 20 倍的狙击白光瞄具。'
               '同轴装在白光瞄具前方后，通过该瞄具看到的画面会变成夜视，倍率仍由白光瞄具提供。'),
    },
    'pvs30': {
        'id': '67a0c0de5056533000000001', 'assort': '67a0c0de5056533000000002', 'base': VULCAN,
        'size': (3, 1), 'ergonomics': -12, 'price': 240000, 'usd': 1650,
        'en': ('AN/PVS-30 Clip-on Sniper Night Sight', 'AN/PVS-30',
               "Knight's Armament clip-on sniper night sight with a 120 mm refractive telephoto lens, rated for "
               'recoil up to .50 calibre and day scopes up to 20x. Mounted in line in front of the scope, it turns '
               'the view through it into night vision while the scope keeps its own magnification.'),
        'ch': ('AN/PVS-30 夹式狙击夜视瞄具', 'AN/PVS-30',
               "Knight's Armament 夹式狙击夜视瞄具，120 mm 折射式长焦物镜，可承受最高 .50 口径的后坐力，"
               '适配最高 20 倍的白光瞄具。同轴装在白光瞄具前方后，通过该瞄具看到的画面会变成夜视，'
               '倍率仍由白光瞄具提供。'),
    },
    'utc': {
        'id': '67a0c0de50565c1200000001', 'assort': '67a0c0de50565c1200000002', 'base': REAP,
        'size': (2, 1), 'ergonomics': -6, 'price': 380000, 'usd': 2600,
        'en': ('Trijicon UTC XII Universal Thermal Clip-on', 'UTC XII',
               'Trijicon/OASYS clip-on thermal sight with a 640x480, 12 micron uncooled sensor running at 60 Hz, '
               'for day scopes up to 10x. Mounted in line in front of the scope, it turns the view through it into '
               'white-hot thermal while the scope keeps its own magnification.'),
        'ch': ('Trijicon UTC XII 通用夹式热成像瞄具', 'UTC XII',
               'Trijicon/OASYS 夹式热成像瞄具，640x480、12 微米非制冷传感器，刷新率 60 Hz，适配最高 10 倍的白光瞄具。'
               '同轴装在白光瞄具前方后，通过该瞄具看到的画面会变成白热热成像，倍率仍由白光瞄具提供。'),
    },
}

# FDE variants: same item and listing data under new ids, with a colour suffix on the names.
for key, item_id, assort_id in (('pvs27', '67a0c0de5056532700000003', '67a0c0de5056532700000004'),
                                ('utc', '67a0c0de50565c1200000003', '67a0c0de50565c1200000004')):
    c = dict(CATALOG[key], id=item_id, assort=assort_id)
    name, short, desc = c['en']; c['en'] = (name + ' (FDE)', short + ' FDE', desc)
    name, short, desc = c['ch']; c['ch'] = (name + '（沙色）', short + ' 沙色', desc)
    CATALOG[key + '_fde'] = c

items = json.loads(DB.read_text(encoding='utf-8-sig'))
out = W / 'package/db/items'
out.mkdir(parents=True, exist_ok=True)
for key, c in CATALOG.items():
    cfg = ITEMS[key]
    t = copy.deepcopy(items[c['base']])
    t['_id'] = c['id']; t['_name'] = f'ustachae_mount_{key}'; t['_proto'] = c['base']; t['_parent'] = MOUNT
    for k in SCOPE_ONLY: t['_props'].pop(k, None)
    t['_props'].update({
        'Name': c['en'][1], 'ShortName': c['en'][1], 'Description': c['en'][1],
        'Prefab': {'path': f'ustachae_clipons/{key}.bundle', 'rcid': ''},
        'Weight': cfg['weight'], 'Width': c['size'][0], 'Height': c['size'][1], 'Ergonomics': c['ergonomics'],
        'BackgroundColor': 'blue', 'RarityPvE': 'Superrare', 'CanSellOnRagfair': True,
        'Slots': [], 'ConflictingItems': [], 'ExamineExperience': 10, 'LootExperience': 10,
        'CoolFactor': 1, 'HeatFactor': 1,
    })
    locales = {lang: {'name': n, 'shortName': s, 'description': d}
               for lang, (n, s, d) in (('en', c['en']), ('ch', c['ch']))}
    catalog = {'item': t, 'locales': locales,
               'handbookParentId': '5b5f749986f774094242f199',  # Special scopes (night vision / thermal)
               'price': c['price'],
               'listing': {'traderId': PEACEKEEPER, 'currency': USD, 'price': c['usd'], 'loyalty': 1, 'assortId': c['assort']}}
    (out / f'{key}.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding='utf-8')
    print('wrote', out / f'{key}.json')
