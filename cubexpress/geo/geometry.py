"""Convert RasterTransforms and points into ee.Geometry search regions.

A RasterTransform describes the pixel grid you will DOWNLOAD. To DISCOVER which
images exist there, Earth Engine needs a search region (an ee.Geometry) to pass
to filterBounds. This module bridges the two.

Robustness notes, measured against Earth Engine (2026-09-21):

- The geometry is built in the RasterTransform's own CRS (typically UTM) and is NOT reprojected
  to EPSG:4326. Reprojecting a rectangle to 4326 degenerates near the antimeridian: a chip of
  4 km at 500 m from the line ends up with corners at 179.9811 and -179.9815, and Earth Engine
  accepts it silently with half the area (8.7 km² instead of 16). Earth Engine reprojects
  internally per operation, so leaving the geometry in rt.crs is correct and safe at any latitude.
- `geodesic=False` makes the search region IDENTICAL to the downloaded grid. By default Earth
  Engine joins the vertices with geodesics, and that default is off the rt's own edge by 1.1 m
  at 200 km (7 m at 500 km) in UTM, and more for a 4326 rt (1 km at 500 km). With planar edges
  Earth Engine measures exactly the rt's rectangle (984412.0 km² against 984411.5 for the exact
  one, on a 2000 x 500 km case).
- `evenOdd=True` goes with `geodesic=False`: in a projected CRS only two of the four flag
  combinations are accepted. `geodesic=False, evenOdd=False` raises "Planar interiors must be
  even/odd", and `geodesic=True, evenOdd=True` raises "Even/odd interiors currently only
  supported in geographic coordinates".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cubexpress.geo.construct import point_to_rt
from cubexpress.geo.transform import RasterTransform

if TYPE_CHECKING:
    import ee


def rt_to_geometry(rt: RasterTransform) -> ee.Geometry:
    """Build an ee.Geometry rectangle covering a RasterTransform's extent, exactly.

    The rectangle is created in the RasterTransform's own CRS, with planar edges, so the
    search region and the grid that gets downloaded are the same rectangle. It is NOT
    reprojected, which keeps it valid near the poles and the antimeridian. A sheared grid
    (shear_x or shear_y) is covered by its four corners instead, because its bbox would be
    an approximation.

    Earth Engine must be initialized before calling this.

    Args:
        rt: The RasterTransform whose extent to cover.

    Returns:
        An ee.Geometry.Rectangle in rt.crs, covering exactly rt's bbox.
    """
    import ee

    if rt.shear_x or rt.shear_y:
        # A sheared grid is a parallelogram: bbox() approximates it (it assumes shear = 0),
        # the four corners cover it exactly.
        esquinas = [
            [rt.translate_x, rt.translate_y],
            [rt.translate_x + rt.width * rt.scale_x, rt.translate_y + rt.width * rt.shear_y],
            [rt.translate_x + rt.width * rt.scale_x + rt.height * rt.shear_x,
             rt.translate_y + rt.width * rt.shear_y + rt.height * rt.scale_y],
            [rt.translate_x + rt.height * rt.shear_x, rt.translate_y + rt.height * rt.scale_y],
        ]
        return ee.Geometry.Polygon(
            [[*esquinas, esquinas[0]]],
            proj=rt.crs,
            geodesic=False,
            evenOdd=True,
        )

    xmin, ymin, xmax, ymax = rt.bbox()
    return ee.Geometry.Rectangle(
        [xmin, ymin, xmax, ymax],
        proj=rt.crs,
        geodesic=False,
        evenOdd=True,
    )


def point_to_geometry(
    lon: float,
    lat: float,
    width: int,
    height: int,
    scale: float,
) -> ee.Geometry:
    """Build an ee.Geometry rectangle around a point, sized in pixels.

    Convenience for the common case: take a lon/lat center and a patch size,
    and get the search region. Internally builds a RasterTransform (auto-UTM)
    and converts it, so the geometry aligns exactly with what point_to_rt would
    download for the same arguments.

    Earth Engine must be initialized before calling this.

    Args:
        lon: Longitude in decimal degrees, range [-180, 180].
        lat: Latitude in decimal degrees, range [-90, 90].
        width: Patch width in pixels (must be > 0).
        height: Patch height in pixels (must be > 0).
        scale: Pixel size in meters (must be > 0).

    Returns:
        An ee.Geometry.Rectangle in the appropriate UTM zone for (lon, lat).
    """
    rt = point_to_rt(lon=lon, lat=lat, width=width, height=height, scale=scale)
    return rt_to_geometry(rt)
