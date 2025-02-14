__init__.py:

# vacío

geo_typing.py:

from pydantic import BaseModel
from typing import List, Optional

# Definición de CRS
class CRS(BaseModel):
    code: str  # EPSG code (e.g., "EPSG:4326")

# Definición de Geotransform
class Geotransform(BaseModel):
    scale_x: int  # Resolution in the X axis (e.g., pixel size in meters or degrees)
    shear_x: int
    translate_x: float  # The X coordinate of the top left corner of the image
    scale_y: int  # Resolution in the Y axis (e.g., pixel size in meters or degrees)
    shear_y: int
    translate_y: float  # The Y coordinate of the top left corner of the image

# Definición de Bbox
class Bbox(BaseModel):
    min_x: float  # Minimum longitude (left edge)
    min_y: float  # Minimum latitude (bottom edge)
    max_x: float  # Maximum longitude (right edge)
    max_y: float  # Maximum latitude (top edge)

# Clase GeoMetadata que utiliza las anteriores
class GeoMetadata(BaseModel):
    crs: CRS
    geotransform: Geotransform
    width: int
    heigth: int

# Ejemplo de clase GeoMetadatas
class GeoMetadatas(BaseModel):
    geometadatas: List[GeoMetadata]



main.py:
from cubexpress.geo_typing import CRS, Geotransform, Bbox, GeoMetadata
from cubexpress.user_utils import query_utm_crs_info
from typing import List, Optional, Dict

# Función intermedia que genera los componentes GeoMetadata
def point2geometadata(
        lon: float, 
        lat: float, 
        edge_size: int, 
        scale: int) -> GeoMetadata:
    # Obtener las coordenadas UTM y el CRS usando query_utm_crs_info
    x, y, crs_code = query_utm_crs_info(lon, lat)
    
    # Definir CRS usando el código obtenido
    crs = CRS(code=crs_code)
    
    # Calcular la caja delimitadora (bounding box)
    bbox = Bbox(
        min_x=x - edge_size * scale / 2,
        min_y=y - edge_size * scale / 2,
        max_x=x + edge_size * scale / 2,
        max_y=y + edge_size * scale / 2
    )
    
    # Calcular los valores para la transformación afín
    geotransform = Geotransform(
        scale_x=scale,
        shear_x=0,
        translate_x=bbox.min_x,  # Usar min_x como translate_x
        scale_y=-scale,  # El eje Y se invierte en imágenes geoespaciales
        shear_y=0,
        translate_y=bbox.max_y,   # Usar max_y como translate_y
    )
    return GeoMetadata(crs=crs, geotransform=geotransform, width=edge_size, heigth=edge_size) # ---> podría ir width=width, heigth=heigth, ver cómo <--

#############
# Ejemplo 1 #
#############

# lon = -76.5  # Longitud en grados decimales
# lat = -9.5   # Latitud en grados decimales
# scale = 90.0  # Resolución en metros por píxel
# edge_size = 128.0  # Tamaño del área en metros

# # Llamada a la función point2geometadata
# geo_metadata = point2geometadata(lon, lat, scale, edge_size)
# geo_metadata.geotransform.scale_x

