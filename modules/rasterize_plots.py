import json
import pystac
from odc.stac import stac_load
import panel as pn
import holoviews as hv
import hvplot.xarray  # noqa
from urllib.request import urlopen
import numpy as np
from skimage import exposure
from holoviews.operation.datashader import rasterize
import spyndex


def s2_image_to_uint8(in_data):
    """
    A function that converts image DN to Reflectance (0, 1) and
    then rescale to uint8 (0-255).
    https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l1c/
    """

    # Convert to reflectance and uint8 (range: 0-255)
    quant_value = 1e4
    out_data = (in_data / quant_value * 255).astype("uint8")
    out_data = np.clip(out_data, 0, 255)

    return out_data


def s2_contrast_stretch(in_data):
    """
    Image enhancement: Contrast stretching.
    """

    p2, p98 = np.percentile(in_data, (2.5, 97.5))
    out_data = exposure.rescale_intensity(in_data, in_range=(p2, p98))
    print(f"scaling to range {p2} : {p98}")

    # out_data = exposure.rescale_intensity(in_data, in_range=(0, 75))

    return out_data

def s2_hv_plot(items, type="RGB"):
    TILES = hv.element.tiles.OSM()

    response = urlopen(
        "https://raw.githubusercontent.com/lalligagger/satgpt-app/main/tmp/items.json"
    )
    # payload = json.loads(response.read())
    # query = payload["features"]
    # items = pystac.ItemCollection(query)

    sel_item = list(items)[0]

    s2_data = stac_load(
        [sel_item],
        bands=["red", "green", "blue", "nir"],
        resolution=50,
        chunks={"time": 1, "x": 2048, "y": 2048},
        crs="EPSG:3857",
    )

    out_data = s2_data.isel(time=0).to_array(dim="band")

    if type == 'RGB':
        # RGB data
        rgb_data = out_data.sel(band=["red", "green", "blue"])

        # Convert the image to uint8
        rgb_data = s2_image_to_uint8(rgb_data)

        # Contrast stretching
        # rgb_data = s2_contrast_stretch(rgb_data)

        rgb_plot = rgb_data.hvplot.rgb(
                x="x",
                y="y",
                # expand=False,
                # rasterize=True,
                # dynspread=True,
                bands='band',
                frame_height=500,
                frame_width=500,
                xaxis=None,
                yaxis=None
                )  # .redim.nodata(value=0)

        
        # This is working with swipe and hvplot
        rgb_plot = TILES * rasterize(rgb_plot, expand=False)
        return(rgb_plot)

    if type=='IDX':
        # Select Red/Nir bands
        spectral_index = out_data.sel(band=["red", "nir"])

        # Image DN to Reflectance (0, 1) and clip between 0, 1
        spectral_index = spectral_index / 1e4
        spectral_index = np.clip(spectral_index, 0.0, 1.0)

        # Get index parameters for spyndex
        plot_data = spyndex.computeIndex(
            index=["NDVI"],
            params={"N": spectral_index.sel(band="nir"),
                    "R": spectral_index.sel(band="red")},
        )

        # Plot the computed spectral index
        index_plot = plot_data.hvplot.image(
                x="x",
                y="y",
                # expand=False,
                # rasterize=True,
                # dynspread=True,
                colorbar=False,
                cnorm="eq_hist",
                frame_width=500,
                frame_height=500,
                xaxis=None,
                yaxis=None
                )

        # This is working with swipe and hvplot
        index_plot = TILES * rasterize(index_plot, expand=False)
        return index_plot