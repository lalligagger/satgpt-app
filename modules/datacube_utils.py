import holoviews as hv
import panel as pn
from bokeh.models import HoverTool, WheelZoomTool
import hvplot.xarray  # noqa
from rasterio.session import AWSSession
from holoviews.operation.datashader import rasterize
from modules.image_processing import s2_contrast_stretch, s2_dn_to_reflectance, mask_clouds
from modules.spyndex_utils import compute_index, get_index_props, get_index_metadata
from modules.image_statistics import plot_spindex_kde

hv.extension("bokeh")

rasterize.expand = False

RGB_BANDS = ["red", "green", "blue"]
OSM_TILES = hv.element.tiles.OSM()


def plot_rgb(raw_data, time_event, clip_range):
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

    # TODO: Merge goes here if using
    rgb_data = raw_data.sel(time=time_event, method="nearest")
    rgb_data = rgb_data.sel(band=RGB_BANDS)

    # # Contrast stretching
    rgb_data = s2_contrast_stretch(rgb_data, clip_range)

    rgb_plot = rgb_data.hvplot.rgb(
        title="",
        x="x",
        y="y",
        rasterize=True,
        bands='band',
        frame_width=500,
        frame_height=500,
        xaxis=None,
        yaxis=None,
        hover=False
        ).opts(hooks=[hook])
    return OSM_TILES * rgb_plot


def get_index_pane(raw_data, time_event, metadata, cmap):
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
    index_props = metadata

    # Get the name of the selected spectral index
    index_name = index_props["short_name"]

    # Define a custom Hover tool for the image
    spindex_hover = HoverTool(
        tooltips=[(f"{index_name}", "@image")]
    )

    print(f"loading data & generating {index_name} plot for {str(time_event)}")

    print("loading delayed data")

    index_bands = index_props["stac_bands"]

    # TODO: Merge goes here if using
    sel_data = raw_data.sel(time=time_event, method="nearest")
    sel_data = sel_data.sel(band=index_bands)

    # Get index parameters for spyndex
    # TODO: Could move to _load_data()/ .data if fast enough over whole daterange?
    # Good for e.g. saving off a datacube with indices after viewing.
    index_data = compute_index(sel_data, index_props)

    # Plot the computed spectral index
    index_plot = index_data.hvplot.image(
        title="",
        x="x",
        y="y",
        rasterize=True,
        colorbar=False,
        cmap=cmap,
        cnorm="eq_hist",
        frame_width=500,
        frame_height=500,
        xaxis=None,
        yaxis=None,
        tools=[spindex_hover],
        ).opts(hooks=[hook])

    lyr_plot = OSM_TILES * index_plot.redim.nodata(value=0)

    meta_pane = get_index_metadata(index_props)

    kde_plot = plot_spindex_kde(index_name, index_data)

    index_pane = pn.Tabs(("Map", lyr_plot), ("Density plot", kde_plot), ("Metadata", meta_pane))

    return index_pane
