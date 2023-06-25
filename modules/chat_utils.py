from typing import Optional
import panel as pn
import param
from pystac_client.client import Client
import geopandas as gpd
from shapely.geometry import shape, Polygon
from odc.stac import stac_load
import pystac
import rasterio
from skimage import exposure

from langchain.tools import StructuredTool

import holoviews as hv
import hvplot.xarray

from modules.image_processing import s2_contrast_stretch, s2_image_to_uint8

## alt mapping
# import folium
# from folium.raster_layers import TileLayer

# from bokeh.models import WMTSTileSource
# import geoviews as gv

import numpy as np
import pandas as pd
from datetime import datetime
from holoviews.operation.datashader import rasterize


class MapManager(param.Parameterized):
    ## TODO: use another gdf for zonal stats - items get stored here for plotting
    gdf = param.DataFrame(
        # gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        # columns=['geometry']
    )

    ## STAC search
    bbox = param.String()  # (=seattle)
    # toi = # (now minus 1-2 months)
    # url =
    # collection(s) = # (satellites)
    items_dict = param.Dict({})

    ## Basic view
    media = None
    # datacube =
    # band = 'RGB'
    # available_dates =
    # selected_date(s) =
    tile_url = param.String("https://tile.openstreetmap.org/{Z}/{X}/{Y}.png")
    # map_bounds =
    # mask_clouds =
    # clip_range =
    # cmap =  # (if not RGB)

    ## Split view
    # split = True
    # split_band = 'NDVI'

    ## Resampling
    # max_resolution =
    # resample_period =
    #

    def stac_search(
        self,
        bbox: str,
        dtime: str,
        url: Optional[str] = "https://earth-search.aws.element84.com/v1/",
        collections: Optional[list] = ["sentinel-2-l2a"],
    ) -> str:
        """Perform a STAC search for Sentinel (sentinel-2-l2a) or Landsat (landsat-c2-l2) L2 images."""

        self.bbox = bbox  # TODO: change to tuple?

        client = Client.open(url)
        result = client.search(collections=[collections], bbox=bbox, datetime=dtime)
        items_dict = result.get_all_items_as_dict()

        self.items_dict = items_dict
        self.gdf = gpd.GeoDataFrame.from_features(items_dict)

        return {
            "count": result.matched(),
        }

    # TODO: switch to holoviews? or ok for demo?
    def view_footprints(
        self,
    ):
        """Load Sentinel & Landsat STAC item footprints to a map. Not for images. DO NOT use for Aqua/Terra/MODIS."""

        m = (
            self.gdf.loc[:, ["geometry"]]
            .set_crs("epsg:4326")
            .explore(tiles="CartoDB positron")
        )  # TODO: could use basemap, have optional tooltips, etc.

        self.media = pn.pane.plot.Folium(m, height=400)
        return "Map is loaded to chat. Return nothing but a text confirmation to let the user know."

    def plot_item_metadata(
        self,
        field: str = "eo:cloud_cover",
    ):
        """Plot any field from the current STAC items, e.g. cloud cover. No images, just STAC metadata fields."""
        dates = [
            ds.split("T")[0] for ds in self.gdf.loc[:, ["datetime"]].values.flatten()
        ]
        dts = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
        self.gdf.loc[:, ["date"]] = dts

        self.media = pn.panel(
                    self.gdf.loc[:, ["date", "eo:cloud_cover"]].set_index("date").plot()
                )

        return "Plot is loaded to chat. Return nothing other than 'Plotted!' to the user."

    def set_basemap(
        self, datestring: str = "2023-06-09", source: Optional[str] = "Aqua"
    ):
        """
        Sets basemap with Modis (source = 'Aqua' or 'Terra') world coverage by date.
        This tool does NOT require a prior STAC search. Currently only supports RGB views, no spectral indices.
        """
        # Valid:
        # https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/wmts.cgi
        # ?Service=WMTS&Request=GetTile&Version=1.0.0&layer=MODIS_Terra_CorrectedReflectance_TrueColor&tilematrixset=250m
        # &TileMatrix=6&TileCol=36&TileRow=13&TIME=2012-07-09&style=default&Format=image%2Fjpeg

        tileMatrixSet = "GoogleMapsCompatible_Level9"
        layer = f"MODIS_{source}_CorrectedReflectance_TrueColor"
        base_url = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
        tile_path = f"{layer}/default/{datestring}/{tileMatrixSet}/" + "{Z}/{Y}/{X}.jpg"
        self.tile_url = base_url + tile_path
        return "Basemap is set. Return nothing but a text confirmation to let the user know."

    def show_datacube(self):
        """Display the datacube viewer for the current items (images). Currently only supports RGB views, no spectral indices."""

        rgb = self.create_rgb_viewer()
        self.media = pn.panel(rgb)

        return "Datacube is loaded to chat. Return nothing other than 'Done!' to the user."

    # TODO: replace with modules.image_plots. Maybe just handle per-band/per-time data loading here & then send to plot calls?
    def s2_hv_plot(
        self,
        items,
        time,
        type="RGB",
    ):
        TILES = hv.Tiles(self.tile_url)
        # TILES = gv.WMTS(WMTSTileSource(url=url)) # maybe?

        mask = [i.datetime.date() == time for i in items]
        items = [b for a, b in zip(mask, items) if a]
        bbox = tuple(map(float, self.bbox.split(",")))

        s2_data = stac_load(
            items,
            bbox=bbox,
            bands=["red", "green", "blue", "nir"],
            resolution=100,
            chunks={"time": 1, "x": 2048, "y": 2048},
            crs="EPSG:3857",
        )

        # TODO: add spatial merge back here (from image_plots?)
        out_data = s2_data.isel(time=0).to_array(dim="band")

        if type == "RGB":
            # RGB data
            rgb_data = out_data.sel(band=["red", "green", "blue"])

            # Convert the image to uint8
            rgb_data = s2_image_to_uint8(rgb_data)

            # Contrast stretching
            rgb_data = s2_contrast_stretch(rgb_data)

            rgb_plot = rgb_data.hvplot.rgb(
                x="x",
                y="y",
                bands="band",
                frame_height=500,
                frame_width=500,
                xaxis=None,
                yaxis=None,
            )  # .redim.nodata(value=0)

            # This is working with swipe and hvplot
            rgb_plot = TILES * rasterize(rgb_plot, expand=False)

            return rgb_plot

    def create_rgb_viewer(self):
        items = pystac.ItemCollection(self.items_dict["features"])

        # Time variable
        time_var = [i.datetime for i in items]
        time_date = [t.date() for t in time_var]

        time_select = pn.widgets.DatePicker(
            name="Date",
            value=time_date[0],
            start=time_date[-1],
            end=time_date[0],
            enabled_dates=time_date,
            description="Select the date for plotting.",
        )

        s2_true_color_bind = pn.bind(
            self.s2_hv_plot,
            items=items,
            time=time_select,
            # mask_clouds=clm_switch,
            # resolution=res_select
        )

        return pn.Column(time_select, s2_true_color_bind)


map_mgr = MapManager()

# define tools
# tools == a wrapped method above
search_tool = StructuredTool.from_function(map_mgr.stac_search)
gribs_tool = StructuredTool.from_function(map_mgr.set_basemap)
datacube_tool = StructuredTool.from_function(map_mgr.show_datacube)
plot_tool = StructuredTool.from_function(map_mgr.plot_item_metadata)
map_tool = StructuredTool.from_function(map_mgr.view_footprints)

tools = [
    search_tool,
    map_tool,
    # gribs_tool, # not working yet
    plot_tool,
    datacube_tool,
]
