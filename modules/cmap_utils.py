import numpy as np
import holoviews as hv


def get_cmap_options():
    """ Get a dictionary with all available color maps grouped by category """

    cmap_opts = {}
    for category in ["Diverging", "Uniform Sequential"]:
        hv_category = hv.plotting.util.list_cmaps(records=True, category=category, reverse=False)
        for cmap in hv_category:
            cmap_opts.setdefault(f"{category} ({cmap.provider})", []).append(cmap.name)
    return cmap_opts


def get_cmap_plot(cmap):
    """ A function that plots the selected colormap """

    def disable_all(plot, element):
        plot.state.toolbar.logo = None
        plot.state.xaxis.major_tick_line_color = None
        plot.state.xaxis.minor_tick_line_color = None
        plot.state.xaxis.major_label_text_font_size = "0pt"
        plot.state.yaxis.major_tick_line_color = None
        plot.state.yaxis.minor_tick_line_color = None
        plot.state.yaxis.major_label_text_font_size = "0pt"

    spacing = np.linspace(0, 1, 64)[np.newaxis]
    hv_img = hv.Image(spacing, ydensity=1).opts(height=50,
                                                xaxis=None,
                                                yaxis=None,
                                                cmap=cmap,
                                                default_tools=[],
                                                hooks=[disable_all])
    return hv_img
