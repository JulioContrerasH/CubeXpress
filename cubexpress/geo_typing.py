from pydantic import BaseModel, field_validator
from typing import List, Optional
import ee

# Definición de CRS
class CRS(BaseModel):
    code: str  # EPSG code (e.g., "EPSG:4326")

    #@field_validator
    #def check_epsg(self, value):
    #    if not ee.Projection(value).getInfo():
    #        raise ValueError(f"Invalid EPSG code. Only EPSG codes and OGC WKT are supported. Got: {value}")

# Definición de Geotransform
class Geotransform(BaseModel):
    scaleX: int  # Resolution in the X axis (e.g., pixel size in meters or degrees)
    shearX: int
    translateX: float  # The X coordinate of the top left corner of the image
    scaleY: int  # Resolution in the Y axis (e.g., pixel size in meters or degrees)
    shearY: int
    translateY: float  # The Y coordinate of the top left corner of the image

# Definición de Bbox
class Bbox(BaseModel):
    xmin: float  # Minimum longitude (left edge)
    ymin: float  # Minimum latitude (bottom edge)
    xmax: float  # Maximum longitude (right edge)
    ymax: float  # Maximum latitude (top edge)

# Clase GeoMetadata que utiliza las anteriores
class GeoMetadata(BaseModel):
    crs: CRS
    geotransform: Geotransform
    width: int
    height: int

# Ejemplo de clase GeoMetadatas
class GeoMetadatas(BaseModel):
    geometadatas: List[GeoMetadata]
