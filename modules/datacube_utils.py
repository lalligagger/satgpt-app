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


def plot_rgb(raw_data, time_event, clip_range, mask_cl):
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

    rgb_data = raw_data.sel(time=time_event, method="nearest")
    rgb_data = rgb_data.sel(band=RGB_BANDS)

    # Convert to reflectance
    rgb_data = s2_dn_to_reflectance(rgb_data)

    # # Contrast stretching
    rgb_data = s2_contrast_stretch(rgb_data, clip_range)

    # Mask the clouds
    # if mask_cl:
    #     cl_data = rgb_data.sel(band=["scl"])

    # # TODO: Clean up try/ (bare) except
    # if mask_cl:
    #     try:
    #         cl_data = rgb_data.sel(band=["scl"])
    #     except:
    #         qa_data = rgb_data.sel(band=["qa_pixel"])
    #         # Make a bitmask---when we bitwise-and it with the data, it leaves just the 4 bits we care about
    #         mask_bitfields = [1, 2, 3, 4]  # dilated cloud, cirrus, cloud, cloud shadow
    #         bitmask = 0
    #         for field in mask_bitfields:
    #             bitmask |= 1 << field
    #         cl_data = qa_data & bitmask

    #     rgb_data = mask_clouds(rgb_data, cl_data)

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


def get_index_pane(raw_data, time_event, collection, composite, mask_cl, cmap):
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
    index_props = get_index_props(composite, collection)

    # Get the name of the selected spectral index
    index_name = index_props["short_name"]

    # Define a custom Hover tool for the image
    spindex_hover = HoverTool(
        tooltips=[(f"{index_name}", "@image")]
    )

    print(f"loading data & generating {index_name} plot for {str(time_event)}")

    print("loading delayed data")

    index_bands = index_props["stac_bands"]

    sel_data = raw_data.sel(time=time_event, method="nearest")
    sel_data = sel_data.sel(band=index_bands)

    # Image DN to Reflectance
    sel_data = s2_dn_to_reflectance(sel_data)

    # Get index parameters for spyndex
    index_data = compute_index(sel_data, index_props)

    # Mask the clouds
    # if mask_cl:
    #     scl_data = s2_data.sel(band=["scl"])
    #     index_data = mask_clouds(index_data, scl_data, False)

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
