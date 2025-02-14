def getPixels(**kwargs):
    # Aquí iría la lógica de descarga, por ejemplo con un mock de GEE.
    print("Descargando datos con los parámetros:", kwargs)
    return ["dummy_path.tif"]

def computePixels(**kwargs):
    # Simula el proceso de computación de píxeles
    print("Computando píxeles con los parámetros:", kwargs)
    return ["computed_data"]
