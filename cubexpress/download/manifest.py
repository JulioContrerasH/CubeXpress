"""Download a single EE manifest to disk or in-memory."""

from __future__ import annotations

import os
import pathlib
import threading
import time
from typing import Any

from cubexpress.download.gee_crs import gee_crs_code

# The project's concurrent interactive request limit (20 in the basic tiers, see
# https://developers.google.com/earth-engine/guides/usage). Every RPC goes through this
# semaphore, so the pools and their nested retries can never overshoot it together.
MAX_REQUESTS = int(os.environ.get("CUBEXPRESS_MAX_REQUESTS", "16"))
_REQUEST_SLOTS = threading.BoundedSemaphore(MAX_REQUESTS)

# Rate rejections are not a size problem: they get a wait and a retry, never a split.
_RATE_PATTERNS = ("too many requests", "concurrency limit", "rate limit", "quota exceeded")


def is_rate_error(error: Exception | str) -> bool:
    msg = str(error).lower()
    return any(pattern in msg for pattern in _RATE_PATTERNS)


def _set_max_requests(n: int) -> None:
    """Change the request budget (tests, or a project with a different limit)."""
    global MAX_REQUESTS, _REQUEST_SLOTS
    MAX_REQUESTS = n
    _REQUEST_SLOTS = threading.BoundedSemaphore(n)

# One lock per output path: on Windows two threads writing the same tile at once raises
# "[WinError 32] The process cannot access the file because it is being used by another
# process". The paths are unique per tile in theory, but retries can revisit one.
_WRITE_LOCKS: dict[str, threading.Lock] = {}
_WRITE_LOCKS_GUARD = threading.Lock()


def _write_lock(path: pathlib.Path) -> threading.Lock:
    key = str(path.resolve())
    with _WRITE_LOCKS_GUARD:
        return _WRITE_LOCKS.setdefault(key, threading.Lock())


def _with_gee_crs(manifest: dict[str, Any]) -> dict[str, Any]:
    """A copy of the manifest whose grid carries a CRS Earth Engine can parse."""
    grid = manifest.get("grid")
    if not grid or not grid.get("crsCode"):
        return manifest
    request = dict(manifest)
    request["grid"] = {**grid, "crsCode": gee_crs_code(grid["crsCode"])}
    return request


def _call_pixels(manifest: dict[str, Any]):
    """One RPC: getPixels for an asset id, computePixels for an expression."""
    import ee

    if "assetId" in manifest:
        return ee.data.getPixels(_with_gee_crs(manifest))
    # 'expression' can be either a serialized JSON string OR an ee.Image instance.
    # ee.data.computePixels accepts both, but if it's a string we must deserialize.
    request = _with_gee_crs(manifest)
    if isinstance(request["expression"], str):
        import json

        request["expression"] = ee.deserializer.decode(json.loads(request["expression"]))
    return ee.data.computePixels(request)


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

    # Dispatch to the correct EE endpoint, inside the request budget, and wait out the
    # rate rejections (2, 4, 8, 16 seconds) instead of splitting the tile.
    result = None
    for attempt in range(5):
        try:
            with _REQUEST_SLOTS:
                result = _call_pixels(manifest)
            break
        except Exception as exc:
            if not is_rate_error(exc) or attempt == 4:
                raise
            time.sleep(2 ** (attempt + 1))

    # NUMPY_NDARRAY: always in-memory, ignore out_path
    if file_format == "NUMPY_NDARRAY":
        return result

    # Byte formats: write to disk if out_path, else return bytes
    if out_path is None:
        return result

    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock(out_path):
        out_path.write_bytes(result)
    return None
