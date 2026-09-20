"""Tests for RasterTransform."""

from __future__ import annotations

import pytest
import pyproj

from cubexpress.geo.transform import RasterTransform
from dataclasses import FrozenInstanceError


# --- Valid construction ---

def test_valid_construction():
    rt = RasterTransform(
        crs="EPSG:32718",
        translate_x=500_000.0,
        translate_y=8_000_000.0,
        scale_x=10.0,
        scale_y=-10.0,
        width=1024,
        height=512,
    )
    assert rt.crs == "EPSG:32718"
    assert rt.translate_x == 500_000.0
    assert rt.translate_y == 8_000_000.0
    assert rt.scale_x == 10.0
    assert rt.scale_y == -10.0
    assert rt.width == 1024
    assert rt.height == 512


# --- Validation: dimensions must be positive ---

def test_zero_width_rejected():
    with pytest.raises(ValueError, match="positive"):
        RasterTransform(
            crs="EPSG:32718", translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=0, height=512,
        )


def test_negative_height_rejected():
    with pytest.raises(ValueError, match="positive"):
        RasterTransform(
            crs="EPSG:32718", translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=512, height=-100,
        )


# --- Validation: scales follow GDAL convention ---

def test_zero_scale_x_rejected():
    with pytest.raises(ValueError, match="scale_x"):
        RasterTransform(
            crs="EPSG:32718", translate_x=0, translate_y=0,
            scale_x=0, scale_y=-10, width=512, height=512,
        )


def test_positive_scale_y_rejected():
    with pytest.raises(ValueError, match="scale_y"):
        RasterTransform(
            crs="EPSG:32718", translate_x=0, translate_y=0,
            scale_x=10, scale_y=10, width=512, height=512,
        )


def test_empty_crs_rejected():
    with pytest.raises(ValueError, match="crs"):
        RasterTransform(
            crs="", translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=512, height=512,
        )


# --- Validation: dimensions must be integers ---

def test_float_width_rejected():
    with pytest.raises(TypeError, match="width"):
        RasterTransform(
            crs="EPSG:32718", translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=100.5, height=512,
        )


def test_int_like_float_height_rejected():
    with pytest.raises(TypeError, match="height"):
        RasterTransform(
            crs="EPSG:32718", translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=512, height=512.0,
        )


def test_bool_width_rejected():
    with pytest.raises(TypeError, match="width"):
        RasterTransform(
            crs="EPSG:32718", translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=True, height=512,
        )


def test_string_height_rejected():
    with pytest.raises(TypeError, match="height"):
        RasterTransform(
            crs="EPSG:32718", translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=512, height="512",
        )


# --- Validation: the four spatial fields must be numbers ---

