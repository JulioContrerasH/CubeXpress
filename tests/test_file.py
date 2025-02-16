import pytest
from cubexpress.geotyping import CRS, Geotransform, Bbox, GeoMetadata, GeoMetadatas

def test_geospatial_data_creation():
    # Creamos instancias válidas de las clases
    crs = CRS(code="EPSG:4326")
    geotransform = Geotransform(scale_x=0.1, scale_y=-0.1, translate_x=100.0, translate_y=200.0)
    bbox = Bbox(min_x=-180.0, min_y=-90.0, max_x=180.0, max_y=90.0)
    
    # Creamos un GeoMetadata válido
    geometadata = GeoMetadata(crs=crs, geotransform=geotransform, bbox=bbox)
    
    # Verificamos que las propiedades estén correctas
    assert geometadata.crs.code == "EPSG:4326"
    assert geometadata.geotransform.scale_x == 0.1
    assert geometadata.geotransform.scale_y == -0.1
    assert geometadata.bbox.min_x == -180.0
    assert geometadata.bbox.max_y == 90.0

def test_invalid_geospatial_data():
    # Intentamos crear un GeoMetadata con datos inválidos
    with pytest.raises(ValueError):
        GeoMetadata(crs=CRS(code="EPSG:9999"), geotransform=Geotransform(scale_x=0.1, scale_y=-0.1, translate_x=100.0, translate_y=200.0), bbox=Bbox(min_x=-180.0, min_y=-90.0, max_x=180.0, max_y=90.0))



def test_geo_metadata_serialization():
    crs = CRS(code="EPSG:4326")
    geotransform = Geotransform(scale_x=0.1, scale_y=-0.1, translate_x=100.0, translate_y=200.0)
    bbox = Bbox(min_x=-180.0, min_y=-90.0, max_x=180.0, max_y=90.0)
    geometadata = GeoMetadata(crs=crs, geotransform=geotransform, bbox=bbox)
    
    # Convertir a diccionario
    geo_dict = geometadata.dict()
    
    # Verificar que los datos están correctos
    assert geo_dict['crs']['code'] == "EPSG:4326"
    assert geo_dict['geotransform']['scale_x'] == 0.1
    assert geo_dict['bbox']['min_x'] == -180.0

def test_geo_metadatas():
    crs = CRS(code="EPSG:4326")
    geotransform = Geotransform(scale_x=0.1, scale_y=-0.1, translate_x=100.0, translate_y=200.0)
    bbox = Bbox(min_x=-180.0, min_y=-90.0, max_x=180.0, max_y=90.0)
    
    geometadatas = GeoMetadatas(
        geometadatas=[
            GeoMetadata(crs=crs, geotransform=geotransform, bbox=bbox),
            GeoMetadata(crs=crs, geotransform=geotransform, bbox=bbox)
        ]
    )
    
    assert len(geometadatas.geometadatas) == 2
