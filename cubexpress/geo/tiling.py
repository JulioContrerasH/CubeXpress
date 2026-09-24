"""Tiling: split a large RasterTransform into smaller tiles."""

from __future__ import annotations

import math

from cubexpress.geo.transform import RasterTransform

# Earth Engine caps every getDownloadURL request at 32768 pixels per side. Straight from the
# error: "Pixel grid dimensions (103439x55072) must be less than or equal to 32768."
EE_MAX_DIMENSION = 32768


def split_transform(
    rt: RasterTransform,
    max_pixels: int,
    force_grid: bool = False,
    max_side: int | None = EE_MAX_DIMENSION,
) -> list[RasterTransform]:
    """Split a RasterTransform into tiles, each with at most `max_pixels` pixels.

    Tiles together cover exactly the same area as the input, share the same
    CRS and scale, and form a perfect tiling (no overlap, no gaps).

    Strategy (in order of preference):
        1. If the input already fits → return [rt].
        2. Horizontal strips (full width, reduced height) — preserves row locality.
        3. Vertical strips (full height, reduced width) — when horizontal fails.
        4. 2D grid — fallback when both strip strategies fail.

    With force_grid=True, strips are skipped and a 2D grid is used directly. This
    matters for polygon clipping: strips span the full width/height and so almost
    always cross the whole polygon (little to skip), whereas a grid of square-ish
    tiles lets the corners of the bbox (outside the polygon) be dropped — that is
    where the download savings come from.

    Args:
        rt: The RasterTransform to split.
        max_pixels: Maximum allowed pixels per tile.
        force_grid: If True, tile as a 2D grid regardless of strip fit (for
            polygon-aware clipping, where square tiles maximize skippable area).
        max_side: Maximum pixels per side per tile (Earth Engine's cap is
            EE_MAX_DIMENSION = 32768). None removes the cap, for callers that
            are not Earth Engine requests.

    Returns:
        A list of RasterTransforms. Always non-empty.
    """
    if max_pixels <= 0:
        raise ValueError(f"max_pixels must be > 0, got {max_pixels}")

    if max_side is not None and max_side < 1:
        raise ValueError(f"max_side must be >= 1 or None, got {max_side}")

    lado = max_side if max_side is not None else 10**9
    fits_side = rt.width <= lado and rt.height <= lado
    if rt.n_pixels() <= max_pixels and fits_side:
        return [rt]

    # Polygon clipping wants square-ish tiles so bbox corners can be skipped.
    if force_grid:
        tile_side = min(lado, max(1, int(math.sqrt(max_pixels))))
        return _grid_tiles(rt, tile_side, tile_side)

    # Try horizontal strips: full width, height reduced. Only when the full width
    # respects the side cap (a 103439 px wide strip does not, no matter the height).
    if rt.width <= lado:
        tile_h = min(max_pixels // rt.width, lado)
        if tile_h >= 1:
            return _horizontal_strips(rt, tile_h)

    # Try vertical strips: full height, width reduced
    if rt.height <= lado:
        tile_w = min(max_pixels // rt.height, lado)
        if tile_w >= 1:
            return _vertical_strips(rt, tile_w)

    # Last resort: 2D grid
    tile_side = min(lado, max(1, int(math.sqrt(max_pixels))))
    return _grid_tiles(rt, tile_side, tile_side)


def _horizontal_strips(rt: RasterTransform, tile_height: int) -> list[RasterTransform]:
    """Split into horizontal strips: same width, reduced height."""
    tiles = []
    y = 0
    while y < rt.height:
        h = min(tile_height, rt.height - y)
        tiles.append(
            RasterTransform(
                crs=rt.crs,
                translate_x=rt.translate_x,
                translate_y=rt.translate_y + y * rt.scale_y,
                scale_x=rt.scale_x,
                scale_y=rt.scale_y,
                width=rt.width,
                height=h,
            )
        )
        y += tile_height
    return tiles


def _vertical_strips(rt: RasterTransform, tile_width: int) -> list[RasterTransform]:
    """Split into vertical strips: same height, reduced width."""
    tiles = []
    x = 0
    while x < rt.width:
        w = min(tile_width, rt.width - x)
        tiles.append(
            RasterTransform(
                crs=rt.crs,
                translate_x=rt.translate_x + x * rt.scale_x,
                translate_y=rt.translate_y,
                scale_x=rt.scale_x,
                scale_y=rt.scale_y,
                width=w,
                height=rt.height,
            )
        )
        x += tile_width
    return tiles


def _grid_tiles(rt: RasterTransform, tile_w: int, tile_h: int) -> list[RasterTransform]:
    """Split into a 2D grid of tiles."""
    tiles = []
    y = 0
    while y < rt.height:
        h = min(tile_h, rt.height - y)
        x = 0
        while x < rt.width:
            w = min(tile_w, rt.width - x)
            tiles.append(
                RasterTransform(
                    crs=rt.crs,
                    translate_x=rt.translate_x + x * rt.scale_x,
                    translate_y=rt.translate_y + y * rt.scale_y,
                    scale_x=rt.scale_x,
                    scale_y=rt.scale_y,
                    width=w,
                    height=h,
                )
            )
            x += tile_w
        y += tile_h
    return tiles
