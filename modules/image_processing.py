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
    quant_value = 1e4
    out_data = (in_data / quant_value * 255).astype("uint8")
    out_data = out_data.clip(0, 255)

    return out_data
    
def s2_contrast_stretch(in_data):
    """
    Image enhancement: Contrast stretching.
    """

    p2, p98 = np.percentile(in_data, (2.5, 97.5))
    in_data.values = exposure.rescale_intensity(in_data, in_range=(p2, p98))
    print(f"scaling to range {p2} : {p98}")

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
