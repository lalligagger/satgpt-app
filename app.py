from agent import agent_executor
from mapper import MapManager

from ipyleaflet import Map, Marker
import json
from odc import ui
from odc.stac import stac_load
from odc import ui
from odc.algo import colorize, to_rgba
import panel as pn
import pystac
from pystac_client.client import Client


# default user request
user_req = 'Sentinel images available over Seattle on August 26 2019'

map_mgr = MapManager()

# TODO: if dates are set here, then there must be a search to load on init.
# how can we handle this?
dp_widget = pn.widgets.DatePicker(
    ## pulled out for now
    # start=map_mgr.allow_dates[-1],
    # end=map_mgr.allow_dates[0],
    # enabled_dates=map_mgr.allow_dates
    
    )

datepicker = pn.Param(map_mgr, widgets={"date":dp_widget})
button = pn.widgets.Button(name='Search', button_type='primary')
text = pn.widgets.TextInput(value=user_req, sizing_mode="stretch_width")
json_widget = pn.pane.JSON({}, height=75)
pn.extension("ipywidgets", sizing_mode="stretch_width")
ACCENT_BASE_COLOR = "#DAA520"

# TODO: have not found any way, yet, to get views of a new stac search
@pn.depends(button, watch=True)
def update_data(clicks):
    # run the agent using text field input
    agent_executor(text.value)

# handles date setting, sends to map_mgr for data load & layer update
watcher = dp_widget.param.watch(map_mgr.set_date, ['value'])

component = pn.Column(
    pn.Row(text, button),
    # pn.Row(datepicker),
    datepicker,
    map_mgr._map
    # map_mgr.view,
    # json_widget  # will add agent stream/ debug here
)

template = pn.template.FastListTemplate(
    # site="Awesome Panel",
    title="SatGPT",
    logo="https://panel.holoviz.org/_static/logo_stacked.png",
    header_background=ACCENT_BASE_COLOR,
    accent_base_color=ACCENT_BASE_COLOR,
    main=[component],
).servable()