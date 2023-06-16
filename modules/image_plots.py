import datetime
import holoviews as hv
import numpy as np
import panel as pn
from bokeh.models import HoverTool, WheelZoomTool
from modules.image_processing import s2_contrast_stretch, s2_image_to_uint8
from modules.image_statistics import enable_hist_refresh_bt
import spyndex
from odc.stac import stac_load
import xarray as xr
import rasterio as rio
from rioxarray.merge import merge_arrays
from rasterio.session import AWSSession

from modules.spyndex_utils import compute_index, get_index_props

hv.extension("bokeh")


def normalize_bounds(in_data):
    y0 = in_data["y"].min()
    y1 = in_data["y"].max()
    dy = y1 - y0
    x0 = in_data["x"].min()
    x1 = in_data["x"].max()
    dx = x1 - x0
    return int(dy/dx)


def plot_true_color_image(items, time, resolution):
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

    # TODO: add time downselection

    # Get the selected image
    sel_item = [it for it in items if it.datetime.date() == time]

    # aws_session = AWSSession(requester_pays=True)
    # with rio.Env(aws_session):

    print("loading delayed data")
    s2_data = stac_load(
        sel_item,
        bands=["red", "green", "blue"],  # , "nir", "nir08", "swir16", "swir22"],
        resolution=resolution,
        chunks={'time': 1, 'x': 2048, 'y': 2048},
        # crs='EPSG:3857',  # We need the data in EPSG:3857
        ).to_stacked_array(new_dim='band', sample_dims=('time', 'x', 'y'))

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

    # normalize bounds
    dxdy = normalize_bounds(out_data)

    # Image bands to be plotted
    b0 = out_data.sel(band=("red",)).data
    b1 = out_data.sel(band=("green",)).data
    b2 = out_data.sel(band=("blue",)).data

    # Plot the RGB image
    plot_data = dict(
        x=out_data["x"],
        y=out_data["y"],
        r=b0,
        g=b1,
        b=b2,
    )

    rgb_plot = hv.RGB(
        data=plot_data,
        kdims=["x", "y"],
        # bounds=(x0, y0, x1, y1),
        vdims=list("rgb"),
    ).opts(
        xlabel="",
        ylabel="",
        hooks=[hook],
        frame_width=500,
        frame_height=500 * dxdy,
    )
    print("finished plotting")
    return rgb_plot  # hv.element.tiles.OSM()


# def assign_spindex_to_cache(s2_spindex_name, spindex):
#     """
#     This function assign the spectral index array to the panel state cache
#     so that it can be used for the histogram floatpanel widget.
#     """
#     pn.state.cache["spindex"] = {"name": s2_spindex_name, "np_array": spindex}


def plot_s2_spindex(items, time, s2_spindex, resolution, cmap):
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

    # Get index information
    s2_index = get_index_props(s2_spindex)

    # Get the name of the selected spectral index
    s2_spindex_name = s2_index["short_name"]

    print(f"loading data & generating {s2_spindex_name} plot for {str(time)}")

    # Get the selected image
    sel_item = [it for it in items if it.datetime.date() == time]

    # aws_session = AWSSession(requester_pays=True)
    # with rio.Env(aws_session):

    print("loading delayed data")

    s2_data = stac_load(
        sel_item,
        bands=[b[0] for b in s2_index["stac_bands"]],
        resolution=resolution,
        chunks={'time': 1, 'x': 2048, 'y': 2048},
        # crs="EPSG:3857"
        ).to_stacked_array(new_dim='band', sample_dims=('time', 'x', 'y'))

    # Image DN to Reflectance (0, 1) and clip between 0, 1
    s2_data = s2_data / 1e4
    s2_data = s2_data.clip(0.0, 1.0)

    # Get the selected image and band combination
    out_data = s2_data.sel(time=slice(time, time + datetime.timedelta(days=1)))  # .median('time')

    # spatial merge
    out_data = merge_arrays(
        dataarrays=[out_data.sel(time=d).transpose('band', 'y', 'x') for d in out_data.coords['time'].values]
        )

    # Define a custom Hover tool for the image
    spindex_hover = HoverTool(
        tooltips=[(f"{s2_spindex_name}", "@image")]
    )

    # Get index parameters for spyndex
    plot_data = compute_index(out_data, s2_index)

    # Mask nodata from visualization?
    plot_data = xr.where(plot_data == 0, 1, plot_data.data)

    # Assign this array to the pn.cache
    # assign_spindex_to_cache(s2_spindex_name, plot_data_mask)

    # Enable the refresh button of the histogram plot
    # enable_hist_refresh_bt()

    # normalize bounds
    dxdy = normalize_bounds(out_data)

    # Plot the computed spectral index
    the_plot = hv.Image((plot_data["x"], plot_data["y"], plot_data)).opts(
        xlabel="",
        ylabel="",
        cmap=cmap,
        cnorm="eq_hist",  # Temporary hack: some indices (e.g. SAVI2) have values outside the index range (-1, +1)
        hooks=[hook],
        tools=[spindex_hover],
        frame_width=500,
        frame_height=500 * dxdy,
    )
    print("finished plotting")
    return the_plot
