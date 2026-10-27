# Converts the purchased AN/PVS-22 OBJ into the binary mesh the Unity builder reads.
# OBJ frame: right-handed, +Y up, big-lens end toward -Z. EFT mod frame: left-handed, +Y up, +Z toward the muzzle,
# origin on the rail surface at the slot point.
import json, struct
from pathlib import Path
import numpy as np

W = Path(__file__).resolve().parent
OBJ = W / 'src/pvs22_baked.obj'  # from blender_bake.py: new UVs, smooth normals, bevelled clamp
OUT = W / 'UnityProject/Assets/PVS22Source'
LENGTH = 0.180          # overall length incl. rear light-seal boot, metres (real UNS: 7.08 in)
AXIS_HEIGHT = 0.0341    # optical axis above the rail surface; puts the top 75 mm (2.95 in) above it like the real one
FORWARD = 0.060         # whole device sits this far toward the muzzle from the slot point
SUBMESH = {'mtl_001': 0, 'mtl_002': 1, 'mtl_003': 2, 'mtl_004': 3, 'mtl_005': 3, 'mtl_006': 4}
NAMES = ['body', 'label', 'text', 'glass', 'rubber', 'black']
BLACK = 5
PLUG_RADIUS = 10.0  # OBJ units; objective-end glass faces inside this radius are the central plug, not the lens
OBJECTIVE_RADIUS = 12.6  # OBJ units; the objective glass reaches r 12.5
SMOOTH_DEG = 30.0   # a corner averages only the faces at its vertex within this angle of its own face

V, VT, VN, faces = [], [], [], []
mat = None
for line in OBJ.open():
    t = line.split()
    if not t: continue
    if t[0] == 'v': V.append([float(x) for x in t[1:4]])
    elif t[0] == 'vt': VT.append([float(x) for x in t[1:3]])
    elif t[0] == 'vn': VN.append([float(x) for x in t[1:4]])
    elif t[0] == 'usemtl': mat = t[1]
    elif t[0] == 'f': faces.append((SUBMESH[mat], [tuple(int(i) - 1 for i in c.split('/')) for c in t[1:]]))
V, VT, VN = np.array(V), np.array(VT), np.array(VN)

# The source puts the objective's raised central plug (and the elements behind the lens) in the glass
# material; the real plug is a dark obscuration, so only faces reaching the lens rim stay glass.
for i, (sm, corners) in enumerate(faces):
    p = V[[c[0] for c in corners]]
    if sm == 3 and p[:, 2].mean() > 0 and np.hypot(p[:, 0], p[:, 1]).max() < PLUG_RADIUS:
        faces[i] = (BLACK, corners)

zmin, zmax = V[:, 2].min(), V[:, 2].max()
s = LENGTH / (zmax - zmin)
clamp_z_obj = (-16.1 + 6.5) / 2  # the clamp sits under the boxy centre housing (Body2 spans OBJ z -16.1..6.5)

def to_unity(p):  # OBJ -> Unity: mirror X (handedness), rubber boot toward +Z, then shift toward the muzzle (+Z)
    return np.stack([-p[:, 0] * s, p[:, 1] * s + AXIS_HEIGHT, (p[:, 2] - clamp_z_obj) * s + FORWARD], axis=1)

P = to_unity(V)

def triangulate(p, n):
    """Corner triples for polygon p (OBJ winding about normal n): a fan when that is valid, else ear clipping,
    since a fan over a concave face (engraved glyphs, the sunshade's notch) flips and spills triangles."""
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

# Output lens (toward the shooter / day scope): the rear-most glass, where the sight's image lens goes.
glass = P[np.unique([c[0] for sm, corners in faces if sm == 3 for c in corners])]
lens_z = float(glass[:, 2].min())
ring = glass[glass[:, 2] < lens_z + 0.003]
lens_radius = float(np.sqrt(ring[:, 0] ** 2 + (ring[:, 1] - AXIS_HEIGHT) ** 2).max())
# The image lens sits 0.5 mm in front of that glass element and covers it; at icon distances the two
# z-fight and the glass shows through as a dark wedge, so the element is dropped.
faces = [(sm, corners) for sm, corners in faces if not (sm == 3 and P[[c[0] for c in corners], 2].max() < lens_z + 0.002)]
# The rest of the eyepiece glass is deeper than the image lens and peeks out round its rim at an angle as
# a bright reflective sliver; the real element there reads dark, so it gets the plug's black.
faces = [(BLACK if sm == 3 and V[[c[0] for c in corners], 2].mean() < 0 else sm, corners) for sm, corners in faces]

