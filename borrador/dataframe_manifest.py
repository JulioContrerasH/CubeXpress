import pandas as pd
from typing import Any

def dataframe_manifest(geometadatas: Any, collection_data: Any, bands: Any) -> pd.DataFrame:
    data = []
    for metadata in geometadatas:
        # Aquí añadirías el procesamiento del `metadata` para llenar el DataFrame.
        data.append({
            'crs': metadata.crs.code,
            'bbox': f"{metadata.bbox.min_x}, {metadata.bbox.min_y}, {metadata.bbox.max_x}, {metadata.bbox.max_y}",
            'bands': ', '.join(bands),
            # Añadir más columnas si es necesario
        })
    return pd.DataFrame(data)

# dataframe_manifest.py

def dataframe_manifest_computepixel_ic():
    # Implementación de la función
    pass

# Otras funciones...
