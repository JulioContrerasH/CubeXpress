"""Reactive retiling: split a manifest into smaller pieces by pixel budget."""

from __future__ import annotations

import pathlib
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

from cubexpress.download.manifest import is_rate_error
from cubexpress.geo.tiling import EE_MAX_DIMENSION, split_transform
from cubexpress.geo.transform import RasterTransform

_SIZE_ERROR_PATTERNS = (
    "total request size",
    "must be less than or equal to",
    "exceed",
    "too large",
)


def is_size_error(error: Exception) -> bool:
    """Return True if the exception looks like an EE size-limit rejection.

    Rate rejections ("concurrency limit was exceeded") also say "exceed", but they are
    not about size: those are handled with a wait and a retry, so they do not count.
    """
    if is_rate_error(error):
        return False
    msg = str(error).lower()
    return any(pattern in msg for pattern in _SIZE_ERROR_PATTERNS)


def parse_size_error(error_message: str) -> tuple[int, int]:
    """Extract (actual_bytes, limit_bytes) from an EE size-error message.

    Typical EE message:
        "Total request size (150994944 bytes) must be less than or equal to 50331648 bytes."

    Falls back to a conservative default if the message cannot be parsed.
    """
    matches = re.findall(r"(\d+)\s*bytes", error_message.lower())
    if len(matches) >= 2:
        return int(matches[0]), int(matches[1])
    # Conservative fallback: assume we're at 1.5x the (hardcoded) 48 MiB limit
    return 75_497_472, 50_331_648


_DIMENSION_RE = re.compile(
    r"dimensions?\s*\((\d+)\s*x\s*(\d+)\)\s*must be less than or equal to (\d+)",
    re.IGNORECASE,
)


