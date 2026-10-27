"""Justachae's Clip-on Sight: builds the clip-on bundles from your own purchased models.

The mod ships with model-free templates (templates/*.bundle.template). This script reads the models you bought,
turns them into the mesh and textures the mod uses, and writes them into those templates, giving the finished
bundles in bundles/. It also adds them to bundles.json, so the server loads those items. Items whose bundle has
not been built stay disabled.

Models (buy the ones you want; each enables its items):
  AN/PVS-22           PVS-22_obj.zip and PVS-22_3ds.zip      https://www.turbosquid.com/3d-models/an-pvs-22-519395
  AN/PVS-27 (+ FDE)   pvs27-magnum-universal-night-sight.zip https://www.cgtrader.com/3d-models/military/other/pvs27-magnum-universal-night-sight
  UTC XII (+ FDE)     utcx-thermal-weapon-sight.zip          https://www.cgtrader.com/3d-models/military/other/utcx-thermal-weapon-sight
(The AN/PVS-30 bundle ships with the mod.)

Requirements: Python 3.10+ with `pip install UnityPy numpy Pillow`; for the PVS-22 also Blender 4.1 or newer.

Usage, with the server and the game closed:
  python build_models.py <folder with the downloaded zips> [--blender <path to blender.exe>]
Run it from the mod folder (SPT_Runtime/user/mods/UstAchae-PVS22), or pass --mod <that folder>.
"""
import argparse, hashlib, io, json, math, shutil, struct, subprocess, sys, tempfile, zipfile
from pathlib import Path

try:
    import bpy  # noqa: F401  (inside Blender: only the PVS-22 bake below runs)
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

if not IN_BLENDER:
    import numpy as np
    from PIL import Image
    import UnityPy
    from UnityPy.export import Texture2DConverter


# ----------------------------------------------------------------------------------------------------------
# What gets built
# ----------------------------------------------------------------------------------------------------------

BASE_DEPS = ['shaders', 'cubemaps', 'assets/systems/effects/opticsight/opticsightsmasks.bundle']
THERMAL_DEPS = BASE_DEPS + ['assets/content/items/mods/scopes/scope_base_trijicon_reap-ir.bundle',
                            'assets/systems/effects/nightvision.bundle', 'assets/systems/effects/nightvision/mask_nv_textures']
PVS22_TEXTURES = ['metal_albedo', 'metal_spec', 'metal_normal', 'rubber_albedo', 'rubber_spec', 'rubber_normal', 'label']
CLIPON_TEXTURES = ['albedo', 'spec', 'normal']

# Each bundle: its key, the purchase it needs, the model mesh and textures in it, and its dependencies.
# `built` is where the author's own build puts the finished bundle (used to make the templates).
MODELS = {
    'pvs22': {'bundle': 'ustachae_pvs22/an_pvs22.bundle', 'source': 'pvs22', 'deps': BASE_DEPS,
              'built': 'pvs22/package/bundles/ustachae_pvs22/an_pvs22.bundle',
              'mesh': 'mesh_an_pvs22', 'textures': PVS22_TEXTURES},
    'pvs27': {'bundle': 'ustachae_clipons/pvs27.bundle', 'source': 'pvs27', 'deps': BASE_DEPS,
              'built': 'clipons/package/bundles/ustachae_clipons/pvs27.bundle',
              'mesh': 'mesh_ustachae_pvs27', 'textures': CLIPON_TEXTURES},
    'pvs27_fde': {'bundle': 'ustachae_clipons/pvs27_fde.bundle', 'source': 'pvs27', 'deps': BASE_DEPS,
                  'built': 'clipons/package/bundles/ustachae_clipons/pvs27_fde.bundle',
                  'mesh': 'mesh_ustachae_pvs27_fde', 'textures': CLIPON_TEXTURES},
    'utc': {'bundle': 'ustachae_clipons/utc.bundle', 'source': 'utc', 'deps': THERMAL_DEPS,
            'built': 'clipons/package/bundles/ustachae_clipons/utc.bundle',
            'mesh': 'mesh_ustachae_utc', 'textures': CLIPON_TEXTURES},
    'utc_fde': {'bundle': 'ustachae_clipons/utc_fde.bundle', 'source': 'utc', 'deps': THERMAL_DEPS,
                'built': 'clipons/package/bundles/ustachae_clipons/utc_fde.bundle',
                'mesh': 'mesh_ustachae_utc_fde', 'textures': CLIPON_TEXTURES},
}

