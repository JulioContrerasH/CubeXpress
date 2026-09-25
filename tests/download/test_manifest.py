
import numpy as np
import pytest

from cubexpress.download.manifest import download_manifest

# --- helpers ---

def _make_asset_manifest():
    return {
        "fileFormat": "GEO_TIFF",
        "bandIds": ["B4", "B3", "B2"],
        "grid": {
            "dimensions": {"width": 64, "height": 64},
            "affineTransform": {
                "scaleX": 10, "shearX": 0, "translateX": 500_000,
                "scaleY": -10, "shearY": 0, "translateY": 8_500_000,
            },
            "crsCode": "EPSG:32718",
        },
        "assetId": "COPERNICUS/S2_HARMONIZED/dummy",
    }


def _make_expression_manifest():
    return {
        "fileFormat": "GEO_TIFF",
        "bandIds": ["B4"],
        "grid": {
            "dimensions": {"width": 64, "height": 64},
            "affineTransform": {
                "scaleX": 10, "shearX": 0, "translateX": 500_000,
                "scaleY": -10, "shearY": 0, "translateY": 8_500_000,
            },
            "crsCode": "EPSG:32718",
        },
        "expression": '{"fake": "serialized_image"}',
    }


# --- dispatch: assetId vs expression ---

def test_download_manifest_with_assetId_calls_getPixels(monkeypatch):
    import ee
    calls = {"getPixels": 0, "computePixels": 0}

    monkeypatch.setattr(ee.data, "getPixels", lambda m: (calls.__setitem__("getPixels", calls["getPixels"] + 1), b"dummy")[1])
    monkeypatch.setattr(ee.data, "computePixels", lambda m: (calls.__setitem__("computePixels", calls["computePixels"] + 1), b"dummy")[1])

    download_manifest(_make_asset_manifest())
    assert calls["getPixels"] == 1
    assert calls["computePixels"] == 0


def test_download_manifest_with_expression_calls_computePixels(monkeypatch):
    import ee
    calls = {"getPixels": 0, "computePixels": 0}

    monkeypatch.setattr(ee.data, "getPixels", lambda m: (calls.__setitem__("getPixels", calls["getPixels"] + 1), b"dummy")[1])
    monkeypatch.setattr(ee.data, "computePixels", lambda m: (calls.__setitem__("computePixels", calls["computePixels"] + 1), b"dummy")[1])
    monkeypatch.setattr(ee.deserializer, "decode", lambda d: "FAKE_IMAGE")

    download_manifest(_make_expression_manifest())
    assert calls["getPixels"] == 0
    assert calls["computePixels"] == 1


def test_download_manifest_expression_is_deserialized_before_computePixels(monkeypatch):
    import ee
    received = {}

    monkeypatch.setattr(ee.deserializer, "decode", lambda d: "DESERIALIZED_OBJECT")
    monkeypatch.setattr(ee.data, "computePixels", lambda m: (received.update(m), b"dummy")[1])

    download_manifest(_make_expression_manifest())
    assert received["expression"] == "DESERIALIZED_OBJECT"


# --- output handling: bytes vs disk vs ndarray ---

def test_download_manifest_returns_bytes_when_no_out_path(monkeypatch):
    import ee
    monkeypatch.setattr(ee.data, "getPixels", lambda m: b"TIFF_BYTES")
    result = download_manifest(_make_asset_manifest())
    assert result == b"TIFF_BYTES"


def test_download_manifest_writes_file_when_out_path_given(tmp_path, monkeypatch):
    import ee
    monkeypatch.setattr(ee.data, "getPixels", lambda m: b"TIFF_BYTES")

    out = tmp_path / "out.tif"
    result = download_manifest(_make_asset_manifest(), out_path=out)

    assert result is None
    assert out.exists()
    assert out.read_bytes() == b"TIFF_BYTES"


def test_download_manifest_creates_parent_directories(tmp_path, monkeypatch):
    import ee
    monkeypatch.setattr(ee.data, "getPixels", lambda m: b"TIFF_BYTES")

    out = tmp_path / "nested" / "deep" / "out.tif"
    download_manifest(_make_asset_manifest(), out_path=out)
    assert out.exists()


def test_download_manifest_numpy_format_returns_ndarray(monkeypatch):
    import ee
    fake_array = np.zeros((64, 64), dtype=np.uint16)
    monkeypatch.setattr(ee.data, "getPixels", lambda m: fake_array)

    manifest = _make_asset_manifest()
    manifest["fileFormat"] = "NUMPY_NDARRAY"
    result = download_manifest(manifest)
    assert isinstance(result, np.ndarray)
    assert result.shape == (64, 64)


