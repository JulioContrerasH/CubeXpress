__init__.py:
from fastcubo.main import (computePixels, getPixels, query_computePixels_image,
                           query_getPixels_image,
                           query_getPixels_imagecollection)

__version__ = "0.1.4"


main.py:
import concurrent.futures
import pathlib
import json
import re
from typing import List, Optional, Tuple, Union

import ee
import pandas as pd

from fastcubo.utils import getImage_batch, query_utm_crs_info


def query_getPixels_image(
    collection: str,
    bands: List[str],
    out_parameters: Optional[List[dict]] = None,
    points: Optional[List[Tuple[float, float]]] = None,
    edge_size: Optional[float] = None,
    resolution: Optional[float] = None,
    outnames: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Returns a DataFrame with the metadata needed to 
    retrieve the data using `ee.data.getPixels`.

    Args:
        out_parameters (Optional[dict], optional): The parameters
            to be used in the query and for exporting the data.
            Defaults to None. If None, the user must provide the
            points, edge_size, resolution, and outnames.
        points (List[Tuple[float, float]]): The centroid 
            of the square to be queried.
        collection (str): The collection to be queried.
        bands (List[str]): The bands to be queried.
        edge_size (float): The size of the square to be queried.
        resolution (float): The resolution of the query.
        outnames (Optional[List[str]], optional): The name 
            of the output files to be saved. Defaults to None.

    Returns:
        pd.DataFrame: A DataFrame with the metadata needed to 
            retrieve the data using `ee.data.getPixels`.
    """
    if out_parameters is None:
        if outnames is None:
            basename = collection.replace("/", "_")
            outnames = [f"{basename}__{i:04d}.tif" for i in range(len(points))]

        # From EPSG to UTM
        epsg_info = [query_utm_crs_info(lon, lat) for lon, lat in points]
        lon_utm, lat_utm, zone_epsg = zip(*epsg_info)

        # Fix the center of the square to be the upper left corner
        lon_utm = [x - edge_size * resolution / 2 for x in lon_utm]
        lat_utm = [y + edge_size * resolution / 2 for y in lat_utm]

        # Create the query_table
        query_table = pd.DataFrame(
            {
                "lon": [lon for lon, _ in points],
                "lat": [lat for _, lat in points],
                "x": lon_utm,
                "y": lat_utm,
                "epsg": out_parameters["crs"],
                "collection": collection,
                "bands": ", ".join(bands),
                "edge_size": edge_size,
                "resolution": resolution,
            }
        )    
    else:
        if outnames is None:
            basename = collection.replace("/", "_")
            outnames = [f"{basename}__{i:04d}.tif" for i in range(len(out_parameters))]

        # does the outname exist?
        if any(["crs" not in x for x in out_parameters]):
            raise ValueError("The 'crs' parameter must be provided in all the out_parameters.")

        # Define the query_table
        query_table = pd.DataFrame({
            "x": [x["transform"][2] for x in out_parameters],
            "y": [x["transform"][5] for x in out_parameters],
            "epsg": [x["crs"] for x in out_parameters],
            "collection": collection,
            "bands": ", ".join(bands),
            "edge_size": [x["width"] for x in out_parameters],
            "resolution": [x["transform"][0] for x in out_parameters],
        })

        # serialize to string
        query_table["outparameters"] = [json.dumps(x) for x in out_parameters]


    # Add manifest to the query_table
    manifests = []
    for index, row in query_table.iterrows():
        manifest = {
            "assetId": row["collection"],
            "fileFormat": "GEO_TIFF",
            "bandIds": bands,
            "grid": {
                "dimensions": {
                    "width": row["edge_size"],
                    "height": row["edge_size"],
                },
                "affineTransform": {
                    "scaleX": row["resolution"],
                    "shearX": 0,
                    "translateX": row["x"],
                    "shearY": 0,
                    "scaleY": -row["resolution"],
                    "translateY": row["y"],
                },
                "crsCode": row["epsg"],
            },
        }
        manifests.append(str(manifest))
    query_table["manifest"] = manifests

    # Save the outnames
    query_table["outname"] = outnames

    return query_table


def query_getPixels_imagecollection(
    collection: str,
    bands: List[str],
    data_range: Tuple[str, str],
    out_parameter: Optional[dict] = None,
    point: Optional[Tuple[float, float]] = None,
    edge_size: Optional[float] = None,
    resolution: Optional[float] = None,
    outnames: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Returns a DataFrame with the metadata needed to 
    retrieve the data using `ee.data.getPixels`.

    Args:
        point (Tuple[float, float]): The centroid of the square 
            to be queried.
        collection (str): The collection to be queried.
        bands (List[str]): The bands to be queried.
        data_range (Tuple[str, str]): The range of dates to be 
            queried in the format (start_date, end_date).
        edge_size (float): The size of the square to be queried.
        resolution (float): The resolution of the query.
        outnames (Optional[List[str]], optional): The name of the 
            output files to be saved. Defaults to None.

    Returns:
        pd.DataFrame: A DataFrame with the metadata needed to 
            retrieve the data using `ee.data.getPixels`.
    """
    if out_parameter is None:

        # From EPSG to UTM
        lon_utm, lat_utm, zone_epsg = query_utm_crs_info(*point)

        # Fix the center of the square to be the upper left corner
        lon_utm = lon_utm - edge_size * resolution / 2
        lat_utm = lat_utm + edge_size * resolution / 2

        # Get the images
        images = (
            ee.ImageCollection(collection)
            .filterBounds(ee.Geometry.Point((lon_utm, lat_utm), proj=zone_epsg))
            .filterDate(data_range[0], data_range[1])
            .select(bands)
        )

        # Get the ids and dates
        ids = images.aggregate_array("system:id").getInfo()
        dates = images.aggregate_array("system:time_start").getInfo()
        dates_str = [
            pd.to_datetime(date, unit="ms").strftime("%Y-%m-%d %H:%M:%S") for date in dates
        ]

        # Create the query_table
        query_table = pd.DataFrame(
            {
                "lon": point[0],
                "lat": point[1],
                "x": lon_utm,
                "y": lat_utm,
                "epsg": zone_epsg,
                "collection": collection,
                "bands": ", ".join(bands),
                "edge_size": edge_size,
                "resolution": resolution,
                "img_id": ids,
                "img_date": dates_str,
            }
        )
    else:
        # does the outname exist?
        if "crs" not in out_parameter:
            raise ValueError("The 'crs' parameter must be provided in all the out_parameters.")

        lon_utm = out_parameter["transform"][2]
        lat_utm = out_parameter["transform"][5]
        zone_epsg = out_parameter["crs"]

        # Get the images
        images = (
            ee.ImageCollection(collection)
            .filterBounds(ee.Geometry.Point((lon_utm, lat_utm), proj=zone_epsg))
            .filterDate(data_range[0], data_range[1])
            .select(bands)
        )
        
        # Get the ids and dates
        ids = images.aggregate_array("system:id").getInfo()
        dates = images.aggregate_array("system:time_start").getInfo()
        dates_str = [
            pd.to_datetime(date, unit="ms").strftime("%Y-%m-%d %H:%M:%S") for date in dates
        ]
        edge_size = out_parameter["width"]
        resolution = out_parameter["transform"][0]


        # Create the query_table
        query_table = pd.DataFrame(
            {
                "x": lon_utm,
                "y": lat_utm,
                "epsg": zone_epsg,
                "collection": collection,
                "bands": ", ".join(bands),
                "edge_size": edge_size,
                "resolution": resolution,
                "img_id": ids,
                "img_date": dates_str,
            }
        )

        query_table["outparameters"] = json.dumps(out_parameter)

    # Add manifest to the query_table
    manifests = []
    for index, row in query_table.iterrows():
        manifest = {
            "assetId": row["img_id"],
            "fileFormat": "GEO_TIFF",
            "bandIds": bands,
            "grid": {
                "dimensions": {
                    "width": row["edge_size"],
                    "height": row["edge_size"],
                },
                "affineTransform": {
                    "scaleX": row["resolution"],
                    "shearX": 0,
                    "translateX": row["x"],
                    "shearY": 0,
                    "scaleY": -row["resolution"],
                    "translateY": row["y"],
                },
                "crsCode": row["epsg"],
            },
        }
        manifests.append(str(manifest))

    # Save the manifests
    query_table["manifest"] = manifests

    if outnames is None:
        query_table["outname"] = query_table["img_id"].apply(
            lambda x: pathlib.Path(x).stem + ".tif"
        )
    else:
        query_table["outname"] = outnames

    return query_table


def getPixels(
    table: pd.DataFrame,
    nworkers: Optional[int] = None,
    deep_level: Optional[int] = 5,
    output_path: Union[str, pathlib.Path, None] = None,
    quiet: bool = False,
) -> List[pathlib.Path]:
    """
    Create GeoTIFF files from a query_table.

    Args:
        table (pd.DataFrame): The query_table to be downloaded.
        nworkers (Optional[int], optional): The number of workers 
            to be used. Defaults to None. If None, the download 
            will be done sequentially.
        deep_level (Optional[int], optional): If the image is too 
            big, a quadtree will be created to download the image 
            in parts. This parameter defines the maximum deep level 
            of the quadtree. Defaults to 5.
        output_path (Union[str, pathlib.Path, None], optional): The path 
            to save the files. Defaults to None.
        quiet (bool, optional): If True, suppress output messages. 
            Defaults to False.

    Returns:
        List[pathlib.Path]: A list of paths to the downloaded GeoTIFF 
        files.
    """

    # Set the output path
    if output_path is None:
        output_path = pathlib.Path(table.iloc[0].collection.replace("/", "_"))
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = pathlib.Path(output_path)

    if nworkers is None:
        results = [
            getImage_batch(
                row=row,
                output_path=output_path,
                type="getPixels",
                max_deep_level=deep_level,
                quiet=quiet
            )
            for _, row in table.iterrows()
            if getImage_batch(
                row=row,
                output_path=output_path,
                type="getPixels",
                max_deep_level=deep_level,
                quiet=quiet
            ) is not False
        ]
    else:
        # Using ThreadPoolExecutor to manage concurrent downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
            futures = [
                executor.submit(
                    getImage_batch, row, output_path, "getPixels", deep_level, quiet
                )
                for _, row in table.iterrows()
            ]
            results = []
            for future in concurrent.futures.as_completed(futures):
                if future.exception() is not None:
                    raise future.exception()
                if future.result() is not False:
                    results.append(future.result())
    return results


def query_computePixels_image(
    points: List[Tuple[float, float]],
    expression: ee.Image,
    bands: List[str],
    edge_size: float,
    resolution: float,
    outnames: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Returns a DataFrame with the metadata needed to 
    retrieve the data using `ee.data.getPixels`.

    Args:
        points (List[Tuple[float, float]]): The centroid of 
            the square to be queried.
        expression (ee.Image): The Earth Engine image expression 
            to be queried.
        bands (List[str]): The bands to be queried.
        edge_size (float): The size of the square to be queried.
        resolution (float): The resolution of the query.
        outnames (Optional[List[str]], optional): The name of 
            the output files to be saved. Defaults to None.

    Returns:
        pd.DataFrame: A DataFrame with the metadata needed to 
            retrieve the data using `ee.data.getPixels`.
    """
    if outnames is None:
        regex_exp = re.compile(r'"constantValue":\s*"([^"]*)"')
        product_id = re.findall(regex_exp, expression.serialize())[0]
        basename = product_id.replace("/", "_")
        outnames = [f"{basename}__{i:04d}.tif" for i in range(len(points))]

    # From EPSG to UTM
    epsg_info = [query_utm_crs_info(lon, lat) for lon, lat in points]
    lon_utm, lat_utm, zone_epsg = zip(*epsg_info)

    # Fix the center of the square to be the upper left corner
    lon_utm = [x - edge_size * resolution / 2 for x in lon_utm]
    lat_utm = [y + edge_size * resolution / 2 for y in lat_utm]

    # Create the query_table
    query_table = pd.DataFrame(
        {
            "lon": [lon for lon, _ in points],
            "lat": [lat for _, lat in points],
            "x": lon_utm,
            "y": lat_utm,
            "epsg": zone_epsg,
            "expression": expression.serialize(),
            "bands": ", ".join(bands),
            "edge_size": edge_size,
            "resolution": resolution,
        }
    )

    # Add manifest to the query_table
    manifests = []
    for index, row in query_table.iterrows():
        manifest = {
            "expression": row["expression"],
            "fileFormat": "GEO_TIFF",
            "bandIds": bands,
            "grid": {
                "dimensions": {
                    "width": row["edge_size"],
                    "height": row["edge_size"],
                },
                "affineTransform": {
                    "scaleX": row["resolution"],
                    "shearX": 0,
                    "translateX": row["x"],
                    "shearY": 0,
                    "scaleY": -row["resolution"],
                    "translateY": row["y"],
                },
                "crsCode": zone_epsg[index],
            },
        }
        manifests.append(str(manifest))
    query_table["manifest"] = manifests

    # Save the outnames
    query_table["outname"] = outnames

    return query_table


def computePixels(
    table: pd.DataFrame,
    nworkers: Optional[int] = None,
    output_path: Union[str, pathlib.Path, None] = None,
    max_deep_level: Optional[int] = 5,
    quiet: bool = False,
) -> List[pathlib.Path]:
    """
    Create GeoTIFF files from a query_table.

    Args:
        table (pd.DataFrame): The query_table to be downloaded.
        nworkers (Optional[int], optional): The number of workers 
            to be used. Defaults to None. If None, the download 
            will be done sequentially.
        output_path (Union[str, pathlib.Path, None], optional): The 
            path to save the files. Defaults to None.
        max_deep_level (Optional[int], optional): If the image is 
            too big, a quadtree will be created to download the 
            image in parts. This parameter defines the maximum deep 
            level of the quadtree. Defaults to 5.
        quiet (bool, optional): If True, suppress output messages. 
            Defaults to False.

    Returns:
        List[pathlib.Path]: A list of paths to the downloaded 
            GeoTIFF files.
    """

    # Set the output path
    if output_path is None:
        output_path = pathlib.Path(".")
    else:
        output_path = pathlib.Path(output_path)

    if nworkers is None:
        results = [
            getImage_batch(
                row=row,
                output_path=output_path,
                type="computePixels",
                max_deep_level=max_deep_level,
                quiet=quiet
            )
            for _, row in table.iterrows()
            if getImage_batch(
                row=row,
                output_path=output_path,
                type="computePixels",
                max_deep_level=max_deep_level,
                quiet=quiet
            ) is not False
        ]
    else:
        # Using ThreadPoolExecutor to manage concurrent downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
            futures = [
                executor.submit(
                    getImage_batch, row, output_path, "computePixels", max_deep_level, quiet
                )
                for _, row in table.iterrows()
            ]
            results = []
            for future in concurrent.futures.as_completed(futures):
                if future.exception() is not None:
                    raise future.exception()
                if future.result() is not False:
                    results.append(future.result())

    return results


utils.py:
import io
import json
import pathlib
from copy import deepcopy
from typing import List, Literal, Optional, Tuple

import ee
import gc
import numpy as np
import pandas as pd
import rasterio as rio
import utm


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


def quadsplit_manifest(manifest: dict) -> List[dict]:
    """
    Splits a manifest into 4 smaller manifests.

    Args:
        manifest (dict): The manifest to be split.

    Returns:
        List[dict]: A list of 4 smaller manifests.
    """
    # Deep copy the manifest to avoid modifying the original.
    manifest_copy = deepcopy(manifest)
    new_width = manifest["grid"]["dimensions"]["width"] // 2
    new_height = manifest["grid"]["dimensions"]["height"] // 2
    manifest_copy["grid"]["dimensions"]["width"] = new_width
    manifest_copy["grid"]["dimensions"]["height"] = new_height

    manifests = []
    for idx in range(4):
        # Load a new manifest.
        new_manifest = deepcopy(manifest_copy)

        # Set the scale.
        res_x = manifest["grid"]["affineTransform"]["scaleX"]
        res_y = manifest["grid"]["affineTransform"]["scaleY"]

        # Adjust the width and height.
        if idx == 0:
            add_x = 0
            add_y = 0
        elif idx == 1:
            add_x = new_width * res_x
            add_y = 0
        elif idx == 2:
            add_x = 0
            add_y = new_height * res_y
        elif idx == 3:
            add_x = new_width * res_x
            add_y = new_height * res_y

        # Adjust the translation.
        new_manifest["grid"]["affineTransform"]["translateX"] += add_x
        new_manifest["grid"]["affineTransform"]["translateY"] += add_y

        # Append the new manifest to the list.
        manifests.append(new_manifest)

    return manifests


def computePixels_np(
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5,
    deep_level: Optional[int] = 0,
    quiet: Optional[bool] = False,
) -> np.ndarray:
    """
    Implements the computePixels method from the Earth 
    Engine API. If the image is too large, it splits the 
    image into 4 and downloads the data in batches.

    Args:
        manifest_dict (dict): The manifest to be downloaded.
        max_deep_level (Optional[int], optional): Maximum 
            recursion depth. Defaults to 5.
        deep_level (Optional[int], optional): Current recursion 
            depth. Defaults to 0.
        quiet (Optional[bool], optional): Suppress output if 
            True. Defaults to False.

    Returns:
        np.ndarray: The image as a numpy array.
    """
    if deep_level == max_deep_level:
        raise ValueError(
            "Max recursion depth reached. Aborting." f" Manifest: {manifest_dict}"
        )

    try:
        # Download the data
        with io.BytesIO(ee.data.computePixels(manifest_dict)) as f:
            with rio.open(f) as f:
                data_np = f.read()

    except Exception as e:
        print(e)
        # Check if the error is due to the image "not being found"
        if check_not_found_error(str(e)):
            #return False
            1

        # Create a container for the data
        data_np = np.zeros(
            (
                len(manifest_dict["bandIds"]),
                int(manifest_dict["grid"]["dimensions"]["width"]),
                int(manifest_dict["grid"]["dimensions"]["height"]),
            )
        )

        # Split the manifest into 4.
        manifest_dicts = quadsplit_manifest(manifest_dict)

        for idx, manifest_dict_batch in enumerate(manifest_dicts):
            if not quiet:
                print(f"Downloading batch {idx + 1} of 4...")

            # Try to obtain the data for the batch.
            dnp = computePixels_np(
                manifest_dict=manifest_dict_batch,
                quiet=quiet,
                deep_level=deep_level + 1,
                max_deep_level=max_deep_level  # Pass the max_deep_level.
            )

            # Insert the data into the container.
            if idx == 0:
                data_np[:, : dnp.shape[1], : dnp.shape[2]] = dnp
            elif idx == 1:
                data_np[:, : dnp.shape[1], -dnp.shape[2] :] = dnp
            elif idx == 2:
                data_np[:, -dnp.shape[1] :, : dnp.shape[2]] = dnp
            elif idx == 3:
                data_np[:, -dnp.shape[1] :, -dnp.shape[2] :] = dnp

        # Clean the memory
        del dnp
        del manifest_dicts
        gc.collect()

    return data_np


def getPixels_np(
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5,
    deep_level: Optional[int] = 0,
    quiet: Optional[bool] = False
) -> np.ndarray:
    """
    Implements the getPixels method from the Earth Engine API.
    If the image is too large, it splits the image into 4 and 
    downloads the data in batches.

    Args:
        manifest_dict (dict): The manifest to be downloaded.
        max_deep_level (Optional[int], optional): Maximum 
            recursion depth. Defaults to 5.
        deep_level (Optional[int], optional): Current recursion 
            depth. Defaults to 0.
        quiet (Optional[bool], optional): Suppress output if True. 
            Defaults to False.

    Returns:
        np.ndarray: The image as a numpy array.
    """
    if deep_level == max_deep_level:
        raise ValueError(
            "Max recursion depth reached. Aborting." f" Manifest: {manifest_dict}"
        )

    try:
        # Download the data
        with io.BytesIO(ee.data.getPixels(manifest_dict)) as f:
            with rio.open(f) as f:
                data_np = f.read()


    except Exception as e:
        # Check if the error is due to the image "not being found".
        if check_not_found_error(str(e)):
            return False

        # Create a container for the data.
        data_np = np.zeros(
            (
                len(manifest_dict["bandIds"]),
                int(manifest_dict["grid"]["dimensions"]["width"]),
                int(manifest_dict["grid"]["dimensions"]["height"]),
            )
        )

        # Split the manifest into 4.
        manifest_dicts = quadsplit_manifest(manifest_dict)

        for idx, manifest_dict_batch in enumerate(manifest_dicts):
            if not quiet:
                print(f"Downloading batch {idx + 1} of 4...")

            # Obtain the data for the batch.
            dnp = getPixels_np(
                manifest_dict=manifest_dict_batch,
                quiet=quiet,
                deep_level=deep_level + 1,
                max_deep_level=max_deep_level  # Pass the max_deep_level.
            )

            # Insert the data into the container.
            if idx == 0:
                data_np[:, : dnp.shape[1], : dnp.shape[2]] = dnp
            elif idx == 1:
                data_np[:, : dnp.shape[1], -dnp.shape[2] :] = dnp
            elif idx == 2:
                data_np[:, -dnp.shape[1] :, : dnp.shape[2]] = dnp
            elif idx == 3:
                data_np[:, -dnp.shape[1] :, -dnp.shape[2] :] = dnp

        # Clean the memory
        del dnp
        del manifest_dicts
        gc.collect()
    
    gc.collect()

    return data_np


def getImage_batch(
    row: pd.Series,
    output_path: str,
    type: Literal["getPixels", "computePixels"],
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False,    
) -> pathlib.Path:
    """
    Downloads the image from the manifest as a GeoTIFF file.

    Args:
        row (pd.Series): A row from the query table containing 
            metadata and manifest.
        output_path (str): The path where the file will be saved.
        type (Literal["getPixels", "computePixels"]): Type of pixel 
            computation to perform.
        max_deep_level (Optional[int], optional): Maximum recursion depth. 
            Defaults to 5.
        quiet (Optional[bool], optional): Suppress output if True. Defaults 
            to False.

    Returns:
        pathlib.Path: The path to the saved GeoTIFF file.
    """
    if not quiet:
        print(f"Downloading {row.outname}...")

    # Load the manifest.
    manifest_dict = eval(row.manifest)

    # Download the data.
    if type == "computePixels":
        manifest_dict["expression"] = ee.deserializer.decode(
            eval(manifest_dict["expression"])
        )
        data_np = computePixels_np(
            manifest_dict=manifest_dict,
            max_deep_level=max_deep_level,
            quiet=quiet,
        )
    
    elif type == "getPixels":
        data_np = getPixels_np(
            manifest_dict=manifest_dict,
            max_deep_level=max_deep_level,
            quiet=quiet
        )
    
    if data_np is False:
        return False

    # Prepare the metadata for saving the image.
    if "outparameters" in row:
        metadata_rio = json.loads(row["outparameters"])
        metadata_rio["count"] = data_np.shape[0]
    else:
        metadata_rio = {
            "driver": "GTiff",
            "count": data_np.shape[0],
            "dtype": data_np.dtype,
            "height": int(manifest_dict["grid"]["dimensions"]["height"]),
            "width": int(manifest_dict["grid"]["dimensions"]["width"]),
            "transform": rio.Affine(
                manifest_dict["grid"]["affineTransform"]["scaleX"],
                manifest_dict["grid"]["affineTransform"]["shearX"],
                manifest_dict["grid"]["affineTransform"]["translateX"],
                manifest_dict["grid"]["affineTransform"]["shearY"],
                manifest_dict["grid"]["affineTransform"]["scaleY"],
                manifest_dict["grid"]["affineTransform"]["translateY"],
            ),
            "crs": manifest_dict["grid"]["crsCode"],
        }

    # Create the output folder if it doesn't exist.
    outfile = pathlib.Path(output_path) / row.outname
    outfile.parent.mkdir(parents=True, exist_ok=True)

    # Save the data as a GeoTIFF.
    with rio.open(outfile, "w", **metadata_rio) as dst:
        dst.write(data_np)

    # Clean the memory
    del data_np
    gc.collect()

    return outfile


def check_not_found_error(error_msg: str) -> bool:
    """
    Check if an error message indicates that the image 
    was not found.

    Args:
        error_msg (str): The error message to check.

    Returns:
        bool: True if the error indicates a "not found" 
            situation, False otherwise.
    """
    wrong_trace_message = "not found"
    return wrong_trace_message in error_msg


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
    
    manifest = generate_manifest(row['x'], row['y'], row['edge_size'], row['resolution'], bands=bands, collection=collection)
    
    # Aserciones
    assert manifest['assetId'] == collection
    assert manifest['fileFormat'] == 'GEO_TIFF'
    assert 'crsCode' in manifest['grid']
    
    # Imprimir algo para ver que todo está bien
    print("Test passed! Manifest generated successfully.")

test_generate_manifest()





from cubexpress.geo_typing import CRS, Geotransform, Bbox, GeoMetadata
from pydantic import ValidationError

def test_invalid_type():
    try:
        # Pasar un tipo incorrecto
        geo_metadata = GeoMetadata(
            crs=CRS(code="EPSG:4326"),
            geotransform=Geotransform(
                scale_x="incorrect_type",  # Esto debería ser un float, no un string
                scale_y=-90,
                translate_x=335343.7418991233,
                translate_y=8949512.65902687
            ),
            bbox=Bbox(min_x=0, min_y=0, max_x=100, max_y=100)
        )
    except ValidationError as e:
        print("Error de validación:", e)

test_invalid_type()


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
