from __future__ import absolute_import
from ztv.source_panel import SourcePanel
from ztv.plot_panel import PlotPanel
from ztv.phot_panel import PhotPanel
from ztv.stats_panel import StatsPanel
from ztv.color_panel import ColorPanel
from ztv_examples.fits_faker_panel.fits_faker_panel import FitsFakerPanel

control_panels_to_load = [("Source", SourcePanel),
                          ("Color", ColorPanel),
                          ("Plot", PlotPanel),
                          ("Stats", StatsPanel),
                          ("Phot", PhotPanel),
                          ("Faker", FitsFakerPanel)]

