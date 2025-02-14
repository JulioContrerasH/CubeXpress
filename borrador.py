import ee
ee.Initialize(opt_url="https://earthengine-highvolume.googleapis.com")
# Region of interest.
coords = [
    -121.58626826832939,
    38.059141484827485,
]
region = ee.Geometry.Point(coords)

# Sentinel-2 median composite.
image = (ee.ImageCollection('COPERNICUS/S2')
              .filterBounds(region)
              .filterDate('2020-04-01', '2020-09-01')
              .median())

# Make a projection to discover the scale in degrees.
proj = ee.Projection('EPSG:4326').atScale(10).getInfo()

# Get scales out of the transform.
scale_x = proj['transform'][0]
scale_y = -proj['transform'][4]

# Make a request object.
request = {
    'expression': image,
    'fileFormat': 'PNG',
    'bandIds': ['B4', 'B3', 'B2'],
    'grid': {
        'dimensions': {
            'width': 640,
            'height': 640
        },
        'affineTransform': {
            'scaleX': scale_x,
            'shearX': 0,
            'translateX': coords[0],
            'shearY': 0,
            'scaleY': scale_y,
            'translateY': coords[1]
        },
        'crsCode': proj['crs'],
    },
    'visualizationOptions': {'ranges': [{'min': 0, 'max': 3000}]},
}

image_png = ee.data.computePixels(request)
# Do something with the image...