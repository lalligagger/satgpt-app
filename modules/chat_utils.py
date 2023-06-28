from datetime import datetime
import holoviews as hv
import hvplot.xarray
from typing import Optional
import panel as pn
import param
from pystac_client.client import Client
from odc.stac import stac_load
import geopandas as gpd
import pystac
from langchain.tools import StructuredTool
from modules.spyndex_utils import BAND_MAPPING
from modules.spyndex_utils import get_indices
from modules.image_plots import plot_rgb, plot_index
from modules.cmap_utils import get_cmap_options, get_cmap_plot


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
    mask_clouds = param.Boolean()
    mask_clouds.precedence = -1  # Hide for now
    mask = None
    # available_dates =
    # selected_date(s) =
    tile_url = param.String("https://tile.openstreetmap.org/{Z}/{X}/{Y}.png")
    # map_bounds =
    # clip_range = param.Range((5,95))
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

        bands = list(BAND_MAPPING[self.collection].values())

        raw_data = stac_load(
            items,
            bbox=tuple(map(float, self.bbox.split(','))),
            bands=bands,
            resolution=resolution,
            chunks={'time': 1, 'x': 2048, 'y': 2048},
            crs="EPSG:3857"
            ).to_array(dim="band")

        self.data = raw_data

    def _viewer(self):
        def switch_layer(raw_data, collection, composite, time_event, clip_range, mask_cl, cmap):
            """
            A function that plots the selected composite.
            """
            if composite == "RGB":
                lyr_plot = plot_rgb(raw_data, time_event, clip_range, mask_cl)
                cmap_select.disabled = True
                cmap_view.disabled = True
                range_select.disabled = False
            else:
                lyr_plot = plot_index(raw_data, time_event, collection, composite, mask_cl, cmap)
                cmap_select.disabled = False
                cmap_view.disabled = False
                range_select.disabled = True
            print("finished plotting")
            return lyr_plot

        items = pystac.ItemCollection(self.items_dict["features"])
        mask_select = self.param.mask_clouds
        # clip_select = self.param.clip_range

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

        # TODO: Planning to add other composites
        composites_indices = {"Composites": ["RGB"], "Indices": get_indices(self.collection)}
        composite_select = pn.widgets.Select(name="Composites/Indices", groups=composites_indices, value="RGB")

        range_select = pn.widgets.EditableRangeSlider(
            name='Image enhancement',
            start=1, end=100,
            value=(2.5, 97.5),
            step=0.5
            )

        # Colormap select
        # TODO: Add an option to revert the colormap
        cmap_select = pn.widgets.Select(name="Colormap", groups=get_cmap_options(), value="RdYlGn")
        cmap_view = pn.bind(get_cmap_plot, cmap=cmap_select)
        cmap_select.disabled = True
        cmap_view.disabled = True

        # initializes the data
        self._load_data(
            time=time_date[0],
            resolution=250,
        )

        s2_true_color_bind = pn.bind(
            switch_layer,
            raw_data=self.data,
            collection=self.collection,
            composite=composite_select,
            time_event=time_select,
            clip_range=range_select,
            mask_cl=mask_select,
            cmap=cmap_select,
        )

        wbox = pn.WidgetBox(
            '',
            time_select,
            composite_select,
            range_select,
            mask_select,
            cmap_select,
            cmap_view,
            )

        return pn.Row(wbox, s2_true_color_bind)


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
