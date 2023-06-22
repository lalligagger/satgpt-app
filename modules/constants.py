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

# https://jspanel.de/#options
FLOATPANEL_CONFIGS = {
    "resizeit": {"disable": "true"},
    "headerControls": "closeonly",
    "closeOnEscape": "true",
}
