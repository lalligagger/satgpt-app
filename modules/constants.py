# Sentinel-2 Band Combinations
S2_BAND_COMB = {
    "True Color": [("red",), ("green",), ("blue",)],
    "False Color (Vegetation)": [("nir",), ("red",), ("green",)],
    "False Color (Urban)": [("swir22",), ("swir16",), ("red",)],
    "Short-Wave Infrared": [("swir22",), ("nir",), ("red",)],
    "Agriculture": [("swir16",), ("nir",), ("blue",)],
    "Geology": [("swir22",), ("swir16",), ("blue",)],
    "Healthy Vegetation": [("nir",), ("swir16",), ("blue",)],
    "Snow and Clouds": [("blue",), ("swir16",), ("swir22",)],
}

# Sentinel-2 spectral indices
S2_SPINDICES = {
    "NDVI": {
        "name": "NDVI",
        "fullname": "Normalized Difference Vegetation Index",
        "b0": ("nir",),
        "b1": ("red",),
        "cmap": "RdYlGn",
    },
    "NDBI": {
        "name": "NDBI",
        "fullname": "Normalized Difference Built-up Index",
        "b0": ("swir16",),
        "b1": ("nir",),
        "cmap": "Greys",
    },
    "NDMI": {
        "name": "NDMI",
        "fullname": "Normalized Difference Moisture Index",
        "b0": ("nir08",), # TODO - not right, should be "B8a"
        "b1": ("swir16",),
        "cmap": "RdYlBu",
    },
    "NDWI": {
        "name": "NDWI",
        "fullname": "Normalized Difference Water Index",
        "b0": ("green",),
        "b1": ("nir",),
        "cmap": "Blues",
    },
}
