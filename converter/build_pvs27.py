"""Justachae's Clip-on Sight: AN/PVS-27 (black and FDE). Builds this mod's bundles from your own purchase of the model.

The model's licence does not allow sharing it, so this mod ships model-free templates (templates/); this script
reads the model you bought, turns it into the mesh and textures the mod uses and writes them into the templates.

Input: the PVS27 Magnum Universal Night Sight model from CGTrader
(https://www.cgtrader.com/3d-models/military/other/pvs27-magnum-universal-night-sight), its download unchanged
(not unzipped, name as downloaded):
  pvs27-magnum-universal-night-sight.zip

Requirements: Python 3.10 or newer with `pip install UnityPy numpy Pillow`.

Usage, with the SPT server and the game closed, from this mod's folder (SPT_Runtime/user/mods/UstAchae-ClipOnSight-PVS27):
  python build_pvs27.py <folder holding the zip>
It writes the bundles into bundles/ and lists them in bundles.json; start the server and the item is there.
"""
# The purchase: the files used from its download ("inner.zip/path" for a zip inside it) with their SHA-256 (the
# processing was measured on exactly these files, so other versions are refused).
SOURCE = {'title': 'AN/PVS-27 (CGTrader)', 'archives': ['pvs27-magnum-universal-night-sight.zip'], 'files': {
    'obj': ('PVS27_nightvision_UPDATE_01.zip/separated_glass/PVS27_nightvision.obj', '87fe11eb166acddf099e25ccc84e37e1f1b4fe95f0241a791acd2e2e64a51e96'),
    'base': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_BaseColor.png', '826319c82990a64ba9708704e02d41abae6a30b67569de92360b00e694113e8f'),
    'normal': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Normal.png', '98262df6b1075bc7390c4ed4b15f9e3d356203f421aa6ed6ed1387fc523df198'),
    'rough': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Roughness.png', '17681fd87e02856643e2f2490e16f104decd56d4381a7e33a4eb739a03840ab0'),
    'metal': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_Metallic.png', '751473eafb107d338b7fd7bbae7087d188e51ef7873b58776e5390935bbf4104'),
    'ao': ('PVS27_nightvision_PACK.zip/textures/PVS27_nightvision_ambient_occlusion.png', '62ca62d4e4131542457d2819ee8d6116e04e86abcb9c204e33d07a2b7c67b65a'),
    'fde_base': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_BaseColor.png', '962dbdfcd87a8c824127111af2e11eec4376a2548b19fa7374d0507506339a5c'),
    'fde_rough': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_Roughness.png', 'b3a58a4b0c8baacd42737e413cb71c6106e6fcc5d87436f89d3a796926afaea1'),
    'fde_metal': ('PVS27_nightvision_PACK.zip/textures/FDE/PVS27_nightvision_Metallic.png', '66909ba674a99fbaa24418b9b631577ee2f6c4a9ecbd38f45a8cf292c40f7626')}}

# The bundles: key, the template's mesh and textures to fill, dependencies.
KEY = 'pvs27'
MODELS = {'pvs27': {'bundle': 'ustachae_clipons/pvs27.bundle', 'mesh': 'mesh_ustachae_pvs27', 'deps': ['shaders', 'cubemaps', 'assets/systems/effects/opticsight/opticsightsmasks.bundle'],
                    'textures': ['albedo', 'spec', 'normal']},
          'pvs27_fde': {'bundle': 'ustachae_clipons/pvs27_fde.bundle', 'mesh': 'mesh_ustachae_pvs27_fde', 'deps': ['shaders', 'cubemaps', 'assets/systems/effects/opticsight/opticsightsmasks.bundle'],
                        'textures': ['albedo', 'spec', 'normal']}}

# How the model maps into the EFT mod frame (+Z toward the muzzle, +Y up, origin on the rail top at the middle of
# the mount), in the OBJ's own units: figures read off the source mesh (as in the author's clipons/items.py).
CLIPON = {
    'length_axis': 0, 'objective': -1, 'scale': 1.0, 'rail_y': 0.003, 'mount_centre': 0.016,
    'eyepiece': {'along': 0.0772, 'y': 0.0374, 'radius': 0.0233},
    'materials': {'PVS27_nightvision': 'body', 'PVS27_front_glass': 'drop', 'PVS27_lense': 'drop'},
    'objective_lens': {'y': 0.0399, 'radius': 0.0442, 'depth': (0.011, 0.0125)},
    'drop_depth': 0.0, 'normal_dx': False,
    'albedo_target': 0.03, 'sheen': 0.6,  # its near-black paint, lifted to 3% so details read
}