# The purchases: the download files, and the files used from them ("inner.zip/path" for a zip inside the zip)
# with their SHA-256. The processing was measured on exactly these files, so other versions are refused.
# Entries without an archive name come from the purchase's only download.
SOURCES = {
    'pvs22': {'title': 'AN/PVS-22 (TurboSquid)', 'archives': ['PVS-22_obj.zip', 'PVS-22_3ds.zip'], 'files': {
        'obj': ('PVS-22_obj.zip', 'AN:PVS-22 obj/AN:PVS-22.obj', 'feb5f68be6c1d5e3084c97329947fe5191579bf6a7e63f96d515c59f8e7f3a2d'),
        'label': ('PVS-22_3ds.zip', 'AN:PVS-22 3ds/T00000.bmp', '64ac1c37e6306d189f93d8bfc464f645e1cb09a992ea5d1d53c7d8e4b2c82753')}},
    'pvs27': {'title': 'AN/PVS-27 (CGTrader)', 'archives': ['pvs27-magnum-universal-night-sight.zip'], 'files': {
        'obj': ('PVS27_nightvision_UPDATE_01.zip/separated_glass/PVS27_nightvision.obj', '87fe11eb166acddf099e25ccc84e37e1f1b4fe95f0241a791acd2e2e64a51e96'),
        'base': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_BaseColor.png', '826319c82990a64ba9708704e02d41abae6a30b67569de92360b00e694113e8f'),
        'normal': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Normal.png', '98262df6b1075bc7390c4ed4b15f9e3d356203f421aa6ed6ed1387fc523df198'),
        'rough': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Roughness.png', '17681fd87e02856643e2f2490e16f104decd56d4381a7e33a4eb739a03840ab0'),
        'metal': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Metallic.png', '751473eafb107d338b7fd7bbae7087d188e51ef7873b58776e5390935bbf4104'),
        'ao': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_ambient_occlusion.png', '62ca62d4e4131542457d2819ee8d6116e04e86abcb9c204e33d07a2b7c67b65a'),
        'fde_base': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_BaseColor.png', '962dbdfcd87a8c824127111af2e11eec4376a2548b19fa7374d0507506339a5c'),
        'fde_rough': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_Roughness.png', 'b3a58a4b0c8baacd42737e413cb71c6106e6fcc5d87436f89d3a796926afaea1'),
        'fde_metal': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_Metallic.png', '66909ba674a99fbaa24418b9b631577ee2f6c4a9ecbd38f45a8cf292c40f7626')}},
    'utc': {'title': 'UTC XII (CGTrader)', 'archives': ['utcx-thermal-weapon-sight.zip'], 'files': {
        'obj': ('UTCX2_thermal_scope_PACK.zip/UTCX2.obj', 'a08d67bcc24e679f2ec4b4f4a4f0b7627f35fd3827ed7b7be3f1e77879daa0e7'),
        'base': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_BaseColor.png', 'caf6eab75c31866d131edb3306213fce0142e34ff1edc36322b7994a0ccf1ed3'),
        'normal': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_Normal.png', 'a5fa5f2a503f7836c1ea7cf6ec2734f435229e41d1c08860372eba980fcbea67'),
        'rough': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_Roughness.png', '7a0186f4ad38e454e908ca5805a92d6783c3d3a063c5e93ebb5a7c5e00f2ee8f'),
        'metal': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_Metallic.png', 'ca4bfbc924abcc4bb41be9e36ee2985d3f07f8db1ffae32894bdafef9991268d'),
        'ao': ('UTCX2_thermal_scope_PACK.zip/textures/UTCX2_ambient_occlusion.png', 'f5e5b68ae404bb4869c34a035fc5db37a6ae1a3d14d2a6b298223e717cf93556'),
        'fde_base': ('UTCX2_thermal_scope_PACK.zip/textures/FDE/UTCX2_BaseColor.png', '23bddc11e42acd6548f67a4593235fa12d7766982740fee7fda2e9c16c3e9ce0'),
        'fde_rough': ('UTCX2_thermal_scope_PACK.zip/textures/FDE/UTCX2_Roughness.png', 'd22afec8cb766bb97fd9d7fcf5cb656d1767b20af67f72e511e82a2a7cd1f632'),
        'fde_metal': ('UTCX2_thermal_scope_PACK.zip/textures/FDE/UTCX2_Metallic.png', '067dc4e1640a932aaf04cdef88d79a21f750d8614d2c72ac019ba0d956ce38fb')}},
}

# How each clip-on model maps into the EFT mod frame (+Z toward the muzzle, +Y up, origin on the rail top at
# the middle of the mount), in the OBJ's own units. Figures read off the source meshes.
CLIPONS = {
    'pvs27': {
        'length_axis': 0, 'objective': -1, 'scale': 1.0, 'rail_y': 0.003, 'mount_centre': 0.016,
        'eyepiece': {'along': 0.0772, 'y': 0.0374, 'radius': 0.0233},
        'materials': {'PVS27_nightvision': 'body', 'PVS27_front_glass': 'drop', 'PVS27_lense': 'drop'},
        'objective_lens': {'y': 0.0399, 'radius': 0.0442, 'depth': (0.011, 0.0125)},
        'drop_depth': 0.0, 'normal_dx': False,
        'albedo_target': 0.03, 'sheen': 0.6,  # its near-black paint, lifted to 3% so details read
    },
    'utc': {
        'length_axis': 0, 'objective': -1, 'scale': 0.158 / 0.6031,  # source is not to scale; real length 158 mm
        'rail_y': 0.003 / (0.158 / 0.6031), 'mount_centre': -0.0016 / (0.158 / 0.6031),
        'eyepiece': {'along': 0.244 - 0.004 / (0.158 / 0.6031), 'y': 0.035 / (0.158 / 0.6031), 'radius': 0.0134 / (0.158 / 0.6031)},
        'materials': {'UTCX2': 'body'},
        'objective_lens': {'y': 0.0514 / (0.158 / 0.6031), 'radius': 0.031 / (0.158 / 0.6031),
                           'depth': (0.0075 / (0.158 / 0.6031), 0.0105 / (0.158 / 0.6031))},
        'drop_depth': 0.001 / (0.158 / 0.6031), 'normal_dx': False,
    },
}

# PVS-22 figures, in OBJ units unless noted (shared by the Blender bake and the mesh step).
PVS22_LENGTH, PVS22_AXIS_HEIGHT, PVS22_FORWARD = 0.180, 0.0341, 0.060  # metres
PVS22_ZMIN, PVS22_ZMAX = -42.05912, 34.65849
PVS22_CLAMP_Z = (-16.1 + 6.5) / 2  # the clamp sits under the boxy centre housing
PVS22_BODY_BOTTOM = -9.9
TEX_SIZE = 2048


# ----------------------------------------------------------------------------------------------------------
# PVS-22 bake (runs inside Blender, started by this same script)
# ----------------------------------------------------------------------------------------------------------

def blender_bake(src, out):
    """Rebuilds the PVS-22 for texturing: glass for the objective element, a bevelled rail clamp, smooth
    normals, a fresh UV atlas; bakes ambient occlusion, an edge mask and bevel normals into it, and exports
    baked.obj in the original OBJ coordinates."""
    import bmesh, random
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    S = PVS22_LENGTH / (PVS22_ZMAX - PVS22_ZMIN)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(src), use_split_groups=True)
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']

    def to_blender(x, y, z): return Vector((x, -z, y))  # the importer maps OBJ (x, y, z) to (x, -z, y)

    # The objective's convex element was modelled with the body material; it is glass.
    glass = bpy.data.materials['mtl_004']
    for o in objs:
        if 'Body1' not in o.name: continue
        me = o.data
        if glass.name not in me.materials: me.materials.append(glass)
        gi = list(me.materials).index(glass)
        for p in me.polygons:
            c = o.matrix_world @ p.center
            if -c.y > 18 and math.hypot(c.x, c.z) < 9: p.material_index = gi

    # Rail clamp, designed in the game frame (metres, +Z toward the muzzle) and converted to OBJ units.
    def game_to_obj(x, y, z): return (-x / S, (y - PVS22_AXIS_HEIGHT) / S, (z - PVS22_FORWARD) / S + PVS22_CLAMP_Z)
    top = PVS22_BODY_BOTTOM * S + PVS22_AXIS_HEIGHT + 0.004
    bm = bmesh.new()

    def box(lo, hi):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        vs = [bm.verts.new(to_blender(*game_to_obj(x, y, z))) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in q])

    def cylinder(centre, radius, length, segments=20):
        cx, cy, cz = centre
        ring = []
        for end in (-0.5, 0.5):
            row = []
            for i in range(segments):
                a = 2 * math.pi * i / segments
                row.append(bm.verts.new(to_blender(*game_to_obj(cx + end * length, cy + math.cos(a) * radius, cz + math.sin(a) * radius))))
            ring.append(row)
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new([ring[0][i], ring[0][j], ring[1][j], ring[1][i]])
        bm.faces.new(ring[0][::-1]); bm.faces.new(ring[1])

    z = PVS22_FORWARD
    box((-0.0155, 0.0, z - 0.024), (0.0155, top, z + 0.024))                 # body of the mount
    box((-0.0155, -0.0075, z - 0.024), (-0.0105, 0.0, z + 0.024))            # left jaw
    box((0.0105, -0.0075, z - 0.024), (0.0155, 0.0, z + 0.024))              # right jaw
    box((-0.0040, top - 0.002, z - 0.026), (0.0040, top + 0.001, z + 0.026)) # recoil lug strip
    cylinder((-0.0185, 0.006, z), 0.0045, 0.006)                             # throw-lever hub
    box((-0.0215, 0.003, z - 0.002), (-0.0195, 0.009, z + 0.020))            # throw lever
    cylinder((0.0170, 0.006, z), 0.0030, 0.004)                              # cross-bolt head
    me = bpy.data.meshes.new('clamp'); bm.normal_update(); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    clamp = bpy.data.objects.new('clamp', me); bpy.context.scene.collection.objects.link(clamp)
    me.materials.append(bpy.data.materials['mtl_001'])
    bpy.context.view_layer.objects.active = clamp
    mod = clamp.modifiers.new('bevel', 'BEVEL'); mod.width = 0.0007 / S; mod.segments = 3; mod.limit_method = 'ANGLE'
    bpy.ops.object.modifier_apply(modifier='bevel')

    bpy.ops.object.select_all(action='DESELECT')
    for o in objs + [clamp]: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active

    # The model is double-sided: every face also exists reversed. Keep one of each and turn it outward.
    bmc = bmesh.new(); bmc.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bmc, verts=bmc.verts, dist=1e-4)
    seen, twins = set(), []
    for f in bmc.faces:
        key = frozenset(v.index for v in f.verts)
        if key in seen: twins.append(f)
        else: seen.add(key)
    bmesh.ops.delete(bmc, geom=twins, context='FACES')
    # Point each face at open space: whichever side lets more rays escape is the outside.
    random.seed(22)
    bmc.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bmc)

    def escapes(origin, n):
        hits = 0
        for _ in range(12):
            d = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
            if d.dot(n) < 0: d = -d
            d = (d + n * 0.6).normalized()
            if tree.ray_cast(origin + d * 0.02, d, 40.0)[0] is None: hits += 1
        return hits
    flips = []
    for f in bmc.faces:
        c, n = f.calc_center_median(), f.normal
        if n.length < 0.5: continue
        if escapes(c - n * 0.01, -n) > escapes(c + n * 0.01, n): flips.append(f)
    bmesh.ops.reverse_faces(bmc, faces=flips)
    bmc.to_mesh(ob.data); bmc.free()
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))

    # Fresh atlas for everything except the data plate, which keeps its own mapping into the label texture.
    me = ob.data
    label_index = [m.name for m in me.materials].index('mtl_002')
    bpy.ops.object.mode_set(mode='EDIT')
    bmx = bmesh.from_edit_mesh(me)
    for f in bmx.faces: f.select_set(f.material_index != label_index)
    bmesh.update_edit_mesh(me)
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, area_weight=0.0, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 96
    scene.render.bake.margin = 8
    scene.world = bpy.data.worlds.new('w'); scene.world.color = (1, 1, 1)
    dummy = bpy.data.images.new('dummy', 16, 16)

    def prepare(img, mode):
        for mat in me.materials:
            mat.use_nodes = True
            nt = mat.node_tree; nt.nodes.clear()
            out_node = nt.nodes.new('ShaderNodeOutputMaterial')
            node = nt.nodes.new('ShaderNodeTexImage'); node.image = dummy if mat.name == 'mtl_002' else img
            nt.nodes.active = node
            if mode == 'edge':
                # Edge mask: how far the bevel-rounded normal turns away from the true normal.
                geo = nt.nodes.new('ShaderNodeNewGeometry')
                bev = nt.nodes.new('ShaderNodeBevel'); bev.samples = 16; bev.inputs['Radius'].default_value = 0.0012 / S
                dot = nt.nodes.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
                nt.links.new(bev.outputs['Normal'], dot.inputs[0]); nt.links.new(geo.outputs['Normal'], dot.inputs[1])
                inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
                nt.links.new(dot.outputs['Value'], inv.inputs[1])
                gain = nt.nodes.new('ShaderNodeMath'); gain.operation = 'MULTIPLY'; gain.inputs[1].default_value = 6.0; gain.use_clamp = True
                nt.links.new(inv.outputs['Value'], gain.inputs[0])
                em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(gain.outputs['Value'], em.inputs['Color'])
                nt.links.new(em.outputs['Emission'], out_node.inputs['Surface'])
            else:
                bsdf = nt.nodes.new('ShaderNodeBsdfDiffuse')
                if mode == 'normal':
                    bev = nt.nodes.new('ShaderNodeBevel'); bev.samples = 16; bev.inputs['Radius'].default_value = 0.0008 / S
                    nt.links.new(bev.outputs['Normal'], bsdf.inputs['Normal'])
                nt.links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    for name, kind, mode, extra in (('ao', 'AO', 'plain', {}), ('edge', 'EMIT', 'edge', {}),
                                    ('bevel_normal', 'NORMAL', 'normal', {'normal_space': 'TANGENT'})):
        img = bpy.data.images.new(name, TEX_SIZE, TEX_SIZE, alpha=False, float_buffer=kind != 'AO')
        if kind != 'AO': img.colorspace_settings.name = 'Non-Color'
        prepare(img, mode)
        if kind == 'AO': scene.world.light_settings.distance = 0.02 / S
        bpy.ops.object.bake(type=kind, margin=8, use_clear=True, **extra)
        img.filepath_raw = str(out / f'{name}.png'); img.file_format = 'PNG'; img.save()
        print('BAKED', name, flush=True)
    bpy.ops.wm.obj_export(filepath=str(out / 'baked.obj'), export_selected_objects=True, export_uv=True,
                          export_normals=True, export_materials=True, export_triangulated_mesh=False, apply_modifiers=True)
    print('PVS22_BAKE_DONE', flush=True)


