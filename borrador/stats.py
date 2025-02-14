def getStats(best_effort, reducer, bestEffort, maxPixels, tileScale):
    return {
        "best_effort": best_effort,
        "reducer": reducer,
        "max_pixels": maxPixels,
        "tile_scale": tileScale,
    }

def getStats_image(**kwargs):
    return getStats(**kwargs)
