
# ----------------------------------------------------------------------------------------------------------
# The model: mesh and textures (the same steps as the author's clipons/prepare.py)
# ----------------------------------------------------------------------------------------------------------

def frame(cfg):
    """OBJ -> EFT mod frame: a reflection for a right-handed OBJ (Unity is left-handed)."""
    ax, across = cfg['length_axis'], 2 if cfg['length_axis'] == 0 else 0
    M = np.zeros((3, 3)); M[2, ax] = cfg['objective']; M[1, 1] = 1; M[0, across] = 1
    if (np.linalg.det(M) > 0) != cfg.get('left_handed', False): M[0, across] = -1
    return M, ax, across


def bore_reach(V, faces, ax, across, centre, radius, seg, margin):
    """How far the objective glass may reach from its centre in each of `seg` directions: up to the barrel's inner
    wall where the body crosses the plane through `centre` (half a millimetre in front of the glass: the opening
    seen from the front; at the glass's own plane what is left of a painted lens's stacked surfaces still crosses
    it), less `margin`, at most `radius`. A disc of one radius showed
    past bores that are not round, such as the PVS-27's, whose rail mount arches up into it. Walls within 0.6 of
    the radius are parts standing in the middle of the lens (the PVS-27's central cap), not the bore."""
    plane = centre[ax]
    starts, ends = [], []
    for sm, corners in faces:
        if sm != 0: continue
        p = V[[c[0] for c in corners]]
        s = p[:, ax] - plane
        if s.min() >= 0 or s.max() <= 0: continue
        hits = []
        for i in range(len(p)):
            a, b, sa, sb = p[i], p[(i + 1) % len(p)], s[i], s[(i + 1) % len(p)]
            if sa * sb < 0: hits.append(a + (b - a) * (sa / (sa - sb)))
        for k in range(0, len(hits) - 1, 2):
            starts.append(hits[k]); ends.append(hits[k + 1])
    if not starts: return np.full(seg, radius)
    A = np.array(starts)[:, [across, 1]] - centre[[across, 1]]
    E = np.array(ends)[:, [across, 1]] - centre[[across, 1]] - A
    cross = lambda u, v: u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]
    angles = 2 * np.pi * np.arange(seg) / seg
    d = np.stack([np.cos(angles), np.sin(angles)], 1)[:, None, :]
    den = cross(d, E[None])
    ok = np.abs(den) > 1e-12
    den = np.where(ok, den, 1.0)
    t = cross(A[None], E[None]) / den      # along the ray
    u = cross(A[None], d) / den            # along the wall segment
    t = np.where(ok & (u >= 0) & (u <= 1) & (t > 0.6 * radius), t, np.inf)
    return np.minimum(t.min(1) - margin, radius)


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
        # The model's own eyepiece lens faces (they face along the axis; the bore wall around them, at the same
        # radius and depth, faces across it).
        normal = np.cross(p[1] - p[0], p[2] - p[0])
        axial = abs(normal[ax]) > 0.5 * np.linalg.norm(normal)
        if cfg['drop_depth'] > 0 and axial and (radius < cfg.get('drop_radius', eye['radius'] * 1.02)).all() \
                and (depth > cfg.get('drop_from', -1e-4)).all() and (depth < cfg['drop_depth']).all():
            continue
        in_from_front = front - p[:, ax] * cfg['objective']
        if (np.hypot(p[:, across], p[:, 1] - lens['y']) < lens['radius'] * 1.01).all() and \
           (in_from_front > lens['depth'][0]).all() and (in_from_front < lens['depth'][1]).all():
            continue  # replaced by a clean glass disc below
        keep.append((roles.index(role), corners))
    faces = keep
    outward = np.zeros(3); outward[ax] = cfg['objective']
    # One objective glass disc, at the painted lens's front surface (`disc`, else the front of its depth range),
    # filling the barrel's bore (`disc_y`, `disc_radius`, else the painted lens's circle; its edge following the
    # bore's wall, bore_reach), facing out.
    disc_y, disc_r = lens.get('disc_y', lens['y']), lens.get('disc_radius', lens['radius'])
    seg, centre = 96, np.zeros(3)
    centre[ax] = (front - lens.get('disc', lens['depth'][0])) * cfg['objective']; centre[1] = disc_y
    reach = bore_reach(V, faces, ax, across, centre + outward * (0.0005 / cfg['scale']), disc_r, seg, 0.0002 / cfg['scale'])
    ring = []
    for i in range(seg):
        q = centre.copy(); a = 2 * np.pi * i / seg
        q[across] += np.cos(a) * reach[i]; q[1] += np.sin(a) * reach[i]
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
                # Glass: normals of a convex dome (radius of curvature 2.5x the disc's radius).
                radial = V[v] - V[v] * np.abs(outward); radial[1] -= disc_y
                n = outward * 2.5 * disc_r + radial
            else:
                n = sum(FN[g] * w for g, w in around[v] if FN[g] @ FN[fi] > cos_limit)
            n = tuple(np.round(M @ (n / np.linalg.norm(n)), 5))
            # Glass UVs are radial (centre 0.5, rim at 0.5 out) for the coated-lens shader.
            uv = tuple(np.clip(np.array([radial[across], radial[1]]) / disc_r * 0.5 + 0.5, 0, 1)) if sm == 1 else tuple(VT[vt])
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


def add_options(ap):
    pass


def build(src, args, work):
    mesh = clipon_mesh(CLIPON, src.read('obj').decode('utf-8', errors='replace'))
    return {KEY: (mesh, clipon_textures(CLIPON, src, fde=False)), KEY + '_fde': (mesh, clipon_textures(CLIPON, src, fde=True))}