import argparse, hashlib, io, json, math, subprocess, sys, tempfile, zipfile
from pathlib import Path

import numpy as np
from PIL import Image
import UnityPy

TEX_SIZE = 2048


# ----------------------------------------------------------------------------------------------------------
# Reading the purchase
# ----------------------------------------------------------------------------------------------------------

class Purchase:
    """Files from the downloaded zips, including zips inside them, checked against the expected SHA-256."""
    def __init__(self, folder):
        self.outer = {name: zipfile.ZipFile(folder / name) for name in SOURCE['archives']}
        self.inner = {}

    def read(self, name):
        entry = SOURCE['files'][name]
        archive, member, digest = entry if len(entry) == 3 else (SOURCE['archives'][0], *entry)
        outer = self.outer[archive]
        head, _, rest = member.partition('.zip/')
        if rest:
            if (archive, head) not in self.inner:
                self.inner[archive, head] = zipfile.ZipFile(io.BytesIO(outer.read(head + '.zip')))
            data = self.inner[archive, head].read(rest)
        else:
            data = outer.read(member)
        if hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f'{SOURCE["title"]}: {member} is not the expected version of the file '
                             f'(the mod was made from a specific version of this model)')
        return data

    def image(self, name):
        return Image.open(io.BytesIO(self.read(name)))


# ----------------------------------------------------------------------------------------------------------
# Geometry and texture helpers
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
# Writing into the template bundles
# ----------------------------------------------------------------------------------------------------------

def tangents(pos, nrm, uv, tris):
    """Per-vertex tangents with handedness in w: each triangle's unit tangent and bitangent, weighted by its
    corner angle at the vertex, summed and made orthogonal to the normal. Of the usual variants, the closest to
    Unity's Mesh.RecalculateTangents, which the author's build uses (half the vertices within 0.01 degrees;
    the rest differ by a few degrees at most, apart from triangles with almost no texture area)."""
    t = tris.reshape(-1, 3)
    p0, p1, p2 = pos[t[:, 0]], pos[t[:, 1]], pos[t[:, 2]]
    w0, w1, w2 = uv[t[:, 0]], uv[t[:, 1]], uv[t[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = w1 - w0, w2 - w0
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-20, 0.0, 1.0 / np.where(np.abs(r) < 1e-20, 1.0, r))
    sdir = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) * r[:, None]
    tdir = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) * r[:, None]
    sdir /= np.maximum(np.linalg.norm(sdir, axis=1, keepdims=True), 1e-30)
    tdir /= np.maximum(np.linalg.norm(tdir, axis=1, keepdims=True), 1e-30)
    tan1 = np.zeros_like(pos); tan2 = np.zeros_like(pos)
    corners = [p0, p1, p2]
    for k in range(3):
        u, v = corners[(k + 1) % 3] - corners[k], corners[(k + 2) % 3] - corners[k]
        angle = np.arccos(np.clip((u * v).sum(1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1) + 1e-30), -1, 1))[:, None]
        np.add.at(tan1, t[:, k], sdir * angle)
        np.add.at(tan2, t[:, k], tdir * angle)
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


def expand565(q):
    """5:6:5 endpoint codes -> the 8-bit colour the GPU decodes."""
    r, g, b = q[..., 0], q[..., 1], q[..., 2]
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.float64)


def quantise565(c):
    c = np.clip(c, 0, 255)
    return np.stack([np.round(c[..., 0] * 31 / 255), np.round(c[..., 1] * 63 / 255), np.round(c[..., 2] * 31 / 255)], -1).astype(np.int64)