def parse_dimension_error(error_message: str) -> tuple[int, int, int] | None:
    """Extract (width, height, side_limit) from EE's pixel-grid error, or None.

    Typical EE message:
        "Pixel grid dimensions (103439x55072) must be less than or equal to 32768."
    """
    match = _DIMENSION_RE.search(error_message)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def learn_max_pixels_from_error(
    error_message: str,
    rt: RasterTransform,
    safety_factor: float = 0.95,
) -> int:
    """The pixel budget a rejected request teaches, from whichever limit binds.

    A byte-size error gives an empirical cost per pixel; a pixel-grid error gives the
    side limit (32768). Taking the minimum keeps the next try under both caps. For a
    pixel-grid error the byte side falls back to a conservative default, so it does
    not bind; for a byte error the side side uses Earth Engine's own cap.
    """
    caps = []
    dims = parse_dimension_error(error_message)
    if dims is not None:
        caps.append(int((dims[2] * safety_factor) ** 2))
    else:
        caps.append(int((EE_MAX_DIMENSION * safety_factor) ** 2))

    by_bytes = re.findall(r"(\d+)\s*bytes", error_message.lower())
    if len(by_bytes) >= 2:
        actual, limit = int(by_bytes[0]), int(by_bytes[1])
        cost = actual / (rt.width * rt.height)
        if cost > 0:
            caps.append(int((limit / cost) * safety_factor))
    elif dims is None:
        # Neither bytes nor pixel-grid numbers to learn from: an Earth Engine memory
        # rejection ("User memory limit exceeded"). There is no number to parse, so
        # halve the tile and let the retry find out.
        caps.append(max(1, rt.n_pixels() // 2))
    return min(caps)


def download_with_retry(
    manifest: dict[str, Any],
    out_path: pathlib.Path,
    nworkers: int = 4,
    max_depth: int = 4,
) -> None:
    """Download one tile, splitting it further whenever Earth Engine says it is too heavy.

    Covers the three Earth Engine limits: the pixel grid (32768 per side), the request
    size (bytes) and the interactive memory limit ("User memory limit exceeded", which
    carries no numbers: the tile is halved). Sub-tiles are downloaded in parallel and
    merged into out_path, recursively, up to max_depth (4 levels: 16 pieces at most).
    """
    from cubexpress.download.manifest import download_manifest

    try:
        download_manifest(manifest, out_path=out_path)
        return
    except Exception as exc:
        if not is_size_error(exc) or max_depth <= 0:
            raise
        sub_manifests = split_manifest_from_error(manifest, str(exc))
        if len(sub_manifests) <= 1:
            raise

    from cubexpress.download.merge import merge_tiles

    with tempfile.TemporaryDirectory(prefix="cubexpress_retry_") as tmp:
        tmp_dir = pathlib.Path(tmp)
        paths = [tmp_dir / f"tile_{i:04d}.tif" for i in range(len(sub_manifests))]
        with ThreadPoolExecutor(max_workers=nworkers) as pool:
            futures = [pool.submit(download_with_retry, m, p, nworkers, max_depth - 1)
                       for m, p in zip(sub_manifests, paths, strict=True)]
            for future in futures:
                future.result()
        merge_tiles(paths, out_path)


def bytes_per_pixel_from_error(manifest: dict[str, Any], error_message: str) -> float:
    """Derive the empirical bytes-per-pixel cost from an EE size error.

    Uses the actual byte count EE reported and the 2D pixel area of the
    manifest's grid. The result already accounts for band count, dtype and
    masks, since EE's reported size bundles all of them.

    Raises:
        ValueError: if the manifest grid is missing or the cost is degenerate.
    """
    rt = _rt_from_manifest(manifest)
    actual_bytes, _ = parse_size_error(error_message)
    bpp = actual_bytes / (rt.width * rt.height)
    if bpp <= 0:
        raise ValueError(f"Invalid bytes_per_pixel computed: {bpp}")
    return bpp


def predict_fits(
    manifest: dict[str, Any],
    bytes_per_pixel: float,
    limit_bytes: int = 50_331_648,
    safety_factor: float = 0.9,
) -> bool:
    """Predict whether a manifest fits under the EE size limit, given a known bpp.

    Args:
        manifest: The manifest to check.
        bytes_per_pixel: Empirical cost per 2D pixel (from a previous error).
        limit_bytes: EE's size limit in bytes. Default 48 MiB.
        safety_factor: Headroom multiplier. Default 0.95 (5% margin).

    Returns:
        True if the predicted payload fits under limit_bytes * safety_factor.
    """
    rt = _rt_from_manifest(manifest)
    if rt.width > EE_MAX_DIMENSION or rt.height > EE_MAX_DIMENSION:
        return False
    predicted = bytes_per_pixel * rt.width * rt.height
    return predicted <= limit_bytes * safety_factor


def split_manifest_by_bpp(
    manifest: dict[str, Any],
    bytes_per_pixel: float,
    limit_bytes: int = 50_331_648,
    safety_factor: float = 0.95,
) -> list[dict[str, Any]]:
    """Split an over-sized manifest into smaller tiles, given a known bpp.

    This is the pure-math core of retiling: it needs only the cost per pixel,
    not an EE error string. Each output manifest inherits assetId/expression/
    bandIds/fileFormat from the input and only changes the grid.

    Args:
        manifest: The manifest to split.
        bytes_per_pixel: Empirical cost per 2D pixel.
        limit_bytes: EE's size limit in bytes. Default 48 MiB.
        safety_factor: Headroom multiplier. Default 0.95.

    Returns:
        A list of smaller manifests covering the same area as the input.

    Raises:
        ValueError: if the manifest grid is missing or the cost is degenerate.
    """
    if "grid" not in manifest:
        raise ValueError("manifest is missing 'grid'")
    grid = manifest["grid"]
    if "dimensions" not in grid or "affineTransform" not in grid or "crsCode" not in grid:
        raise ValueError("manifest['grid'] is missing required keys")
    if bytes_per_pixel <= 0:
        raise ValueError(f"bytes_per_pixel must be > 0, got {bytes_per_pixel}")

    rt = _rt_from_manifest(manifest)

    max_pixels = int((limit_bytes / bytes_per_pixel) * safety_factor)
    if max_pixels < 1:
        raise ValueError(f"Computed max_pixels={max_pixels}; manifest too costly to split sensibly.")

    sub_rts = split_transform(rt, max_pixels=max_pixels)
    return [_manifest_with_rt(manifest, sub_rt) for sub_rt in sub_rts]


def split_manifest_from_error(
    manifest: dict[str, Any],
    error_message: str,
    safety_factor: float = 0.95,
) -> list[dict[str, Any]]:
    """Split an over-sized manifest into smaller tiles based on EE's error.

    Thin wrapper around split_manifest_by_bpp: parses the EE error to derive
    the empirical bytes-per-pixel and the limit, then delegates the actual
    tiling math.

    Args:
        manifest: The manifest that EE rejected.
        error_message: The full error string from EE.
        safety_factor: Headroom multiplier. Default 0.95.

    Returns:
        A list of smaller manifests covering the same area as the input.
    """
    if "grid" not in manifest:
        raise ValueError("manifest is missing 'grid'")
    grid = manifest["grid"]
    if "dimensions" not in grid or "affineTransform" not in grid or "crsCode" not in grid:
        raise ValueError("manifest['grid'] is missing required keys")

    rt = _rt_from_manifest(manifest)
    dims = parse_dimension_error(error_message)
    max_pixels = learn_max_pixels_from_error(error_message, rt, safety_factor)
    max_side = dims[2] if dims is not None else EE_MAX_DIMENSION
    sub_rts = split_transform(rt, max_pixels=max_pixels, max_side=max_side)
    return [_manifest_with_rt(manifest, sub_rt) for sub_rt in sub_rts]


# --- internal helpers ---


def _rt_from_manifest(manifest: dict[str, Any]) -> RasterTransform:
    grid = manifest["grid"]
    dims = grid["dimensions"]
    aff = grid["affineTransform"]
    return RasterTransform(
        crs=grid["crsCode"],
        translate_x=aff["translateX"],
        translate_y=aff["translateY"],
        scale_x=aff["scaleX"],
        scale_y=aff["scaleY"],
        width=dims["width"],
        height=dims["height"],
    )


def _manifest_with_rt(manifest: dict[str, Any], rt: RasterTransform) -> dict[str, Any]:
    new = deepcopy(manifest)
    new["grid"] = {
        "dimensions": {"width": rt.width, "height": rt.height},
        "affineTransform": rt.to_ee_dict(),
        "crsCode": rt.crs,
    }
    return new
