from typing import Tuple, Optional, List, Dict

import folium
from folium.raster_layers import TileLayer
import panel as pn
import param
from pystac_client.client import Client
import json
import geopandas as gpd
from shapely.geometry import shape, Polygon
from odc.stac import stac_load
import pystac
import rasterio

from langchain.tools import StructuredTool

import numpy as np
import pandas as pd
from datetime import datetime

from modules.rasterize_plots import s2_hv_plot, create_rgb_viewer

# this little guy isn't doing much yet. could take care of state (bbox, bands/ indeces, etc.)

class MapManager(param.Parameterized):
    gdf = param.DataFrame(
        gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
    )
    items_dict = param.Dict({})
    # def panel(self):
    #     return pn.Column(pn.panel(self._map))
map_mgr = MapManager()
# these are just a few python functions (note the typing) # TODO: move to modules.tools

def stac_search(
        bbox: str,
        dtime: str,
        url: Optional[str] = 'https://earth-search.aws.element84.com/v1/',
        collections: Optional[list] = ['sentinel-2-l2a'],
    ) -> str:
    """Perform a STAC search."""
    
    client = Client.open(url)

    result = client.search(
        collections=[collections],
        bbox=bbox,
        datetime=dtime
    )

    items_dict = result.get_all_items_as_dict()
    map_mgr.items_dict = items_dict
    map_mgr.gdf = gpd.GeoDataFrame.from_features(items_dict)

    return {
        'count': result.matched(),
        }

def load_items(
    latitude: float,
    longitude: float,
):
    """Load Sentinel & Landsat STAC items to a map. DO NOT use for Aqua/Terra/MODIS"""

    m = map_mgr.gdf.loc[:, ['geometry']].set_crs('epsg:4326').explore(tiles="CartoDB positron") # TODO: basemap updates

    chat_box.append(
        {"SatGPT": pn.pane.plot.Folium(m, height=400)}
        )
    return "Map is loaded to chat. Return nothing but a text confirmation to let the user know."

# TODO: This should just be a "set basemap" function so the basemap applies to all future maps
def load_gribs(
    latitude: float,
    longitude: float,
    datestring: str = '2023-06-09',
    source: Optional[str] = 'Aqua'
):
    """
    Loads a map with Modis (source = 'Aqua' or 'Terra') world coverage by date. 
    This tool does NOT require a prior STAC search. Currently only supports RGB views, no spectral indices.
    """
    # good read: https://coolum001.github.io/foliummaps.html
    start_coords = (latitude, longitude)
    folium_map = folium.Map(
        location=start_coords, zoom_start=9, width='80%'
    )

    # TODO: case/switch for VIIRS
    TileLayer(
        tiles='https://gibs-{s}.earthdata.nasa.gov/wmts/epsg3857/best/'
        + '{layer}/default/{time}/{tileMatrixSet}/{z}/{y}/{x}.jpg',
        subdomains='abc',
        name='GIBS',
        attr='NASA GIBS',
        overlay=True,
        layer=f'MODIS_{source}_CorrectedReflectance_TrueColor',
        tileMatrixSet='GoogleMapsCompatible_Level9',
        time=datestring,
        tileSize=256,
    ).add_to(folium_map)
    folium.LayerControl().add_to(folium_map)
    
    chat_box.append(
        {"SatGPT": pn.pane.plot.Folium(folium_map, height=400)}
        )
    return "Map is loaded to chat. Return nothing but a text confirmation to let the user know."

def plot_items(
    field: str = 'eo:cloud_cover',
):
    """Plot any field from the current STAC items, e.g. cloud cover. No images, just STAC metadata fields."""
    dates = [ds.split('T')[0] for ds in map_mgr.gdf.loc[:, ['datetime']].values.flatten()]
    dts = [datetime.strptime(d, '%Y-%m-%d') for d in dates]
    map_mgr.gdf.loc[:, ['date']] = dts

    chat_box.append(
        {"SatGPT": pn.panel(map_mgr.gdf.loc[:, ['date', 'eo:cloud_cover']].set_index('date').plot())}
        )
    return "Plot is loaded to chat. Return nothing other than 'Plotted!' to the user."

def load_datacube(
    bbox: Optional[str],
):
    """Display the datacube viewer for the current items. Currently only supports RGB views, no spectral indices."""
    
    item_collection = pystac.ItemCollection(map_mgr.items_dict['features'])

    #TODO: actual error catching (e.g. cube too big); do we still need bbox exception w/ memory?
    try:
        bbox = tuple(map(float, bbox.split(',')))
        rgb = create_rgb_viewer(item_collection, bbox=bbox)
    except:
        rgb = create_rgb_viewer(item_collection)

    chat_box.append({"SatGPT": pn.panel(rgb)})
    
    return "Datacube is loaded to chat. Return nothing other than 'Done!' to the user."

# define tools
# tools == a wrapped function above
search_tool = StructuredTool.from_function(stac_search)
plot_tool = StructuredTool.from_function(plot_items)
map_tool = StructuredTool.from_function(load_items)
gribs_tool = StructuredTool.from_function(load_gribs)
datacube_tool  = StructuredTool.from_function(load_datacube)

tools = [
    search_tool, 
    map_tool, 
    gribs_tool, 
    plot_tool,
    datacube_tool
    ]

chat_box = pn.widgets.ChatBox()
