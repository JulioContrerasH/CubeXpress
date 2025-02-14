import utm
from typing import Tuple
from typing import Optional

# Función para convertir latitud y longitud a UTM
def query_utm_crs_info(lon: float, lat: float) -> Tuple[float, float, str]:
    """
    Converts a pair of lat, lon to UTM coordinates.

    Args:
        lon (float): The longitude of the point.
        lat (float): The latitude of the point.
    
    Returns:
        Tuple[float, float, str]: The UTM coordinates and the 
            EPSG code of the zone.
    """
    x, y, zone, _ = utm.from_latlon(lat, lon)
    zone_epsg = f"326{zone:02d}" if lat >= 0 else f"327{zone:02d}"
    return x, y, "EPSG:" + zone_epsg


def _create_query_entry(
    manifest: dict,
    collection: str,
    index: int = 0,
    lon: Optional[float] = None,
    lat: Optional[float] = None,
    edge_size: Optional[int] = None,
    scale: Optional[int] = None
) -> dict:
    """
    Función auxiliar que extrae los datos relevantes de 'manifest'
    y los organiza en un diccionario.
    """
    affine = manifest["grid"]["affineTransform"]
    xmin = affine["translateX"]
    ymax = affine["translateY"]
    # Nota: si lo llamabas 'espg' por equivocación, aquí lo normalizamos como 'epsg'
    epsg = manifest["grid"]["crsCode"]
    
    # Si la resolución no se pasó explícitamente, la tomamos del manifest
    # (escala en X, asumiendo que scaleX == scaleY en valor absoluto).
    if scale is None:
        scale = affine.get("scaleX", None)

    outname = f"{collection.replace('/', '_')}__{index:04d}.tif"

    row_data = {
        "xmin": xmin,
        "ymax": ymax,
        "epsg": epsg,
        "edge_size": edge_size,
        "scale": scale,
        "manifest": manifest,
        "outname": outname
    }
    # Si recibimos lon/lat, los incluimos en el diccionario
    if lon is not None:
        row_data["lon"] = lon
    if lat is not None:
        row_data["lat"] = lat

    return row_data