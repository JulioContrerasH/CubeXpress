"""Download a single EE manifest to disk or in-memory."""

from __future__ import annotations

import functools
import pathlib
from typing import Any


@functools.lru_cache(maxsize=64)
def _gee_crs_code(crs: str) -> str:
    """The CRS to send Earth Engine: the code when it parses it, else its WKT1.

    Earth Engine's EPSG database is older than the registry, so a code can be valid in pyproj
    and unknown to Earth Engine (Equi7 South America, EPSG:27707, registered in 2024). One
    probe per distinct CRS, cached, so a run with 250k rows and one CRS probes once.
    """
    import ee

    try:
        ee.Projection(crs).getInfo()
        return crs
    except Exception:
        return _as_wkt1(crs)


def _as_wkt1(crs: str) -> str:
    """The same CRS written as WKT version 1, which Earth Engine does accept."""
    try:
        import pyproj

        return pyproj.CRS.from_user_input(crs).to_wkt(version="WKT1_GDAL")
    except Exception:
        return crs


def _with_gee_crs(manifest: dict[str, Any]) -> dict[str, Any]:
    """A copy of the manifest whose grid carries a CRS Earth Engine can parse."""
    grid = manifest.get("grid")
    if not grid or not grid.get("crsCode"):
        return manifest
    request = dict(manifest)
    request["grid"] = {**grid, "crsCode": _gee_crs_code(grid["crsCode"])}
    return request


def download_manifest(
    manifest: dict[str, Any],
    out_path: str | pathlib.Path | None = None,
) -> bytes | Any:
    """Download one Earth Engine manifest.

    Dispatches to ee.data.getPixels (asset id) or ee.data.computePixels
    (computed expression) based on the manifest contents.

    Earth Engine must be initialized before calling this:
        >>> import ee
        >>> ee.Initialize(project='your-project')

    Args:
        manifest: A request dict with at least 'fileFormat', 'bandIds',
            'grid' and either 'assetId' or 'expression'. Typically built via
            RequestRow.to_manifest().
        out_path: Where to write the result.
            - If None: returns the payload (bytes or ndarray).
            - If a path: writes to disk and returns None.
            For fileFormat='NUMPY_NDARRAY' the value is always returned
            in memory (out_path is ignored).

    Returns:
        - np.ndarray when fileFormat == 'NUMPY_NDARRAY' (always).
        - bytes when out_path is None and fileFormat is a byte format.
        - None when out_path is given and bytes are written to disk.

    Raises:
        ValueError: if manifest is missing required keys.
        ee.EEException: propagated from Earth Engine (size limit, auth, etc.).
    """
    import ee

    if "fileFormat" not in manifest:
        raise ValueError("manifest is missing 'fileFormat'")
    if "assetId" not in manifest and "expression" not in manifest:
        raise ValueError("manifest must contain either 'assetId' or 'expression'")

    file_format = manifest["fileFormat"]

    # Dispatch to the correct EE endpoint
    if "assetId" in manifest:
        result = ee.data.getPixels(_with_gee_crs(manifest))
    else:
        # 'expression' can be either a serialized JSON string OR an ee.Image instance.
        # ee.data.computePixels accepts both, but if it's a string we must deserialize.
        request = _with_gee_crs(manifest)
        if isinstance(request["expression"], str):
            import json

            request["expression"] = ee.deserializer.decode(json.loads(request["expression"]))
        result = ee.data.computePixels(request)

    # NUMPY_NDARRAY: always in-memory, ignore out_path
    if file_format == "NUMPY_NDARRAY":
        return result

    # Byte formats: write to disk if out_path, else return bytes
    if out_path is None:
        return result

    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(result)
    return None
