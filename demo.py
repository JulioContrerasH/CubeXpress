from pydantic import BaseModel
from typing import List, Tuple
import utm

# DataClasses
class CRS(BaseModel):
    code: str  # EPSG code

class Geotransform(BaseModel):
    scale_x: float  # Resolution in the X axis
    scale_y: float  # Resolution in the Y axis
    translate_x: float  # The X coordinate of the top left corner
    translate_y: float  # The Y coordinate of the top left corner

class Bbox(BaseModel):
    min_x: float  # Minimum longitude
    min_y: float  # Minimum latitude
    max_x: float  # Maximum longitude
    max_y: float  # Maximum latitude

class GeoMetadata(BaseModel):
    crs: CRS
    geotransform: Geotransform
    bbox: Bbox

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


# Función intermedia que genera los componentes GeoMetadata
def point2geometadata(lon: float, lat: float, scale: float, edge_size: float) -> GeoMetadata:
    # Obtener las coordenadas UTM y el CRS usando query_utm_crs_info
    x, y, crs_code = query_utm_crs_info(lon, lat)
    
    # Definir CRS usando el código obtenido
    crs = CRS(code=crs_code)
    
    # Calcular los valores para la transformación afín
    geotransform = Geotransform(
        scale_x=scale,
        scale_y=-scale,  # El eje Y se invierte en imágenes geoespaciales
        translate_x=x,
        translate_y=y
    )
    
    # Calcular la caja delimitadora (bounding box)
    bbox = Bbox(
        min_x=x - edge_size * scale / 2,
        min_y=y - edge_size * scale / 2,
        max_x=x + edge_size * scale / 2,
        max_y=y + edge_size * scale / 2
    )
    
    return GeoMetadata(crs=crs, geotransform=geotransform, bbox=bbox)


# Ejemplo de uso
lon = -76.5
lat = -9.5
scale = 90  # Resolución
edge_size = 128  # Tamaño de la cuadrícula

geo_metadata = point2geometadata(lon, lat, scale, edge_size)
print(geo_metadata)



def generate_manifest(row, bands):
    # Convert from EPSG to UTM
    lon_utm, lat_utm, zone_epsg = query_utm_crs_info(row["x"], row["y"])
    
    crs = CRS(code=zone_epsg)
    geotransform = Geotransform(
        scale_x=row["resolution"], 
        scale_y=-row["resolution"], 
        translate_x=lon_utm, 
        translate_y=lat_utm
    )
    
    # Calculate bounding box based on the edge size
    bbox = Bbox(
        min_x=lon_utm - row["edge_size"] * row["resolution"] / 2,
        min_y=lat_utm - row["edge_size"] * row["resolution"] / 2,
        max_x=lon_utm + row["edge_size"] * row["resolution"] / 2,
        max_y=lat_utm + row["edge_size"] * row["resolution"] / 2
    )
    
    geo_metadata = GeoMetadata(crs=crs, geotransform=geotransform, bbox=bbox)
    
    manifest = {
        "assetId": row["collection"],
        "fileFormat": "GEO_TIFF",
        "bandIds": bands,
        "grid": {
            "dimensions": {
                "width": row["edge_size"],
                "height": row["edge_size"],
            },
            "affineTransform": geotransform.model_dump(),  # Use model_dump() here
            "crsCode": crs.code,
        },
        "bbox": bbox.model_dump(),  # Use model_dump() here
    }
    
    return manifest

# Example usage
row = {
    "collection": "NASA/NASADEM_HGT/001",
    "x": -76.5,
    "y": -9.5,
    "edge_size": 128,
    "resolution": 90
}
bands = ["elevation"]

manifest = generate_manifest(row, bands)
print(manifest)



from pydantic import BaseModel
from typing import List, Tuple
import utm




# Función intermedia que genera los componentes GeoMetadata
def point2geometadata(x: float, y: float, scale: float, edge_size: float) -> GeoMetadata:
    crs = CRS(code="EPSG:32718")  # Ajusta el EPSG según sea necesario
    
    # Calcular los valores para la transformación afín
    geotransform = Geotransform(
        scale_x=scale,
        scale_y=-scale,  # El eje Y se invierte en imágenes geoespaciales
        translate_x=x,
        translate_y=y
    )
    
    # Calcular la caja delimitadora (bounding box)
    bbox = Bbox(
        min_x=x - edge_size * scale / 2,
        min_y=y - edge_size * scale / 2,
        max_x=x + edge_size * scale / 2,
        max_y=y + edge_size * scale / 2
    )
    
    return GeoMetadata(crs=crs, geotransform=geotransform, bbox=bbox)

# Ejemplo de uso
x = 335343.7418991233
y = 8949512.65902687
scale = 90  # Resolución
edge_size = 128  # Tamaño de la cuadrícula
geo_metadata = point2geometadata(x, y, scale, edge_size)
print(geo_metadata)


# Función 'generate_manifest' que usa 'point2geometadata' cuando recibe coordenadas y tamaño de cuadrícula
def generate_manifest(*args, bands: List[str], collection: str) -> dict:
    """
    Esta función genera el manifiesto de la imagen de dos maneras:
    1. Usando coordenadas (x, y), tamaño de cuadrícula y resolución (cuando se pasan como parámetros).
    2. Usando los componentes `geotransform`, `crs` y `bbox` ya calculados.
    """
    if len(args) == 4:  # Caso 1: Recibe (x, y, size, bands)
        x, y, size, resolution = args
        geo_metadata = point2geometadata(x, y, resolution, size)
    elif len(args) == 3:  # Caso 2: Recibe los componentes directamente (geotransform, crs, bbox)
        geotransform, crs, bbox = args
        geo_metadata = GeoMetadata(crs=crs, geotransform=geotransform, bbox=bbox)
    else:
        raise ValueError("Invalid number of arguments. Must provide either coordinates or components.")

    # Crear el manifiesto
    manifest = {
        "assetId": collection,
        "fileFormat": "GEO_TIFF",
        "bandIds": bands,
        "grid": {
            "dimensions": {
                "width": geo_metadata.geotransform.scale_x,  # Suponiendo que el edge_size es proporcionado correctamente
                "height": geo_metadata.geotransform.scale_y,
            },
            "affineTransform": geo_metadata.geotransform.model_dump(),
            "crsCode": geo_metadata.crs.code,
        },
        "bbox": geo_metadata.bbox.model_dump(),
    }
    
    return manifest

# Ejemplo 1: Usando coordenadas (x, y), tamaño de cuadrícula y resolución
x = -76.5
y = -9.5
size = 128
resolution = 90
bands = ["elevation"]
collection = "NASA/NASADEM_HGT/001"

manifest = generate_manifest(x, y, size, resolution, bands=bands, collection=collection)
print("Manifest usando coordenadas:")
print(manifest)

# Ejemplo 2: Usando componentes directamente (geotransform, crs, bbox)
crs_code = "EPSG:32718"  # Ejemplo de CRS
geotransform = Geotransform(scale_x=90, scale_y=-90, translate_x=335343.7418991233, translate_y=8949512.65902687)
bbox = Bbox(min_x=329583.7418991233, min_y=8943752.65902687, max_x=341103.7418991233, max_y=8955272.65902687)

manifest = generate_manifest(geotransform, CRS( ), bbox, bands=bands, collection=collection)
print("\nManifest usando componentes:")
print(manifest)
