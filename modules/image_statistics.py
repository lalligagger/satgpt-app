import panel as pn
from bokeh.models import WheelZoomTool
import hvplot.xarray  # noqa
from modules.constants import FLOATPANEL_CONFIGS


def plot_spindex_kde():
    """
    This function shows the density plot of the selected index
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

    # Get the index from the cache?
    cache = pn.state.cache["index"]

    index_name = cache["name"]
    index_data = cache["data"]

    # Convert to dataset
    plot_data = index_data.to_dataset(name="Index")
    kde_plot = plot_data.hvplot.kde("Index", title="", xlabel=f"{index_name}", alpha=0.5, hover=False)

    # Embed the histogram in a FloatPanel
    float_hist = pn.layout.FloatPanel(
        kde_plot,
        contained=False,
        position="center",
        margin=20,
        config=FLOATPANEL_CONFIGS
    )

    return float_hist
