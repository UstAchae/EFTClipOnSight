# Turns each purchased clip-on model (items.py) into what ClipOnBuilder reads: a binary mesh in the EFT
# mod frame at real scale, an info file (lens, axis and end positions), and the game shader's maps made
# from the model's PBR textures. Usage: python prepare.py [key ...]
import json, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image
from items import ITEMS
from native_look import match_spec, stretch_albedo

W = Path(__file__).resolve().parent
UNITY = Path(r'D:/games/SPT-4.1.6/.codex-work/EFTClipOnSight/pvs22/UnityProject/Assets/ClipOnSource')
SUBMESHES = ['body', 'glass']
SMOOTH_DEG = 30.0   # a corner averages only the faces at its vertex within this angle of its own face
TEX_SIZE = 2048


def read_obj(path):
    V, VT, faces, mat = [], [], [], None
    for line in open(path, encoding='utf-8', errors='replace'):
        t = line.split()
        if not t: continue
        if t[0] == 'v': V.append([float(x) for x in t[1:4]])
        elif t[0] == 'vt': VT.append([float(x) for x in t[1:3]])
        elif t[0] == 'usemtl': mat = t[1]
        elif t[0] == 'f':
            faces.append((mat, [(int(c.split('/')[0]) - 1, int(c.split('/')[1]) - 1) for c in t[1:]]))
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


def frame(cfg):
    """OBJ -> EFT mod frame: a reflection for a right-handed OBJ (Unity is left-handed), a plain rotation for
    one exported already mirrored (left_handed in items.py)."""
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


