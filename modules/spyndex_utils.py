import spyndex
import panel as pn
from modules.constants import FLOATPANEL_CONFIGS

BAND_MAPPING = {
    "A": "coastal",
    "B": "blue",
    "G": "green",
    "R": "red",
    "RE1": "rededge1",
    "RE2": "rededge2",
    "RE3": "rededge3",
    "N": "nir",
    "N2": "nir08",
    "S1": "swir16",
    "S2": "swir22",
}

LANDSAT_BAND_MAPPING = {  # We can drop this dictionary
    "A": "coastal",
    "B": "blue",
    "G": "green",
    "R": "red",
    # "RE1": "rededge1",
    # "RE2": "rededge2",
    # "RE3": "rededge3",
    "N": "nir08",
    # "N2": "nir08", 
    "S1": "swir16",
    "S2": "swir22",
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
        BAND_MAPPING[b]
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


def get_oli_indices():
    """Create a list with all available landsat indices"""

    oli_indices = []
    for spindex in SPYNDEX_INDICES:
        application_domain = SPYNDEX_INDICES[spindex].application_domain
        platforms = SPYNDEX_INDICES[spindex].platforms
        if "Landsat-OLI" in platforms and application_domain != "kernel":
            oli_indices.append(SPYNDEX_INDICES[spindex].short_name)
    return oli_indices


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
        "formula": SPYNDEX_INDICES[spindex].formula,
        "reference": SPYNDEX_INDICES[spindex].reference,
        "contributor": SPYNDEX_INDICES[spindex].contributor,
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

    return spyndex.computeIndex(index=[index_name], params=out_params)


def get_index_metadata():
    spindex = pn.state.cache["index"]["meta"]
    short_name = spindex["short_name"]
    long_name = spindex["long_name"]
    bands = ", ".join(spindex["stac_bands"]).upper()
    # constants = spindex["constants"]
    contributor = spindex["contributor"]
    formula = spindex["formula"]  # TODO: Formula in latex
    reference = spindex["reference"]

    markdown = f"""

    **Long name**  
    {long_name}

    **Bands**  
    {bands}

    **Formula**  
    {formula}

    **Contributors**  
    {contributor}

    **Reference**  
    {reference}

    """

    spyndex_pane = pn.layout.FloatPanel(
        pn.pane.Markdown(markdown),
        name=f"{short_name}",
        contained=False,
        position="center",
        margin=20,
        config=FLOATPANEL_CONFIGS,
    )

    return spyndex_pane