if IN_BLENDER:
    argv = sys.argv[sys.argv.index('--') + 1:]
    blender_bake(Path(argv[0]), Path(argv[1]))
    raise SystemExit(0)


# ----------------------------------------------------------------------------------------------------------
# Reading the purchases
# ----------------------------------------------------------------------------------------------------------

class Purchase:
    """Files from the downloaded zips, including zips inside them, checked against the expected SHA-256."""
    def __init__(self, key, folder):
        self.key, self.spec = key, SOURCES[key]
        self.outer = {name: zipfile.ZipFile(folder / name) for name in self.spec['archives']}
        self.inner = {}

    def read(self, name):
        entry = self.spec['files'][name]
        archive, member, digest = entry if len(entry) == 3 else (self.spec['archives'][0], *entry)
        outer = self.outer[archive]
        head, _, rest = member.partition('.zip/')
        if rest:
            if (archive, head) not in self.inner:
                self.inner[archive, head] = zipfile.ZipFile(io.BytesIO(outer.read(head + '.zip')))
            data = self.inner[archive, head].read(rest)
        else:
            data = outer.read(member)
        if hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f'{self.spec["title"]}: {member} is not the expected version of the file '
                             f'(the mod was made from a specific version of this model)')
        return data

    def image(self, name):
        return Image.open(io.BytesIO(self.read(name)))


