import os
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
from modules.spyndex_utils import BAND_MAPPING, get_indices, get_index_props
from modules.datacube_utils import plot_rgb, get_index_pane
from modules.cmap_utils import get_cmap_options, get_cmap_plot
from modules.image_processing import s2_dn_to_reflectance, landsat_dn_to_reflectance

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

    ## Index view
    # split = True
    index = 'NDVI' # TODO: could make this a param Selector

    ## Resampling
    # max_resolution =
    # resample_period =
    # zonal_url =  # point to e.g. geojson gist?

    def stac_search(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        dtime: str,
        collection: str = "sentinel-2-l2a",
        url: Optional[str] = "https://earth-search.aws.element84.com/v1/",
    ) -> str:
        """Perform a STAC search for Sentinel (sentinel-2-l2a) or Landsat (landsat-c2-l2) L2 images.
        The area of interest is a bounding box in WGS84 degrees: west (min longitude), south (min latitude),
        east (max longitude), north (max latitude). dtime is an ISO date range like 2024-07-01/2024-07-31."""

        bbox = [float(west), float(south), float(east), float(north)]
        self.bbox = ",".join(str(v) for v in bbox)  # _load_data splits this string
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

        if self.collection == "landsat-c2-l2" and os.environ.get("AWS_REQUEST_PAYER") != "requester":
            # Landsat Collection 2 lives in the requester-pays usgs-landsat bucket; without AWS credentials and
            # AWS_REQUEST_PAYER=requester every read is refused. Sentinel-2 (sentinel-cogs) is public.
            return (
                "Landsat imagery can't be loaded on this server: the usgs-landsat bucket is requester-pays and "
                "AWS_REQUEST_PAYER is not set. Tell the user to search Sentinel-2 (sentinel-2-l2a) instead, "
                "or to restart the server with AWS credentials and AWS_REQUEST_PAYER=requester."
            )

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

        if self.collection == 'sentinel-2-l2a':
            data = s2_dn_to_reflectance(raw_data)
            # if self.mask_clouds:
                # mask the clouds

        if self.collection == 'landsat-c2-l2':
            data = landsat_dn_to_reflectance(raw_data)
            # if self.mask_clouds:
                # mask the clouds

        else:
            data = raw_data

        self.data = data

    def _viewer(self):
        def switch_layer(raw_data, collection, comp_index, time_event, clip_range, mask_cl, cmap):
            """
            # TODO: Simplify, Add more composites
            A function that plots the selected composite or index.
            """

            if comp_index == "RGB":
                map_pane = plot_rgb(raw_data, time_event, clip_range)
                cmap_select.disabled = True
                cmap_view.disabled = True
                range_select.disabled = False
            else:
                self.index = comp_index.strip('\"')
                metadata = get_index_props(self.index, collection)

                map_pane = get_index_pane(raw_data, time_event, clip_range, metadata, cmap)
                cmap_select.disabled = False
                cmap_view.disabled = False
                range_select.disabled = True

            print("finished plotting")

            # load metadata

            return map_pane

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

        # TODO: Planning to add more composites
        comp_index = {"Composites": ["RGB"], "Indices": get_indices(self.collection)}
        comp_index_select = pn.widgets.Select(name="Composites/Indices", groups=comp_index, value="RGB")

        # TODO: Attach to map_mgr.clip_range, could update when switching to index based on min/ max values
        range_select = pn.widgets.EditableRangeSlider(
            name='Clip percentiles (%)',
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
            resolution=None,
        )

        viewer_bind = pn.bind(
            switch_layer,
            raw_data=self.data,
            collection=self.collection, # TODO: remove from plot func, eventually
            comp_index=comp_index_select,
            time_event=time_select,
            clip_range=range_select,
            mask_cl=mask_select,
            cmap=cmap_select,
        )

        wbox = pn.WidgetBox(
            '',
            time_select,
            comp_index_select,
            range_select,
            mask_select,
            cmap_select,
            cmap_view,
            )

        return pn.Row(wbox, viewer_bind)


def make_tools() -> tuple[MapManager, list[StructuredTool]]:
    """Build a fresh MapManager and the LangChain tools bound to *that* instance.

    Call this once per Panel session. A module-level MapManager would be
    created once per server process and shared by every browser session,
    so all visitors would see the same STAC search, footprint map and
    datacube; the factory keeps search state private to each session.
    """
    map_mgr = MapManager()

    # tools == a wrapped method of this instance
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
    return map_mgr, tools
