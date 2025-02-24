from cubexpress.geotyping import GeotransformDict, RasterTransform, RasterTransformSet
from cubexpress.manifest import dataframe_manifest
from cubexpress.download import getCube

import ee
ee.Initialize()




from cubexpress import RasterTransform, RasterTransformSet
import cubexpress
import pandas as pd
import geopandas as gpd

import ee
ee.Initialize()

# Load the table of images positions
table_path = "tables/neon_equigrid_geodata.gpkg"
table = gpd.read_file(table_path)
table["ID"] = ["NEON_S2__" + str(i + 1).zfill(4) for i in range(len(table))]
bands_neon = [f"B{str(i).zfill(3)}" for i in range(1, 427)]
bands_s2 = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B9", "B10", "B11", "B12"]


# Load the table of weights
table_path_norm = "tables/S2toAVIRIS_norm.csv"
df_s2_aviris_norm = pd.read_csv(table_path_norm)
band_indices = {band: df_s2_aviris_norm[df_s2_aviris_norm[band].notnull()].index.to_list()
                for band in bands_s2}


# Download the images
for i, row in table.iterrows():
    
    ###########################
    ## Processing image neon ##
    ###########################
    neon_id = row["image_id_neon"]
    neon_img = ee.Image(neon_id)
    s2_alike_bands = {} # Crear diccionario para almacenar las bandas generadas
    for band in bands_s2:

        indices = band_indices[band] 
        weights = df_s2_aviris_norm.loc[indices, band].values  # Pesos de convolución
        neon_band_names = [f"B{str(i + 1).zfill(3)}" for i in indices]
        expression = " + ".join([f"{w} * b{i+1}" for i, w in zip(indices, weights)])

        s2_alike_band = neon_img.expression(expression, {
            f'b{i+1}': neon_img.select(f"B{str(i + 1).zfill(3)}") for i in indices
        })
        s2_alike_bands[band] = s2_alike_band

    s2_alike_image = ee.Image(list(s2_alike_bands.values())).rename(list(bands_s2))

    x_centroid = row["utm_x"]
    y_centroid = row["utm_y"]
    xmin = x_centroid - 5200/2
    ymax = y_centroid + 5200/2
    raster_transform = RasterTransform(
        crs=row["utm"],
        geotransform = dict(
            scaleX=1,
            shearX=0,
            translateX=xmin,
            scaleY=-1,
            shearY=0,
            translateY=ymax
        ), 
        width=5200, 
        height=5200
    )
    raster_transform_set = RasterTransformSet(rastertransformset = [raster_transform])

    table_manifest = cubexpress.dataframe_manifest(
        geometadatas=raster_transform_set, 
        bands=bands_s2, 
        image=s2_alike_image,
    )
    table_manifest["outname"] = row["ID"] + ".tif"

    cubexpress.getCube(table_manifest, nworkers=16, deep_level=6, output_path="/media/disk/databases/LuisGomez/NEON")




import ee
import cubexpress
from cubexpress import RasterTransform, RasterTransformSet, lonlat2geoTransforms, points2geoTransforms

ee.Initialize(project = "ee-julius013199")
# ee.Initialize(opt_url="https://earthengine-highvolume.googleapis.com")


################
## 1) Example ##
################

raster_transform_set = cubexpress.lonlat2geoTransforms(
    lon=-76.5,
    lat=-9.5,
    edge_size=128,
    scale=90
)

table_manifest = cubexpress.dataframe_manifest(
    geometadatas=raster_transform_set,
    bands=["elevation"],
    image="NASA/NASADEM_HGT/001",
)

cubexpress.getCube(table_manifest, nworkers=4, deep_level=5, output_path="DEM")


################
## 2) Example ##
################

points = [
    (-76.5, -9.5),
    (-76.5, -10.5),
    (-77.5, -10.5)
]

edge_size = 128 
scale = 90    

raster_transform_set = points2geoTransforms(points, edge_size, scale)

table_manifest = cubexpress.dataframe_manifest(
    geometadatas=raster_transform_set,
    bands=["elevation"],
    image="NASA/NASADEM_HGT/001",
)
table_manifest.iloc[0]

cubexpress.getCube(table_manifest, nworkers=4, deep_level=5, output_path="DEM")


################
## 3) Example ##
################

# Define raster transform
raster_transform = RasterTransform(
    crs="EPSG:32718",
    geotransform = {
        "scaleX": 90,
        "shearX": 0,
        "translateX": 329583.741899,
        "scaleY": -90,
        "shearY": 0,
        "translateY": 8955272.659027
    },
    width=128,
    height=128
)

raster_transform_set = RasterTransformSet(rastertransformset=[raster_transform])

table_manifest = cubexpress.dataframe_manifest(
    geometadatas=raster_transform_set,
    bands=["elevation"],
    image="NASA/NASADEM_HGT/001"
)

cubexpress.getCube(table_manifest, nworkers=4, deep_level=5, output_path="DEM")

################
## 4) Example ##
################

# Define raster transform
raster_transform = RasterTransform(
    crs="EPSG:32718",
    geotransform = {
        "scaleX": 90,
        "shearX": 0,
        "translateX": 329583.741899,
        "scaleY": -90,
        "shearY": 0,
        "translateY": 8955272.659027
    },
    width=128,
    height=128
)

raster_transform_set = RasterTransformSet(rastertransformset=[raster_transform])

table_manifest = cubexpress.dataframe_manifest(
    geometadatas=raster_transform_set,
    bands=["elevation"],
    image=ee.Image("NASA/NASADEM_HGT/001").divide(1000)
)

cubexpress.getCube(table_manifest, nworkers=4, deep_level=5, output_path="DEM")