def test_download_manifest_numpy_ignores_out_path(tmp_path, monkeypatch):
    import ee
    fake_array = np.zeros((64, 64), dtype=np.uint16)
    monkeypatch.setattr(ee.data, "getPixels", lambda m: fake_array)

    manifest = _make_asset_manifest()
    manifest["fileFormat"] = "NUMPY_NDARRAY"
    out = tmp_path / "should_not_exist.npy"

    result = download_manifest(manifest, out_path=out)
    assert isinstance(result, np.ndarray)
    assert not out.exists()


# --- validation ---

def test_download_manifest_missing_fileFormat_rejected():
    bad = _make_asset_manifest()
    del bad["fileFormat"]
    with pytest.raises(ValueError, match="fileFormat"):
        download_manifest(bad)


def test_download_manifest_missing_asset_and_expression_rejected():
    bad = _make_asset_manifest()
    del bad["assetId"]
    with pytest.raises(ValueError, match=r"assetId.*expression"):
        download_manifest(bad)


# --- error propagation ---

def test_download_manifest_ee_error_propagates(monkeypatch):
    import ee

    def fail(m):
        raise ee.EEException("Total request size exceeded the limit of 50331648 bytes")

    monkeypatch.setattr(ee.data, "getPixels", fail)

    with pytest.raises(ee.EEException, match="Total request size"):
        download_manifest(_make_asset_manifest())


# --- integration (real EE) ---

@pytest.mark.integration
def test_download_manifest_real_s2_chip_to_disk(tmp_path, require_ee):
    """Download a real S2 chip from EE and verify the file is a valid GeoTIFF."""
    from cubexpress.geo.construct import point_to_rt
    from cubexpress.request.row import RequestRow

    rt = point_to_rt(lon=6.659, lat=0.249, width=64, height=64, scale=10)
    row = RequestRow(
        id="demo_chip",
        raster_transform=rt,
        image="COPERNICUS/S2_HARMONIZED/20230509T093549_20230509T095123_T32NKF",
        bands=["B4", "B3", "B2"],
    )
    out = tmp_path / "chip.tif"
    download_manifest(row.to_manifest(), out_path=out)

    assert out.exists()
    assert out.stat().st_size > 0
    # Minimal GeoTIFF magic byte check (II = little-endian TIFF header)
    header = out.read_bytes()[:4]
    assert header[:2] in (b"II", b"MM"), f"Not a TIFF: {header!r}"


@pytest.mark.integration
def test_download_manifest_real_s2_chip_as_numpy(require_ee):
    """Download a real S2 chip as in-memory ndarray."""
    from cubexpress.geo.construct import point_to_rt
    from cubexpress.request.row import RequestRow

    rt = point_to_rt(lon=6.659, lat=0.249, width=32, height=32, scale=10)
    row = RequestRow(
        id="demo_chip",
        raster_transform=rt,
        image="COPERNICUS/S2_HARMONIZED/20230509T093549_20230509T095123_T32NKF",
        bands=["B4", "B3", "B2"],
    )
    arr = download_manifest(row.to_manifest(file_format="NUMPY_NDARRAY"))

    assert isinstance(arr, np.ndarray)
    assert arr.shape == (32, 32)
    assert arr.dtype.names == ("B4", "B3", "B2")  # structured array: one field per band

# --- The CRS sent to Earth Engine ---
# The code list ships with the package (cubexpress/download/gee_crs.py), so known codes cost
# no query at all: they are resolved with the table.

def test_supported_code_is_sent_as_is():
    from cubexpress.download.gee_crs import gee_crs_code
    assert gee_crs_code("EPSG:32718") == "EPSG:32718"
    assert gee_crs_code("EPSG:24878") == "EPSG:24878"


def test_rejected_code_goes_as_wkt1_without_asking():
    from cubexpress.download.gee_crs import gee_crs_code
    salida = gee_crs_code("EPSG:27707")          # Equi7 South America
    assert salida.startswith("PROJCS[")
    assert "Equi7" in salida


def test_unknown_code_asks_gee(monkeypatch):
    """A code in neither list (a new one) is asked to Earth Engine, and falls back to WKT1."""
    import ee

    import cubexpress.download.gee_crs as g

    class FakeProjection:
        def __init__(self, crs): self.crs = crs
        def getInfo(self): raise Exception("Could not parse")

    monkeypatch.setattr(ee, "Projection", FakeProjection)
    g.gee_crs_code.cache_clear()
    assert g.gee_crs_code("EPSG:99999").startswith("EPSG:99999")   # could not be converted


