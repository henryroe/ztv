from __future__ import absolute_import
from .source_panel import SourcePanel
from .plot_panel import PlotPanel
from .phot_panel import PhotPanel
from .stats_panel import StatsPanel
from .color_panel import ColorPanel

# in adapting this file to your own use, you will most likely put it in some other directory.
# the above default imports will probably then need to be:
# from ztv.source_panel import SourcePanel
# from ztv.plot_panel import PlotPanel
# from ztv.phot_panel import PhotPanel
# from ztv.stats_panel import StatsPanel
# from ztv.color_panel import ColorPanel

# The requirements for a file that defines which control panels to show in ztv is:
# An iterator named `control_panels_to_load` 
# that returns tuples of a title string (to be displayed in GUI)
#                     and the class definition for the panel.

control_panels_to_load = [("Source", SourcePanel),
                          ("Color", ColorPanel),
                          ("Plot", PlotPanel),
                          ("Stats", StatsPanel),
                          ("Phot", PhotPanel)]
