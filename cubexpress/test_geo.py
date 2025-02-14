from cubexpress.main import generate_manifest
from cubexpress.geo_typing import CRS, Geotransform, Bbox
from typing import List

from cubexpress.geo_typing import CRS, Geotransform, Bbox, GeoMetadata
from pydantic import ValidationError

def test_generate_manifest():
    row = {
        "x": -76.5,
        "y": -9.5,
        "edge_size": 128,
        "resolution": 90
    }
    bands = ["elevation"]
    collection = "NASA/NASADEM_HGT/001"
    
    manifest = generate_manifest(row['x'], row['y'], row['edge_size'], row['resolution'], bands=bands, collection=collection)
    
    # Aserciones
    assert manifest['assetId'] == collection
    assert manifest['fileFormat'] == 'GEO_TIFF'
    assert 'crsCode' in manifest['grid']
    
    # Imprimir algo para ver que todo está bien
    print("Test passed! Manifest generated successfully.")

test_generate_manifest()



def test_invalid_type():
    try:
        # Pasar un tipo incorrecto
        geo_metadata = GeoMetadata(
            crs=CRS(code="EPSG:4326"),
            geotransform=Geotransform(
                scale_x="incorrect_type",  # Esto debería ser un float, no un string
                scale_y=-90,
                translate_x=335343.7418991233,
                translate_y=8949512.65902687
            ),
            bbox=Bbox(min_x=0, min_y=0, max_x=100, max_y=100)
        )
    except ValidationError as e:
        print("Error de validación:", e)

test_invalid_type()