def test_grid_crs_is_replaced_in_the_manifest():
    import cubexpress.download.manifest as m
    original = {"grid": {"crsCode": "EPSG:27707", "dimensions": {"width": 2, "height": 2}}}
    salida = m._with_gee_crs(original)
    assert salida["grid"]["crsCode"].startswith("PROJCS[")
    assert original["grid"]["crsCode"] == "EPSG:27707"      # the original is not modified


def test_write_lock_is_stable_per_path(tmp_path):
    """One lock per output path: on Windows two writers of the same tile raise WinError 32."""
    from cubexpress.download.manifest import _write_lock

    a, b = tmp_path / "x.tif", tmp_path / "y.tif"
    assert _write_lock(a) is _write_lock(a)
    assert _write_lock(a) is not _write_lock(b)


# --- el limite de concurrencia: 429 con espera, y cupo global de requests ---

_429 = ("Too Many Requests: Request was rejected because the concurrency limit was exceeded. "
        "Learn more at ...")


def test_is_rate_error_detects_the_concurrency_message():
    from cubexpress.download.manifest import is_rate_error

    assert is_rate_error(Exception(_429))
    assert not is_rate_error(Exception("Total request size (150994944 bytes) must be ..."))


def test_a_rate_error_gets_a_wait_and_a_retry(monkeypatch, tmp_path):
    """Two 429s and then success: the download must not fail nor split."""
    import ee

    from cubexpress.download.manifest import download_manifest

    monkeypatch.setattr("cubexpress.download.manifest.time.sleep", lambda _s: None)
    llamadas = []

    def falso_get_pixels(request):
        llamadas.append(request)
        if len(llamadas) < 3:
            raise Exception(_429)
        return b"tif"

    monkeypatch.setattr(ee.data, "getPixels", falso_get_pixels)
    ruta = tmp_path / "rate_test.tif"
    manifiesto = {"fileFormat": "GEO_TIFF", "bandIds": ["B4"], "assetId": "X",
                  "grid": {"crsCode": "EPSG:32718", "dimensions": {"width": 2, "height": 2},
                           "affineTransform": {"scaleX": 10, "shearX": 0, "translateX": 0,
                                               "scaleY": -10, "shearY": 0, "translateY": 0}}}
    download_manifest(manifiesto, out_path=ruta)
    assert len(llamadas) == 3


def test_the_request_budget_caps_concurrency(monkeypatch):
    """The nested retries cannot push the project over its concurrent request limit."""
    import threading
    import time as _time

    import ee

    import cubexpress.download.manifest as m

    m._set_max_requests(2)
    vivos = []
    pico = []

    def falso_get_pixels(request):
        vivos.append(1)
        pico.append(len(vivos))
        _time.sleep(0.05)
        vivos.pop()
        return b"tif"

    monkeypatch.setattr(ee.data, "getPixels", falso_get_pixels)
    manifiesto = {"fileFormat": "GEO_TIFF", "bandIds": ["B4"], "assetId": "X",
                  "grid": {"crsCode": "EPSG:32718", "dimensions": {"width": 2, "height": 2},
                           "affineTransform": {"scaleX": 10, "shearX": 0, "translateX": 0,
                                               "scaleY": -10, "shearY": 0, "translateY": 0}}}
    hilos = [threading.Thread(target=m.download_manifest, args=(manifiesto,)) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    m._set_max_requests(16)
    assert max(pico) <= 2


def test_the_budget_shrinks_when_earth_engine_pushes_back(monkeypatch):
    """A 429 lowers the concurrency for the rest of the run: it adapts, no hammering."""
    import ee

    import cubexpress.download.manifest as m

    monkeypatch.setattr("cubexpress.download.manifest.time.sleep", lambda _s: None)
    m._set_max_requests(16)

    def siempre_429(request):
        raise Exception(_429)

    monkeypatch.setattr(ee.data, "getPixels", siempre_429)
    manifiesto = {"fileFormat": "GEO_TIFF", "bandIds": ["B4"], "assetId": "X",
                  "grid": {"crsCode": "EPSG:32718", "dimensions": {"width": 2, "height": 2},
                           "affineTransform": {"scaleX": 10, "shearX": 0, "translateX": 0,
                                               "scaleY": -10, "shearY": 0, "translateY": 0}}}
    import pytest
    with pytest.raises(Exception, match="concurrency"):
        m.download_manifest(manifiesto)
    assert m._BUDGET.max == 16        # el techo no cambia
    assert m._BUDGET.cap < 16         # el cupo sí: se achicó solo
    m._set_max_requests(16)
