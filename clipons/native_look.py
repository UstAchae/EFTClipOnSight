# Distribution targets measured from the Nightforce ATACR 7-35x56 body textures (the native scope the user
# picked as the reference), as stored 8-bit values over the painted texels: spec map median 0.59 with its
# 10th-90th percentile at 0.44-0.65, and a base colour whose 90th percentile is about 3.4x its 10th.
import numpy as np

SPEC_P10, SPEC_P90 = 0.44, 0.65
ALBEDO_SPREAD = 0.225 / 0.067  # ATACR _MainTex p90 / p10


def match_spec(spec, painted, p10=SPEC_P10, p90=SPEC_P90):
    """Linearly remap the painted texels' 10th-90th percentile band onto the target band; order is kept,
    so what the source made glossier stays glossier."""
    lo, hi = np.percentile(spec[painted], [10, 90])
    out = p10 + (spec - lo) / max(hi - lo, 1e-6) * (p90 - p10)
    return np.clip(out, 0.0, 1.0)


def to_linear(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def stretch_albedo(albedo, painted, spread=ALBEDO_SPREAD):
    """Widen the brightness spread to the target p90/p10 ratio, in log space and per texel on its luminance
    (each texel keeps its hue), then scale so the painted texels' mean reflectance in linear light is what it
    was: the overall depth of the finish stays, only light and dark parts move apart."""
    lum = np.maximum(albedo.mean(-1), 1e-4)
    p10, med, p90 = np.percentile(lum[painted], [10, 50, 90])
    k = np.log(spread) / max(np.log(p90 / max(p10, 1e-4)), 1e-6)
    target = np.exp(np.log(med) + (np.log(lum) - np.log(med)) * k)
    mean_before = to_linear(albedo)[painted].mean()
    out = albedo * (target / lum)[..., None]
    for _ in range(4):  # clipping at 1 shifts the mean a little; a few rounds settle it
        out = np.clip(out, 0.0, 1.0)
        gain = (mean_before / max(to_linear(out)[painted].mean(), 1e-6)) ** (1 / 2.4)  # linear gain, in encoded units
        out = out * gain
    return np.clip(out, 0.0, 1.0)
