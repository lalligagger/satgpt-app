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
    out_data = out_data.clip(0, 255)

    return out_data


def s2_contrast_stretch(in_data):
    """
    Image enhancement: Contrast stretching.
    """

    p2, p98 = np.percentile(in_data.values.ravel(), (2.5, 97.5))
    print(f"scaling to range {p2} : {p98}")
    in_data.values = exposure.rescale_intensity(in_data, in_range=(p2, p98))

    return in_data

def s2_hv_plot(items, time, bbox=None, type="RGB"):
    TILES = hv.element.tiles.OSM()

    response = urlopen(
        "https://raw.githubusercontent.com/lalligagger/satgpt-app/main/tmp/items.json"
    )

    mask = [i.datetime.date() == time for i in items]
    items = [b for a, b in zip(mask, items) if a]

    s2_data = stac_load(
        # [sel_item],
        items,
        bbox=bbox,
        # lon = (bbox[0], bbox[2]),
        # lat = (bbox[1], bbox[3]),
        bands=["red", "green", "blue", "nir"],
        resolution=100,
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
        rgb_data = s2_contrast_stretch(rgb_data)

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


def create_rgb_viewer(items, bbox=None):
    # Time variable
    time_var = [i.datetime for i in items]
    time_date = [t.date() for t in time_var]

    time_select = pn.widgets.DatePicker(
        name="Date",
        value=time_date[0], 
        start=time_date[-1], 
        end=time_date[0], 
        enabled_dates=time_date,
        description="Select the date for plotting."
        )

    s2_true_color_bind = pn.bind(
        s2_hv_plot,
        items=items,
        bbox=bbox,
        time=time_select,
        # mask_clouds=clm_switch,
        # resolution=res_select
    )

    return pn.Column(time_select, s2_true_color_bind)