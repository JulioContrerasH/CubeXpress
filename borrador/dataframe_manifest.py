from cubexpress.geotyping import GeotransformDict, RasterTransform, RasterTransformSet
from cubexpress.user_utils import query_utm_crs_info, _create_query_entry
from typing import List, Optional, Union, Dict, Tuple

import ee
import re
import pandas as pd
ee.Initialize()

# Intermediate functions that generate RasterTransformSet
def lonlatgeometadata(
    lon: float, 
    lat: float, 
    edge_size: int, 
    scale: int
) -> RasterTransformSet:
    # Get UTM coordinates and CRS using query_utm_crs_info
    x, y, crs = query_utm_crs_info(lon, lat)

    # Calculate the bounding box
    bbox = dict(
        xmin=x - edge_size * scale / 2,
        ymin=y - edge_size * scale / 2,
        xmax=x + edge_size * scale / 2,
        ymax=y + edge_size * scale / 2
    )

    
    # Calculate the geotransform using the bounding box and scale
    geotransform = GeotransformDict(
        scaleX=scale,
        shearX=0,
        translateX=bbox["xmin"],  # Use min_x as translate_x 
        scaleY=-scale,  # The axis Y is inverted in geospatial images
        shearY=0,
        translateY=bbox["ymax"],   # Use max_y as translate_y
    )

    return RasterTransformSet(
        rastertransformset = [
            RasterTransform(crs=crs, geotransform=geotransform, width=edge_size, height=edge_size)
            ]
        )

def point2geometadata(
    points: List[Tuple[float, float]],  # Lista de tuplas (lon, lat)
    edge_size: int, 
    scale: int
) -> RasterTransformSet:
    """
    Esta función genera un GeoMetadatas para una lista de puntos, cada uno con su correspondiente GeoMetadata.
    """
    setrastertransform = []

    # Para cada punto (lon, lat) en la lista de puntos, generar un GeoMetadata
    for lon, lat in points:
        rastertransformset = lonlatgeometadata(lon, lat, edge_size, scale)
        setrastertransform.append(rastertransformset.rastertransformset[0])

    # Devolver un GeoMetadatas con la lista de GeoMetadata
    return RasterTransformSet(rastertransformset=setrastertransform)

# isinstance(ee.Image(0), ee.Image)


def dataframe_manifest(
    geometadatas: RasterTransformSet,
    bands: List[str] = [],
    image: Union[str, ee.Image] = ""
) -> pd.DataFrame:
    """
    Generates a DataFrame manifest for geospatial metadata, including transformation 
    parameters, resolution, and other properties.

    Args:
        geometadatas (RasterTransformSet): Set of geospatial metadata entries.
        bands (List[str], optional): List of band names to include in the manifest.
        image (Union[str, ee.Image], optional): The Earth Engine expression or assetId. 
            If it's an `ee.Image`, it will be serialized, otherwise, the string is treated as an asset ID.

    Returns:
        pd.DataFrame: A DataFrame containing the metadata manifest, including geospatial 
                      information, transformation, resolution, and output file names.

    Example:
        >>> metadata_set = RasterTransformSet(rastertransformset=[geometadata1, geometadata2])
        >>> bands = ["elevation"]
        >>> image = "NASA/NASADEM_HGT/001"
        >>> table_manifest = dataframe_manifest(metadata_set, bands, image)
    """
    if isinstance(image, ee.Image):
        # Serialize the ee.Image expression
        serialized_expression = image.serialize()
        collection_str = re.findall(r'"constantValue":\s*"([^"]*)"', serialized_expression)[0]
        expression_key = 'expression'

    else:
        # Handle the case where expression is a string (assetId)
        collection_str = image
        serialized_expression = image
        expression_key = 'assetId'

    # Create the DataFrame manifest from the geospatial metadata
    df_manifest = geometadatas.export_df().reset_index().apply(
        lambda df: pd.Series({
            'x': df.x,
            'y': df.y,
            'crs': df.crs,
            'image_id': collection_str,
            'bands': bands,
            'width': df.width,
            'height': df.height,
            'geotransform': df.geotransform,
            'resolution': df.geotransform['scaleX'],
            'manifest': {
                expression_key: serialized_expression,
                'fileFormat': 'GEO_TIFF',
                'bandIds': bands, 
                'grid': { 
                    'dimensions': {
                        'width': df.width,
                        'height': df.height
                    },
                    'affineTransform': df.geotransform,
                    'crsCode': df.crs
                },
            },
            'outname': f"{collection_str.replace('/', '_')}__{df.name:04d}.tif" 
        }), 
        axis=1
    )

    return df_manifest


