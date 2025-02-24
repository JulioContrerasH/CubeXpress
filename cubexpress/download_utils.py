
from copy import deepcopy
from cubexpress.error_utils import check_not_found_error
from typing import Optional, List

import io
import numpy as np
import gc
import rasterio as rio
import ee
import json

def quadsplit_manifest(manifest: dict) -> List[dict]:
    """
    Splits a manifest into four smaller manifests by dividing the grid dimensions.

    Args:
        manifest (dict): The original manifest to be split.

    Returns:
        List[dict]: A list of four smaller manifests with updated grid transformations.
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

def getPixels_np(
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False
) -> Optional[np.ndarray]:
    """
    Fetches pixel data from Earth Engine using getPixels with recursion if needed.

    Args:
        manifest_dict (dict): The manifest containing image metadata.
        max_deep_level (Optional[int]): Maximum recursion depth.
        quiet (Optional[bool]): If True, suppresses console output.

    Returns:
        Optional[np.ndarray]: The image as a numpy array or None if the download fails.
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

def computePixels_np(
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False
) -> Optional[np.ndarray]:
    """
    Fetches pixel data from Earth Engine using computePixels with recursion if needed.

    Args:
        manifest_dict (dict): The manifest containing image metadata.
        max_deep_level (Optional[int]): Maximum recursion depth.
        quiet (Optional[bool]): If True, suppresses console output.

    Returns:
        Optional[np.ndarray]: The image as a numpy array or None if the download fails.
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
    
def image_from_manifest(
    manifest_dict: dict,
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False
) -> Optional[np.ndarray]:
    """
    Retrieves an image from Earth Engine using the appropriate method based on the manifest type.

    Args:
        manifest_dict (dict): The manifest containing image metadata.
        max_deep_level (Optional[int]): Maximum recursion depth for fetching the image.
        quiet (Optional[bool]): If True, suppresses console output.

    Returns:
        Optional[np.ndarray]: The image as a numpy array or None if the download fails.
    """
    if 'assetId' in manifest_dict:
        return getPixels_np(manifest_dict, max_deep_level, quiet)
    elif 'expression' in manifest_dict:
        manifest_dict = eval(str(manifest_dict))
        manifest_dict["expression"] = ee.deserializer.decode(
            json.loads(manifest_dict["expression"])
        )
        return computePixels_np(manifest_dict, max_deep_level, quiet)
    else:
        raise ValueError("Manifest does not contain 'assetId' or 'expression'")