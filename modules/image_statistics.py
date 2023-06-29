import panel as pn
from bokeh.models import WheelZoomTool
import hvplot.xarray  # noqa
from modules.constants import FLOATPANEL_CONFIGS


def plot_spindex_kde(index_name, index_data):
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

    # Convert to dataset
    plot_data = index_data.to_dataset(name="Index")
    kde_plot = plot_data.hvplot.kde(
        "Index", title="", xlabel=f"{index_name}", alpha=0.5, hover=False
    )

    kde_plot.opts(hooks=[hook])

    return kde_plot
