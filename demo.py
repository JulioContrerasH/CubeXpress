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
