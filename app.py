import holoviews as hv
import panel as pn
# import xarray as xr
import json
# from odc.stac import stac_load
import pystac
from pystac_client.client import Client

from modules.chat_agent import component as chat_agent
from modules.image_plots import (
    # plot_s2_band_comb,
    plot_s2_spindex,
    plot_true_color_image,
)
from modules.image_statistics import HIST_PLACEHOLDER, plot_s2_spindex_hist
from modules.spyndex_utils import get_s2_indices
# from holoviews.plotting.util import process_cmap

# Load the floatpanel & terminal extension
pn.extension("floatpanel")
pn.extension('terminal')

# Disable webgl: https://github.com/holoviz/panel/issues/4855
hv.renderer("bokeh").webgl = False


client = Client.open('https://earth-search.aws.element84.com/v1/')


def create_s2_dashboard():
    """
    This function creates the main dashboard
    """
    print("loading STAC items")
    with open('./tmp/items.json', "r") as f:
        payload = json.loads(f.read())
        query = payload["features"]
        items = pystac.ItemCollection(query)

    # Time variable
    time_var = [i.datetime for i in items]
    time_date = [t.date() for t in time_var]

    # Time Select
    time_opts = dict(zip(time_date, time_date))
    time_select = pn.widgets.DatePicker(
        name="Date",
        value=time_date[0],
        start=time_date[-1],
        end=time_date[0],
        enabled_dates=time_date,
        description="Select the date for plotting."
        )

    # Sentinel-2 spectral indices ToogleGroup
    # TODO: Switch AutocompleteInput values/ spectral index calc to spyndex

    s2_spindices_ac = pn.widgets.AutocompleteInput(
        name='Spectral Index',
        restrict=True,
        options=get_s2_indices(),
        value='NDVI',
        description="Select the [index](https://davemlz-espectro-espectro-91350i.streamlit.app/) for overlay plot."
        )

    # Create histogram button
    # TODO: Fix hist functionality
    # show_hist_bt = pn.widgets.Button(name="Create Histogram", icon="chart-histogram")
    # show_hist_bt.on_click(plot_s2_spindex_hist)

    # Resolution slider
    res_select = pn.widgets.IntInput(
        name="Resolution",
        start=20, end=2500, step=50, value=250,
        description="Select the display resolution in meters.")

    # Colormap selector (e. g Diverging) - This can be improved...
    diverging_cmap = hv.plotting.util.list_cmaps(records=True, category="Diverging", reverse=False)
    diverging_cmap = list(set([div_.name for div_ in diverging_cmap]))
    cmap_select = pn.widgets.Select(name="Colormap", options=diverging_cmap, value="RdYlGn")

    # TODO: could these be merged into a single function that returns the slider plot?
    # Or returns 2 hv plots that are bound w/ Swipe below?
    # (Would solve current lag of spindex showing after RGB)
    s2_true_color_bind = pn.bind(
        plot_true_color_image,
        items=items,
        time=time_select,
        resolution=res_select
    )

    s2_spindex_bind = pn.bind(
        plot_s2_spindex,
        items=items,
        time=time_select,
        s2_spindex=s2_spindices_ac,
        resolution=res_select,
        cmap=cmap_select
    )

    # Use the Swipe tool to compare the spectral index with the true color image
    spindex_truecolor_swipe = pn.Swipe(
        pn.pane.HoloViews(s2_true_color_bind, sizing_mode='stretch_both'),
        pn.pane.HoloViews(s2_spindex_bind, sizing_mode='stretch_both')
        )

    # Create the main layout
    main_layout = pn.Row(
        pn.Column(HIST_PLACEHOLDER, spindex_truecolor_swipe)  # , show_hist_bt),
    )

    # Create the dashboard and turn into a deployable application
    s2_dash = pn.template.FastListTemplate(
        site="",
        title="SatGPT App Demo <font size='3'> (STAC x LangChain x Panel) </font>",
        theme="default",
        main=[main_layout],
        sidebar=[
            time_select,
            s2_spindices_ac,
            res_select,
            cmap_select
            # clm_title,
            # clm_switch,
        ],
        modal=[chat_agent]
    )
    # Create a button
    modal_btn = pn.widgets.Button(name="Start New Search...", icon='satellite')

    # Callback that will open the modal when the button is clicked
    def about_callback(event):
        s2_dash.open_modal()

    # Link the button to the callback and append it to the sidebar
    modal_btn.on_click(about_callback)
    s2_dash.sidebar.insert(0, modal_btn)

    return s2_dash


if __name__.startswith("bokeh"):
    # Create the dashboard and turn into a deployable application
    s2_dash = create_s2_dashboard()
    s2_dash.servable()
