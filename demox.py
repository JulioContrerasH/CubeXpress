from typing import Any
import pandas as pd
import pydantic

# typing_data.py
class CRS(pydantic.BaseModel):
    pass

class Geotransform(pydantic.BaseModel):
    pass

class Bbox(pydantic.BaseModel):
    pass

class GeoMetadata(pydantic.BaseModel):
    crs: CRS
    geotransform: Geotransform
    bbox: Bbox

class GeoMetadatas(pydantic.BaseModel):
    geometadatas: list[GeoMetadata]

# user_utils.py
def point2geometadata(x, y, scale, edge_size) -> GeoMetadata:
    pass 

# dataframe_manifest.py
def dataframe_manifest(
    geometadatas: Any,
    collection_data: Any,
    bands: Any
) -> pd.DataFrame:    
    pass

def dataframe_manifest_computepixel_ic():
    pass

def dataframe_manifest_computepixel_img():
    pass

def dataframe_manifest_getpixel_ic():
    pass

def dataframe_manifest_getpixel_img():
    pass


# downloader.py
def getPixels(**kwargs):
    pass

def computePixels(**kwargs):
    pass

# stats.py
def getStats(best_effort, reducer, bestEffort, maxPixels, tileScale):
    pass

def getStats_image(**kwargs):
    pass

def getStats_ic(**kwargs):
    # ic.lambda(x: x.reduceRegion(....).set("STAT:", x.get("system:index"))).G
    pass


# demo
# Sentinel-2
df_s2 = dataframe_manifest(...)

# Sentinel-2 cloud
df_s2_cloud = dataframe_manifest(...)

# Sentinel-2 cloud stats
df_s2_cloud_stats = getStats_image(df_s2_cloud)

# Merge 
df_s2["cloud_clover"] = df_s2_cloud_stats["cloud_clover"]
df_s2_final = df_s2[df_s2["cloud_clover"] > 0.4] 

fastcubo.getPixel(df_s2_final)



