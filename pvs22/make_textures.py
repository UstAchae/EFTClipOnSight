# Builds the material maps on the baked UV atlas (blender_bake.py): ambient occlusion darkens crevices,
# convex edges (edge mask x AO) get lighter wear, bevel normals round off hard edges, and tileable
# grain noise adds the finish. Albedo alpha is the cubemap reflection strength for the game's p0 shader
# (native items average ~0.1). Spec rgb is specular strength; normal maps are tangent space.
from pathlib import Path
import numpy as np
from PIL import Image
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'clipons'))
from native_look import match_spec, stretch_albedo

W = Path(__file__).resolve().parent
BAKED = W / 'src/baked'
OUT = W / 'UnityProject/Assets/PVS22Source'
TILE = 512
REPEAT = 4  # 4 x 512 fills the 2048 atlas exactly
rng = np.random.default_rng(22)

def load(name, channels=1):
    a = np.asarray(Image.open(BAKED / f'{name}.png').convert('RGB')).astype(float) / 255
    return a[..., 0] if channels == 1 else a

def noise(scale, power=2.0):
    """Tileable band-limited noise in [0,1], tiled up to the atlas size; scale is the feature size in pixels."""
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
    """Whiteout blend of two tangent-space normals (z up)."""
    n = np.dstack([base[..., 0] + detail[..., 0], base[..., 1] + detail[..., 1], base[..., 2] * detail[..., 2]])
    return n / np.linalg.norm(n, axis=-1, keepdims=True)

def save(name, rgb, alpha=1.0):
    alpha = np.broadcast_to(alpha, rgb.shape[:2])
    Image.fromarray((np.clip(np.dstack([rgb, alpha]), 0, 1) * 255).astype(np.uint8), 'RGBA').save(OUT / f'{name}.png')

def grey(v): return np.dstack([v, v, v])

ao = load('ao')
size = ao.shape[0]
edge = load('edge')
convex = np.clip(edge * (ao - 0.35) / 0.65, 0, 1)  # edges that stick out; occluded creases stay dark
bevel = load('bevel_normal', 3) * 2 - 1
occlusion = 0.22 + 0.78 * ao ** 1.4

def clamp_tilt(n, max_deg):
    """Tangent-space normals tilted past max_deg are pulled back to it: the bevel bake goes wrong in thin,
    enclosed shells (the objective's barrel sleeve came out 39 deg on average, past 90 at worst), and strong
    specular on those scatters into glitter."""
    n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    xy = np.linalg.norm(n[..., :2], axis=-1, keepdims=True)
    limit = np.tan(np.radians(max_deg))
    z = np.maximum(n[..., 2:3], 1e-3)
    scale = np.where(xy / z > limit, limit * z / np.maximum(xy, 1e-6), 1.0)
    n = np.concatenate([n[..., :2] * scale, z], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)

bevel = clamp_tilt(bevel, 25)

# Metal: anodised finish with fine blast grain, soft blotches, and paint worn back on exposed edges.
grain = fit(noise(1.2) * 0.6 + noise(3.0) * 0.4, size)
blotch = fit(noise(60.0), size)
wear = np.clip(convex * (0.6 + 0.8 * grain) - 0.15, 0, 1)
metal = (0.88 + 0.08 * blotch + 0.03 * grain) * occlusion + 0.9 * wear
# Surface contrast and specular at the Nightforce ATACR's level (clipons/native_look.py); median kept.
everywhere = ao > 0.01  # baked texels only; most of the atlas is empty padding
# Cavities catch less light and mirror less of the room: specular and reflection fall off with occlusion,
# normalised so a typical texel keeps its level (the ATACR match stays) and recesses drop below it.
cavity = np.clip((ao - 0.3) / 0.6, 0, 1)
cavity = np.clip(cavity / np.median(cavity[everywhere]), 0, 1)
save('metal_albedo', stretch_albedo(grey(metal), everywhere), (0.18 * ao + 0.15 * wear) * cavity)  # above native ~0.1: read too matte in game
save('metal_spec', grey(match_spec((0.45 + 0.30 * blotch * (0.6 + 0.4 * grain)) * (0.35 + 0.65 * ao) + 0.45 * wear, everywhere) * cavity))
save('metal_normal', combine(bevel, height_normal(grain, 0.3)) * 0.5 + 0.5)  # atlas texels are coarse, keep grain subtle

# Rubber: dense stipple, dusty high points and edges, almost no reflection.
stipple = fit(noise(1.4, 3.0) * 0.8 + noise(6.0) * 0.2, size)
rubber = (0.92 + 0.05 * stipple) * occlusion + 0.25 * convex
save('rubber_albedo', stretch_albedo(grey(rubber), everywhere), 0.05 * ao * cavity)
# Rubber below the metal: the ATACR band scaled to 70%.
save('rubber_spec', grey(match_spec((0.25 + 0.30 * (1 - stipple)) * (0.3 + 0.7 * ao), everywhere, 0.31, 0.46) * cavity))
save('rubber_normal', combine(bevel, height_normal(stipple, 0.8)) * 0.5 + 0.5)

# The data plate keeps its own mapping and colours, with the same low reflection as the metal.
label = np.asarray(Image.open(W / 'src/label.png').convert('RGB')).astype(float) / 255
save('label', label, 0.10)
print('textures written to', OUT, 'atlas', size)
