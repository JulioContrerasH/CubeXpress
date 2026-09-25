import pytest

from cubexpress.geo.geometry import point_to_geometry, rt_to_geometry
from cubexpress.geo.transform import RasterTransform

# --- helper: capture what gets passed to ee.Geometry.Rectangle ---

def _patch_rectangle(monkeypatch):
    """Patch ee.Geometry.Rectangle and .Polygon to record their args instead of hitting GEE."""
    import ee

    captured = {}

    def fake_rectangle(coords, proj=None, geodesic=None, evenOdd=None):
        captured["forma"] = "Rectangle"
        captured["coords"] = coords
        captured["proj"] = proj
        captured["geodesic"] = geodesic
        captured["evenOdd"] = evenOdd
        return {"fake_geometry": True, "coords": coords, "proj": proj}

    def fake_polygon(coords, proj=None, geodesic=None, evenOdd=None):
        captured["forma"] = "Polygon"
        captured["coords"] = coords
        captured["proj"] = proj
        captured["geodesic"] = geodesic
        captured["evenOdd"] = evenOdd
        return {"fake_geometry": True, "coords": coords, "proj": proj}

    monkeypatch.setattr(ee.Geometry, "Rectangle", fake_rectangle)
    monkeypatch.setattr(ee.Geometry, "Polygon", fake_polygon)
    return captured


def _rt(crs="EPSG:32632", tx=236874.0, ty=42855.0, sx=10, sy=-10, w=1500, h=1500):
    return RasterTransform(
        crs=crs, translate_x=tx, translate_y=ty,
        scale_x=sx, scale_y=sy, width=w, height=h,
    )


# --- rt_to_geometry ---

def test_rt_to_geometry_uses_rt_crs(monkeypatch):
    captured = _patch_rectangle(monkeypatch)
    rt = _rt(crs="EPSG:32718")
    rt_to_geometry(rt)
    assert captured["proj"] == "EPSG:32718"


def test_rt_to_geometry_uses_planar_edges(monkeypatch):
    """Planar edges (geodesic=False + evenOdd=True) are what make the geometry exact.

    In a projected CRS only this pair of flags is accepted for a planar rectangle:
    geodesic=True + evenOdd=True raises, geodesic=False + evenOdd=False raises.
    """
    captured = _patch_rectangle(monkeypatch)
    rt_to_geometry(_rt())
    assert captured["geodesic"] is False
    assert captured["evenOdd"] is True


def test_rt_to_geometry_coords_match_bbox(monkeypatch):
    """The rectangle coords must equal the RasterTransform's bbox."""
    captured = _patch_rectangle(monkeypatch)
    rt = _rt(tx=236874.0, ty=42855.0, sx=10, sy=-10, w=1500, h=1500)
    rt_to_geometry(rt)

    xmin, ymin, xmax, ymax = rt.bbox()
    assert captured["coords"] == [xmin, ymin, xmax, ymax]


def test_rt_to_geometry_bbox_dimensions(monkeypatch):
    """A 1500x1500 px at 10m should span 15000m each side."""
    captured = _patch_rectangle(monkeypatch)
    rt = _rt(tx=0.0, ty=15000.0, sx=10, sy=-10, w=1500, h=1500)
    rt_to_geometry(rt)
    xmin, ymin, xmax, ymax = captured["coords"]
    assert xmax - xmin == 15000
    assert ymax - ymin == 15000


def test_rt_to_geometry_does_not_reproject(monkeypatch):
    """The geometry must stay in the RT's CRS — no .transform() to 4326.

    We assert proj is the UTM CRS, never 'EPSG:4326'.
    """
    captured = _patch_rectangle(monkeypatch)
    rt = _rt(crs="EPSG:32632")
    rt_to_geometry(rt)
    assert captured["proj"] == "EPSG:32632"
    assert captured["proj"] != "EPSG:4326"


# --- point_to_geometry ---

def test_point_to_geometry_returns_rectangle(monkeypatch):
    captured = _patch_rectangle(monkeypatch)
    point_to_geometry(lon=6.659, lat=0.249, width=512, height=512, scale=10)
    assert "coords" in captured
    assert captured["geodesic"] is False
    assert captured["evenOdd"] is True


def test_point_to_geometry_matches_point_to_rt(monkeypatch):
    """point_to_geometry must cover the same extent as point_to_rt would."""
    from cubexpress.geo.construct import point_to_rt

    captured = _patch_rectangle(monkeypatch)
    point_to_geometry(lon=6.659, lat=0.249, width=512, height=512, scale=10)

    rt = point_to_rt(lon=6.659, lat=0.249, width=512, height=512, scale=10)
    xmin, ymin, xmax, ymax = rt.bbox()
    assert captured["coords"] == [xmin, ymin, xmax, ymax]
    assert captured["proj"] == rt.crs


def test_point_to_geometry_uses_utm_not_4326(monkeypatch):
    """A point near the equator should produce a UTM proj, not 4326."""
    captured = _patch_rectangle(monkeypatch)
    point_to_geometry(lon=6.659, lat=0.249, width=512, height=512, scale=10)
    assert captured["proj"].startswith("EPSG:326") or captured["proj"].startswith("EPSG:327")


