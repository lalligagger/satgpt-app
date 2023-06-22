import holoviews as hv
import panel as pn
from bokeh.models import HoverTool, WheelZoomTool
from odc.stac import stac_load
import hvplot.xarray  # noqa
from rasterio.session import AWSSession
from holoviews.operation.datashader import rasterize
from modules.image_processing import s2_contrast_stretch, s2_dn_to_reflectance, mask_clouds
from modules.spyndex_utils import compute_index, get_index_props

hv.extension("bokeh")

rasterize.expand = False

OSM_TILES = hv.element.tiles.OSM()


def plot_true_color_image(items, time, resolution, mask_cl):
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
    sel_item = [it for it in items if it.datetime.date() == time]

    # aws_session = AWSSession(requester_pays=True)
    # with rio.Env(aws_session):

    print("loading delayed data")

    rgb_bands = ["red", "green", "blue"]

    s2_data = stac_load(
        sel_item,
        bands=rgb_bands + ["scl"],
        resolution=resolution,
        chunks={'time': 1, 'x': 2048, 'y': 2048},
        crs='EPSG:3857',
        ).isel(time=0).to_array(dim="band")

    # RGB data
    rgb_data = s2_data.sel(band=rgb_bands)

    # Convert to reflectance
    rgb_data = s2_dn_to_reflectance(rgb_data)

    # Contrast stretching
    rgb_data = s2_contrast_stretch(rgb_data)

    # Mask the clouds
    if mask_cl:
        scl_data = s2_data.sel(band=["scl"])
        rgb_data = mask_clouds(rgb_data, scl_data)

    rgb_plot = rgb_data.hvplot.rgb(
        title="",
        x="x",
        y="y",
        rasterize=True,
        bands='band',
        frame_height=500,
        frame_width=500,
        xaxis=None,
        yaxis=None,
        hover=False
        ).redim.nodata(z=0)  # nodata is displayed as black: https://github.com/holoviz/hvplot/issues/1091
    print("finished plotting")
    return OSM_TILES * rgb_plot


def plot_s2_spindex(items, time, s2_spindex, resolution, cmap, mask_cl):
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
    index_name = s2_index["short_name"]

    # Define a custom Hover tool for the image
    spindex_hover = HoverTool(
        tooltips=[(f"{index_name}", "@image")]
    )

    print(f"loading data & generating {index_name} plot for {str(time)}")

    # Get the selected image
    sel_item = [it for it in items if it.datetime.date() == time]

    # aws_session = AWSSession(requester_pays=True)
    # with rio.Env(aws_session):

    print("loading delayed data")

    index_bands = s2_index["stac_bands"]
    s2_data = stac_load(
        sel_item,
        bands=index_bands + ["scl"],
        resolution=resolution,
        chunks={'time': 1, 'x': 2048, 'y': 2048},
        crs="EPSG:3857"
        ).isel(time=0).to_array(dim="band")

    out_data = s2_data.sel(band=index_bands)

    # Image DN to Reflectance
    out_data = s2_dn_to_reflectance(out_data)

    # Get index parameters for spyndex
    index_data = compute_index(out_data, s2_index)

    # Mask the clouds
    if mask_cl:
        scl_data = s2_data.sel(band=["scl"])
        index_data = mask_clouds(index_data, scl_data, False)

    # Save the index to the cache?
    pn.state.cache["index"] = {
        "name": index_name,
        "data": index_data,
        "meta": s2_index
        }

    # Plot the computed spectral index
    index_plot = index_data.hvplot.image(
        title="",
        x="x",
        y="y",
        rasterize=True,
        colorbar=False,
        cmap=cmap,
        cnorm="eq_hist",  # Temporary hack: some indices (e.g. SAVI2) have values outside the index range (-1, +1)
        frame_width=500,
        frame_height=500,
        xaxis=None,
        yaxis=None,
        tools=[spindex_hover],
        ).redim.nodata(value=0)

    print("finished plotting")
    return OSM_TILES * index_plot
