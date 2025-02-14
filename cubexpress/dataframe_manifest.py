from cubexpress.geo_typing import CRS, Geotransform, Bbox, GeoMetadata, GeoMetadatas
from cubexpress.user_utils import query_utm_crs_info, _create_query_entry
from typing import List, Optional, Dict, Tuple


import pandas as pd

# Función intermedia que genera los componentes GeoMetadata
def lonlatgeometadata(
    lon: float, 
    lat: float, 
    edge_size: int, 
    scale: int
) -> GeoMetadata:
    # Obtener las coordenadas UTM y el CRS usando query_utm_crs_info
    x, y, crs_code = query_utm_crs_info(lon, lat)
    
    # Definir CRS usando el código obtenido
    crs = CRS(code=crs_code)
    
    # Calcular la caja delimitadora (bounding box)
    bbox = Bbox(
        xmin=x - edge_size * scale / 2,
        ymin=y - edge_size * scale / 2,
        xmax=x + edge_size * scale / 2,
        ymax=y + edge_size * scale / 2
    )
    
    # Calcular los valores para la transformación afín
    geotransform = Geotransform(
        scaleX=scale,
        shearX=0,
        translateX=bbox.xmin,  # Usar min_x como translate_x
        scaleY=-scale,  # El eje Y se invierte en imágenes geoespaciales
        shearY=0,
        translateY=bbox.ymax,   # Usar max_y como translate_y
    )

    geo_metadatas = [GeoMetadata(crs=crs, geotransform=geotransform, width=edge_size, height=edge_size)]

    return GeoMetadatas(geometadatas=geo_metadatas)

# # #############
# # # Ejemplo 1 #
# # #############

# # Parámetros para el ejemplo 1
# lon = -76.5
# lat = -9.5
# edge_size = 128
# scale = 90

# # Llamada a la función point2geometadata para un solo punto
# geo_metadata = lonlatgeometadata(lon, lat, edge_size, scale)
# geo_metadata


def point2geometadata(
    points: List[Tuple[float, float]],  # Lista de tuplas (lon, lat)
    edge_size: int, 
    scale: int
) -> GeoMetadatas:
    """
    Esta función genera un GeoMetadatas para una lista de puntos, cada uno con su correspondiente GeoMetadata.
    """
    geo_metadatas = []

    # Para cada punto (lon, lat) en la lista de puntos, generar un GeoMetadata
    for lon, lat in points:
        geo_metadata = lonlatgeometadata(lon, lat, edge_size, scale)
        geo_metadatas.append(geo_metadata.geometadatas[0])

    # Devolver un GeoMetadatas con la lista de GeoMetadata
    return GeoMetadatas(geometadatas=geo_metadatas)


# #############
# # Ejemplo 1 #
# #############

# points = [(-76.5, -9.5)]
# edge_size = 128
# scale = 90

# # Llamada a la función points2geometadatas para una lista de puntos
# geo_metadatas = point2geometadata(points, edge_size, scale)
# geo_metadatas

# #############
# # Ejemplo 2 #
# #############

# points = [(-76.5, -9.5), (-77.0, -9.8), (-77.5, -10.5)]
# edge_size = 128
# scale = 90

# # Llamada a la función points2geometadatas para una lista de puntos
# geo_metadatas = point2geometadata(points, edge_size, scale)
# geo_metadatas



def dataframe_manifest(
    geometadatas: GeoMetadatas,  # Recibe una instancia de GeoMetadatas (una lista de GeoMetadata)
    bands: List[str] = [],
    collection: str = ""
) -> pd.DataFrame:  # Ahora devuelve una lista de manifiestos, uno por cada GeoMetadata

    query_data = []

    # Iterar sobre cada GeoMetadata en GeoMetadatas
    for i, geometadata in enumerate(geometadatas.geometadatas):
        # Crear el manifiesto para cada GeoMetadata
        manifest = {
            "assetId": collection,
            "fileFormat": "GEO_TIFF",  # Formato de archivo
            "bandIds": bands,  # Bandas de la imagen
            "grid": {
                "dimensions": {
                    "width": geometadata.width,  # El tamaño en píxeles
                    "height": geometadata.height,
                },
                "affineTransform": geometadata.geotransform.model_dump(),  # Transformación afín
                "crsCode": geometadata.crs.code,  # Código del CRS
            }

        }
        query_data.append(
            {
                "xmin": geometadata.geotransform.translateX,
                "ymax": geometadata.geotransform.translateY,
                "epsg": geometadata.crs,
                "edge_size": geometadata.width,
                "scale": geometadata.geotransform.scaleX,
                "manifest": manifest,
                "outname": f"{collection.replace('/', '_')}__{i:04d}.tif"
            }
        )

    query_table = pd.DataFrame(query_data)
    
    return query_table

