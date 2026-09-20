"""RasterTransform: a rectangle of pixels in a CRS. Central type of the package."""

from __future__ import annotations

import functools
from dataclasses import dataclass

_WKT1_PREFIXES = ("PROJCS", "GEOGCS", "GEOCCS", "COMPD_CS")
_NUMERIC_FIELDS = ("translate_x", "translate_y", "scale_x", "scale_y", "shear_x", "shear_y")


@functools.lru_cache(maxsize=64)
def _parsed_crs(value: str):
    """Parse a CRS with pyproj, whatever its spelling (EPSG, WKT, PROJJSON, PROJ).

    This is for the *input* CRS: a GeoParquet, for example, declares its CRS as PROJJSON, and
    that is fine here because it is only used locally with pyproj.
    """
    from pyproj import CRS

    try:
        return CRS.from_user_input(value)
    except Exception as exc:
        raise ValueError(f"crs is not a valid CRS: {value!r}") from exc


@functools.lru_cache(maxsize=64)
def _validated_crs(value: str):
    """Return the parsed CRS if Earth Engine can take it, raise otherwise.

    Earth Engine accepts standard codes ("EPSG:32718") or WKT version 1. It rejects WKT2
    (what pyproj returns by default) and PROJ strings. The cache keeps this free: there are a
    handful of distinct CRS values per run, and parsing one costs ~190 microseconds.
    """
    crs = _parsed_crs(value)

    text = value.strip().upper()
    if not (text.startswith("EPSG:") or text.split("[", 1)[0] in _WKT1_PREFIXES):
        raise ValueError(
            f"crs is not a format Earth Engine accepts (use EPSG:XXXX or WKT1): {value[:40]!r}"
        )
    return crs


def metres_to_degrees(scale_m: float, latitude: float) -> tuple[float, float]:
    """Pixel size in degrees that matches `scale_m` metres at that latitude.

    Longitude shrinks with the cosine of the latitude, latitude does not. Measured with the
    WGS84 ellipsoid: one degree of latitude is ~110.6 km anywhere, while one degree of
    longitude goes from 111.3 km at the equator to 19.4 km at 80 degrees south.
    """
    from pyproj import Geod

    lat = max(min(latitude, 89.9), -89.9)
    geod = Geod(ellps="WGS84")
    _, _, metres_lat = geod.inv(0.0, lat, 0.0, lat + 1.0)
    _, _, metres_lon = geod.inv(0.0, lat, 1.0, lat)
    return scale_m / metres_lon, scale_m / metres_lat


@dataclass(frozen=True)
class RasterTransform:
    """Describes a rectangle of pixels in a coordinate reference system.

    GDAL convention: scale_x > 0, scale_y < 0.
    The origin (translate_x, translate_y) is the upper-left corner.

    shear_x / shear_y default to 0.0 (axis-aligned raster, the common case for
    Sentinel-2, Landsat, etc.). Non-zero shear describes a rotated raster; it is
    supported for completeness but rarely needed in Earth observation.
    """

    crs: str
    translate_x: float
    translate_y: float
    scale_x: float
    scale_y: float
    width: int
    height: int
    shear_x: float = 0.0
    shear_y: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.crs, str):
            raise TypeError(f"crs must be str, got {type(self.crs).__name__}")
        crs = _validated_crs(self.crs)
        for name in _NUMERIC_FIELDS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number, got {type(value).__name__}")
        for name, value in (("width", self.width), ("height", self.height)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be int, got {type(value).__name__}")
        if crs.is_geographic and max(abs(self.scale_x), abs(self.scale_y)) >= 1:
            scale_m = max(abs(self.scale_x), abs(self.scale_y))
            lon_deg, lat_deg = metres_to_degrees(scale_m, self.translate_y)
            raise ValueError(
                f"scale is in degrees for {self.crs}, not metres. For {scale_m:g} m at "
                f"latitude {self.translate_y:g} use scale_x={lon_deg:.6f}, scale_y=-{lat_deg:.6f}"
            )
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"width/height must be positive, got {self.width}x{self.height}")
        if self.scale_x <= 0:
            raise ValueError(f"scale_x must be > 0, got {self.scale_x}")
        if self.scale_y >= 0:
            raise ValueError(f"scale_y must be < 0 (GDAL convention), got {self.scale_y}")

    def n_pixels(self) -> int:
        """Total number of pixels."""
        return self.width * self.height

    def bbox(self) -> tuple[float, float, float, float]:
        """Bounding box (xmin, ymin, xmax, ymax) in the raster CRS.

        Note: assumes axis-aligned (shear = 0). For sheared rasters the bbox is
        an approximation of the unrotated extent.
        """
        xmin = self.translate_x
        ymax = self.translate_y
        xmax = xmin + self.width * self.scale_x
        ymin = ymax + self.height * self.scale_y  # scale_y is negative
        return (xmin, ymin, xmax, ymax)

    def to_ee_dict(self) -> dict[str, float]:
        """Earth Engine compatible affineTransform dictionary."""
        return {
            "scaleX": self.scale_x,
            "shearX": self.shear_x,
            "translateX": self.translate_x,
            "scaleY": self.scale_y,
            "shearY": self.shear_y,
            "translateY": self.translate_y,
        }