import io
import pathlib
import concurrent.futures
import numpy as np
import pandas as pd
import gc
import json
import rasterio as rio
import ee
from typing import Optional, List, Union
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Asume que `get_image_from_manifest` es similar a `getPixels`
def image_from_manifest(
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False
) -> np.ndarray:
    """
    Download image from Earth Engine based on the manifest and type.
    Args:
        manifest_dict (dict): El manifiesto que contiene los metadatos de la imagen.
        type (str): El método para descargar los píxeles ("getPixels" o "computePixels").
        max_deep_level (Optional[int]): Profundidad máxima de recursión para la descarga.
        quiet (Optional[bool]): Si es True, suprime los mensajes de salida.
    Returns:
        np.ndarray: La imagen como un array de numpy.
    """
    if 'assetId' in manifest_dict:
        return getPixels_np(manifest_dict, max_deep_level, quiet)
    elif 'expression' in manifest_dict:
        manifest_dict = eval(str(manifest_dict))
        manifest_dict["expression"] = ee.deserializer.decode(
            eval(manifest_dict["expression"])
        )
        return computePixels_np(manifest_dict, max_deep_level, quiet)
    else:
        raise ValueError("Manifest does not contain 'assetId' or 'expression'")


from typing import Optional, List
import numpy as np
import io
import rasterio as rio
import ee
import gc
from copy import deepcopy

def quadsplit_manifest(manifest: dict) -> List[dict]:
    """
    Splits a manifest into 4 smaller manifests.

    Args:
        manifest (dict): The manifest to be split.

    Returns:
        List[dict]: A list of 4 smaller manifests.
    """
    manifest_copy = deepcopy(manifest)
    new_width = manifest["grid"]["dimensions"]["width"] // 2
    new_height = manifest["grid"]["dimensions"]["height"] // 2
    manifest_copy["grid"]["dimensions"]["width"] = new_width
    manifest_copy["grid"]["dimensions"]["height"] = new_height

    manifests = []
    for idx in range(4):
        new_manifest = deepcopy(manifest_copy)
        res_x = manifest["grid"]["affineTransform"]["scaleX"]
        res_y = manifest["grid"]["affineTransform"]["scaleY"]

        add_x, add_y = (0, 0)
        if idx == 1:
            add_x = new_width * res_x
        elif idx == 2:
            add_y = new_height * res_y
        elif idx == 3:
            add_x = new_width * res_x
            add_y = new_height * res_y

        new_manifest["grid"]["affineTransform"]["translateX"] += add_x
        new_manifest["grid"]["affineTransform"]["translateY"] += add_y

        manifests.append(new_manifest)

    return manifests

# def getPixels_np(
#     manifest_dict: dict,
#     max_deep_level: Optional[int] = 5,
#     quiet: Optional[bool] = False
# ) -> np.ndarray:
#     """
#     Implements the getPixels method from the Earth Engine API with recursion and batching.
#     Args:
#         manifest_dict (dict): The manifest containing image metadata.
#         max_deep_level (Optional[int]): Maximum recursion depth.
#         quiet (Optional[bool]): If True, suppress output messages.
#     Returns:
#         np.ndarray: The image as a numpy array.
#     """
#     if max_deep_level == 0:
#         raise ValueError("Max recursion depth reached.")
#     # Attempt to download the image using Earth Engine API
#     try:
#         with io.BytesIO(ee.data.getPixels(manifest_dict)) as f:
#             with rio.open(f) as img:
#                 return img.read()
#     except Exception as e:
#         # Handle errors like image not found or any other exception
#         if check_not_found_error(str(e)):
#             return None
#         # Recursively attempt downloading the image in smaller chunks
#         return getPixels_np(
#             manifest_dict=manifest_dict,
#             max_deep_level=max_deep_level - 1,
#             quiet=quiet
#         )