def prepare_mesh(key, cfg, out):
    V, VT, faces = read_obj(cfg['obj'])
    M, ax, across = frame(cfg)
    eye = cfg['eyepiece']
    rear = -cfg['objective']  # the eyepiece end's direction along the length axis

    # Drop the eyepiece glass right behind the sight's image lens: they would z-fight at icon distances.
    # Objective lenses painted into the body texture become glass (flat paint reads as a board, not a lens).
    lens = cfg['objective_lens']
    front = (V[:, ax] * cfg['objective']).max()  # the objective end
    keep = []
    for mat, corners in faces:
        role = cfg['materials'][mat]
        if role == 'drop': continue
        p = V[[c[0] for c in corners]]
        depth = (eye['along'] - p[:, ax]) * rear
        radius = np.hypot(p[:, across], p[:, 1] - eye['y'])
        # Lens faces face along the axis; the bore wall around them (same radius, same depth) faces across it.
        normal = np.cross(p[1] - p[0], p[2] - p[0])
        axial = abs(normal[ax]) > 0.5 * np.linalg.norm(normal)
        if cfg['drop_depth'] > 0 and axial and (radius < cfg.get('drop_radius', eye['radius'] * 1.02)).all()                 and (depth > cfg.get('drop_from', -1e-4)).all() and (depth < cfg['drop_depth']).all():
            continue
        if 'depth' in lens:
            in_from_front = front - p[:, ax] * cfg['objective']
            if (np.hypot(p[:, across], p[:, 1] - lens['y']) < lens['radius'] * 1.01).all() and \
               (in_from_front > lens['depth'][0]).all() and (in_from_front < lens['depth'][1]).all():
                continue  # replaced by a clean glass disc below: the painted lens is several stacked surfaces
        keep.append((SUBMESHES.index(role), corners))
    faces = keep
    outward = np.zeros(3); outward[ax] = cfg['objective']  # the objective lens faces this way
    # The new glass disc fills the barrel's bore, which need not be the painted lens's circle (`disc_y`, `disc_radius`).
    disc_y, disc_r = lens.get('disc_y', lens['y']), lens.get('disc_radius', lens['radius'])
    if 'depth' in lens:
        # One glass disc at the front of the lens depth range (or at `disc`, the painted lens's own front surface,
        # when a retaining ring narrower than the lens stands in that range), its edge following the bore
        # (bore_reach), wound to face out of the objective.
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
        faces.append((SUBMESHES.index('glass'), [(base + i, len(VT) - 1) for i in range(seg)]))

    origin = np.zeros(3); origin[ax] = cfg['mount_centre']; origin[1] = cfg['rail_y']
    P = ((V - origin) @ M.T) * cfg['scale']

    # Corner normals from the face windings, smoothing only across faces within SMOOTH_DEG of each other.
    FN = np.array([face_normal(V[[c[0] for c in corners]]) for _, corners in faces])
    around = [[] for _ in V]
    for fi, (_, corners) in enumerate(faces):
        p = V[[c[0] for c in corners]]
        for k, c in enumerate(corners):
            a, b = p[k - 1] - p[k], p[(k + 1) % len(p)] - p[k]
            around[c[0]].append((fi, np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12), -1, 1))))
    cos_limit = np.cos(np.radians(SMOOTH_DEG))

    verts, index = [], {}
    tris = [[] for _ in SUBMESHES]
    for fi, (sm, corners) in enumerate(faces):
        ids = []
        for v, vt in corners:
            if sm == 1:
                # Glass: normals of a convex dome (radius of curvature 2.5x the lens radius), so the cubemap
                # reflection sweeps across the lens like on real curved glass instead of one flat colour.
                radial = V[v] - V[v] * np.abs(outward); radial[1] -= disc_y
                n = outward * 2.5 * disc_r + radial
            else:
                n = sum(FN[g] * w for g, w in around[v] if FN[g] @ FN[fi] > cos_limit)
            n = tuple(np.round(M @ (n / np.linalg.norm(n)), 5))
            # Glass UVs are radial (centre 0.5, rim at 0.5 out) for the coated-lens shader.
            uv = tuple(np.clip(np.array([radial[across], radial[1]]) / disc_r * 0.5 + 0.5, 0, 1)) if sm == 1 else tuple(VT[vt])
            key_ = (v, vt, n, uv)
            if key_ not in index:
                index[key_] = len(verts)
                verts.append((P[v], np.array(n), np.array(uv)))
            ids.append(index[key_])
        # Unity's front face is the side cross(b-a, c-a) points to; order each triangle so that is the outside
        # (the face normal carried through the frame change), whether or not the frame change mirrors.
        facing = M @ FN[fi]
        for a, b, c in triangulate(V[[c_[0] for c_ in corners]], FN[fi]):
            if np.cross(P[corners[b][0]] - P[corners[a][0]], P[corners[c][0]] - P[corners[a][0]]) @ facing < 0: b, c = c, b
            tris[sm] += [ids[a], ids[b], ids[c]]
            if sm == 1: tris[sm] += [ids[a], ids[c], ids[b]]  # glass is double-sided

    pos = np.array([v[0] for v in verts], '<f4'); nor = np.array([v[1] for v in verts], '<f4'); uv = np.array([v[2] for v in verts], '<f4')
    with open(out / 'mesh.bin', 'wb') as f:
        f.write(struct.pack('<iii', len(pos), 1 | 2 | 8, len(tris)))
        f.write(pos.tobytes()); f.write(nor.tobytes()); f.write(uv.tobytes())
        for t in tris:
            f.write(struct.pack('<i', len(t))); f.write(np.array(t, '<i4').tobytes())

    lo, hi = pos.min(0), pos.max(0)
    info = {'key': key, 'vertices': len(pos), 'triangles': [len(t) // 3 for t in tris], 'submeshes': SUBMESHES,
            'boundsMin': lo.tolist(), 'boundsMax': hi.tolist(),
            'axisHeight': float((eye['y'] - cfg['rail_y']) * cfg['scale']),
            'lensZ': float(cfg['objective'] * (eye['along'] - cfg['mount_centre']) * cfg['scale']),
            'lensRadius': float(eye['radius'] * cfg['scale']),
            'frontZ': float(lo[2]), 'rearZ': float(hi[2]), 'objectiveZ': float(hi[2]),
            'thermal': cfg['thermal'], 'fov': cfg['fov']}
    (out / 'info.json').write_text(json.dumps(info, indent=1))
    return info


def channel(path, size):
    im = Image.open(path)
    a = np.asarray(im.resize((size, size), Image.LANCZOS) if im.mode not in ('I;16', 'I') else im.convert('I').resize((size, size), Image.BILINEAR)).astype(np.float64)
    if a.ndim == 3: a = a[..., 0]
    return a / (65535.0 if im.mode in ('I;16', 'I') else 255.0)


def prepare_textures(cfg, out):
    t = cfg['textures']['body']
    base = np.asarray(Image.open(t['base']).convert('RGB').resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float64) / 255
    ao, rough, metal = (channel(t[k], TEX_SIZE) for k in ('ao', 'rough', 'metal'))
    gloss = 1 - rough
    # Albedo alpha is the p0 shader's cubemap reflection strength (native items average ~0.1); spec rgb is
    # specular strength. Both come from roughness and metalness.
    albedo = base * (0.25 + 0.75 * ao[..., None])
    if 'albedo_target' in cfg:
        # Lift a near-black base colour (in linear light) so the painted texels' median reflectance matches the
        # target. A power curve rather than a flat gain: the paint comes up while already-light parts (bare
        # screws, worn edges, white print) move much less instead of clipping to white.
        lin = np.where(albedo <= 0.04045, albedo / 12.92, ((albedo + 0.055) / 1.055) ** 2.4)
        painted_ = base.max(-1) > 2 / 255
        median = np.median(lin[painted_].mean(-1))
        lin = np.clip(cfg['albedo_target'] * (lin / median) ** 0.55, 0, 1)
        albedo = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    painted = base.max(-1) > 2 / 255  # the atlas padding is pure black
    # Surface contrast and specular at the native reference's level (native_look.py); the median base colour
    # keeps the depth set above. Sheen only damps the cubemap reflection now, which is what greyed them out.
    albedo = stretch_albedo(albedo, painted)
    sheen = cfg.get('sheen', 1.0)
    reflect = np.clip(0.04 + 0.30 * metal * gloss + 0.12 * gloss ** 2, 0, 0.5) * sheen
    spec = match_spec((0.15 + 0.85 * gloss ** 1.5 * (0.5 + 0.5 * metal)) * (0.4 + 0.6 * ao), painted)
    save = lambda name, rgb, alpha=1.0: Image.fromarray((np.clip(np.dstack([rgb, np.broadcast_to(alpha, rgb.shape[:2])]), 0, 1) * 255).astype(np.uint8), 'RGBA').save(out / f'{name}.png')
    save('albedo', albedo, reflect)
    save('spec', np.dstack([spec] * 3))
    normal = np.asarray(Image.open(t['normal']).convert('RGB').resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)).astype(np.float64) / 255
    if t['normal_dx']: normal[..., 1] = 1 - normal[..., 1]  # DirectX -> OpenGL (Unity) green channel
    save('normal', normal)


if __name__ == '__main__':
    for key in sys.argv[1:] or ITEMS:
        out = UNITY / key
        out.mkdir(parents=True, exist_ok=True)
        info = prepare_mesh(key, ITEMS[key], out)
        prepare_textures(ITEMS[key], out)
        size = (np.array(info['boundsMax']) - np.array(info['boundsMin'])) * 1000
        print('PREPARED', key, 'size mm %.0f x %.0f x %.0f' % tuple(size), 'above rail %.0f' % (info['boundsMax'][1] * 1000),
              'axis %.1f' % (info['axisHeight'] * 1000), 'lensZ %.1f r %.1f' % (info['lensZ'] * 1000, info['lensRadius'] * 1000), 'tris', info['triangles'])