def test_point_to_geometry_invalid_scale_rejected():
    with pytest.raises(ValueError, match="scale must be > 0"):
        point_to_geometry(lon=6.659, lat=0.249, width=512, height=512, scale=0)


# --- integration (real GEE) ---

@pytest.mark.integration
def test_rt_to_geometry_real_area(require_ee):
    """The real geometry's area should match the RT's expected size."""
    rt = _rt(crs="EPSG:32632", tx=236874.0, ty=42855.0, sx=10, sy=-10, w=1500, h=1500)
    geom = rt_to_geometry(rt)
    area_km2 = geom.area(maxError=1).getInfo() / 1e6
    # 15km x 15km = 225 km² (small distortion tolerated)
    assert 220 < area_km2 < 230


@pytest.mark.integration
def test_rt_to_geometry_real_filterbounds(require_ee):
    """A UTM geometry must work with filterBounds (the whole point of an ROI)."""
    import ee

    rt = _rt(crs="EPSG:32632", tx=236874.0, ty=27855.0, sx=10, sy=-10, w=1500, h=1500)
    geom = rt_to_geometry(rt)
    col = (ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
           .filterBounds(geom)
           .filterDate("2023-01-01", "2023-02-01"))
    assert col.size().getInfo() > 0


@pytest.mark.integration
def test_point_to_geometry_real_filterbounds(require_ee):
    import ee

    geom = point_to_geometry(lon=6.659, lat=0.249, width=1500, height=1500, scale=10)
    col = (ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
           .filterBounds(geom)
           .filterDate("2023-01-01", "2023-06-01"))
    assert col.size().getInfo() > 0

@pytest.mark.integration
def test_rt_to_geometry_is_exact_for_a_big_rt(require_ee):
    """Planar edges make the search region the rt's own rectangle.

    A 2000 x 500 km rt in UTM: the exact rectangular area is 984411.5 km². With the geodesic
    default Earth Engine reports 984842.6 (431 km² more), which this test catches.
    """
    rt = _rt(crs="EPSG:32718", tx=200_000.0, ty=8_500_000.0, sx=500, sy=-500,
             w=4000, h=1000)
    geom = rt_to_geometry(rt)
    area_km2 = geom.area(maxError=1).getInfo() / 1e6
    assert abs(area_km2 - 984_411.5) < 10


@pytest.mark.integration
def test_rt_to_geometry_keeps_the_antimeridian_chip_whole(require_ee):
    """A chip crossing the antimeridian keeps its full area (16 km², not half)."""
    from cubexpress.geo.construct import point_to_rt

    rt = point_to_rt(lon=179.9995, lat=-16.5, width=400, height=400, scale=10)
    geom = rt_to_geometry(rt)
    area_km2 = geom.area(maxError=1).getInfo() / 1e6
    assert 15.5 < area_km2 < 16.5


@pytest.mark.integration
def test_rt_to_geometry_accepts_a_polar_rt(require_ee):
    """A polar stereographic rt builds a sane geometry, in its own CRS."""
    rt = _rt(crs="EPSG:3413", tx=0.0, ty=-200_000.0, sx=100, sy=-100, w=200, h=200)
    geom = rt_to_geometry(rt)
    area_km2 = geom.area(maxError=1).getInfo() / 1e6
    assert 350 < area_km2 < 450


def test_rt_to_geometry_uses_a_polygon_when_sheared(monkeypatch):
    """A sheared grid cannot be covered by a rectangle: its four corners are used instead."""
    captured = _patch_rectangle(monkeypatch)
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=450_000.0, translate_y=8_600_000.0,
        scale_x=10, scale_y=-10, width=100, height=100, shear_x=5.0,
    )
    rt_to_geometry(rt)
    assert captured["forma"] == "Polygon"
    anillo = captured["coords"][0]
    assert anillo[0] == [450_000.0, 8_600_000.0]
    assert anillo[1] == [451_000.0, 8_600_000.0]      # +100 columnas en x
    assert anillo[2] == [451_500.0, 8_599_000.0]      # +100 filas: 500 m de shear
    assert anillo[3] == [450_500.0, 8_599_000.0]
    assert anillo[-1] == anillo[0]                    # el anillo se cierra


@pytest.mark.integration
def test_rt_to_geometry_sheared_is_exact(require_ee):
    """The sheared region follows the parallelogram, not its bbox."""
    import ee

    rt = RasterTransform(
        crs="EPSG:32718", translate_x=450_000.0, translate_y=8_600_000.0,
        scale_x=10, scale_y=-10, width=100, height=100, shear_x=5.0,
    )
    geom = rt_to_geometry(rt)
    dentro = ee.Geometry.Point([450_750.0, 8_599_500.0], proj="EPSG:32718")
    solo_bbox = ee.Geometry.Point([450_050.0, 8_599_050.0], proj="EPSG:32718")
    assert geom.contains(dentro).getInfo() is True
    assert geom.contains(solo_bbox).getInfo() is False


def test_point_to_geometry_accepts_a_target(monkeypatch):
    captured = _patch_rectangle(monkeypatch)
    point_to_geometry(lon=-77.04, lat=-12.06, width=200, height=200, scale=10,
                      target_crs="EPSG:24878")
    assert captured["proj"] == "EPSG:24878"
