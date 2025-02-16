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
