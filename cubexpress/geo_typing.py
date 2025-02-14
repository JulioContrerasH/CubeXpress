from pydantic import BaseModel, field_validator
from typing import List, Optional
import ee

from pyproj import CRS

large_list = [CRS.from_wkt('PROJCS["WGS 84 / Equi7 Europe",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Azimuthal_Equidistant"],PARAMETER["latitude_of_center",53],PARAMETER["longitude_of_center",24],PARAMETER["false_easting",5837287.82],PARAMETER["false_northing",2121415.696],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","27704"]]') for _ in range(100000)]




# Definición de CRS
class CRS(BaseModel):
    code: str  # EPSG code (e.g., "EPSG:4326")

    @field_validator
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
