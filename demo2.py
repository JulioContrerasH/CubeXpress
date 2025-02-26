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