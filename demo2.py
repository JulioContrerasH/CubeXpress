import ee

import cubexpress

ee.Initialize(project="ee-julius013199")

# Example 1 --------------------------------------------------------------
geotransform = cubexpress.lonlat2rt(    
    lon=-76.5,
    lat=-9.5,
    edge_size=2560*2,
    scale=10
)

request = cubexpress.Request(
    id="s2test",    
    raster_transform=geotransform,
    bands=["elevation"],
    image=ee.Image("NASA/NASADEM_HGT/001").multiply(0.1)
)

cube_requests = cubexpress.RequestSet(requestset=[request])


cubexpress.getcube(
    request=cube_requests,
    nworkers=4,
    output_path="DEM",
    max_deep_level = 5
)

# Example 2 --------------------------------------------------------------
points = [
    (-76.5, -9.5),
    (-76.5, -10.5),
    (-77.5, -10.5)
]

geotransforms = [
    cubexpress.lonlat2rt(
        lon=lon,
        lat=lat,
        edge_size=2560*2,
        scale=10
    )
    for lon, lat in points
]

cube_requests = cubexpress.RequestSet(
    requestset=[
        cubexpress.Request(
            id=f"s2test_{i}",
            raster_transform=geotransform,
            bands=["elevation"],
            image=ee.Image("NASA/NASADEM_HGT/001").multiply(0.1)
        )
        for i, geotransform in enumerate(geotransforms)
    ]
)

cubexpress.getcube(
    request=cube_requests,
    nworkers=4,
    output_path="DEM2",
    max_deep_level = 5
)



#####################

import ee

import cubexpress

ee.Initialize(project="ee-julius013199")

# Example: NDVI from Sentinel-2
image = ee.Image("COPERNICUS/S2_HARMONIZED/20170804T154911_20170804T155116_T18SUJ") \
           .normalizedDifference(["B8", "B4"]) \
           .rename("NDVI")

geotransform = cubexpress.lonlat2rt(
    lon=-76.59, 
    lat=38.89, 
    edge_size=256, 
    scale=10
)

request = cubexpress.Request(
    id="ndvi_test",
    raster_transform=geotransform,
    bands=["NDVI"],
    image=image  # custom expression
)

cube_requests = cubexpress.RequestSet(requestset=[request])

cubexpress.getcube(
    request=cube_requests,
    output_path="output_ndvi",
    nworkers=2,
    max_deep_level=5
)


######


import ee

import cubexpress

# Initialize Earth Engine
ee.Initialize(project="ee-julius013199")

# Define multiple points (longitude, latitude)
points = [
    (-97.64, 33.37),
    (-97.59, 33.37)
]

# Filter a Sentinel-2 collection ONCE
collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterDate("2024-01-01", "2024-01-31")
)

requestset = []

for i, (lon, lat) in enumerate(points):
    print(i)
    point_geom = ee.Geometry.Point([lon, lat])
    collection_filtered = collection.filterBounds(point_geom)
    image_ids = collection_filtered.aggregate_array('system:id').getInfo()

    geotransform = cubexpress.lonlat2rt(
        lon=lon,
        lat=lat,
        edge_size=512,
        scale=10
    )

    requestset.extend([
        cubexpress.Request(
            id=f"s2test_{i}_{idx}",
            raster_transform=geotransform,
            bands=["B4", "B3", "B2"],
            image=images_id
        )
        for idx, images_id in enumerate(image_ids)
    ])
    
cube_requests = cubexpress.RequestSet(requestset=requestset)

cubexpress.getcube(
    request=cube_requests,
    nworkers=4,
    output_path="images_s2",
    max_deep_level = 5
)









# Extract image IDs
image_ids = collection.aggregate_array("system:id").getInfo()

# Build requests for each (point, image) pair
requests = []
for idx, (lon, lat) in enumerate(points):
    # Create geotransform for this particular point
    geotransform = cubexpress.lonlat2rt(
        lon=lon,
        lat=lat,
        edge_size=512,  # Adjust as needed
        scale=10        # Sentinel-2 has 10m resolution for B4, B3, B2
    )
    for j, image_id in enumerate(image_ids):
        requests.append(
            cubexpress.Request(
                id=f"s2_global_{idx}_{j}",
                raster_transform=geotransform,
                bands=["B4", "B3", "B2"],
                image=image_id
            )
        )

# Build the RequestSet and download
cube_requests = cubexpress.RequestSet(requestset=requests)

cube_requests._dataframe

result_paths = cubexpress.getcube(
    request=cube_requests,
    output_path="output_sentinel_global",
    nworkers=4,
    max_deep_level=5
)

print("Downloaded files (Advanced Usage 1):", result_paths)

















import ee

import cubexpress

ee.Initialize(project="ee-julius013199")

# Example 1 --------------------------------------------------------------
geotransform = cubexpress.lonlat2rt(    
    lon=-76.5,
    lat=-9.5,
    edge_size=2560*2,
    scale=10
)

request = cubexpress.Request(
    id="s2test",    
    raster_transform=geotransform,
    bands=["elevation"],
    image=ee.Image("NASA/NASADEM_HGT/001").multiply(0.1)
)

cube_requests = cubexpress.RequestSet(requestset=[request])


cubexpress.getcube(
    request=cube_requests,
    nworkers=4,
    output_path="DEM",
    max_deep_level = 5
)

# Example 2 --------------------------------------------------------------
points = [
    (-76.5, -9.5),
    (-76.5, -10.5),
    (-77.5, -10.5)
]

geotransforms = [
    cubexpress.lonlat2rt(
        lon=lon,
        lat=lat,
        edge_size=2560*2,
        scale=10
    )
    for lon, lat in points
]

cube_requests = cubexpress.RequestSet(
    requestset=[
        cubexpress.Request(
            id=f"s2test_{i}",
            raster_transform=geotransform,
            bands=["elevation"],
            image=ee.Image("NASA/NASADEM_HGT/001").multiply(0.1)
        )
        for i, geotransform in enumerate(geotransforms)
    ]
)

cubexpress.getcube(
    request=cube_requests,
    nworkers=4,
    output_path="DEM2",
    max_deep_level = 5
)

