from cubexpress.download_utils import image_from_manifest
from typing import Optional, List, Union
from concurrent.futures import ThreadPoolExecutor
import pathlib
import concurrent.futures
import pandas as pd
import gc
import json
import rasterio as rio

import numpy as np
from PIL import Image

def getCube_batch(
    row: pd.Series,
    output_path: str,
    max_deep_level: Optional[int] = 5,
    quiet: Optional[bool] = False,
    format: Optional[str] = "GTiff"
) -> Optional[pathlib.Path]:
    """
    Downloads and saves an image from a manifest entry.

    Args:
        row (pd.Series): A row containing the image manifest and metadata.
        output_path (str): Directory where the image will be saved.
        max_deep_level (Optional[int]): Maximum recursion depth for fetching the image.
        quiet (Optional[bool]): If True, suppresses console output.
        format (Optional[str]): Output format, either "GTiff" (default) or "PNG".

    Returns:
        Optional[pathlib.Path]: The path to the saved image, or None if download fails.
    """
    if not quiet:
        print(f"Downloading {row.outname}...")

    manifest_dict = json.loads(row.manifest) if isinstance(row.manifest, str) else row.manifest

    data_np = image_from_manifest(
        manifest_dict=manifest_dict,
        max_deep_level=max_deep_level,
        quiet=quiet
    )
    
    if data_np is None:
        return None
    
    if "GTiff".upper() == "GTiff":
        outfile = pathlib.Path(output_path) / row.outname
        outfile.parent.mkdir(parents=True, exist_ok=True)
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
                manifest_dict["grid"]["affineTransform"]["translateY"]
            ),
            "crs": manifest_dict["grid"]["crsCode"],
        }

        with rio.open(outfile, "w", **metadata_rio) as dst:
            dst.write(data_np)

    elif format.upper() == "PNG":
        outfile = pathlib.Path(output_path) / (row.outname.split(".")[0] + ".png")
        outfile.parent.mkdir(parents=True, exist_ok=True)
        if data_np.shape[0] >= 3:
            rgb_data = data_np[:3, :, :]
        else:
            raise ValueError("PNG output requires at least 3 bands for RGB format.")
        img_to_save = np.moveaxis(rgb_data, 0, -1)
        img = Image.fromarray(img_to_save)
        img.save(outfile, format="PNG")
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'GTiff' or 'PNG'.")

    gc.collect()
    return outfile

def getCube(
    table: pd.DataFrame,
    nworkers: Optional[int] = None,
    deep_level: Optional[int] = 5,
    output_path: Union[str, pathlib.Path, None] = None,
    format: Optional[str] = "GTiff",
    quiet: bool = False
) -> List[pathlib.Path]:
    """
    Processes a table of image manifests and downloads them in parallel.

    Args:
        table (pd.DataFrame): DataFrame containing image manifests.
        nworkers (Optional[int]): Number of parallel workers. If None, runs sequentially.
        deep_level (Optional[int]): Maximum recursion depth for fetching images.
        output_path (Union[str, pathlib.Path, None]): Directory where images will be saved.
        format (Optional[str]): Output format, either "GTiff" (default) or "PNG".
        quiet (bool): If True, suppresses console output.

    Returns:
        List[pathlib.Path]: List of paths to the downloaded images.
    """
    if output_path is None:
        output_path = pathlib.Path(table.iloc[0].image_id.replace("/", "_"))
    output_path = pathlib.Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []

    if nworkers is None:
        for _, row in table.iterrows():
            result = getCube_batch(
                row=row, 
                output_path=output_path,
                max_deep_level=deep_level, 
                format=format,
                quiet=quiet
            )
            if result:
                results.append(result)
    else:
        with ThreadPoolExecutor(max_workers=nworkers) as executor:
            futures = {
                executor.submit(getCube_batch, row, output_path, deep_level, format, quiet): row
                for _, row in table.iterrows()
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"Error processing {futures[future].outname}: {e}")

    return results
