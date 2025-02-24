from cubexpress.geotyping import RasterTransformSet
import ee
import re
import pandas as pd

def dataframe_manifest(
    geometadatas: RasterTransformSet,    
    image: str | ee.Image,
    bands: list[str],
) -> pd.DataFrame:
    """
    Generates a DataFrame manifest for geospatial metadata, including 
    transformation parameters, resolution, and other properties.

    Args:
        geometadatas (RasterTransformSet): Set of geospatial metadata entries.
        bands (List[str], optional): List of band names to include in the manifest.
        image (Union[str, ee.Image], optional): The Earth Engine expression or assetId. 
            If it's an `ee.Image`, it will be serialized, otherwise, the string
            is treated as an asset ID.

    Returns:
        pd.DataFrame: A DataFrame containing the metadata manifest, including geospatial 
                      information, transformation, resolution, and output file names.

    Example:
        >>> metadata_set = RasterTransformSet(rastertransformset=[geometadata1, geometadata2])
        >>> bands = ["elevation"]
        >>> image = "NASA/NASADEM_HGT/001"
        >>> table_manifest = dataframe_manifest(metadata_set, bands, image)
    """
    if isinstance(image, ee.Image):
        # Serialize the ee.Image expression
        serialized_expression = image.serialize()
        collection_str = re.findall(r'"constantValue":\s*"([^"]*)"', serialized_expression)[0]
        expression_key = 'expression'

    else:
        # Handle the case where expression is a string (assetId)
        collection_str = image
        serialized_expression = image
        expression_key = 'assetId'

    # Create the DataFrame manifest from the geospatial metadata
    df_manifest = geometadatas.export_df().reset_index().apply(
        lambda df: pd.Series({
            'x': df.x,
            'y': df.y,
            'crs': df.crs,
            'image_id': collection_str,
            'bands': bands,
            'width': df.width,
            'height': df.height,
            'geotransform': df.geotransform,
            'resolution': df.geotransform['scaleX'],
            'manifest': {
                expression_key: serialized_expression,
                'fileFormat': 'GEO_TIFF',
                'bandIds': bands, 
                'grid': { 
                    'dimensions': {
                        'width': df.width,
                        'height': df.height
                    },
                    'affineTransform': df.geotransform,
                    'crsCode': df.crs
                },
            },
            'outname': f"{collection_str.replace('/', '_')}__{df.name:04d}.tif" 
        }), 
        axis=1
    )

    return df_manifest