def colour_blocks(px):
    """BC1 colour blocks for (N, 16, 3) pixels: endpoints along the colours' principal axis, then refined by
    least squares on the chosen indices (twice), always in four-colour mode. A quality close to Unity's own
    compressor (the faster etcpak encoder UnityPy uses showed visible block errors)."""
    mean = px.mean(1)
    centred = px - mean[:, None]
    cov = np.einsum('nki,nkj->nij', centred, centred)
    axis = np.ones((len(px), 3)) / np.sqrt(3)
    for _ in range(8):
        axis = np.einsum('nij,nj->ni', cov, axis)
        axis /= np.maximum(np.linalg.norm(axis, axis=1, keepdims=True), 1e-12)
    proj = np.einsum('nki,ni->nk', centred, axis)
    e0 = mean + axis * proj.max(1)[:, None]
    e1 = mean + axis * proj.min(1)[:, None]
    weights = np.array([1.0, 0.0, 2 / 3, 1 / 3])  # each index's share of endpoint 0
    for _ in range(3):
        d0, d1 = expand565(quantise565(e0)), expand565(quantise565(e1))
        palette = np.stack([d0, d1, (2 * d0 + d1) / 3, (d0 + 2 * d1) / 3], 1)
        idx = ((px[:, :, None, :] - palette[:, None, :, :]) ** 2).sum(-1).argmin(-1)
        a = weights[idx]; b = 1 - a
        aa, ab, bb = (a * a).sum(1), (a * b).sum(1), (b * b).sum(1)
        det = aa * bb - ab * ab
        ax, bx = np.einsum('nk,nki->ni', a, px), np.einsum('nk,nki->ni', b, px)
        ok = np.abs(det) > 1e-9
        safe = np.where(ok, det, 1.0)[:, None]
        e0 = np.where(ok[:, None], (bb[:, None] * ax - ab[:, None] * bx) / safe, e0)
        e1 = np.where(ok[:, None], (aa[:, None] * bx - ab[:, None] * ax) / safe, e1)
    q0, q1 = quantise565(e0), quantise565(e1)
    c0 = (q0[:, 0] << 11) | (q0[:, 1] << 5) | q0[:, 2]
    c1 = (q1[:, 0] << 11) | (q1[:, 1] << 5) | q1[:, 2]
    swap = c0 < c1  # four-colour mode needs the first endpoint larger
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    q0, q1 = np.where(swap[:, None], q1, q0), np.where(swap[:, None], q0, q1)
    d0, d1 = expand565(q0), expand565(q1)
    palette = np.stack([d0, d1, (2 * d0 + d1) / 3, (d0 + 2 * d1) / 3], 1)
    idx = ((px[:, :, None, :] - palette[:, None, :, :]) ** 2).sum(-1).argmin(-1)
    idx[c0 == c1] = 0
    bits = (idx.astype(np.uint64) << (2 * np.arange(16, dtype=np.uint64))).sum(1)
    out = np.zeros((len(px), 8), np.uint8)
    out[:, 0:2] = c0.astype('<u2').view(np.uint8).reshape(-1, 2)
    out[:, 2:4] = c1.astype('<u2').view(np.uint8).reshape(-1, 2)
    out[:, 4:8] = bits.astype('<u4').view(np.uint8).reshape(-1, 4)
    return out


def alpha_blocks(alpha):
    """BC3 alpha blocks for (N, 16) values: eight-step mode between the block's extremes, refined once by least
    squares on the chosen indices."""
    shares = np.array([1.0, 0.0, 6 / 7, 5 / 7, 4 / 7, 3 / 7, 2 / 7, 1 / 7])  # each index's share of endpoint 0
    a0, a1 = alpha.max(1), alpha.min(1)
    for refine in (True, False):
        e0, e1 = np.round(a0), np.round(a1)
        palette = shares * e0[:, None] + (1 - shares) * e1[:, None]
        idx = np.abs(alpha[:, :, None] - palette[:, None, :]).argmin(-1)
        if not refine: break
        s = shares[idx]; t = 1 - s
        ss, st, tt = (s * s).sum(1), (s * t).sum(1), (t * t).sum(1)
        det = ss * tt - st * st
        ok = np.abs(det) > 1e-9
        safe = np.where(ok, det, 1.0)
        sx, tx = (s * alpha).sum(1), (t * alpha).sum(1)
        a0 = np.clip(np.where(ok, (tt * sx - st * tx) / safe, a0), 0, 255)
        a1 = np.clip(np.where(ok, (ss * tx - st * sx) / safe, a1), 0, 255)
    e0, e1 = e0.astype(np.int64), e1.astype(np.int64)
    swap = e0 < e1  # eight-step mode needs the first endpoint larger: swap and renumber
    e0, e1 = np.where(swap, e1, e0), np.where(swap, e0, e1)
    idx = np.where(swap[:, None], np.array([1, 0, 7, 6, 5, 4, 3, 2])[idx], idx)
    idx[e0 == e1] = 0
    bits = (idx.astype(np.uint64) << (3 * np.arange(16, dtype=np.uint64))).sum(1)
    out = np.zeros((len(alpha), 8), np.uint8)
    out[:, 0], out[:, 1] = e0, e1
    out[:, 2:8] = bits.astype('<u8').view(np.uint8).reshape(-1, 8)[:, :6]
    return out


