import ee

import cubexpress

ee.Initialize(project="ee-julius013199")

# Coordenadas de ejemplo
lon, lat = -97.59208957295374, 33.37104797051992

# Crear un punto a partir de las coordenadas
point = ee.Geometry.Point([lon, lat])

# Filtrar la colección de imágenes Sentinel-2 con el filtro de bounds
collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
               .filterBounds(point) \
               .filterDate('2024-01-01', '2024-01-31')

# Obtener las IDs de las imágenes usando aggregate_array para obtener un array de los assetId
image_ids = collection \
            .aggregate_array('system:id') \
            .getInfo() 

# Configuración del geotransform (puedes modificar estos valores según sea necesario)
geotransform = cubexpress.lonlat2rt(    
    lon=lon,
    lat=lat,
    edge_size=128,  # Ajusta según el tamaño deseado
    scale=10  # Escala de la imagen (ajustar según resolución deseada)
)

# Preparar las solicitudes para obtener los cubos de datos
requests = [
    cubexpress.Request(   
        id=f"s2test_{i}",
        raster_transform=geotransform,
        bands=["B4", "B3", "B2"],
        image=image_id
    )
    for i, image_id in enumerate(image_ids)
]

cube_requests = cubexpress.RequestSet(requestset=requests)

# Usar cubexpress para obtener el cubo de datos
cubexpress.getcube(
    request=cube_requests,
    nworkers=4,
    output_path="output_sentinel",  # Directorio de salida para los archivos
    max_deep_level=5  # Nivel máximo de recursión
)




ee.Image("COPERNICUS/S2_SR_HARMONIZED/20240101T165741_20240101T165742_T14RNR")
S2B_MSIL1C_20250213T100029_N0511_R122_T32RNR_20250213T122736

image = ee.Image("COPERNICUS/S2_HARMONIZED/20250213T100029_20250213T122736_T32RNR")
image.getInfo()

 "/content/images_s2/20250213T100029_20250213T100858_T32RNR.tif"





import json
import random

## SIMON
import ee

import cubexpress

ee.Initialize(project="ee-julius013199")

# Load GeoJSON
with open('demo/world_50k_L8.geojson') as f:
    data = json.load(f)

#  Randomly select 5 features
random_features = random.sample(data['features'], 5)

# Extract coordinates
points = [
   (
      feature["geometry"]["coordinates"][0], 
      feature["geometry"]["coordinates"][1]
    ) for feature in random_features
]


# Start with a broad Sentinel-2 collection
collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterDate("2024-03-28", "2025-02-26")
)

# Build a list of Request objects
requestset = []

for i, (lon, lat) in enumerate(points):

    # Create a point geometry for the current coordinates
    point_geom = ee.Geometry.Point([lon, lat])
    collection_filtered = collection.filterBounds(point_geom)
    
    # Convert the filtered collection into a list of asset IDs
    image_ids = collection_filtered.aggregate_array("system:id").getInfo()
    
    # Define a geotransform for this point
    geotransform = cubexpress.lonlat2rt(
        lon=lon,
        lat=lat,
        edge_size=64,  # Adjust the image size in pixels
        scale=10        # 10m resolution for Sentinel-2
    )
    
    # Create one Request per image found for this point
    requestset.extend([
        cubexpress.Request(
            id=f"s2test_{i}_{idx}",
            raster_transform=geotransform,
            bands=["B4", "B3", "B2"], # You can add more bands here
            image=image_id
        )
        for idx, image_id in enumerate(image_ids)
    ])

# Combine into a RequestSet
cube_requests = cubexpress.RequestSet(requestset=requestset)
print(cube_requests._dataframe)

# Download everything in parallel
results = cubexpress.getcube(
    request=cube_requests,
    nworkers=4,
    output_path="images_s2",
    max_deep_level=5
)
print("Downloaded files:", results)





import cubexpress

rt = cubexpress.lonlat2rt(
   lon=-76.0, 
   lat=40.0, 
   edge_size=512, 
   scale=30
)
print(rt)







class RasterTransform(BaseModel):
    """
    Represents a single geospatial metadata entry with CRS and transformation information.
    
    Attributes:
        id (str): The unique identifier for the raster metadata.
        crs (str): The Coordinate Reference System string (EPSG code or WKT).
        geotransform (GeotransformDict): A dictionary containing spatial transformation parameters.
        width (int): Raster width in pixels.
        height (int): Raster height in pixels.
    
    Example:
        >>> metadata = RasterTransform(
        ...     id="image1",
        ...     crs="EPSG:4326",
        ...     geotransform={
        ...         'scaleX': 1.0, 'shearX': 0, 'translateX': 100.0,
        ...         'scaleY': 1.0, 'shearY': 0, 'translateY': 200.0
        ...     },
        ...     width=1000,
        ...     height=1000
        ... )
        RasterTransform(crs='EPSG:4326', width=1000, height=1000)