# ----------------------------------------------------------------------------------------------------------
# Shared geometry and texture helpers
# ----------------------------------------------------------------------------------------------------------

def read_obj(text, with_normals=False):
    V, VT, VN, faces, mat = [], [], [], [], None
    for line in text.splitlines():
        t = line.split()
        if not t: continue
        if t[0] == 'v': V.append([float(x) for x in t[1:4]])
        elif t[0] == 'vt': VT.append([float(x) for x in t[1:3]])
        elif t[0] == 'vn': VN.append([float(x) for x in t[1:4]])
        elif t[0] == 'usemtl': mat = t[1]
        elif t[0] == 'f':
            if with_normals: faces.append((mat, [tuple(int(i) - 1 for i in c.split('/')) for c in t[1:]]))
            else: faces.append((mat, [(int(c.split('/')[0]) - 1, int(c.split('/')[1]) - 1) for c in t[1:]]))
    return np.array(V), np.array(VT), faces


def face_normal(p):
    n = np.cross(p, np.roll(p, -1, axis=0)).sum(0)  # Newell's method
    return n / (np.linalg.norm(n) + 1e-12)


def triangulate(p, n):
    """Corner triples for polygon p (winding about normal n): a fan when that is valid, else ear clipping."""
    m = len(p)
    if all(np.cross(p[k] - p[0], p[k + 1] - p[0]) @ n > 0 for k in range(1, m - 1)):
        return [(0, k, k + 1) for k in range(1, m - 1)]
    left, out = list(range(m)), []
    while len(left) > 3:
        for j in range(len(left)):
            a, b, c = left[j - 1], left[j], left[(j + 1) % len(left)]
            if np.cross(p[b] - p[a], p[c] - p[a]) @ n <= 0: continue  # reflex corner
            tri = (p[a], p[b], p[c])
            inside = any(all(np.cross(tri[(e + 1) % 3] - tri[e], p[q] - tri[e]) @ n > 0 for e in range(3))
                         for q in left if q not in (a, b, c))
            if not inside:
                out.append((a, b, c)); left.pop(j); break
        else:  # numerically degenerate leftovers: close with a fan
            out += [(left[0], left[k], left[k + 1]) for k in range(1, len(left) - 1)]; break
    if len(left) == 3: out.append(tuple(left))
    return out


def corner_angles(V, faces):
    """Vertex -> (face, corner angle) of every face using it."""
    around = [[] for _ in V]
    for fi, (_, corners) in enumerate(faces):
        p = V[[c[0] for c in corners]]
        for k, c in enumerate(corners):
            a, b = p[k - 1] - p[k], p[(k + 1) % len(p)] - p[k]
            around[c[0]].append((fi, np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12), -1, 1))))
    return around


def rgba(rgb, alpha=1.0):
    """An 8-bit RGBA image from float channels in 0..1 (what the PNGs of the author's build hold)."""
    return Image.fromarray((np.clip(np.dstack([rgb, np.broadcast_to(alpha, rgb.shape[:2])]), 0, 1) * 255).astype(np.uint8), 'RGBA')


# Texture distribution targets measured from the Nightforce ATACR 7-35x56 body (the native reference).
SPEC_P10, SPEC_P90 = 0.44, 0.65
ALBEDO_SPREAD = 0.225 / 0.067


def match_spec(spec, painted, p10=SPEC_P10, p90=SPEC_P90):
    """Linearly remap the painted texels' 10th-90th percentile band onto the target band."""
    lo, hi = np.percentile(spec[painted], [10, 90])
    return np.clip(p10 + (spec - lo) / max(hi - lo, 1e-6) * (p90 - p10), 0.0, 1.0)