@pytest.mark.parametrize("field", ["translate_x", "translate_y", "scale_x", "scale_y", "shear_x", "shear_y"])
@pytest.mark.parametrize("bad", ["0", None, True])
def test_numeric_fields_reject_non_numbers(field, bad):
    kwargs = dict(
        crs="EPSG:32718", translate_x=0, translate_y=0,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    kwargs[field] = bad
    with pytest.raises(TypeError, match=field):
        RasterTransform(**kwargs)


def test_int_numeric_fields_accepted():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=0, translate_y=0,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    assert rt.scale_x == 10


# --- The metres-to-degrees conversion ---

def test_metres_to_degrees_at_lat_minus_12():
    from cubexpress.geo.transform import metres_to_degrees
    lon_deg, lat_deg = metres_to_degrees(30, -12.0)
    assert lon_deg == pytest.approx(0.000275, abs=1e-6)
    assert lat_deg == pytest.approx(0.000271, abs=1e-6)
    assert lon_deg > lat_deg          # a 12 grados del ecuador, la longitud son más grados


def test_metres_to_degrees_at_equator_are_close():
    """En el elipsoide no son idénticos ni en el ecuador, pero difieren menos del 1%."""
    from cubexpress.geo.transform import metres_to_degrees
    lon_deg, lat_deg = metres_to_degrees(30, 0.0)
    assert lon_deg == pytest.approx(0.000269, abs=1e-6)
    assert lat_deg == pytest.approx(0.000271, abs=1e-6)
    assert abs(lon_deg - lat_deg) / lat_deg < 0.01


# --- Validation: the CRS must be one Earth Engine can parse ---

def test_wkt1_crs_is_respected():
    """Un WKT1 se respeta tal cual: es lo que GEE acepta y la salida para un código nuevo."""
    wkt1 = pyproj.CRS.from_epsg(32718).to_wkt(version="WKT1_GDAL")
    rt = RasterTransform(
        crs=wkt1, translate_x=0, translate_y=0,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    assert rt.crs == wkt1


def test_equi7_proj4_canonicalized_to_its_epsg():
    """Equi7 South America: pyproj lo resuelve a EPSG:27707 (registrado en 2024)."""
    equi7 = pyproj.CRS.from_epsg(27707).to_proj4()
    rt = RasterTransform(
        crs=equi7, translate_x=7257179.236, translate_y=5592024.446,
        scale_x=100, scale_y=-100, width=10, height=10,
    )
    assert rt.crs == "EPSG:27707"


def test_equi7_wkt1_is_the_escape_hatch():
    """Ese mismo CRS, en WKT1, se respeta: es lo que GEE sí entiende."""
    wkt1 = pyproj.CRS.from_epsg(27707).to_wkt(version="WKT1_GDAL")
    rt = RasterTransform(
        crs=wkt1, translate_x=7257179.236, translate_y=5592024.446,
        scale_x=100, scale_y=-100, width=10, height=10,
    )
    assert rt.crs.startswith("PROJCS[")


def test_wkt2_crs_canonicalized():
    wkt2 = pyproj.CRS.from_epsg(32718).to_wkt()  # pyproj returns WKT2 by default
    rt = RasterTransform(
        crs=wkt2, translate_x=0, translate_y=0,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    assert rt.crs == "EPSG:32718"


def test_proj4_crs_canonicalized():
    proj4 = pyproj.CRS.from_epsg(32718).to_proj4()
    rt = RasterTransform(
        crs=proj4, translate_x=0, translate_y=0,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    assert rt.crs == "EPSG:32718"


def test_projjson_crs_canonicalized():
    projjson = pyproj.CRS.from_epsg(32718).to_json()   # what a GeoParquet stores
    rt = RasterTransform(
        crs=projjson, translate_x=0, translate_y=0,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    assert rt.crs == "EPSG:32718"


def test_custom_crs_without_epsg_becomes_wkt1():
    """A CRS written by hand, with no standard code, goes to Earth Engine as WKT1."""
    local = pyproj.CRS.from_proj4(
        "+proj=tmerc +lat_0=-10 +lon_0=-76 +k=0.9999 +x_0=100000 +y_0=0 "
        "+datum=WGS84 +units=m +no_defs"
    )
    assert pyproj.CRS.from_user_input(local.to_wkt()).to_epsg() is None   # sanity
    rt = RasterTransform(
        crs=local.to_proj4(), translate_x=100000, translate_y=0,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    assert rt.crs.startswith("PROJCS[")     # WKT1, que es lo que GEE acepta


def test_unknown_epsg_rejected():
    with pytest.raises(ValueError, match="not a valid CRS"):
        RasterTransform(
            crs="EPSG:99999", translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=512, height=512,
        )


def test_non_string_crs_rejected():
    with pytest.raises(TypeError, match="crs"):
        RasterTransform(
            crs=32718, translate_x=0, translate_y=0,
            scale_x=10, scale_y=-10, width=512, height=512,
        )


# --- Validation: a geographic CRS takes degrees, not metres ---

def test_geographic_crs_with_metre_scale_rejected():
    with pytest.raises(ValueError, match="degrees for EPSG:4326"):
        RasterTransform(
            crs="EPSG:4326", translate_x=-77.0, translate_y=-12.0,
            scale_x=30, scale_y=-30, width=2, height=2,
        )


def test_error_message_suggests_the_degrees():
    with pytest.raises(ValueError, match=r"scale_x=0\.000275"):
        RasterTransform(
            crs="EPSG:4326", translate_x=-77.0, translate_y=-12.0,
            scale_x=30, scale_y=-30, width=2, height=2,
        )


def test_geographic_crs_with_degree_scale_accepted():
    rt = RasterTransform(
        crs="EPSG:4326", translate_x=-77.0, translate_y=-12.0,
        scale_x=0.000276, scale_y=-0.000269, width=100, height=100,
    )
    assert rt.n_pixels() == 10_000


def test_projected_crs_with_metre_scale_accepted():
    rt = RasterTransform(
        crs="EPSG:24878", translate_x=282462.19, translate_y=8673024.59,
        scale_x=30, scale_y=-30, width=100, height=100,
    )
    assert rt.scale_x == 30


# --- Derived methods ---

def test_n_pixels():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=0, translate_y=0,
        scale_x=10, scale_y=-10, width=100, height=200,
    )
    assert rt.n_pixels() == 20_000


def test_bbox():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=500_000, translate_y=8_000_000,
        scale_x=10, scale_y=-10, width=100, height=200,
    )
    xmin, ymin, xmax, ymax = rt.bbox()
    assert xmin == 500_000
    assert ymax == 8_000_000
    assert xmax == 501_000       # 500_000 + 100 * 10
    assert ymin == 7_998_000     # 8_000_000 + 200 * (-10)


# --- Earth Engine conversion ---

def test_to_ee_dict():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=500_000, translate_y=8_000_000,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    d = rt.to_ee_dict()
    assert d == {
        "scaleX": 10,
        "shearX": 0.0,
        "translateX": 500_000,
        "scaleY": -10,
        "shearY": 0.0,
        "translateY": 8_000_000,
    }


# --- Immutability (frozen dataclass) ---

def test_frozen():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=0, translate_y=0,
        scale_x=10, scale_y=-10, width=100, height=100,
    )
    with pytest.raises(FrozenInstanceError):
        rt.width = 200  # type: ignore[misc]


# --- Structural equality ---

def test_equality():
    a = RasterTransform("EPSG:32718", 0, 0, 10, -10, 100, 100)
    b = RasterTransform("EPSG:32718", 0, 0, 10, -10, 100, 100)
    c = RasterTransform("EPSG:32718", 0, 0, 10, -10, 200, 100)
    assert a == b
    assert a != c


# --- Fractional values: math must work for non-integer scales ---

def test_bbox_with_fractional_scale():
    """Scales below 1m (sub-meter resolution) must still compute correctly."""
    rt = RasterTransform(
        crs="EPSG:32718",
        translate_x=500_000.5,
        translate_y=8_000_000.75,
        scale_x=0.5,
        scale_y=-0.5,
        width=100,
        height=200,
    )
    xmin, ymin, xmax, ymax = rt.bbox()
    assert xmin == 500_000.5
    assert ymax == 8_000_000.75
    assert xmax == 500_050.5    # 500_000.5 + 100 * 0.5
    assert ymin == 7_999_900.75  # 8_000_000.75 + 200 * (-0.5)


# --- shear (rotated rasters) ---

def test_shear_defaults_to_zero():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=500_000, translate_y=8_500_000,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    assert rt.shear_x == 0.0
    assert rt.shear_y == 0.0


def test_shear_can_be_set():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=500_000, translate_y=8_500_000,
        scale_x=10, scale_y=-10, width=512, height=512,
        shear_x=0.5, shear_y=0.3,
    )
    assert rt.shear_x == 0.5
    assert rt.shear_y == 0.3


def test_shear_propagates_to_ee_dict():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=500_000, translate_y=8_500_000,
        scale_x=10, scale_y=-10, width=512, height=512,
        shear_x=0.5, shear_y=0.3,
    )
    d = rt.to_ee_dict()
    assert d["shearX"] == 0.5
    assert d["shearY"] == 0.3


def test_default_shear_gives_zero_in_ee_dict():
    rt = RasterTransform(
        crs="EPSG:32718", translate_x=500_000, translate_y=8_500_000,
        scale_x=10, scale_y=-10, width=512, height=512,
    )
    d = rt.to_ee_dict()
    assert d["shearX"] == 0.0
    assert d["shearY"] == 0.0