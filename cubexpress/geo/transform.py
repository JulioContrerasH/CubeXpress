"""RasterTransform: a rectangle of pixels in a CRS. Central type of the package."""

from __future__ import annotations

import functools
from dataclasses import dataclass

_WKT1_PREFIXES = ("PROJCS", "GEOGCS", "GEOCCS", "COMPD_CS")


@functools.lru_cache(maxsize=64)
def _validate_crs(value: str) -> None:
    """Raise if the CRS is not one that Earth Engine can parse.

    Earth Engine takes standard codes ("EPSG:32718") or WKT version 1. It rejects WKT2
    (what pyproj returns by default) and PROJ strings. The cache keeps this free: there are
    a handful of distinct CRS values per run, and parsing one costs ~190 microseconds.
    """
    from pyproj import CRS

    try:
        CRS.from_user_input(value)
    except Exception as exc:
        raise ValueError(f"crs is not a valid CRS: {value!r}") from exc

    text = value.strip().upper()
    if not (text.startswith("EPSG:") or text.split("[", 1)[0] in _WKT1_PREFIXES):
        raise ValueError(
            f"crs is not a format Earth Engine accepts (use EPSG:XXXX or WKT1): {value[:40]!r}"
        )


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
        _validate_crs(self.crs)
        for name, value in (("width", self.width), ("height", self.height)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be int, got {type(value).__name__}")
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