# Corner normals from the face windings. The baked OBJ's smoothing chains across neighbouring faces, so
# long faces next to a lip carry normals bent 30-50 degrees (one ring over 120) and shade as dents.
def face_normal(p):
    n = np.cross(p, np.roll(p, -1, axis=0)).sum(0)  # Newell's method
    return n / (np.linalg.norm(n) + 1e-12)
FN = np.array([face_normal(V[[c[0] for c in corners]]) for sm, corners in faces])
around = [[] for _ in V]  # vertex -> (face, corner angle) of every face using it
for fi, (sm, corners) in enumerate(faces):
    p = V[[c[0] for c in corners]]
    for k, c in enumerate(corners):
        a, b = p[k - 1] - p[k], p[(k + 1) % len(p)] - p[k]
        angle = np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12), -1, 1))
        around[c[0]].append((fi, angle))
cos_limit = np.cos(np.radians(SMOOTH_DEG))
corner_normals = []
for fi, (sm, corners) in enumerate(faces):
    row = []
    for c in corners:
        n = sum(FN[g] * w for g, w in around[c[0]] if FN[g] @ FN[fi] > cos_limit)
        row.append(tuple(np.round(n / np.linalg.norm(n), 5)))
    # The objective's plug comes from a double-sided source and some of its cap faces point into the tube, which
    # leaves them unlit black from the front: axial plug faces at the objective end face out of it (+Z in OBJ).
    if sm == BLACK and V[[c[0] for c in corners], 2].mean() > 0 and FN[fi][2] < -0.5:
        row = [tuple(-np.array(n)) for n in row]
    corner_normals.append(row)

verts, index = [], {}
tris = [[] for _ in NAMES]
for (sm, corners), normals, fn in zip(faces, corner_normals, FN):
    ids = []
    for (v, vt, _), n in zip(corners, normals):
        # Glass UVs are radial around the optical axis (centre 0.5, rim at 0.5 out) for the coated-lens shader.
        uv = tuple(np.clip(V[v, :2] / OBJECTIVE_RADIUS * 0.5 + 0.5, 0, 1)) if sm == 3 else tuple(VT[vt])
        key = (v, vt, n, uv)
        if key not in index:
            index[key] = len(verts)
            verts.append((P[v], np.array(n) * np.array([-1, 1, 1]), np.array(uv)))  # normals mirror with the positions
        ids.append(index[key])
    # Mirroring flips the winding, so each triangle is reversed for Unity's clockwise front faces.
    for a, b, c in triangulate(V[[k[0] for k in corners]], fn):
        tris[sm] += [ids[a], ids[c], ids[b]]
        # Lens glass and the plug are double-sided: the objective element's facing can't be told apart
        # reliably and the game shader culls back faces.
        if sm in (3, BLACK): tris[sm] += [ids[a], ids[b], ids[c]]

pos = np.array([v[0] for v in verts], '<f4'); nor = np.array([v[1] for v in verts], '<f4'); uv = np.array([v[2] for v in verts], '<f4')
OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / 'pvs22.bin', 'wb') as f:
    f.write(struct.pack('<iii', len(pos), 1 | 2 | 8, len(tris)))
    f.write(pos.tobytes()); f.write(nor.tobytes()); f.write(uv.tobytes())
    for t in tris:
        f.write(struct.pack('<i', len(t))); f.write(np.array(t, '<i4').tobytes())

lo, hi = pos.min(0), pos.max(0)
front_z = to_unity(np.array([[0, 0, zmin]]))[0, 2]
rear_z = to_unity(np.array([[0, 0, zmax]]))[0, 2]
info = {'vertices': len(pos), 'triangles': [len(t) // 3 for t in tris], 'submeshes': NAMES,
        'boundsMin': lo.tolist(), 'boundsMax': hi.tolist(), 'scale': s,
        'axisHeight': AXIS_HEIGHT, 'frontZ': float(front_z), 'rearZ': float(rear_z),
        'lensZ': lens_z, 'lensRadius': lens_radius, 'objectiveZ': float(hi[2])}
(OUT / 'pvs22.json').write_text(json.dumps(info, indent=1))
print(json.dumps(info))
