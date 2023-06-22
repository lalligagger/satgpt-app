import holoviews as hv
import panel as pn
# import xarray as xr
import json
# from odc.stac import stac_load
import pystac
from pystac_client.client import Client

from modules.chat_agent import component as chat_agent
from modules.image_plots import (
    plot_s2_spindex,
    plot_true_color_image,
)
from modules.image_statistics import plot_spindex_kde
from modules.spyndex_utils import get_s2_indices, get_index_metadata
from modules.cmap_utils import get_cmap_options, get_cmap_plot

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

    # Resolution slider
    res_select = pn.widgets.IntInput(
        name="Resolution",
        start=20, end=2500, step=50, value=250,
        description="Select the display resolution in meters.")

    # Colormap select
    # TODO: Add an option to revert the colormap
    cmap_select = pn.widgets.Select(name="Colormap", groups=get_cmap_options(), value="RdYlGn")
    cmap_view = pn.bind(get_cmap_plot, cmap=cmap_select)

    # Mask clouds
    mask_clouds_label = pn.widgets.StaticText(name='', value='Mask clouds?')
    mask_clouds_switch = pn.widgets.Switch(name='Mask clouds?')

    # TODO: could these be merged into a single function that returns the slider plot?
    # Or returns 2 hv plots that are bound w/ Swipe below?
    # (Would solve current lag of spindex showing after RGB)
    s2_true_color_bind = pn.bind(
        plot_true_color_image,
        items=items,
        time=time_select,
        resolution=res_select,
        mask_cl=mask_clouds_switch
    )

    s2_spindex_bind = pn.bind(
        plot_s2_spindex,
        items=items,
        time=time_select,
        s2_spindex=s2_spindices_ac,
        resolution=res_select,
        cmap=cmap_select,
        mask_cl=mask_clouds_switch
    )

    # Use the Swipe tool to compare the spectral index with the true color image
    spindex_truecolor_swipe = pn.Swipe(
        pn.pane.HoloViews(s2_true_color_bind, sizing_mode='stretch_height'),
        pn.pane.HoloViews(s2_spindex_bind, sizing_mode='stretch_height')
        )

    # Create the main layout
    main_layout = pn.Row(
        pn.Row(spindex_truecolor_swipe)
    )

    # Create a button to open the chat
    chat_btn = pn.widgets.Button(name="Start New Search...", icon='satellite')

    # This button will open the kde plot of the computed spectral index
    kde_btn = pn.widgets.Button(name="Show Density plot")

    # Metadata button
    index_meta_btn = pn.widgets.Button(name="Show Metadata")

    # Create the dashboard and turn into a deployable application
    s2_dash = pn.template.FastListTemplate(
        site="",
        title="SatGPT App Demo <font size='3'> (STAC x LangChain x Panel) </font>",
        theme="default",
        main=[main_layout],
        sidebar=[
            chat_btn,
            time_select,
            res_select,
            s2_spindices_ac,
            pn.Row(kde_btn, index_meta_btn),
            pn.Column(cmap_select, cmap_view),
            pn.Column(mask_clouds_label, mask_clouds_switch),
        ],
        modal=[pn.Row()]
    )

    # Callback that will open the modal when the button is clicked
    def chat_callback(event):
        s2_dash.modal[0].clear()
        s2_dash.modal[0].append(chat_agent)
        s2_dash.open_modal()

    # TODO: Update the floatpanel content (status: open) when data changes
    def show_kde_plot(event):
        s2_dash.modal[0].clear()
        s2_dash.modal[0].append(plot_spindex_kde())
        s2_dash.open_modal()
        s2_dash.close_modal()  # Hack

    def show_index_meta(event):
        s2_dash.modal[0].clear()
        s2_dash.modal[0].append(get_index_metadata())
        s2_dash.open_modal()
        s2_dash.close_modal()  # Hack

    # Link the button to the respective callback
    chat_btn.on_click(chat_callback)
    kde_btn.on_click(show_kde_plot)
    index_meta_btn.on_click(show_index_meta)

    return s2_dash


if __name__.startswith("bokeh"):
    # Create the dashboard and turn into a deployable application
    s2_dash = create_s2_dashboard()
    s2_dash.servable()