def getPixels_np(
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False
) -> np.ndarray:
    """
    Implements the getPixels method from the Earth Engine API with recursion and batching.
    
    Args:
        manifest_dict (dict): The manifest containing image metadata.
        max_deep_level (Optional[int]): Maximum recursion depth.
        quiet (Optional[bool]): If True, suppress output messages.
    
    Returns:
        np.ndarray: The image as a numpy array.
    """
    if max_deep_level == 0:
        raise ValueError("Max recursion depth reached.")
    
    try:
        with io.BytesIO(ee.data.getPixels(manifest_dict)) as f:
            with rio.open(f) as img:
                return img.read()
    
    except Exception as e:
        if check_not_found_error(str(e)):
            return None

        # Initialize empty array for stitched data
        data_np = np.zeros(
            (
                len(manifest_dict["bandIds"]),
                int(manifest_dict["grid"]["dimensions"]["width"]),
                int(manifest_dict["grid"]["dimensions"]["height"]),
            )
        )

        # Split the manifest and recursively download data in chunks
        manifest_dicts = quadsplit_manifest(manifest_dict)
        for idx, manifest_dict_batch in enumerate(manifest_dicts):
            if not quiet:
                print(f"Downloading batch {idx + 1} of 4...")

            dnp = getPixels_np(
                manifest_dict=manifest_dict_batch,
                max_deep_level=max_deep_level - 1,
                quiet=quiet
            )

            if dnp is not None:
                if idx == 0:
                    data_np[:, : dnp.shape[1], : dnp.shape[2]] = dnp
                elif idx == 1:
                    data_np[:, : dnp.shape[1], -dnp.shape[2] :] = dnp
                elif idx == 2:
                    data_np[:, -dnp.shape[1] :, : dnp.shape[2]] = dnp
                elif idx == 3:
                    data_np[:, -dnp.shape[1] :, -dnp.shape[2] :] = dnp

        gc.collect()
        return data_np
# max_deep_level = 5
# quiet = False
def computePixels_np(
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False
) -> np.ndarray:
    """
    Implements the computePixels method for downloading large images in batches.
    
    Args:
        manifest_dict (dict): The manifest containing image metadata.
        max_deep_level (Optional[int]): Maximum recursion depth.
        quiet (Optional[bool]): If True, suppress output messages.
    
    Returns:
        np.ndarray: The image as a numpy array.
    """
    if max_deep_level == 0:
        raise ValueError("Max recursion depth reached.")
    
    try:
        with io.BytesIO(ee.data.computePixels(manifest_dict)) as f:
            with rio.open(f) as img:
                return img.read()
    
    except Exception as e:
        if check_not_found_error(str(e)):
            return None

        data_np = np.zeros(
            (
                len(manifest_dict["bandIds"]),
                int(manifest_dict["grid"]["dimensions"]["width"]),
                int(manifest_dict["grid"]["dimensions"]["height"]),
            )
        )

        manifest_dicts = quadsplit_manifest(manifest_dict)
        for idx, manifest_dict_batch in enumerate(manifest_dicts):
            if not quiet:
                print(f"Downloading batch {idx + 1} of 4...")

            dnp = computePixels_np(
                manifest_dict=manifest_dict_batch,
                max_deep_level=max_deep_level - 1,
                quiet=quiet
            )

            if dnp is not None:
                if idx == 0:
                    data_np[:, : dnp.shape[1], : dnp.shape[2]] = dnp
                elif idx == 1:
                    data_np[:, : dnp.shape[1], -dnp.shape[2] :] = dnp
                elif idx == 2:
                    data_np[:, -dnp.shape[1] :, : dnp.shape[2]] = dnp
                elif idx == 3:
                    data_np[:, -dnp.shape[1] :, -dnp.shape[2] :] = dnp

        gc.collect()
        return data_np



def check_not_found_error(error_msg: str) -> bool:
    """
    Check if the error message indicates that the image was not found.
    
    Args:
        error_msg (str): The error message to check.
        
    Returns:
        bool: True if the error message indicates "not found", False otherwise.
    """
    return "not found" in error_msg

# getPixels(table_manifest2, nworkers=4, deep_level=5, output_path="images", quiet=False)
# row = table_manifest2.iloc[0]
# nworkers=4
# deep_level = 5
# quiet = False
# output_path="images"

def getCube_batch(
    row: pd.Series,
    output_path: str,
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False
) -> pathlib.Path:
    
    if not quiet:
        print(f"Downloading {row.outname}...")

    manifest_dict = json.loads(row.manifest) if isinstance(row.manifest, str) else row.manifest

    # Get the image data from the manifest
    data_np = image_from_manifest(
        manifest_dict=manifest_dict,
        max_deep_level=max_deep_level,
        quiet=quiet
    )
    if data_np is None:
        return None

    # Prepare metadata for saving the image
    metadata_rio = {
        "driver": "GTiff", # --> esto podria cambiarse ya que no se controla desde el manifest, si lo quieres como png?, si lo quieres como cog
        "count": data_np.shape[0],
        "dtype": data_np.dtype,
        "height": data_np.shape[1],
        "width": data_np.shape[2],
        "transform": rio.Affine(
            manifest_dict["grid"]["affineTransform"]["scaleX"],
            manifest_dict["grid"]["affineTransform"]["shearX"],
            manifest_dict["grid"]["affineTransform"]["translateX"],
            manifest_dict["grid"]["affineTransform"]["shearY"],
            manifest_dict["grid"]["affineTransform"]["scaleY"],
            manifest_dict["grid"]["affineTransform"]["translateY"]
        ),
        "crs": manifest_dict["grid"]["crsCode"],
    }

    # Save the image
    outfile = pathlib.Path(output_path) / row.outname
    outfile.parent.mkdir(parents=True, exist_ok=True)
    
    with rio.open(outfile, "w", **metadata_rio) as dst:
        dst.write(data_np)

    # Clean up
    gc.collect()

    return outfile

