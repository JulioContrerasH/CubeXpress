"""Geometry constructors that build RasterTransforms from various inputs."""

from __future__ import annotations

import math

import shapely
from pyproj import Transformer
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from shapely.ops import transform as shp_transform

from cubexpress.geo.transform import MAX_DEGREES, MIN_METRES, RasterTransform


def _require_number(name: str, value) -> None:
    """Fail fast with a clear message: a text where a number goes breaks later, in GEE."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")


def _require_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")


def _utm_zone_epsg(lon: float, lat: float) -> str:
    if not -180 <= lon <= 180:
        raise ValueError(f"lon must be in [-180, 180], got {lon}")
    if not -90 <= lat <= 90:
        raise ValueError(f"lat must be in [-90, 90], got {lat}")

    utm_crs_list = query_utm_crs_info(
        datum_name="WGS 84",
        area_of_interest=AreaOfInterest(
            west_lon_degree=lon,
            south_lat_degree=lat,
            east_lon_degree=lon,
            north_lat_degree=lat,
        ),
    )
    if not utm_crs_list:
        raise ValueError(f"No UTM zone found for (lon={lon}, lat={lat})")
    return f"EPSG:{utm_crs_list[0].code}"


def point_to_rt(
    lon: float,
    lat: float,
    width: int,
    height: int,
    scale: float,
) -> RasterTransform:
    """Build a RasterTransform centered on (lon, lat).

    The resulting patch is `width` x `height` pixels at `scale` meters/pixel,
    projected to the appropriate UTM zone for the given coordinates.

    Args:
        lon: Longitude in decimal degrees, range [-180, 180].
        lat: Latitude in decimal degrees, range [-90, 90].
        width: Patch width in pixels (must be > 0).
        height: Patch height in pixels (must be > 0).
        scale: Pixel size in meters (must be > 0).

    Returns:
        RasterTransform anchored so its bounding box is centered on (lon, lat).
    """
    _require_number("lon", lon)
    _require_number("lat", lat)
    _require_int("width", width)
    _require_int("height", height)
    _require_number("scale", scale)
    if scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale}")

    crs = _utm_zone_epsg(lon, lat)
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    cx, cy = transformer.transform(lon, lat)

    ul_x = cx - (width * scale) / 2
    ul_y = cy + (height * scale) / 2

    return RasterTransform(
        crs=crs,
        translate_x=ul_x,
        translate_y=ul_y,
        scale_x=scale,
        scale_y=-scale,
        width=width,
        height=height,
    )


def _pixel_size(
    crs: str, scale: float, latitude: float, unit: str = "m"
) -> tuple[float, float]:
    """Pixel size in the CRS units, as (scale_x, scale_y) with scale_y negative.

    `scale` is read in metres (`unit="m"`), which is how everyone reads a pixel size, and is
    converted at that latitude when the CRS is geographic: the two axes need different values.
    With `unit="deg"` the value is taken as degrees already, which is what matching a grid
    like a global 4326 product needs.

    No guessing from the number: 0.6 is 0.6 metres (an aerial photo), and 0.25 is 0.25
    degrees only when `unit="deg"` says so (a reanalysis product). Values outside what
    Earth Engine actually serves are stopped with the conversion in the message.
    """
    from cubexpress.geo.transform import _parsed_crs, metres_to_degrees

    if unit not in ("m", "deg"):
        raise ValueError(f'scale_unit must be "m" or "deg", got {unit!r}')

    if unit == "deg":
        if not _parsed_crs(crs).is_geographic:
            raise ValueError(
                f'scale_unit="deg" needs a geographic CRS, but "{crs}" is projected and takes '
                "metres"
            )
        if scale > MAX_DEGREES:
            raise ValueError(
                f"scale={scale} degrees is coarser than any grid in Earth Engine "
                f"(2.5, NCEP/NCAR). If you meant metres, drop scale_unit=\"deg\": metres is "
                f"the default"
            )
        return scale, -scale

    if scale < MIN_METRES:
        raise ValueError(
            f"scale={scale} metres is finer than any pixel in Earth Engine (0.6 m, NAIP). "
            f'If you meant degrees, pass scale_unit="deg" (0.05 is the MODIS CMG grid)'
        )

    if _parsed_crs(crs).is_geographic:
        scale_x, scale_y = metres_to_degrees(scale, latitude)
        return scale_x, -scale_y
    return scale, -scale


def bbox_to_rt(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    crs: str,
    scale: float,
    scale_unit: str = "m",
) -> RasterTransform:
    """Build a RasterTransform covering the given bbox at `scale` metres per pixel.

    The output raster's upper-left corner is anchored at (xmin, ymax). If the bbox dimensions
    aren't exact multiples of the pixel size, the resulting raster extends slightly beyond
    `xmax` and below `ymin` (rounded up) to guarantee full coverage of the input bbox.

    Args:
        xmin: Minimum x coordinate (longitude or easting) in `crs`.
        ymin: Minimum y coordinate (latitude or northing) in `crs`.
        xmax: Maximum x coordinate in `crs`.
        ymax: Maximum y coordinate in `crs`.
        crs: Coordinate Reference System (EPSG code or WKT).
        scale: Pixel size in metres, or in degrees when `scale_unit="deg"`.
        scale_unit: "m" (default) or "deg". In metres, a geographic CRS gets the value
            converted to degrees at the bbox latitude; in degrees, the value is taken as is
            and needs a geographic CRS.

    Returns:
        RasterTransform whose bbox contains the input bbox at the given scale.
    """
    for name, value in (("xmin", xmin), ("ymin", ymin), ("xmax", xmax), ("ymax", ymax), ("scale", scale)):
        _require_number(name, value)
    if scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale}")
    if xmin >= xmax:
        raise ValueError(f"xmin must be < xmax, got xmin={xmin}, xmax={xmax}")
    if ymin >= ymax:
        raise ValueError(f"ymin must be < ymax, got ymin={ymin}, ymax={ymax}")

    scale_x, scale_y = _pixel_size(crs, scale, (ymin + ymax) / 2, scale_unit)

    width = math.ceil((xmax - xmin) / scale_x)
    height = math.ceil((ymax - ymin) / abs(scale_y))

    return RasterTransform(
        crs=crs,
        translate_x=xmin,
        translate_y=ymax,
        scale_x=scale_x,
        scale_y=scale_y,
        width=width,
        height=height,
    )


def to_polygon(
    geometry,
) -> shapely.Polygon | shapely.MultiPolygon:
    """Normalize various polygon inputs to a shapely (Multi)Polygon.

    Accepts:
      - a shapely Polygon or MultiPolygon (returned as-is)
      - a WKT string: "POLYGON ((lon lat, ...))"
      - a GeoJSON string: '{"type": "Polygon", ...}'
      - a GeoJSON geometry dict: {"type": "Polygon", "coordinates": [...]}
      - a GeoJSON Feature dict: {"type": "Feature", "geometry": {...}}
      - a GeoJSON FeatureCollection dict: all features are unioned

    It absorbs formats, not sources. A GeoDataFrame, a GeoSeries or a file path are
    sources: convert them first (the error message shows the one line that does it).

    Args:
        geometry: a shapely (Multi)Polygon, a WKT string, or a GeoJSON dict or string.

    Returns:
        A shapely Polygon or MultiPolygon.

    Raises:
        TypeError: if the input type is unsupported or yields a non-polygon.
        ValueError: if a WKT or GeoJSON string can't be parsed.
    """
    # already shapely
    if isinstance(geometry, (shapely.Polygon, shapely.MultiPolygon)):
        return geometry

    # WKT string or GeoJSON string
    if isinstance(geometry, str):
        if geometry.lstrip().startswith("{"):
            import json

            try:
                geometry = json.loads(geometry)
            except Exception as exc:
                raise ValueError(f"could not parse GeoJSON string: {exc}") from exc
        else:
            from shapely import wkt

            try:
                geom = wkt.loads(geometry)
            except Exception as exc:
                raise ValueError(f"could not parse WKT string: {exc}") from exc
            if not isinstance(geom, (shapely.Polygon, shapely.MultiPolygon)):
                raise TypeError(f"WKT parsed to {geom.geom_type}, expected Polygon/MultiPolygon.")
            return geom

    # GeoJSON dict
    if isinstance(geometry, dict):
        from shapely.geometry import shape

        gtype = geometry.get("type")
        if gtype == "FeatureCollection":
            feats = geometry.get("features", [])
            if not feats:
                raise ValueError("FeatureCollection has no features.")
            geom = shapely.union_all([shape(f["geometry"]) for f in feats])
        elif gtype == "Feature":
            geom = shape(geometry["geometry"])
        else:
            geom = shape(geometry)  # assume it's a geometry dict
        if not isinstance(geom, (shapely.Polygon, shapely.MultiPolygon)):
            raise TypeError(f"GeoJSON is a {geom.geom_type}, expected Polygon/MultiPolygon.")
        return geom

    raise TypeError(
        f"unsupported geometry input: {type(geometry).__name__}. Expected a shapely "
        f"(Multi)Polygon, a WKT string, or a GeoJSON dict/string. From geopandas use "
        f"gdf.geometry.iloc[0] (one feature) or gdf.union_all() (the whole layer); "
        f"from a file use geopandas.read_file(path).geometry.iloc[0]."
    )


def polygon_to_rt(
    geometry: shapely.Polygon,
    scale: float,
    crs: str = "EPSG:4326",
    target_crs: str | None = None,
    scale_unit: str = "m",
) -> RasterTransform:
    """Build a RasterTransform that covers a polygon's bbox.

    Earth Engine downloads need an axis-aligned raster grid, so this function takes a
    polygon and returns a RasterTransform fitted to it. The polygon gives the area, the
    `scale` gives the pixel size, and the dimensions come from dividing one by the other.

    Accepts anything `to_polygon` accepts: a shapely Polygon or MultiPolygon, a WKT string,
    or a GeoJSON dict or string. A MultiPolygon is covered by the bbox of all its parts.

    Args:
        geometry: a shapely (Multi)Polygon, a WKT string, or a GeoJSON dict or string.
        scale: Pixel size in metres, or in degrees when `scale_unit="deg"`.
        scale_unit: "m" (default) or "deg". A geographic target in metres gets the value
            converted to degrees at the polygon's latitude; in degrees it is taken as is.
        crs: CRS of the input geometry. Default 'EPSG:4326'.
        target_crs: CRS of the output. None → the input CRS when it is already projected, or
            the automatic UTM zone by centroid when the input is geographic.

    Returns:
        RasterTransform in target_crs covering the polygon's bbox.

    Raises:
        TypeError: if the input is not a polygon or cannot be parsed as one.
        ValueError: if scale <= 0, the polygon is topologically invalid, or
            coordinates are inconsistent with the declared CRS.
    """
    _require_number("scale", scale)
    if scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale}")

    geometry = to_polygon(geometry)

    if not geometry.is_valid:
        from shapely.validation import explain_validity

        raise ValueError(f"Invalid polygon: {explain_validity(geometry)}")

    # Sanity check: coords vs declared CRS
    xmin, ymin, xmax, ymax = geometry.bounds
    if crs == "EPSG:4326":
        if not (-180 <= xmin <= 180 and -90 <= ymin <= 90 and -180 <= xmax <= 180 and -90 <= ymax <= 90):
            raise ValueError(
                f"Declared crs='EPSG:4326' but bounds={geometry.bounds} look projected. "
                f"Did you forget to pass crs=? (e.g. crs='EPSG:32718')"
            )

    # Decide target_crs: the input CRS when it is already projected, auto-UTM when geographic
    if target_crs is None:
        from cubexpress.geo.transform import _gee_crs, _parsed_crs

        parsed = _parsed_crs(crs)
        if parsed.is_geographic:
            if crs == "EPSG:4326":
                lon_c, lat_c = geometry.centroid.x, geometry.centroid.y
            else:
                t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
                lon_c, lat_c = t.transform(geometry.centroid.x, geometry.centroid.y)
            target_crs = _utm_zone_epsg(lon_c, lat_c)
        else:
            # Keep the input CRS, in the spelling Earth Engine accepts: a GeoParquet declares
            # PROJJSON, and a WKT1 is respected as is, which is the escape hatch for a code
            # Earth Engine does not know yet (Equi7, for example).
            target_crs = _gee_crs(crs)

    # Reproject FULL polygon (not just bounds) to target_crs
    if crs == target_crs:
        bxmin, bymin, bxmax, bymax = geometry.bounds
    else:
        transformer = Transformer.from_crs(crs, target_crs, always_xy=True)
        poly_proj = shp_transform(transformer.transform, geometry)
        bxmin, bymin, bxmax, bymax = poly_proj.bounds

    return bbox_to_rt(bxmin, bymin, bxmax, bymax, crs=target_crs, scale=scale, scale_unit=scale_unit)


def asset_to_rt(
    image,
    scale: float | None = None,
    scale_unit: str = "m",
) -> RasterTransform:
    """Build a RasterTransform from a GEE asset or ee.Image, in its native CRS.

    Queries Earth Engine for the asset's native projection, transform and
    dimensions, and constructs a RasterTransform that covers the full image.

    Earth Engine must be initialized before calling this:
        >>> import ee
        >>> ee.Initialize(project='your-project')

    Args:
        image: Either an Earth Engine asset path (str) or an ee.Image instance.
            Accepting ee.Image lets you build complex computed images
            (e.g. img.clip(), img1.add(img2), ic.median()) and pass them
            directly without serializing.
        scale: Pixel size in metres of the native CRS, or in degrees when `scale_unit="deg"`
            (useful for assets stored in 4326, like JRC Global Surface Water). None → use the
            asset's native scale (10 m for S2 B2/B3/B4/B8, 30 m for Landsat, etc.).
        scale_unit: "m" (default) or "deg". Only used when `scale` is given.

    Returns:
        RasterTransform in the image's native CRS, covering its full footprint.

    Raises:
        TypeError: if image is not str or ee.Image.
        ValueError: if asset has no bands or scale <= 0.
    """
    import ee

    if isinstance(image, str):
        if not image:
            raise TypeError("image string must be non-empty")
        img = ee.Image(image)
    elif isinstance(image, ee.Image):
        img = image
    else:
        raise TypeError(f"image must be str (asset id) or ee.Image, got {type(image).__name__}")

    info = img.getInfo()

    bands = info.get("bands", [])
    if not bands:
        raise ValueError(f"Image has no bands: {image!r}")

    band0 = bands[0]
    if not all(key in band0 for key in ("crs", "crs_transform", "dimensions")):
        raise ValueError(
            f"The image has no native projection: {image!r}. That happens with computed "
            f"images like ee.Image.constant(), which have no crs, transform or dimensions. "
            f"Use a projected asset, or build the RasterTransform by hand."
        )

    native_crs = band0["crs"]
    native_transform = band0["crs_transform"]
    native_width, native_height = band0["dimensions"]

    # Native scale: return the exact RT of the file on disk
    if scale is None:
        return RasterTransform(
            crs=native_crs,
            translate_x=native_transform[2],
            translate_y=native_transform[5],
            scale_x=native_transform[0],
            scale_y=native_transform[4],
            width=native_width,
            height=native_height,
        )

    _require_number("scale", scale)
    if scale <= 0:
        raise ValueError(f"scale must be > 0, got {scale}")

    # Custom scale: recompute dimensions over the native bbox
    xmin = native_transform[2]
    ymax = native_transform[5]
    xmax = xmin + native_width * native_transform[0]
    ymin = ymax + native_height * native_transform[4]  # native_transform[4] is negative

    return bbox_to_rt(xmin, ymin, xmax, ymax, crs=native_crs, scale=scale, scale_unit=scale_unit)
