# Clip-on sights built by this pipeline: purchased source model, how it maps into the EFT frame, and the
# real-world figures the item uses. Geometry figures were read off the source meshes (cross-sections of the
# mounts, eyepiece discs) and are in the source OBJ's own units; `scale` turns those into metres.
#
# EFT mod frame: +Z toward the muzzle (the objective end), +Y up, origin on the rail top surface at the
# middle of the mount. `length_axis` is the OBJ axis along the device and `objective` the sign of the
# objective end on it; the across axis is mirrored as needed so the change of handedness keeps text readable.
# `objective_lens` locates the objective glass (centre height, radius, and for textured-in lenses the depth
# range in from the objective end): those faces become the glass material, with normals bent into a dome.

SRC = r'D:/games/SPT-4.1.6/.codex-work/EFTClipOnSight/clipons/src'

ITEMS = {
    'pvs27': {
        'title': 'AN/PVS-27 MUNS',
        'obj': SRC + '/pvs27/update/separated_glass/PVS27_nightvision.obj',
        'length_axis': 0, 'objective': -1, 'scale': 1.0,
        'rail_y': 0.003,          # ceiling of the mount's rail channel
        'mount_centre': 0.016,    # along the length axis
        # Eyepiece glass: the image lens of the sight goes here (plane along the length axis, centre, radius).
        'eyepiece': {'along': 0.0772, 'y': 0.0374, 'radius': 0.0233},
        # Its front cover glass is an annulus polygon with a slit; the generated disc below replaces it.
        'materials': {'PVS27_nightvision': 'body', 'PVS27_front_glass': 'drop', 'PVS27_lense': 'drop'},
        # Its own glass material is one annulus polygon with a slit, which triangulates with a slice missing;
        # it is replaced by a clean disc like the painted-in lenses (the central cap sits in front of it).
        'objective_lens': {'y': 0.0399, 'radius': 0.0442, 'depth': (0.011, 0.0125)},
        'drop_depth': 0.0,        # eyepiece faces right behind the image lens are dropped (material above)
        'textures': {'body': {'base': SRC + '/pvs27/pack/textures/PVS27_nightvision_BaseColor.png',
                              'normal': SRC + '/pvs27/pack/textures/PVS27_nightvision_Normal.png',
                              'rough': SRC + '/pvs27/pack/textures/PVS27_nightvision_Roughness.png',
                              'metal': SRC + '/pvs27/pack/textures/PVS27_nightvision_Metallic.png',
                              'ao': SRC + '/pvs27/pack/textures/PVS27_nightvision_ambient_occlusion.png',
                              'normal_dx': False}},
        # Its base colour averages 0.4% reflectance, far darker than real black paint; lifted to 3% so the
        # details read (5% looked grey in game), with less sheen so it stays black.
        'albedo_target': 0.03, 'sheen': 0.6,
        'thermal': False,
        # Real figures (FLIR/US Night Vision listings): 8.7 in long, 3.75 in above the rail, 50 oz, 10 deg FOV.
        'length': 0.221, 'weight': 1.42, 'fov': 10,
    },
    'pvs30': {
        'title': 'AN/PVS-30',
        'obj': SRC + '/pvs30/raw/Sight_PVS30_v01/Mesh/PVS30.obj',
        'length_axis': 2, 'objective': -1, 'scale': 1.0,
        'albedo_target': 0.016, 'sheen': 0.6,  # its paint (2.4%) and sheen read grey in game
        'rail_y': 0.000,
        'mount_centre': 0.017,
        'eyepiece': {'along': 0.114, 'y': 0.038, 'radius': 0.0172},
        'materials': {'MI_PVS30': 'body'},
        # The painted lens's front surface is 10.5 mm in. Its painted circle (centre 42 mm, r 36) is wider than the
        # barrel's bore there, which is centred on the optical axis (38 mm) with r 31.9: the disc fills the bore.
        'objective_lens': {'y': 0.042, 'radius': 0.0362, 'depth': (0.0095, 0.0135), 'disc': 0.0104,
                           'disc_y': 0.038, 'disc_radius': 0.0317},
        'drop_depth': 0.008,      # the domed eyepiece lens reaches 7.2 mm behind its front pole (its 9-sided back)
        'drop_from': -0.001,      # its front pole stands 0.5 mm proud of the eyepiece plane
        'drop_radius': 0.019,     # and its rim meets the bore at 18.8 mm, wider than the image lens
        'textures': {'body': {'base': SRC + '/pvs30/raw/Sight_PVS30_v01/Textures/PBR_PVS30_tx/PVS30_BaseColor.png',
                              'normal': SRC + '/pvs30/raw/Sight_PVS30_v01/Textures/PBR_PVS30_tx/PVS30_Normal.png',
                              'rough': SRC + '/pvs30/raw/Sight_PVS30_v01/Textures/PBR_PVS30_tx/PVS30_Roughness.png',
                              'metal': SRC + '/pvs30/raw/Sight_PVS30_v01/Textures/PBR_PVS30_tx/PVS30_Metalness.png',
                              'ao': SRC + '/pvs30/raw/Sight_PVS30_v01/Textures/PBR_PVS30_tx/PVS30_AO.png',
                              'normal_dx': True}},  # Unreal-style asset (MI_ material): DirectX normals
        'thermal': False,
        # Real figures (Knight's / dealer listings): 9.6 in (244 mm) long, 2.9 lb, 9 deg FOV.
        'length': 0.244, 'weight': 1.32, 'fov': 9,
    },
    'utc': {
        'title': 'Trijicon UTC XII',
        'obj': SRC + '/utc/pack/UTCX2.obj',
        'length_axis': 0, 'objective': -1, 'scale': 0.158 / 0.6031,  # source is not to scale; real length 158 mm
        'rail_y': 0.003 / (0.158 / 0.6031),
        'mount_centre': -0.0016 / (0.158 / 0.6031),
        'eyepiece': {'along': 0.244 - 0.004 / (0.158 / 0.6031), 'y': 0.035 / (0.158 / 0.6031), 'radius': 0.0134 / (0.158 / 0.6031)},
        'materials': {'UTCX2': 'body'},
        # The lens's widest surface (r 30.9 mm) is 10 mm in; the barrel is narrower further out.
        'objective_lens': {'y': 0.0514 / (0.158 / 0.6031), 'radius': 0.0309 / (0.158 / 0.6031), 'depth': (0.0075 / (0.158 / 0.6031), 0.0105 / (0.158 / 0.6031)), 'disc': 0.0099 / (0.158 / 0.6031)},
        'drop_depth': 0.001 / (0.158 / 0.6031),
        'textures': {'body': {'base': SRC + '/utc/pack/textures/UTCX2_BaseColor.png',
                              'normal': SRC + '/utc/pack/textures/UTCX2_Normal.png',
                              'rough': SRC + '/utc/pack/textures/UTCX2_Roughness.png',
                              'metal': SRC + '/utc/pack/textures/UTCX2_Metallic.png',
                              'ao': SRC + '/utc/pack/textures/UTCX2_ambient_occlusion.png',
                              'normal_dx': False}},
        'thermal': True,
        # Real figures (Trijicon/OASYS spec sheet): 6.3 x 3.3 x 3.1 in, 20.2 oz, 640x480 12 um, 7.8 deg diagonal FOV.
        'length': 0.158, 'weight': 0.573, 'fov': 7.8,
    },
}


def fde(key, folder, prefix):
    """Flat Dark Earth variant: the pack's FDE colour, metalness and roughness maps on the same mesh, normals
    and AO. The black version's darkening (albedo_target, sheen) was for its near-black paint and is dropped."""
    cfg = {k: v for k, v in ITEMS[key].items() if k not in ('albedo_target', 'sheen')}
    tex = dict(cfg['textures']['body'])
    tex.update(base=f'{folder}/FDE/{prefix}_BaseColor.png', rough=f'{folder}/FDE/{prefix}_Roughness.png',
               metal=f'{folder}/FDE/{prefix}_Metallic.png')
    cfg['textures'] = {'body': tex}
    cfg['title'] = cfg['title'] + ' FDE'
    return cfg


# Only these two packs ship an FDE texture set; the PVS-22 and PVS-30 packs are black only.
ITEMS['pvs27_fde'] = fde('pvs27', SRC + '/pvs27/pack/textures', 'PVS27_nightvision')
ITEMS['utc_fde'] = fde('utc', SRC + '/utc/pack/textures', 'UTCX2')
