import spyndex

S2_BAND_MAPPING = {
    "A": ("coastal",),
    "N": ("nir",),
    "N2": ("nir08",),
    "R": ("red",),
    "G": ("green",),
    "B": ("blue",),
    "RE1": ("rededge1",),
    "RE2": ("rededge2",),
    "RE3": ("rededge3",),
    "S1": ("swir16",),
    "S2": ("swir22",),
}

# Constants
SPYNDEX_CONSTANTS = spyndex.constants

# Spectral indices
SPYNDEX_INDICES = spyndex.indices


def to_stac_bands(spindex):
    """
    Get the list of bands for the selected index according to stac
    naming conventions
    """

    return [
        S2_BAND_MAPPING[b]
        for b in SPYNDEX_INDICES[spindex].bands
        if b not in SPYNDEX_CONSTANTS
    ]


def get_index_bands(spindex):
    """Get the list of bands for the selected index"""

    return [b for b in SPYNDEX_INDICES[spindex].bands if b not in SPYNDEX_CONSTANTS]


def get_index_constants(spindex):
    """
    Get the list of constants (constant, default_value)
    for the selected index
    """

    constants_lst = [
        b for b in SPYNDEX_INDICES[spindex].bands if b in SPYNDEX_CONSTANTS
    ]

    if constants_lst:
        return [
            (constant, SPYNDEX_CONSTANTS[constant].default)
            for constant in constants_lst
        ]
    return None


def get_s2_indices():
    """Create a list with all available sentinel-2 indices"""

    s2_indices = []
    for spindex in SPYNDEX_INDICES:
        application_domain = SPYNDEX_INDICES[spindex].application_domain
        platforms = SPYNDEX_INDICES[spindex].platforms
        if "Sentinel-2" in platforms and application_domain != "kernel":
            s2_indices.append(SPYNDEX_INDICES[spindex].short_name)
    return s2_indices


def get_index_props(spindex):
    """Create a dictionary with some properties of the selected index"""

    return {
        "short_name": SPYNDEX_INDICES[spindex].short_name,
        "long_name": SPYNDEX_INDICES[spindex].long_name,
        "application_domain": SPYNDEX_INDICES[spindex].application_domain,
        "index_bands": get_index_bands(spindex),
        "stac_bands": to_stac_bands(spindex),
        "constants": get_index_constants(spindex),
    }


def compute_index(in_data, spindex):
    """
    Calculate the selected spectral index given a list of params (bands, constants).
    """

    out_params = {}
    index_name = spindex["short_name"]
    stac_bands = spindex["stac_bands"]
    index_bands = spindex["index_bands"]
    constants = spindex["constants"]

    for idx, index_band in enumerate(index_bands):
        out_params[index_band] = in_data.sel(band=stac_bands[idx])

    if constants:
        out_params.update(constants)

    return spyndex.computeIndex(
        index=[index_name],
        params=out_params
    )