def dxt_level(img, fmt):
    """One mip level in DXT1 (10) or DXT5 (12), bottom row first as Unity stores it; levels under 4x4 are
    padded to one block."""
    if img.width < 4 or img.height < 4:
        pad = Image.new(img.mode, (max(4, img.width), max(4, img.height)))
        pad.paste(img, (0, 0)); img = pad
    a = np.asarray(img.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)).astype(np.float64)
    h, w = a.shape[0] // 4, a.shape[1] // 4
    px = a[:h * 4, :w * 4].reshape(h, 4, w, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    out = []
    for i in range(0, len(px), 32768):  # in parts, to keep the palette distances small in memory
        part = px[i:i + 32768]
        colour = colour_blocks(part[:, :, :3])
        out.append(colour if fmt == 10 else np.hstack([alpha_blocks(part[:, :, 3]), colour]))
    return np.vstack(out).tobytes()


def write_texture(obj, img, normal_map=False, size=TEX_SIZE):
    """Fills a template Texture2D: resized to at most `size`, a full box-filtered mip chain down to 1x1, in
    the template's own compressed format. Normal maps go in Unity's layout (X in alpha, Y in green)."""
    tex = obj.read()
    fmt = tex.m_TextureFormat
    img = img.convert('RGBA')
    # Unity's import scales each side to the nearest power of two (the PVS-22's 283 px label became 256 px).
    pot = lambda n: min(size, 1 << max(0, round(math.log2(n))))
    if img.size != (pot(img.width), pot(img.height)):
        img = img.resize((pot(img.width), pot(img.height)), Image.Resampling.LANCZOS)
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

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('models', type=Path, help='folder holding the downloaded zip' + ('s' if len(SOURCE['archives']) > 1 else ''))
    ap.add_argument('--mod', type=Path, default=Path(__file__).resolve().parent, help='this mod\'s folder (default: where this script is)')
    add_options(ap)
    args = ap.parse_args()

    running = subprocess.run(['tasklist'], capture_output=True, text=True).stdout if sys.platform == 'win32' else ''
    for exe in ('SPT.Server.exe', 'EscapeFromTarkov.exe'):
        if exe in running: raise SystemExit(f'{exe} is running; close it first')
    templates = args.mod / 'templates'
    if not templates.is_dir(): raise SystemExit(f'no templates folder in {args.mod}; pass --mod <this mod\'s folder>')
    missing = [a for a in SOURCE['archives'] if not (args.models / a).exists()]
    if missing: raise SystemExit(f'{SOURCE["title"]}: {", ".join(missing)} not found in {args.models}')

    print('reading', SOURCE['title'], flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        jobs = build(Purchase(args.models), args, Path(tmp))
        for key, (mesh, textures) in jobs.items():
            model = MODELS[key]
            data = fill_template(templates / f'{key}.bundle.template', model, mesh, textures)
            out = args.mod / 'bundles' / model['bundle']
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            print('  built', model['bundle'], f'{len(data) / 1e6:.1f} MB', flush=True)
    manifest = {'manifest': [{'key': m['bundle'], 'dependencyKeys': m['deps']} for m in MODELS.values()]}
    (args.mod / 'bundles.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('done - start the server; ' + SOURCE['title'] + ' is enabled now.')


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


if __name__ == '__main__':
    main()
