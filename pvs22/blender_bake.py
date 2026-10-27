# Run with: blender -b --factory-startup --python blender_bake.py
# Rebuilds the AN/PVS-22 for texturing: glass for the objective element, a bevelled rail clamp, smooth
# normals, a fresh UV atlas, then bakes ambient occlusion, an edge mask and bevel normals into it.
# Exports src/pvs22_baked.obj in the original OBJ coordinates, so prepare_mesh.py keeps its transform.
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

W = Path(__file__).resolve().parent
SRC = W / 'src/pvs22.obj'
OUT = W / 'src/baked'
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 2048

# Must match prepare_mesh.py.
LENGTH, AXIS_HEIGHT, FORWARD = 0.180, 0.0341, 0.060
OBJ_ZMIN, OBJ_ZMAX = -42.05912, 34.65849
S = LENGTH / (OBJ_ZMAX - OBJ_ZMIN)
CLAMP_Z = (-16.1 + 6.5) / 2
BODY_BOTTOM = -9.9

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=str(SRC), use_split_groups=True)
objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']

# Blender's importer maps OBJ (x, y, z) to (x, -z, y).
def to_blender(x, y, z): return Vector((x, -z, y))

# The objective's convex element was modelled with the body material; it is glass.
glass = bpy.data.materials['mtl_004']
for o in objs:
    if 'Body1' not in o.name:
        continue
    me = o.data
    if glass.name not in me.materials: me.materials.append(glass)
    gi = list(me.materials).index(glass)
    moved = 0
    for p in me.polygons:
        c = o.matrix_world @ p.center  # world space; the importer may keep its axis change on the object
        if -c.y > 18 and math.hypot(c.x, c.z) < 9:
            p.material_index = gi; moved += 1
    print('OBJECTIVE_GLASS', o.name, moved, 'faces', tuple(round(v, 2) for v in o.rotation_euler))

# Rail clamp, designed in the game frame (metres, +Z toward the muzzle) and converted to OBJ units.
def game_to_obj(x, y, z): return (-x / S, (y - AXIS_HEIGHT) / S, (z - FORWARD) / S + CLAMP_Z)
top = BODY_BOTTOM * S + AXIS_HEIGHT + 0.004
bm = bmesh.new()
def box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    vs = [bm.verts.new(to_blender(*game_to_obj(x, y, z))) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in q])
def cylinder(centre, axis, radius, length, segments=20):
    cx, cy, cz = centre
    ring = []
    for end in (-0.5, 0.5):
        row = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            off = {'x': (end * length, math.cos(a) * radius, math.sin(a) * radius)}[axis]
            row.append(bm.verts.new(to_blender(*game_to_obj(cx + off[0], cy + off[1], cz + off[2]))))
        ring.append(row)
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new([ring[0][i], ring[0][j], ring[1][j], ring[1][i]])
    bm.faces.new(ring[0][::-1]); bm.faces.new(ring[1])
z = FORWARD
box((-0.0155, 0.0, z - 0.024), (0.0155, top, z + 0.024))                 # body of the mount
box((-0.0155, -0.0075, z - 0.024), (-0.0105, 0.0, z + 0.024))            # left jaw
box((0.0105, -0.0075, z - 0.024), (0.0155, 0.0, z + 0.024))              # right jaw
box((-0.0040, top - 0.002, z - 0.026), (0.0040, top + 0.001, z + 0.026)) # recoil lug strip
cylinder((-0.0185, 0.006, z), 'x', 0.0045, 0.006)                        # throw-lever hub
box((-0.0215, 0.003, z - 0.002), (-0.0195, 0.009, z + 0.020))            # throw lever
cylinder((0.0170, 0.006, z), 'x', 0.0030, 0.004)                         # cross-bolt head
me = bpy.data.meshes.new('clamp'); bm.normal_update(); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
clamp = bpy.data.objects.new('clamp', me); bpy.context.scene.collection.objects.link(clamp)
me.materials.append(bpy.data.materials['mtl_001'])
bpy.context.view_layer.objects.active = clamp
mod = clamp.modifiers.new('bevel', 'BEVEL'); mod.width = 0.0007 / S; mod.segments = 3; mod.limit_method = 'ANGLE'
bpy.ops.object.modifier_apply(modifier='bevel')

