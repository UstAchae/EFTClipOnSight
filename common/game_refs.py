# References into the game's shared bundles and small UnityPy helpers used by the finalize scripts.
from UnityPy.files.SerializedFile import FileIdentifier

# The game's shader bundle and cubemap bundle, as external file paths inside a bundle.
SHADERS = 'archive:/CAB-56d919bd5479d38f741da52a6beef92f/CAB-56d919bd5479d38f741da52a6beef92f'
CUBES = 'archive:/CAB-4d8a4131cf377709ee7c7e960f65d349/CAB-4d8a4131cf377709ee7c7e960f65d349'
METAL_CUBE = -2064706391146893937  # the crisp "metal" cubemap in CUBES


def objects(bundle):
    return [o for f in bundle.files.values() if hasattr(f, 'objects') for o in f.objects.values()]


class Stored:
    """A bundle resource file written back unchanged."""
    def __init__(self, data, flags): self.data, self.flags = bytes(data), flags
    def save(self): return self.data


def external_id(sf, path):
    """File id of `path` among the serialized file's externals, adding it if missing."""
    for i, x in enumerate(sf.externals, 1):
        if x.path == path: return i
    x = FileIdentifier.__new__(FileIdentifier)
    x.temp_empty = ''; x.guid = bytes(16); x.type = 0; x.path = path
    sf.externals.append(x)
    return len(sf.externals)
