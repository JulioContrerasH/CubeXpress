from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import pandas as pd

from copy import deepcopy
from typing import Optional

import pathlib
import numpy as np
import ee
import json

def check_not_found_error(error_message: str) -> bool:
    """
    Checks if the error message indicates that the image was not found.
    
    Args:
        error_message (str): The error message to check.
        
    Returns:
        bool: True if the error message indicates "not found", False otherwise.
    
    Example:
        >>> check_not_found_error("Total request size must be less than or equal to...")
        True
    """
    return "Total request size" in error_message and "must be less than or equal to" in error_message

def quadsplit_manifest(manifest: dict) -> list[dict]:
    """
    Splits a manifest into four smaller ones by dividing the grid dimensions.
    
    Args:
        manifest (dict): The original manifest to split.
        
    Returns:
        List[dict]: A list of four smaller manifests with updated grid transformations.

    Example:
        >>> manifest = {'grid': {'dimensions': {'width': 100, 'height': 100}, 'affineTransform': {'scaleX': 0.1, 'scaleY': 0.1, 'translateX': 0, 'translateY': 0}}}
        >>> quadsplit_manifest(manifest)
        [{'grid': {'dimensions': {'width': 50, 'height': 50}, 'affineTransform': {'scaleX': 0.1, 'scaleY': 0.1, 'translateX': 0, 'translateY': 0}}}, {'grid': {'dimensions': {'width': 50, 'height': 50}, 'affineTransform': {'scaleX': 0.1, 'scaleY': 0.1, 'translateX': 5.0, 'translateY': 0}}}, ...]
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

def getGeoTIFFbatch(    
    manifest_dict: dict,
    full_outname: pathlib.Path,
    max_deep_level: Optional[int] = 5,
    method: Optional[str] = "getPixels" 
) -> Optional[np.ndarray]:
    """
    Fetches pixel data from Earth Engine using getPixels with recursion if needed.

    Args:
        manifest_dict (dict): The manifest containing image metadata.
        full_outname (pathlib.Path): The full path to the output file.
        max_deep_level (Optional[int]): Maximum recursion depth.
        method (Optional[str]): The method to use ('getPixels' or 'computePixels').

    Returns:
        Optional[np.ndarray]: The image as a numpy array or None if the download fails.
    
    Example:
        >>> ee.Initialize()
        >>> manifest_dict = {'assetId': 'NASA/NASADEM_HGT/001'}
        >>> getGeoTIFFbatch(manifest_dict, pathlib.Path('/output/image.tif'))
        PosixPath('/output/image.tif')
    """
    
    # Check if the maximum recursion depth has been reached
    if max_deep_level == 0:
        raise ValueError("Max recursion depth reached.")    

    try:        
        # Get the image bytes
        if method == "getPixels":
            image_bytes: bytes = ee.data.getPixels(manifest_dict)
        elif method == "computePixels":
            image_bytes: bytes = ee.data.computePixels(manifest_dict)
        else:
            raise ValueError("Method must be either 'getPixels' or 'computePixels'")
        
        # Write the image bytes to a file
        with open(full_outname, "wb") as src:
            src.write(image_bytes)    
    except Exception as e:
        # TODO: This is a workaround when the image is not found, as it is a message from the server
        # it is not possible to check the type of the exception    
        if not check_not_found_error(str(e)):
            raise ValueError(f"Error downloading the GeoTIFF file from Earth Engine: {e}")   

        # Create the output directory if it doesn't exist
        child_folder: pathlib.Path = full_outname.parent / full_outname.stem
        pathlib.Path(child_folder).mkdir(parents=True, exist_ok=True)
        
        # Split the manifest into four smaller manifests
        manifest_dicts = quadsplit_manifest(manifest_dict)

        for idx, manifest_dict_batch in enumerate(manifest_dicts):
            # Recursively download the image
            getGeoTIFFbatch(
                full_outname=child_folder/ ("%s__%02d.tif" % (full_outname.stem, idx)),
                manifest_dict=manifest_dict_batch,
                max_deep_level=max_deep_level - 1,
                method=method
            )

    return full_outname

def getGeoTIFF(
    full_outname: pathlib.Path,
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5    
) -> Optional[np.ndarray]:
    """
    Retrieves an image from Earth Engine using the appropriate method based on the manifest type.
    
    Args:
        full_outname (pathlib.Path): The full path to the output file.
        manifest_dict (dict): The manifest containing image metadata.
        max_deep_level (Optional[int]): Maximum recursion depth.

    Returns:
        Optional[np.ndarray]: The image as a numpy array or None if the download fails.
    
    Example:
        >>> ee.Initialize()
        >>> manifest_dict = {'assetId': 'NASA/NASADEM_HGT/001'}
        >>> getGeoTIFF(manifest_dict, pathlib.Path('/output/image.tif'))
        PosixPath('/output/image.tif')
    """
    if 'assetId' in manifest_dict:
        return getGeoTIFFbatch(
            manifest_dict=manifest_dict,
            full_outname=full_outname,
            max_deep_level=max_deep_level,
            method="getPixels"
        )
    elif 'expression' in manifest_dict:
        # From a string to a ee.Image object        
        manifest_dict["expression"] = ee.deserializer.decode(
            json.loads(manifest_dict["expression"])
        )

        return getGeoTIFFbatch(
            manifest_dict=manifest_dict, 
            full_outname=full_outname,
            max_deep_level=max_deep_level,
            method="computePixels"
        )
    else:
        raise ValueError("Manifest does not contain 'assetId' or 'expression'")


def getcube(
    request: pd.DataFrame,
    output_path: str | pathlib.Path,
    nworkers: Optional[int] = None,
    max_deep_level: Optional[int] = 5
) -> list[pathlib.Path]:
    """
    Processes a table of image manifests and downloads them in parallel.

    Args:
        table (pd.DataFrame): DataFrame containing image manifests.
        nworkers (Optional[int]): Number of parallel workers. If None, runs sequentially.
        deep_level (Optional[int]): Maximum recursion depth for fetching images.
        output_path (Union[str, pathlib.Path, None]): Directory where images will be saved.
        quiet (bool): If True, suppresses console output.

    Returns:
        List[pathlib.Path]: List of paths to the downloaded images.
    """ 
    # Get the table
    table: pd.DataFrame = request._dataframe
    
    # Create the output directory if it doesn't exist
    output_path = pathlib.Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []
    with ThreadPoolExecutor(max_workers=nworkers) as executor:
        futures = {
            executor.submit(getGeoTIFF, output_path / row.outname, row.manifest, max_deep_level): row
            for _, row in table.iterrows()
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                # TODO add this into the log
                print(f"Error processing {futures[future].outname}: {e}")

    return results