# Función 'generate_manifest' que usa 'point2geometadata' cuando recibe coordenadas y tamaño de cuadrícula
def generate_manifest(
    x: Optional[float] = None, 
    y: Optional[float] = None, 
    edge_size: Optional[int] = None, 
    scale: Optional[int] = None, 
    geotransform: Optional[Dict[str, float]] = None, 
    crs: Optional[str] = None, 
    bands: List[str] = [], 
    collection: str = ""
) -> dict: # ---> podría ir date, pero no se usaría para los image, ver cómo. *args podría ir en otro orden, ver si hay error o afecta <--
    """
    Esta función genera el manifiesto de la imagen de dos maneras:
    1. Usando coordenadas (x, y), tamaño de cuadrícula y resolución (cuando se pasan como parámetros).
    2. Usando los componentes `geotransform`, `crs` y `bbox` ya calculados.
    """
    if x is not None and y is not None and edge_size is not None and scale is not None:
        geo_metadata = point2geometadata(x, y, edge_size, scale)
    elif geotransform is not None and crs is not None and edge_size is not None:
        # Convertimos el geotransform si es un diccionario
        if isinstance(geotransform, dict):
            geotransform = Geotransform(**geotransform)
        # Convertimos el crs si es un string
        crs = CRS(code=crs)
        geo_metadata = GeoMetadata(crs=crs, geotransform=geotransform, width=edge_size, heigth=edge_size) # ---> podría ir width=width, heigth=heigth, ver cómo <--
    else:
        raise ValueError("Invalid arguments. Must provide either coordinates (x, y) and size, or geotransform and crs.")

    # Crear el manifiesto
    manifest = {
        "assetId": collection,
        "fileFormat": "GEO_TIFF", #
        "bandIds": bands, #
        "grid": { #
            "dimensions": { # ->
                "width": geo_metadata.width,  # Suponiendo que el edge_size es proporcionado correctamente
                "height": geo_metadata.heigth,
            },
            "affineTransform": geo_metadata.geotransform.model_dump(), #->
            "crsCode": geo_metadata.crs.code, # ->
        }
    }
    return manifest


#############
# Ejemplo 1 #
#############

# Parámetros para el ejemplo 1
x = -76.5
y = -9.5
edge_size = 128
scale = 90
bands = ["elevation"]
collection = "NASA/NASADEM_HGT/001"

# Llamada a la función generate_manifest pasando las coordenadas y otros parámetros
manifest = generate_manifest(
    x=x,
    y=y,
    edge_size=edge_size,
    scale=scale,
    bands=bands,
    collection=collection
)

# Mostrar el manifiesto generado
print("Manifest usando coordenadas:")
print(manifest)

#############
# Ejemplo 2 #
#############

# Parámetros para el ejemplo 2
crs = "EPSG:32718"  # Código del CRS
geotransform = {
    "scale_x": 90,
    "shear_x": 0,
    "translate_x": 329583.7418991233,
    "scale_y": -90,
    "shear_y": 0,
    "translate_y": 8955272.65902687
}  # Geotransform como un diccionario

edge_size = 128
bands = ["elevation"]
collection = "NASA/NASADEM_HGT/001"

# Llamada a la función generate_manifest pasando el geotransform, crs y otros parámetros
manifest = generate_manifest(
    geotransform=geotransform,
    crs=crs,
    edge_size=edge_size,
    bands=bands,
    collection=collection
)

# Mostrar el manifiesto generado
print("\nManifest usando componentes:")
print(manifest)


test_geo.py:

from cubexpress.main import generate_manifest
from cubexpress.geo_typing import CRS, Geotransform, Bbox
from typing import List

def test_generate_manifest():
    row = {
        "x": -76.5,
        "y": -9.5,
        "edge_size": 128,
        "resolution": 90
    }
    bands = ["elevation"]
    collection = "NASA/NASADEM_HGT/001"

    manifest = generate_manifest(row['x'], row['y'], row['edge_size'], row['resolution'], bands, collection)
    assert manifest['assetId'] == collection
    assert manifest['fileFormat'] == 'GEO_TIFF'
    assert 'crsCode' in manifest['grid']




user_utils.py:

import utm
from typing import Tuple

# Función para convertir latitud y longitud a UTM
def query_utm_crs_info(lon: float, lat: float) -> Tuple[float, float, str]:
    """
    Converts a pair of lat, lon to UTM coordinates.

    Args:
        lon (float): The longitude of the point.
        lat (float): The latitude of the point.
    
    Returns:
        Tuple[float, float, str]: The UTM coordinates and the 
            EPSG code of the zone.
    """
    x, y, zone, _ = utm.from_latlon(lat, lon)
    zone_epsg = f"326{zone:02d}" if lat >= 0 else f"327{zone:02d}"
    return x, y, "EPSG:" + zone_epsg