# getPixels(table_manifest2, nworkers=4, deep_level=5, output_path="images", quiet=False)
# table2 = table_manifest2
# nworkers = 4
# deep_level = 5
# output_path2 = "images2"
# quiet = False

# table = table_manifest
# nworkers = 4
# deep_level = 5
# output_path = "images"
# quiet = False

# table_manifest2.manifest[0]

# getPixels()

# computePixels()

def getCube(
    table: pd.DataFrame,
    nworkers: Optional[int] = None,
    deep_level: Optional[int] = 5,
    output_path: Union[str, pathlib.Path, None] = None,
    quiet: bool = False
) -> List[pathlib.Path]:
    if output_path is None:
        output_path = pathlib.Path(table.iloc[0].image_id.replace("/", "_"))
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = pathlib.Path(output_path)

    for _, row in table.iterrows():
        print(f"Processing row: {row}") 

    if nworkers is None:
        results = []
        for _, row in table.iterrows():
            result = getCube_batch(
                row=row, 
                output_path=output_path,
                max_deep_level=deep_level, 
                quiet=quiet
            )
            if result is not None:
                results.append(result)
    else:
        with ThreadPoolExecutor(max_workers=nworkers) as executor:
            futures = [
                executor.submit(getCube_batch, row, output_path, deep_level, quiet)
                for _, row in table.iterrows()
            ]
            results = []
            for future in concurrent.futures.as_completed(futures):
                if future.exception() is not None:
                    raise future.exception()
                if future.result() is not None:
                    results.append(future.result())
    return results





#############
# Ejemplo 4 #
#############

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
    width=128, 
    height=128
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

# str(ee.Image("NASA/NASADEM_HGT/001").divide(1000))
# str(table_manifest2.manifest[0])

# table_manifest2['manifest'] = table_manifest2['manifest'].apply(str)
# table_manifest2.manifest[0]
# json.dumps()


getCube(table_manifest, nworkers=4, deep_level=5, output_path="images", quiet=False)
getCube(table_manifest2, nworkers=4, deep_level=5, output_path="images_deep", quiet=False)

table_manifest2.manifest[0]

table_manifest2.iloc[0]
manifest_dict =  eval(str(table_manifest2.manifest[0]))
table_manifest2.manifest[0]["expression"]



manifest_str = row.manifest
manifest_str = manifest_str.replace("'", "\"")  # Replacing single quotes with double quotes to make it valid JSON

# Convert the JSON string to a dictionary
manifest_dict = json.loads(manifest_str)


##################################################################################################################################################


# Region of interest.
coords = [
    -121.58626826832939,
    38.059141484827485,
]
region = ee.Geometry.Point(coords)

# Sentinel-2 median composite.
image = (ee.ImageCollection('COPERNICUS/S2')
              .filterBounds(region)
              .filterDate('2020-04-01', '2020-09-01')
              .median())

# Make a projection to discover the scale in degrees.
proj = ee.Projection('EPSG:4326').atScale(10).getInfo()

# Get scales out of the transform.
scale_x = proj['transform'][0]
scale_y = -proj['transform'][4]

# Make a request object.
request = {
    'expression': image,
    'fileFormat': 'PNG',
    'bandIds': ['B4', 'B3', 'B2'],
    'grid': {
        'dimensions': {
            'width': 640,
            'height': 640
        },
        'affineTransform': {
            'scaleX': scale_x,
            'shearX': 0,
            'translateX': coords[0],
            'shearY': 0,
            'scaleY': scale_y,
            'translateY': coords[1]
        },
        'crsCode': proj['crs'],
    },
    'visualizationOptions': {'ranges': [{'min': 0, 'max': 3000}]},
}

image_png = ee.data.computePixels(json.dumps(request))
# Do something with the image...