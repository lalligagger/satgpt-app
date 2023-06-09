import numpy as np
from skimage import exposure


def s2_dn_to_reflectance(in_data):
    """
    A function that converts image DN to Reflectance (0, 1)
    https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l1c/
    """

    quant_value = 1e4
    in_data.values = in_data / quant_value
    in_data.values = in_data.clip(0.0, 1.0)

    return in_data


def s2_image_to_uint8(in_data):
    """
    A function that converts image DN to Reflectance (0, 1) and
    then rescale to uint8 (0-255).
    https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l1c/
    """

    # Convert to reflectance and uint8 (range: 0-255)
    # quant_value = 1e4
    out_data = (in_data / in_data.max() * 255).astype("uint8")
    out_data = out_data.clip(0, 255)

    return out_data


def s2_contrast_stretch(in_data, clip_range=(2.5, 97.5)):
    """
    Image enhancement: Contrast stretching.
    """

    pmin, pmax = np.percentile(in_data, clip_range)
    in_data.values = exposure.rescale_intensity(in_data, in_range=(pmin, pmax))
    print(f"scaling to range {pmin} : {pmax}")

    return in_data


# Scene classification classes: https://usermanual.readthedocs.io/en/stable/pages/ProductGuide.html
def mask_clouds(to_mask_data, scl_data, is_rgb=True):
    """
    Clouds masking for RGB/single band images
    """

    to_mask_values = to_mask_data.values
    scl_values = scl_data.values

    if is_rgb:
        to_mask_data.values = np.where((scl_values == 8) | (scl_values == 9), False, to_mask_values)
    else:
        to_mask_data.values = np.where((scl_values == 8) | (scl_values == 9), np.nan, to_mask_values)[0, :, :]
    return to_mask_data

# Mask the clouds (Landsat)
# if mask_cl:
    # cl_data = rgb_data.sel(band=["scl"])

    # qa_data = rgb_data.sel(band=["qa_pixel"])
    # # Make a bitmask---when we bitwise-and it with the data, it leaves just the 4 bits we care about
    # mask_bitfields = [1, 2, 3, 4]  # dilated cloud, cirrus, cloud, cloud shadow
    # bitmask = 0
    # for field in mask_bitfields:
    #     bitmask |= 1 << field
    # cl_data = qa_data & bitmask

    # to_mask_data = mask_clouds(rgb_data, cl_data)

def landsat_dn_to_reflectance(in_data):
    """
    A function that converts image DN to Reflectance (0, 1)
    https://www.usgs.gov/faqs/how-do-i-use-a-scale-factor-landsat-level-2-science-products
    """

    in_data.values = (in_data * 0.0000275) - 0.2
    in_data.values = in_data.clip(0.0, 1.0)

    return in_data
