from cubexpress.geotyping import GeotransformDict, RasterTransform, RasterTransformSet
from typing import List, Tuple
import utm


def geo2UTM(
    lon: float, 
    lat: float
) -> Tuple[float, float, str]:
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

def lonlat2geoTransforms(
    lon: float, 
    lat: float, 
    edge_size: int, 
    scale: int
) -> RasterTransformSet:
    """
    Generates a RasterTransformSet for a given point using its UTM projection.

    Args:
        lon (float): Longitude.
        lat (float): Latitude.
        edge_size (int): Number of pixels in the raster.
        scale (int): Spatial resolution in meters per pixel.
    
    Returns:
        RasterTransformSet: Transformation metadata for the raster.
    """
    x, y, crs = geo2UTM(lon, lat)
    half_extent = (edge_size * scale) / 2

    geotransform = GeotransformDict(
        scaleX=scale,
        shearX=0,
        translateX=x - half_extent,
        scaleY=-scale,  # Y-axis is inverted in geospatial images
        shearY=0,
        translateY=y + half_extent
    )

    return RasterTransformSet([
        RasterTransform(crs=crs, geotransform=geotransform, width=edge_size, height=edge_size)
    ])

def points2geoTransforms(
    points: List[Tuple[float, float]],  
    edge_size: int, 
    scale: int
) -> RasterTransformSet:
    """
    Generates a RasterTransformSet for a list of geographic points.

    Args:
        points (List[Tuple[float, float]]): List of (longitude, latitude) tuples.
        edge_size (int): Number of pixels in the raster.
        scale (int): Spatial resolution in meters per pixel.
    
    Returns:
        RasterTransformSet: Collection of raster transformations.
    """
    transforms = [
        lonlat2geoTransforms(lon, lat, edge_size, scale).rastertransformset[0]
        for lon, lat in points
    ]
    
    return RasterTransformSet(transforms)