def to_linear(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def stretch_albedo(albedo, painted, spread=ALBEDO_SPREAD):
    """Widen the brightness spread to the target p90/p10 ratio (each texel keeps its hue), then scale so the
    painted texels' mean reflectance in linear light is what it was."""
    lum = np.maximum(albedo.mean(-1), 1e-4)
    p10, med, p90 = np.percentile(lum[painted], [10, 50, 90])
    k = np.log(spread) / max(np.log(p90 / max(p10, 1e-4)), 1e-6)
    target = np.exp(np.log(med) + (np.log(lum) - np.log(med)) * k)
    mean_before = to_linear(albedo)[painted].mean()
    out = albedo * (target / lum)[..., None]
    for _ in range(4):
        out = np.clip(out, 0.0, 1.0)
        out = out * (mean_before / max(to_linear(out)[painted].mean(), 1e-6)) ** (1 / 2.4)
    return np.clip(out, 0.0, 1.0)


# ----------------------------------------------------------------------------------------------------------
# AN/PVS-27 and UTC XII
# ----------------------------------------------------------------------------------------------------------

def frame(cfg):
    """OBJ -> EFT mod frame: a reflection for a right-handed OBJ (Unity is left-handed)."""
    ax, across = cfg['length_axis'], 2 if cfg['length_axis'] == 0 else 0
    M = np.zeros((3, 3)); M[2, ax] = cfg['objective']; M[1, 1] = 1; M[0, across] = 1
    if (np.linalg.det(M) > 0) != cfg.get('left_handed', False): M[0, across] = -1
    return M, ax, across


def clipon_mesh(cfg, obj_text):
    V, VT, faces = read_obj(obj_text)
    M, ax, across = frame(cfg)
    eye = cfg['eyepiece']
    rear = -cfg['objective']
    lens = cfg['objective_lens']
    front = (V[:, ax] * cfg['objective']).max()
    roles = ['body', 'glass']
    keep = []
    for mat, corners in faces:
        role = cfg['materials'][mat]
        if role == 'drop': continue
        p = V[[c[0] for c in corners]]
        depth = (eye['along'] - p[:, ax]) * rear
        radius = np.hypot(p[:, across], p[:, 1] - eye['y'])
        # Eyepiece glass right behind the sight's image lens would z-fight at icon distances.
        if cfg['drop_depth'] > 0 and (radius < eye['radius'] * 1.02).all() and (depth > -1e-4).all() and (depth < cfg['drop_depth']).all():
            continue
        in_from_front = front - p[:, ax] * cfg['objective']
        if (np.hypot(p[:, across], p[:, 1] - lens['y']) < lens['radius'] * 1.01).all() and \
           (in_from_front > lens['depth'][0]).all() and (in_from_front < lens['depth'][1]).all():
            continue  # replaced by a clean glass disc below
        keep.append((roles.index(role), corners))
    faces = keep
    outward = np.zeros(3); outward[ax] = cfg['objective']
    # One objective glass disc at the front of the lens depth range, wound to face out of the objective.
    seg, centre = 48, np.zeros(3)
    centre[ax] = (front - lens['depth'][0]) * cfg['objective']; centre[1] = lens['y']
    ring = []
    for i in range(seg):
        q = centre.copy(); a = 2 * np.pi * i / seg
        q[across] += np.cos(a) * lens['radius']; q[1] += np.sin(a) * lens['radius']
        ring.append(q)
    if face_normal(np.array(ring)) @ outward < 0: ring.reverse()
    base = len(V)
    V = np.vstack([V, ring]); VT = np.vstack([VT, np.zeros((1, 2))])
    faces.append((1, [(base + i, len(VT) - 1) for i in range(seg)]))

    origin = np.zeros(3); origin[ax] = cfg['mount_centre']; origin[1] = cfg['rail_y']
    P = ((V - origin) @ M.T) * cfg['scale']
    FN = np.array([face_normal(V[[c[0] for c in corners]]) for _, corners in faces])
    around = corner_angles(V, faces)
    cos_limit = np.cos(np.radians(30.0))
    verts, index = [], {}
    tris = [[], []]
    for fi, (sm, corners) in enumerate(faces):
        ids = []
        for v, vt in corners:
            if sm == 1:
                # Glass: normals of a convex dome (radius of curvature 2.5x the lens radius).
                radial = V[v] - V[v] * np.abs(outward); radial[1] -= lens['y']
                n = outward * 2.5 * lens['radius'] + radial
            else:
                n = sum(FN[g] * w for g, w in around[v] if FN[g] @ FN[fi] > cos_limit)
            n = tuple(np.round(M @ (n / np.linalg.norm(n)), 5))
            # Glass UVs are radial (centre 0.5, rim at 0.5 out) for the coated-lens shader.
            uv = tuple(np.clip(np.array([radial[across], radial[1]]) / lens['radius'] * 0.5 + 0.5, 0, 1)) if sm == 1 else tuple(VT[vt])
            key = (v, vt, n, uv)
            if key not in index:
                index[key] = len(verts)
                verts.append((P[v], np.array(n), np.array(uv)))
            ids.append(index[key])
        facing = M @ FN[fi]
        for a, b, c in triangulate(V[[c_[0] for c_ in corners]], FN[fi]):
            if np.cross(P[corners[b][0]] - P[corners[a][0]], P[corners[c][0]] - P[corners[a][0]]) @ facing < 0: b, c = c, b
            tris[sm] += [ids[a], ids[b], ids[c]]
            if sm == 1: tris[sm] += [ids[a], ids[c], ids[b]]  # glass is double-sided
    pos = np.array([v[0] for v in verts], '<f4'); nor = np.array([v[1] for v in verts], '<f4'); uv = np.array([v[2] for v in verts], '<f4')
    return pos, nor, uv, [np.array(t, '<i4') for t in tris]


def channel(img, size):
    a = np.asarray(img.resize((size, size), Image.LANCZOS) if img.mode not in ('I;16', 'I') else img.convert('I').resize((size, size), Image.BILINEAR)).astype(np.float64)
    if a.ndim == 3: a = a[..., 0]
    return a / (65535.0 if img.mode in ('I;16', 'I') else 255.0)


def clipon_textures(cfg, src, fde):
    """The game shader's maps from the model's PBR textures: albedo (alpha = cubemap reflection), spec and
    normal. The FDE set swaps in the pack's FDE colour, metalness and roughness and drops the black paint's lift."""
    k = (lambda n: 'fde_' + n) if fde else (lambda n: n)
    base = np.asarray(src.image(k('base')).convert('RGB').resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float64) / 255
    ao = channel(src.image('ao'), TEX_SIZE)
    rough, metal = channel(src.image(k('rough')), TEX_SIZE), channel(src.image(k('metal')), TEX_SIZE)
    gloss = 1 - rough
    albedo = base * (0.25 + 0.75 * ao[..., None])
    if 'albedo_target' in cfg and not fde:
        lin = to_linear(albedo)
        painted_ = base.max(-1) > 2 / 255
        median = np.median(lin[painted_].mean(-1))
        lin = np.clip(cfg['albedo_target'] * (lin / median) ** 0.55, 0, 1)
        albedo = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    painted = base.max(-1) > 2 / 255  # the atlas padding is pure black
    albedo = stretch_albedo(albedo, painted)
    sheen = 1.0 if fde else cfg.get('sheen', 1.0)
    reflect = np.clip(0.04 + 0.30 * metal * gloss + 0.12 * gloss ** 2, 0, 0.5) * sheen
    spec = match_spec((0.15 + 0.85 * gloss ** 1.5 * (0.5 + 0.5 * metal)) * (0.4 + 0.6 * ao), painted)
    normal = np.asarray(src.image('normal').convert('RGB').resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float64) / 255
    if cfg['normal_dx']: normal[..., 1] = 1 - normal[..., 1]
    return {'albedo': rgba(albedo, reflect), 'spec': rgba(np.dstack([spec] * 3)), 'normal': rgba(normal)}


# ----------------------------------------------------------------------------------------------------------
# AN/PVS-22
# ----------------------------------------------------------------------------------------------------------

def find_blender(given):
    if given: return given
    found = shutil.which('blender')
    if found: return found
    for root in (Path('C:/Program Files/Blender Foundation'), Path.home() / 'AppData/Local/Programs/Blender Foundation'):
        for exe in sorted(root.glob('Blender*/blender.exe'), reverse=True):
            return str(exe)
    return None


def pvs22_bake(src, blender, work):
    obj = work / 'pvs22.obj'
    obj.write_bytes(src.read('obj'))
    print('  baking in Blender (several minutes)...', flush=True)
    run = subprocess.run([blender, '-b', '--factory-startup', '--python', str(Path(__file__).resolve()), '--', str(obj), str(work / 'baked')],
                         capture_output=True, text=True)
    if 'PVS22_BAKE_DONE' not in run.stdout:
        sys.stderr.write(run.stdout[-3000:] + run.stderr[-3000:])
        raise SystemExit('the PVS-22 bake in Blender failed (Blender 4.1 or newer is needed)')
    return work / 'baked'


def pvs22_textures(baked, label_img):
    """Material maps on the baked atlas: ambient occlusion darkens crevices, convex edges get lighter wear,
    bevel normals round off hard edges, and tileable grain noise adds the finish."""
    TILE, REPEAT = 512, 4
    rng = np.random.default_rng(22)

    def load(name, channels=1):
        a = np.asarray(Image.open(baked / f'{name}.png').convert('RGB')).astype(float) / 255
        return a[..., 0] if channels == 1 else a

    def noise(scale, power=2.0):
        f = np.fft.fftfreq(TILE)
        k = np.sqrt(f[:, None] ** 2 + f[None, :] ** 2)
        n = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((TILE, TILE))) * np.exp(-(k * scale) ** power) * (k > 0)))
        n = (n - n.min()) / (n.max() - n.min())
        return np.tile(n, (REPEAT, REPEAT))

    def fit(a, size):
        return a[:size, :size] if a.shape[0] >= size else np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((size, size))) / 255

    def height_normal(height, strength):
        dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * strength
        dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * strength
        n = np.stack([-dx, -dy, np.ones_like(dx)], -1)
        return n / np.linalg.norm(n, axis=-1, keepdims=True)

    def combine(base, detail):
        n = np.dstack([base[..., 0] + detail[..., 0], base[..., 1] + detail[..., 1], base[..., 2] * detail[..., 2]])
        return n / np.linalg.norm(n, axis=-1, keepdims=True)

    def clamp_tilt(n, max_deg):
        n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
        xy = np.linalg.norm(n[..., :2], axis=-1, keepdims=True)
        limit = np.tan(np.radians(max_deg))
        z = np.maximum(n[..., 2:3], 1e-3)
        scale = np.where(xy / z > limit, limit * z / np.maximum(xy, 1e-6), 1.0)
        n = np.concatenate([n[..., :2] * scale, z], -1)
        return n / np.linalg.norm(n, axis=-1, keepdims=True)

    def grey(v): return np.dstack([v, v, v])

    ao = load('ao'); size = ao.shape[0]
    edge = load('edge')
    convex = np.clip(edge * (ao - 0.35) / 0.65, 0, 1)
    bevel = clamp_tilt(load('bevel_normal', 3) * 2 - 1, 25)
    occlusion = 0.22 + 0.78 * ao ** 1.4
    grain = fit(noise(1.2) * 0.6 + noise(3.0) * 0.4, size)
    blotch = fit(noise(60.0), size)
    wear = np.clip(convex * (0.6 + 0.8 * grain) - 0.15, 0, 1)
    metal = (0.88 + 0.08 * blotch + 0.03 * grain) * occlusion + 0.9 * wear
    everywhere = ao > 0.01
    cavity = np.clip((ao - 0.3) / 0.6, 0, 1)
    cavity = np.clip(cavity / np.median(cavity[everywhere]), 0, 1)
    out = {'metal_albedo': rgba(stretch_albedo(grey(metal), everywhere), (0.18 * ao + 0.15 * wear) * cavity),
           'metal_spec': rgba(grey(match_spec((0.45 + 0.30 * blotch * (0.6 + 0.4 * grain)) * (0.35 + 0.65 * ao) + 0.45 * wear, everywhere) * cavity)),
           'metal_normal': rgba(combine(bevel, height_normal(grain, 0.3)) * 0.5 + 0.5)}
    stipple = fit(noise(1.4, 3.0) * 0.8 + noise(6.0) * 0.2, size)
    rubber = (0.92 + 0.05 * stipple) * occlusion + 0.25 * convex
    out['rubber_albedo'] = rgba(stretch_albedo(grey(rubber), everywhere), 0.05 * ao * cavity)
    out['rubber_spec'] = rgba(grey(match_spec((0.25 + 0.30 * (1 - stipple)) * (0.3 + 0.7 * ao), everywhere, 0.31, 0.46) * cavity))
    out['rubber_normal'] = rgba(combine(bevel, height_normal(stipple, 0.8)) * 0.5 + 0.5)
    label = np.asarray(label_img.convert('RGB')).astype(float) / 255
    out['label'] = rgba(label, 0.10)
    return out


