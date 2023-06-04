import datetime
from ipyleaflet import (Map, LayerGroup, LayersControl, basemaps, basemap_to_tiles)
import json
from odc import ui
from odc.algo import to_rgba
from odc.stac import stac_load
import panel as pn
import param
import pystac
from pystac_client.client import Client
import time
from xarray import Dataset

pn.extension("ipywidgets", sizing_mode="stretch_width")

client = Client.open('https://earth-search.aws.element84.com/v1/')

bmap = basemap_to_tiles(basemaps.OpenStreetMap.Mapnik)

class MapManager(param.Parameterized):

    itempath = param.String("./items.json")
    date = param.Date()
    data = param.ClassSelector(Dataset, precedence=-1)
    items = param.ListSelector()
    allow_dates = param.ListSelector(precedence=-1)
    _map = Map(center=(47.4, -122.2), zoom=6, scroll_wheel_zoom=True)

    # fires anytime agent completes search & update items.json
    @pn.depends('itempath', watch=True)
    def load_items(self):
        print(f"loading items: {self.itempath}")

        with open(self.itempath, "r") as f:
            payload = json.loads(f.read())
            query = payload["features"]
            items = pystac.ItemCollection(query)

        self.items = items.items
        self.allow_dates = [i.datetime.date() for i in self.items] #not used yet

    # main update function on calendar date set
    def set_date(self, event):
        print(f"setting new date {event.new}")
        self.date = event.new
        self.update_layer()
        return self.date

    # layer handler
    # TODO: Link to controls for RGB vs. NIR vs. NDVI ...
    def update_layer(self):

        # clear last layer and re-add basemap
        self._map.clear_layers()
        self._map.add_layer(bmap)

        print(f"adding layer for {self.date}")
        self.load_data(self.date)
        rgba = to_rgba(self.data, clamp=(1, 3_000))
        ovr = ui.mk_image_overlay(rgba.sel(time=self.date, method='nearest'))
        self._map.add_layer(ovr)

        ## needs to force reload to view new image layer
        try:
            pn.state.location.reload = True # https://github.com/holoviz/panel/issues/3148
        except:
            "skipping reload"
        ## for debug only
        return self._map 
        
    # data loader
    # TODO: allow daterange
    def load_data(self, date):
        self.load_items()

        print("loading data")
        print(self.items)
        items = self.items

        # picks out single item by selected date
        mask = [i.datetime.date() == date for i in self.items]
        item = [b for a, b in zip(mask, self.items) if a]

        xx = stac_load(
            item,
            bands=["red", "green", "blue"],
            resolution=1000
            )
        self.data = xx
        return self.data
    
    ## not used
    # def panel(self):
        
    #     map_params = pn.Param(    

    #         parameters=["itempath", "date"],
            
    #         widgets={
    #             "date": {
    #                 "type": pn.widgets.DatePicker(
    #                     start=self.allow_dates[-1], 
    #                     end=self.allow_dates[0], 
    #                     enabled_dates=self.allow_dates
    #                     )
    #                 }, 
    #         },
    #         show_name=False,
    #         default_layout=pn.Row,
    #         width=600
    #     )
    #     return pn.Column(pn.panel(map_params), pn.panel(self._map))