from cubexpress.conversion import lonlat2rt
from cubexpress.geotyping import RasterTransform, Request, RequestSet
from cubexpress.download import getcube, getGeoTIFF

# Export the functions
__all__ = [
    "lonlat2rt",
    "RasterTransform",
    "Request",
    "RequestSet",
    "getcube",
    "getGeoTIFF"
]

# Dynamic version import
import importlib.metadata

__version__ = importlib.metadata.version("cubexpress")