def pvs22_mesh(obj_text):
    """The baked PVS-22 in the EFT frame: mirrored for Unity's handedness, rear boot toward +Z, shifted toward
    the muzzle; plug and inner eyepiece glass go black, glass gets radial UVs."""
    SUBMESH = {'mtl_001': 0, 'mtl_002': 1, 'mtl_003': 2, 'mtl_004': 3, 'mtl_005': 3, 'mtl_006': 4}
    BLACK, PLUG_RADIUS, OBJECTIVE_RADIUS = 5, 10.0, 12.6
    V, VT, raw = read_obj(obj_text, with_normals=True)
    faces = [(SUBMESH[m], corners) for m, corners in raw]
    for i, (sm, corners) in enumerate(faces):
        p = V[[c[0] for c in corners]]
        if sm == 3 and p[:, 2].mean() > 0 and np.hypot(p[:, 0], p[:, 1]).max() < PLUG_RADIUS:
            faces[i] = (BLACK, corners)
    zmin, zmax = V[:, 2].min(), V[:, 2].max()
    s = PVS22_LENGTH / (zmax - zmin)
    P = np.stack([-V[:, 0] * s, V[:, 1] * s + PVS22_AXIS_HEIGHT, (V[:, 2] - PVS22_CLAMP_Z) * s + PVS22_FORWARD], axis=1)
    glass = P[np.unique([c[0] for sm, corners in faces if sm == 3 for c in corners])]
    lens_z = float(glass[:, 2].min())
    faces = [(sm, corners) for sm, corners in faces if not (sm == 3 and P[[c[0] for c in corners], 2].max() < lens_z + 0.002)]
    faces = [(BLACK if sm == 3 and V[[c[0] for c in corners], 2].mean() < 0 else sm, corners) for sm, corners in faces]
    FN = np.array([face_normal(V[[c[0] for c in corners]]) for sm, corners in faces])
    around = corner_angles(V, faces)
    cos_limit = np.cos(np.radians(30.0))
    verts, index = [], {}
    tris = [[] for _ in range(6)]
    for fi, (sm, corners) in enumerate(faces):
        normals = []
        for c in corners:
            n = sum(FN[g] * w for g, w in around[c[0]] if FN[g] @ FN[fi] > cos_limit)
            normals.append(tuple(np.round(n / np.linalg.norm(n), 5)))
        if sm == BLACK and V[[c[0] for c in corners], 2].mean() > 0 and FN[fi][2] < -0.5:
            normals = [tuple(-np.array(n)) for n in normals]
        ids = []
        for (v, vt, _), n in zip(corners, normals):
            uv = tuple(np.clip(V[v, :2] / OBJECTIVE_RADIUS * 0.5 + 0.5, 0, 1)) if sm == 3 else tuple(VT[vt])
            key = (v, vt, n, uv)
            if key not in index:
                index[key] = len(verts)
                verts.append((P[v], np.array(n) * np.array([-1, 1, 1]), np.array(uv)))
            ids.append(index[key])
        for a, b, c in triangulate(V[[k[0] for k in corners]], FN[fi]):
            tris[sm] += [ids[a], ids[c], ids[b]]
            if sm in (3, BLACK): tris[sm] += [ids[a], ids[b], ids[c]]
    pos = np.array([v[0] for v in verts], '<f4'); nor = np.array([v[1] for v in verts], '<f4'); uv = np.array([v[2] for v in verts], '<f4')
    return pos, nor, uv, [np.array(t, '<i4') for t in tris]


