import utm
from cubexpress.geotyping import RasterTransform

# Define your GeotransformDict type if not already defined
GeotransformDict = dict[str, float]

def geo2utm(
    lon: float, 
    lat: float
) -> tuple[float, float, str]:
    """
    Converts latitude and longitude coordinates to UTM coordinates and returns the EPSG code.

    Args:
        lon (float): Longitude.
        lat (float): Latitude.
    
    Returns:
        Tuple[float, float, str]: UTM coordinates (x, y) and the EPSG code.
    """
    x, y, zone, _ = utm.from_latlon(lat, lon)
    epsg_code = f"326{zone:02d}" if lat >= 0 else f"327{zone:02d}"
    return x, y, f"EPSG:{epsg_code}"

def lonlat2rt(
    lon: float, 
    lat: float, 
    edge_size: int, 
    scale: int
) -> 'RasterTransform':
    """
    Generates a RasterTransformSet for a given point using its UTM projection.

    Args:
        id (str): Identifier for the raster.
        lon (float): Longitude.
        lat (float): Latitude.
        edge_size (int): Number of pixels in the raster.
        scale (int): Spatial resolution in meters per pixel.
    
    Returns:
        RasterTransformSet: Transformation metadata for the raster.
    """
    x, y, crs = geo2utm(lon, lat)
    half_extent = (edge_size * scale) / 2

    geotransform = GeotransformDict(
        scaleX=scale,
        shearX=0,
        translateX=x - half_extent,
        scaleY=-scale,  # Y-axis is inverted in geospatial images
        shearY=0,
        translateY=y + half_extent
    )

    return RasterTransform(
        crs=crs,
        geotransform=geotransform,
        width=edge_size,
        height=edge_size
    )