# One mesh, smooth shading split at 40 degrees.
bpy.ops.object.select_all(action='DESELECT')
for o in objs + [clamp]: o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active

# The purchased model is double-sided: every face also exists reversed on the same vertices. Those twins
# occlude each other completely when baking, so keep one of each and turn the normals outward.
bmc = bmesh.new(); bmc.from_mesh(ob.data)
bmesh.ops.remove_doubles(bmc, verts=bmc.verts, dist=1e-4)
seen, twins = set(), []
for f in bmc.faces:
    key = frozenset(v.index for v in f.verts)
    if key in seen: twins.append(f)
    else: seen.add(key)
bmesh.ops.delete(bmc, geom=twins, context='FACES')
# Point each face at open space. recalc_face_normals only works on closed shells, and this model has many
# thin sheets and decals (data plate, engraved text) that sit on the body; for those the side facing the
# body is blocked straight away, so whichever side lets more rays escape is the outside.
from mathutils.bvhtree import BVHTree
import random
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
    out, back = escapes(c + n * 0.01, n), escapes(c - n * 0.01, -n)
    if back > out: flips.append(f)
bmesh.ops.reverse_faces(bmc, faces=flips)
bmc.to_mesh(ob.data); bmc.free()
print('REMOVED_TWIN_FACES', len(twins), 'FLIPPED', len(flips))
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))

# Fresh atlas for everything except the data plate, which keeps its own mapping into label.png.
me = ob.data
label_index = [m.name for m in me.materials].index('mtl_002')
bpy.ops.object.mode_set(mode='EDIT')
bmx = bmesh.from_edit_mesh(me)
for f in bmx.faces: f.select_set(f.material_index != label_index)
bmesh.update_edit_mesh(me)
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, area_weight=0.0, scale_to_bounds=False)
bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
bpy.ops.object.mode_set(mode='OBJECT')

# Bake setup: every material gets an emission override and an image node as the bake target.
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 96
scene.render.bake.margin = 8
scene.world = bpy.data.worlds.new('w'); scene.world.color = (1, 1, 1)

def target(name, non_colour):
    img = bpy.data.images.new(name, SIZE, SIZE, alpha=False, float_buffer=non_colour)
    if non_colour: img.colorspace_settings.name = 'Non-Color'
    return img
dummy = bpy.data.images.new('dummy', 16, 16)

def prepare(img, mode):
    for mat in me.materials:
        mat.use_nodes = True
        nt = mat.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
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
            nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
        else:
            bsdf = nt.nodes.new('ShaderNodeBsdfDiffuse')
            if mode == 'normal':
                bev = nt.nodes.new('ShaderNodeBevel'); bev.samples = 16; bev.inputs['Radius'].default_value = 0.0008 / S
                nt.links.new(bev.outputs['Normal'], bsdf.inputs['Normal'])
            nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
for name, kind, mode, extra in (('ao', 'AO', 'plain', {}), ('edge', 'EMIT', 'edge', {}),
                                ('bevel_normal', 'NORMAL', 'normal', {'normal_space': 'TANGENT'})):
    img = target(name, kind != 'AO')
    prepare(img, mode)
    if kind == 'AO': scene.world.light_settings.distance = 0.02 / S
    bpy.ops.object.bake(type=kind, margin=8, use_clear=True, **extra)
    img.filepath_raw = str(OUT / f'{name}.png'); img.file_format = 'PNG'; img.save()
    print('BAKED', name)

bpy.ops.wm.obj_export(filepath=str(W / 'src/pvs22_baked.obj'), export_selected_objects=True, export_uv=True,
                      export_normals=True, export_materials=True, export_triangulated_mesh=False, apply_modifiers=True)
print('PVS22_BAKE_DONE', len(me.polygons), 'faces')
