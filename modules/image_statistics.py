import holoviews as hv
import numpy as np
import panel as pn
from bokeh.models import WheelZoomTool
from bokeh.models.formatters import NumeralTickFormatter

# Create a placeholder for the FloatPanel
HIST_PLACEHOLDER = pn.Column(height=0, width=0)

# https://jspanel.de/#options
FLOATPANEL_CONFIGS = {
    "resizeit": {"disable": "true"},
    "headerControls": "closeonly",
    "closeOnEscape": "true",
}

# Save the histogram placeholder to the cache
pn.state.cache["hist_placeholder"] = HIST_PLACEHOLDER
pn.state.cache["hist_refresh_bt"] = []


def enable_hist_refresh_bt():
    """
    This function enables the refresh button used to update the histogram plot
    """

    refresh_bt = pn.state.cache["hist_refresh_bt"]
    if refresh_bt:
        refresh_bt.button_type = "warning"
        refresh_bt.disabled = False


def plot_s2_spindex_hist(event):
    """
    This function shows the Histogram of the computed Sentinel-2 spectral index
    in a FloatPanel on button click.
    Solution by @Hoxbro: https://discourse.holoviz.org/t/how-to-display-a-floatpanel-on-button-click/5346/3
    """

    def hook(plot, element):
        """
        Custom hook for disabling zoom on axis
        """

        # Disable zoom on axis
        for tool in plot.state.toolbar.tools:
            if isinstance(tool, WheelZoomTool):
                tool.zoom_on_axis = False
                break

    # Get spectral index data from the cache
    spindex_cache = pn.state.cache["spindex"]

    spindex_name = spindex_cache["name"]
    spindex_array = spindex_cache["np_array"]

    # Remove the masked values
    spindex_array = spindex_array.compressed()

    # Calculates the histogram
    frequencies, edges = np.histogram(spindex_array, 20)

    # Plot the histogram
    spindex_hist = hv.Histogram((edges, frequencies)).opts(
        xlabel=spindex_name,
        yformatter=NumeralTickFormatter(format="0a"),
        title=f"Histogram of {spindex_name} values",
        hooks=[hook],
        width=400,
        height=400,
    )

    # A button to refresh the histogram
    refresh_bt = pn.widgets.Button(name="Refresh", icon="refresh")
    refresh_bt.on_click(plot_s2_spindex_hist)
    refresh_bt.disabled = True

    # Assign the refresh button to the cache
    pn.state.cache["hist_refresh_bt"] = refresh_bt

    # Embed the histogram in a FloatPanel
    float_hist = pn.layout.FloatPanel(
        spindex_hist,
        refresh_bt,
        contained=False,
        position="center",
        margin=20,
        config=FLOATPANEL_CONFIGS,
    )

    # Show the dialog
    pn.state.cache["hist_placeholder"][:] = [float_hist]
