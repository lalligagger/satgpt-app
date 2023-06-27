from datetime import datetime
import holoviews as hv
import hvplot.xarray
from holoviews.operation.datashader import rasterize
from typing import Optional
import panel as pn
import param
from pystac_client.client import Client
from odc.stac import stac_load
import geopandas as gpd
import pystac
import rasterio
from langchain.tools import StructuredTool

from modules.spyndex_utils import get_oli_indices, get_s2_indices
from modules.image_plots import plot_true_color_image
from modules.image_processing import s2_contrast_stretch, s2_image_to_uint8, s2_dn_to_reflectance


class MapManager(param.Parameterized):
    gdf = param.DataFrame(
        # gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        # columns=['geometry']
    )

    ## STAC search
    bbox = param.String()  # (=seattle)
    # toi = # (now minus 1-2 months)
    stac_url = "https://earth-search.aws.element84.com/v1/"
    # collection = # (~satellites)
    items_dict = param.Dict({})

    ## Basic view
    media = None
    data = None
    product = param.Selector(['RGB'])
    mask_clouds = param.Boolean()
    mask = None
    # available_dates =
    # selected_date(s) =
    tile_url = param.String("https://tile.openstreetmap.org/{Z}/{X}/{Y}.png")
    # map_bounds =
    clip_range = param.Range((5,95))
    # cmap =  # (if not RGB)

    ## Split view
    # split = True
    # split_band = 'NDVI'

    ## Resampling
    # max_resolution =
    # resample_period =
    # zonal_url =  # point to e.g. geojson gist?

    def stac_search(
        self,
        bbox: str,
        dtime: str,
        collection: str = "sentinel-2-l2a",
        url: Optional[str] = "https://earth-search.aws.element84.com/v1/",
    ) -> str:
        """Perform a STAC search for Sentinel (sentinel-2-l2a) or Landsat (landsat-c2-l2) L2 images."""

        self.bbox = bbox  # TODO: change to tuple?
        self.collection = collection

        if collection == "sentinel-2-l2a":
            self.indices = get_s2_indices()
            #self.data = 
            #self.cloud_mask = 

        if collection == "landsat-c2-l2":
            self.indices = get_oli_indices()
            #self.data = 
            #self.cloud_mask = 

        [self.param.product.objects.append(i) for i in self.indices]

        client = Client.open(url)
        result = client.search(collections=[collection], bbox=bbox, datetime=dtime)
        items_dict = result.get_all_items_as_dict()

        self.items_dict = items_dict
        self.gdf = gpd.GeoDataFrame.from_features(items_dict)

        return {
            "count": result.matched(),
        }

    def view_footprints(
        self,
    ):
        """Load Sentinel & Landsat STAC item footprints to a map. Not for images. DO NOT use for Aqua/Terra/MODIS."""

        m = (
            self.gdf.loc[:, ["geometry"]]
            .set_crs("epsg:4326")
            .explore(tiles="CartoDB positron")
        )

        self.media = pn.pane.plot.Folium(m, height=400)
        return "Map is loaded to chat. Return nothing but a text confirmation to let the user know."

    def plot_metadata(
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
                    self.gdf.loc[:, ["date", field]].set_index("date").plot()
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
        """Display the image viewer for the current items (images). Currently only supports RGB views, no spectral indices."""

        rgb = self._viewer()
        self.media = pn.panel(rgb)

        return "Images are loaded to chat. Return nothing other than 'Done!' to the user."

    def _load_data(self, time, resolution):

        print(f"loading data for {str(time)}")
        items = pystac.ItemCollection(self.items_dict["features"])
        # sel_item = [it for it in items if it.datetime.date() == time]

        if self.collection=="sentinel-2-l2a":
            rgb_bands = ["red", "green", "blue", "scl"]
    
        if self.collection=="landsat-c2-l2":
            rgb_bands = ["red", "green", "blue", "qa_pixel"]

        raw_data = stac_load(
            items,
            bands=rgb_bands,
            resolution=resolution,
            chunks={'time': 1, 'x': 2048, 'y': 2048},
            crs="EPSG:3857"
            ).to_array(dim="band")

        # Convert to reflectance
        rgb_data = s2_dn_to_reflectance(raw_data)

        self.data=rgb_data

    def _viewer(self):
        items = pystac.ItemCollection(self.items_dict["features"])
        prod_select = self.param.product
        mask_select = self.param.mask_clouds
        clip_select = self.param.clip_range

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

        # initializes the data
        self._load_data(
            time=time_date[0],
            resolution=250,
        )

        s2_true_color_bind = pn.bind(
            plot_true_color_image,
            raw_data=self.data,
            time_event=time_select,
            mask_cl=mask_select,
            range=clip_select
        )

        return pn.Column(time_select, prod_select, clip_select, mask_select, s2_true_color_bind)


map_mgr = MapManager()

# define tools
# tools == a wrapped method above
search_tool = StructuredTool.from_function(map_mgr.stac_search)
gribs_tool = StructuredTool.from_function(map_mgr.set_basemap)
datacube_tool = StructuredTool.from_function(map_mgr.show_datacube)
plot_tool = StructuredTool.from_function(map_mgr.plot_metadata)
map_tool = StructuredTool.from_function(map_mgr.view_footprints)

tools = [
    search_tool,
    map_tool,
    # gribs_tool, # not working yet
    plot_tool,
    datacube_tool,
]