# ----------------------------------------------------------------------------------------------------------
# Writing into the template bundles
# ----------------------------------------------------------------------------------------------------------

def tangents(pos, nrm, uv, tris):
    """Per-vertex tangents with handedness in w, accumulated from the triangles and made orthogonal to the
    normal (the same idea as Unity's Mesh.RecalculateTangents)."""
    t = tris.reshape(-1, 3)
    p0, p1, p2 = pos[t[:, 0]], pos[t[:, 1]], pos[t[:, 2]]
    w0, w1, w2 = uv[t[:, 0]], uv[t[:, 1]], uv[t[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = w1 - w0, w2 - w0
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-20, 0.0, 1.0 / np.where(np.abs(r) < 1e-20, 1.0, r))
    sdir = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) * r[:, None]
    tdir = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) * r[:, None]
    tan1 = np.zeros_like(pos); tan2 = np.zeros_like(pos)
    for k in range(3):
        np.add.at(tan1, t[:, k], sdir)
        np.add.at(tan2, t[:, k], tdir)
    tg = tan1 - nrm * (nrm * tan1).sum(1, keepdims=True)
    length = np.linalg.norm(tg, axis=1, keepdims=True)
    fallback = np.cross(nrm, np.array([0.0, 0.0, 1.0]))
    fallback = np.where(np.linalg.norm(fallback, axis=1, keepdims=True) < 1e-6, np.cross(nrm, np.array([0.0, 1.0, 0.0])), fallback)
    tg = np.where(length > 1e-12, tg / np.maximum(length, 1e-12), fallback / np.linalg.norm(fallback, axis=1, keepdims=True))
    w = np.where((np.cross(nrm, tg) * tan2).sum(1) < 0.0, -1.0, 1.0)
    return np.hstack([tg, w[:, None]])


def aabb(points):
    lo, hi = points.min(0), points.max(0)
    return {'m_Center': dict(zip('xyz', map(float, (lo + hi) / 2))), 'm_Extent': dict(zip('xyz', map(float, (hi - lo) / 2)))}


def write_mesh(obj, pos, nrm, uv, submeshes):
    """Fills a template Mesh with the geometry: one interleaved float32 stream (position, normal, tangent,
    uv) and 32-bit indices, the layout the Unity builder produces."""
    t = obj.read_typetree()
    tris = np.concatenate(submeshes).astype(np.int64)
    tan = tangents(pos.astype(np.float64), nrm.astype(np.float64), uv.astype(np.float64), tris)
    t['m_VertexData']['m_VertexCount'] = len(pos)
    t['m_VertexData']['m_DataSize'] = np.hstack([pos, nrm, tan, uv]).astype('<f4').tobytes()
    t['m_IndexFormat'] = 1
    t['m_IndexBuffer'] = list(tris.astype('<u4').tobytes())
    subs, first = [], 0
    for s in submeshes:
        s = np.asarray(s, np.int64)
        subs.append({'firstByte': first * 4, 'indexCount': len(s), 'topology': 0, 'baseVertex': 0,
                     'firstVertex': int(s.min()), 'vertexCount': int(s.max() - s.min() + 1), 'localAABB': aabb(pos[np.unique(s)])})
        first += len(s)
    t['m_SubMeshes'] = subs
    t['m_LocalAABB'] = aabb(pos)
    obj.save_typetree(t)


