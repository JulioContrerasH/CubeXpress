from cubexpress.geotyping import GeotransformDict, RasterTransform, RasterTransformSet
from cubexpress.manifest import dataframe_manifest
from cubexpress.download import getCube

import ee
ee.Initialize()


geo_metadata_1 = RasterTransform(
    crs="EPSG:32718", 
    geotransform = GeotransformDict(
        scaleX=90,
        shearX=0,
        translateX=329583.7418991233,
        scaleY=-90,
        shearY=0,
        translateY=8955272.65902687
    ), 
    width=8192, 
    height=8192
)
print(geo_metadata_1)

geo_metadata_3 = RasterTransform(
    crs="EPSG:3857", 
    geotransform = dict(
        scaleX=100,
        shearX=0,
        translateX=300000,
        scaleY=-100,
        shearY=0,
        translateY=400000
    ), 
    width=256, 
    height=256
)

# Create a set of metadata entries
metadata_set = RasterTransformSet(
    rastertransformset=[
        geo_metadata_1
    ]
)
bands = ["elevation"]
collection = "NASA/NASADEM_HGT/001"

# Table manifest
table_manifest = dataframe_manifest(
    geometadatas=metadata_set, 
    bands=bands, 
    image=collection
)
print(table_manifest)


table_manifest.manifest[0]

table_manifest2 = dataframe_manifest(
    geometadatas=metadata_set, 
    bands=bands, 
    image=ee.Image("NASA/NASADEM_HGT/001").divide(1000)
)


getCube(table_manifest, nworkers=4, deep_level=5, output_path="images", quiet=False)
getCube(table_manifest2, nworkers=4, deep_level=5, output_path="images_deep", quiet=False)
























import rasterio as rio
import pandas as pd
import numpy as np

# Rutas de archivos

neon_image_path = "/home/contreras/Documents/GitHub/NEON/neon_images/projects_neon-prod-earthengine_assets_HSI_REFL_002_2022_UNDE_5__0000.tif"
table_path = "/home/contreras/Documents/GitHub/NEON/tables/S2toAVIRIS_norm.csv"
output_path = "/home/contreras/Documents/GitHub/NEON/neon_images/projects_neon-prod-earthengine_assets_HSI_REFL_002_2022_UNDE_5__0000_s2.tif"

df_s2_aviris_norm = pd.read_csv(table_path)

sentinel_bands = df_s2_aviris_norm.columns[2:] 

# Crear un diccionario con los índices de bandas NEON que corresponden a cada banda Sentinel-2
band_indices = {band: df_s2_aviris_norm[df_s2_aviris_norm[band].notnull()].index.to_list()
                for band in sentinel_bands}

# Cargar la imagen NEON hiperespectral
with rio.open(neon_image_path) as src:
    neon_img = src.read()  # Leer todas las bandas (426, H, W)
    profile = src.profile  # Guardar metadatos


# Obtener dimensiones de la imagen
_, height, width = neon_img.shape

# Crear un array para la imagen "S2-alike" con 12 bandas
s2_alike_img = np.zeros((len(sentinel_bands), height, width), dtype=np.float32)

# Aplicar la convolución para generar cada banda de Sentinel-2
for i, band in enumerate(sentinel_bands):

    indices = band_indices[band]  # Bandas de NEON a usar
    weights = df_s2_aviris_norm.loc[indices, band].values  # Pesos de convolución

    # Asegurar que los pesos no tengan NaN
    weights = np.nan_to_num(weights)

    # Multiplicar las bandas seleccionadas por sus pesos y sumarlas
    s2_alike_img[i] = np.tensordot(weights, neon_img[indices, :, :], axes=([0], [0]))

# Actualizar el perfil para la nueva imagen con 12 bandas
profile.update(count=s2_alike_img.shape[0], dtype='float32')

# Guardar la imagen resultante
with rio.open(output_path, "w", **profile) as dst:
    dst.write(s2_alike_img)

print(f"Imagen Sentinel-2 generada: {output_path}")
