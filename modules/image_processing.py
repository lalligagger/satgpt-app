import numpy as np
from skimage import exposure


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

    p2, p98 = np.percentile(in_data.ravel(), (2.5, 97.5))
    out_data = exposure.rescale_intensity(in_data, in_range=(p2, p98))
    print(f"scaling to range {p2} : {p98}")

    # out_data = exposure.rescale_intensity(in_data, in_range=(0, 75))

    return out_data