def dxt_level(img, fmt):
    """One mip level in DXT1 (10) or DXT5 (12); levels under 4x4 are padded to one block."""
    if img.width < 4 or img.height < 4:
        pad = Image.new(img.mode, (max(4, img.width), max(4, img.height)))
        pad.paste(img, (0, 0)); img = pad
    return Texture2DConverter.image_to_texture2d(img, fmt)[0]


def write_texture(obj, img, normal_map=False, size=TEX_SIZE):
    """Fills a template Texture2D: resized to at most `size`, a full box-filtered mip chain down to 1x1, in
    the template's own compressed format. Normal maps go in Unity's layout (X in alpha, Y in green)."""
    tex = obj.read()
    fmt = tex.m_TextureFormat
    img = img.convert('RGBA')
    if max(img.size) > size:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    levels, level = [], img
    while True:
        levels.append(level)
        if level.width == 1 and level.height == 1: break
        level = level.resize((max(1, level.width // 2), max(1, level.height // 2)), Image.Resampling.BOX)
    data = b''
    for lv in levels:
        if normal_map:
            a = np.asarray(lv).astype(np.float32) / 255 * 2 - 1
            n = a[..., :3] / np.maximum(np.linalg.norm(a[..., :3], axis=-1, keepdims=True), 1e-6)
            x, y = (n[..., 0] + 1) / 2, (n[..., 1] + 1) / 2
            lv = Image.fromarray((np.stack([np.ones_like(x), y, y, x], -1) * 255 + 0.5).astype(np.uint8), 'RGBA')
        data += dxt_level(lv, fmt)
    tex.m_Width, tex.m_Height = img.width, img.height
    tex.m_MipCount = len(levels)
    tex.m_MipMap = True
    tex.image_data = data
    tex.m_CompleteImageSize = len(data)
    if tex.m_StreamData is not None:
        tex.m_StreamData.path, tex.m_StreamData.offset, tex.m_StreamData.size = '', 0, 0
    tex.save()


def fill_template(template, model, mesh, textures):
    env = UnityPy.load(str(template))
    meshes = filled = 0
    for o in env.objects:
        if o.type.name == 'Mesh' and o.read_typetree()['m_Name'] == model['mesh']:
            write_mesh(o, *mesh); meshes += 1
        elif o.type.name == 'Texture2D':
            name = o.read().m_Name
            if name in textures:
                write_texture(o, textures[name], normal_map=name.endswith('normal')); filled += 1
    if meshes != 1 or filled != len(model['textures']):
        raise SystemExit(f'{template.name} does not match this script (mesh {meshes}, textures {filled})')
    return env.file.save(packer='lz4')


# ----------------------------------------------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------------------------------------------

def update_manifest(mod, keys):
    path = mod / 'bundles.json'
    manifest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'manifest': []}
    have = {e['key'] for e in manifest['manifest']}
    for key in keys:
        model = MODELS[key]
        if model['bundle'] not in have:
            manifest['manifest'].append({'key': model['bundle'], 'dependencyKeys': model['deps']})
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('models', type=Path, help='folder holding the downloaded model zips')
    ap.add_argument('--mod', type=Path, default=Path(__file__).resolve().parent, help='the mod folder (default: where this script is)')
    ap.add_argument('--blender', help='blender.exe, for the PVS-22 (found automatically when installed normally)')
    args = ap.parse_args()

    running = subprocess.run(['tasklist'], capture_output=True, text=True).stdout if sys.platform == 'win32' else ''
    for exe in ('SPT.Server.exe', 'EscapeFromTarkov.exe'):
        if exe in running: raise SystemExit(f'{exe} is running; close it first')
    templates = args.mod / 'templates'
    if not templates.is_dir(): raise SystemExit(f'no templates folder in {args.mod}; pass --mod <the mod folder>')

    found = []
    for key, spec in SOURCES.items():
        missing = [a for a in spec['archives'] if not (args.models / a).exists()]
        if not missing: found.append(key)
        elif len(missing) < len(spec['archives']): print(f'{spec["title"]}: also needs {", ".join(missing)}; skipped')
    if not found:
        raise SystemExit('none of the model downloads found in ' + str(args.models) + ':\n  ' +
                         '\n  '.join(f'{" + ".join(s["archives"])}  ({s["title"]})' for s in SOURCES.values()))
    built = []
    with tempfile.TemporaryDirectory() as tmp:
        for source in found:
            src = Purchase(source, args.models)
            print('reading', SOURCES[source]['title'], flush=True)
            jobs = {}
            if source == 'pvs22':
                blender = find_blender(args.blender)
                if not blender:
                    print('  skipped: Blender 4.1 or newer is needed for the PVS-22 (pass --blender <blender.exe>)'); continue
                label = src.image('label')
                baked = pvs22_bake(src, blender, Path(tmp))
                mesh = pvs22_mesh((Path(tmp) / 'baked' / 'baked.obj').read_text(encoding='utf-8', errors='replace'))
                jobs['pvs22'] = (mesh, pvs22_textures(baked, label))
            else:
                cfg = CLIPONS[source]
                mesh = clipon_mesh(cfg, src.read('obj').decode('utf-8', errors='replace'))
                jobs[source] = (mesh, clipon_textures(cfg, src, fde=False))
                jobs[source + '_fde'] = (mesh, clipon_textures(cfg, src, fde=True))
            for key, (mesh, textures) in jobs.items():
                model = MODELS[key]
                data = fill_template(templates / f'{key}.bundle.template', model, mesh, textures)
                out = args.mod / 'bundles' / model['bundle']
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
                built.append(key)
                print('  built', model['bundle'], f'{len(data) / 1e6:.1f} MB', flush=True)
    update_manifest(args.mod, built)
    print('done:', ', '.join(built), '- start the server; these items are enabled now.')


if __name__ == '__main__':
    main()
