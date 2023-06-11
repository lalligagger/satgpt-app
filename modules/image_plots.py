import datetime
import holoviews as hv
import numpy as np
import panel as pn
from bokeh.models import CustomJSHover, HoverTool, WheelZoomTool
from modules.image_processing import s2_contrast_stretch, s2_image_to_uint8
from modules.image_statistics import enable_hist_refresh_bt
import spyndex
from odc.stac import stac_load
import xarray as xr
import rasterio as rio
from rioxarray.merge import merge_arrays
from rasterio.session import AWSSession

from modules.constants import S2_SPINDICES

# This function hide the tooltip when the pixel value is NaN
HIDE_NAN_HOVTOOL = CustomJSHover(
    code="""
    var value;
    var tooltips = document.getElementsByClassName("bk-tooltip");
    if (isNaN(value)) {
        tooltips[0].hidden=true;
    } else {
        tooltips[0].hidden=false;
    }
        return value;
    """
)

# tiles = hv.Tiles('https://tile.openstreetmap.org/{Z}/{X}/{Y}.png', name="OSM")#.opts(width=600, height=550)

def plot_true_color_image(items, time, mask_clouds, resolution):
    """
    A function that plots the True Color band combination.
    """

    def hook(plot, element):
        """
        Custom hook for disabling x/y tick lines/labels
        """
        plot.state.xaxis.major_tick_line_color = None
        plot.state.xaxis.minor_tick_line_color = None
        plot.state.xaxis.major_label_text_font_size = "0pt"
        plot.state.yaxis.major_tick_line_color = None
        plot.state.yaxis.minor_tick_line_color = None
        plot.state.yaxis.major_label_text_font_size = "0pt"

        # Disable zoom on axis
        for tool in plot.state.toolbar.tools:
            if isinstance(tool, WheelZoomTool):
                tool.zoom_on_axis = False
                break


    print(f"loading data & generating RGB plot for {str(time)}")
    #TODO: add time downselection

    mask = [i.datetime.date() == time for i in items]
    items = [b for a, b in zip(mask, items) if a]

    # aws_session = AWSSession(requester_pays=True)
    # with rio.Env(aws_session):
    print("loading delayed data")
    s2_data = stac_load(
        items,
        bands=["red", "green", "blue"],#, "nir", "nir08", "swir16", "swir22"],
        resolution=resolution,
        chunks={'time':1, 'x': 2048, 'y': 2048},
        # crs='EPSG:4326',
        ).to_stacked_array(new_dim='band', sample_dims=('time', 'x', 'y'))
    
    s2_data = s2_data.astype("int16")
    # Get the selected image and band combination
    # TODO: add stac_load here
    out_data = s2_data.sel(band=[("red",), ("green",), ("blue",)], time=slice(time, time + datetime.timedelta(days=1)))#.median('time')

    # spatial merge
    out_data = merge_arrays(
        dataarrays=[out_data.sel(time=d).transpose('band', 'y', 'x') for d in out_data.coords['time'].values]
        )

    # Convert the image to uint8
    out_data.data = s2_image_to_uint8(out_data.data)

    # Contrast stretching
    out_data.data = s2_contrast_stretch(out_data.data)

    # Check whether to apply a mask to the image
    if mask_clouds:
        # Assign a value of 255 to the pixels representing clouds
        out_data = out_data.where(out_data.mask == 0, 255)

    # Image bands to be plotted
    b0 = out_data.sel(band=("red",)).data
    b1 = out_data.sel(band=("green",)).data
    b2 = out_data.sel(band=("blue",)).data

    # Create masked arrays
    b0_mask = np.ma.masked_where(b0 == 255, b0)
    b1_mask = np.ma.masked_where(b1 == 255, b1)
    b2_mask = np.ma.masked_where(b2 == 255, b2)

    # Plot the RGB image
    plot_data = dict(
        x=out_data["x"],
        y=out_data["y"],
        r=b0_mask,
        g=b1_mask,
        b=b2_mask,
    )

    # normalize bounds
    y0 = out_data["y"].min()
    y1 = out_data["y"].max()
    dy = y1 - y0
    x0 = out_data["x"].min()
    x1 = out_data["x"].max()
    dx = x1 - x0

    the_plot = hv.RGB(
        data=plot_data,
        kdims=["x", "y"],
        # bounds=(x0,y0,x1,y1),
        vdims=list("rgb"),
    ).opts(
        xlabel="",
        ylabel="",
        hooks=[hook],
        frame_width=500,
        frame_height=int(500*dy/dx),
    )
    print("finished plotting")
    return the_plot#*tiles

