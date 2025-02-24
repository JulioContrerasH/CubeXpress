from cubexpress.user_utils import lonlat2rt
from cubexpress.geotyping import RasterTransform, RasterTransformSet
from cubexpress.download import getcube
from cubexpress.manifest import getmanifest
from cubexpress.getstats import getstats

# Export the functions
__all__ = [
    "lonlat2rt",
    "RasterTransform",
    "RasterTransformSet",
    "getcube",
    "getmanifest",
    "getstats"
]

# Dynamic version import
import importlib.metadata

__version__ = importlib.metadata.version("cubexpress")