# #############
# # Ejemplo 1 #
# #############

# lon = -76.5
# lat = -9.5
# edge_size = 128
# scale = 90
# bands=["elevation"]
# collection="NASA/NASADEM_HGT/001"

# # Llamada a la función point2geometadata para un solo punto
# geo_metadata = lonlatgeometadata(lon, lat, edge_size, scale)

# # Llamada a la función generate_manifest pasando el GeoMetadatas
# manifest = dataframe_manifest(geometadatas=geo_metadata, bands=bands, collection=collection)

# # Mostrar el manifiesto generado
# print(manifest)


# #############
# # Ejemplo 2 #
# #############
# points = [(-76.5, -9.5)]
# edge_size = 128
# scale = 90
# bands = ["elevation"]
# collection = "NASA/NASADEM_HGT/001"

# # Llamada a la función point2geometadata para una lista de puntos
# geo_metadatas = point2geometadata(points=points, edge_size=edge_size, scale=scale)

# # Llamada a la función generate_manifest pasando el GeoMetadatas
# manifests = dataframe_manifest(geometadatas=geo_metadatas, bands=bands, collection=collection)

# # Mostrar los manifiestos generados
# print("Manifiestos usando point2geometadata (varios puntos):")
# print(manifests)


# #############
# # Ejemplo 3 #
# #############
# points = [(-76.5, -9.5), (-77.0, -9.8), (-77.5, -10.5)]
# edge_size = 128
# scale = 90
# bands = ["elevation"]
# collection = "NASA/NASADEM_HGT/001"

# # Llamada a la función point2geometadata para una lista de puntos
# geo_metadatas = point2geometadata(points=points, edge_size=edge_size, scale=scale)

# # Llamada a la función generate_manifest pasando el GeoMetadatas
# manifests = dataframe_manifest(geometadatas=geo_metadatas, bands=bands, collection=collection)

# # Mostrar los manifiestos generados
# print("Manifiestos usando point2geometadata (varios puntos):")
# print(manifests)


#############
# Ejemplo 4 #
#############

geo_metadata_1 = GeoMetadata(
    crs=CRS(code="EPSG:32718"), 
    geotransform = Geotransform(
        scaleX=90,
        shearX=0,
        translateX=329583.7418991233,
        scaleY=-90,
        shearY=0,
        translateY=8955272.65902687
    ), 
    width=128, 
    height=128
)

geo_metadatas = GeoMetadatas(
    geometadatas=[
        geo_metadata_1
    ]
)
bands = ["elevation"]
collection = "NASA/NASADEM_HGT/001"

table_manifest = dataframe_manifest(geometadatas=geo_metadatas, bands=bands, collection=collection)

# Mostrar los manifiestos generados
print("Manifiestos construidos desde cero:")
print(table_manifest)









# #############
# # Ejemplo 4 #
# #############

# geotransforms = [
#     {
#         "scaleX": 90,
#         "shearX": 0,
#         "translateX": 329583.7418991233,
#         "scaleY": -90,
#         "shearY": 0,
#         "translateY": 8955272.65902687
#     },
#     {
#         "scaleX": 100, 
#         "shearX": 0, 
#         "translateX": 330000.7418991233, 
#         "scaleY": -100, 
#         "shearY": 0, 
#         "translateY": 8960000.65902687
#     }
# ]
# crs = "EPSG:32718"
# edge_size = 128
# bands = ["elevation"]
# collection = "NASA/NASADEM_HGT/001"

# # Llamada a la función dataframe_manifest_getpixel_img pasando la lista de geotransforms y otros parámetros
# table = dataframe_manifest_getpixel_img(
#     geotransforms=geotransforms,
#     crs=crs,
#     edge_size=edge_size,
#     bands=bands,
#     collection=collection
# )

# # Mostrar el DataFrame generado
# print(table)