def assign_spindex_to_cache(s2_spindex_name, spindex):
    """
    This function assign the spectral index array to the panel state cache
    so that it can be used for the histogram floatpanel widget.
    """
    pn.state.cache["spindex"] = {"name": s2_spindex_name, "np_array": spindex}


# TODO: generalize with spyndex(!)
def plot_s2_spindex(items, time, s2_spindex, mask_clouds, resolution):
    """
    A function that plots the selected Sentinel-2 spectral index.
    """

    def hook(plot, element):
        """
        Custom hook for disabling x/y tick lines/labels
        """
        plot.state.xaxis.major_tick_line_color = None
        plot.state.xaxis.minor_tick_line_color = None
        plot.state.xaxis.major_label_text_font_size = "0pt"
        plot.state.yaxis.major_tick_line_color = None
        plot.state.yaxis.minor_tick_line_color = None
        plot.state.yaxis.major_label_text_font_size = "0pt"

        # Disable zoom on axis
        for tool in plot.state.toolbar.tools:
            if isinstance(tool, WheelZoomTool):
                tool.zoom_on_axis = False
                break

    # TODO: Clean up spyndex use w constants module.
    spyndex_band_mapping = {
        "N": ("nir",),
        "N2": ("nir08",),
        "R": ("red",),
        "G": ("green",),
        "S1": ("swir16",),
        "S2": ("swir22",),
        # "L": 0.5
    }
    # Get the name of the selected spectral index
    s2_spindex = S2_SPINDICES[s2_spindex]
    s2_spindex_name = s2_spindex["name"]

    load_bands = [spyndex_band_mapping[b] for b in spyndex.indices[s2_spindex['name']].bands]
    print(f"loading data & generating {s2_spindex['name']} plot for {str(time)}")

    # Get the selected image and band combination
    mask = [i.datetime.date() == time for i in items]
    items = [b for a, b in zip(mask, items) if a]

    # aws_session = AWSSession(requester_pays=True)
    # with rio.Env(aws_session):
    print("loading delayed data")
    s2_data = stac_load(
        items,
        bands=[b[0] for b in load_bands],
        resolution=resolution,
        chunks={'time':1, 'x': 2048, 'y': 2048},
        # crs='EPSG:4326',
        ).to_stacked_array(new_dim='band', sample_dims=('time', 'x', 'y'))
    s2_data = s2_data.astype("int16")

    # Get the selected image and band combination
    out_data = s2_data.sel(time=slice(time, time + datetime.timedelta(days=1)))#.median('time')

    # spatial merge
    out_data = merge_arrays(
        dataarrays=[out_data.sel(time=d).transpose('band', 'y', 'x') for d in out_data.coords['time'].values]
        )

    # Define a custom Hover tool for the image
    spindex_hover = HoverTool(
        tooltips=[(f"{s2_spindex_name}", "@image")],
        formatters={"@image": HIDE_NAN_HOVTOOL},
    )

    for b in spyndex_band_mapping:
        band = spyndex_band_mapping[b]
        if band in load_bands:
            spyndex_band_mapping[b] = out_data.sel(band=band)

    plot_data = spyndex.computeIndex(
        index = [s2_spindex_name],
        params = spyndex_band_mapping
    )

    # Check whether to apply a mask to the image
    if mask_clouds:
        # Assign a value of 255 to the pixels representing clouds
        plot_data[out_data.mask == 1] = 255

    # Create a masked array
    plot_data_mask = np.ma.masked_where(plot_data == 255, plot_data)

    # Assign this array to the pn.cache
    assign_spindex_to_cache(s2_spindex_name, plot_data_mask)

    # Enable the refresh button of the histogram plot
    enable_hist_refresh_bt()

    # normalize bounds
    y0 = out_data["y"].min()
    y1 = out_data["y"].max()
    dy = y1 - y0
    x0 = out_data["x"].min()
    x1 = out_data["x"].max()
    dx = x1 - x0
    
    # Plot the computed spectral index
    the_plot = hv.Image((out_data["x"], out_data["y"], plot_data_mask)).opts(
        xlabel="",
        ylabel="",
        cmap=s2_spindex["cmap"],
        hooks=[hook],
        tools=[spindex_hover],
        frame_width=500,
        frame_height=int(500*dy/dx),
    )
    print("finished plotting")
    return the_plot#*tiles
