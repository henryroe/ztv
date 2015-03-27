import wx
from wx.lib.pubsub import Publisher
from wx.lib.pubsub.core.datamsg import Message
import matplotlib
matplotlib.interactive(True)
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.patches import PathPatch
from matplotlib.path import Path
import numpy as np
import sys


class PlotPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        self.primary_image_patch = None
        self.figure = Figure(dpi=None, figsize=(1.,1.))
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.Bind(wx.EVT_SIZE, self._onSize)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.EXPAND)
        self.SetSizer(self.sizer)
        self.Fit()
        self.start_pt = wx.RealPoint(0., 0.)
        self.end_pt = wx.RealPoint(0., 0.)
        self.redraw()
        Publisher().subscribe(self.on_new_xy0, "new_slice_plot_xy0")
        Publisher().subscribe(self.on_new_xy1, "new_slice_plot_xy1")
        Publisher().subscribe(self.redraw, "primary_xy_limits-changed")
        Publisher().subscribe(self.redraw, "new-image-loaded")

    def _onSize(self, event):
        self._SetSize()

    def _SetSize(self):
        pixels = tuple(self.GetClientSize())
        self.SetSize(pixels)
        self.canvas.SetSize(pixels)
        self.figure.set_size_inches(float(pixels[0])/self.figure.get_dpi(),
                                    float(pixels[1])/self.figure.get_dpi())

    def on_new_xy0(self, msg):
        if isinstance(msg, Message):
            x,y = msg.data
        else:
            x,y = msg
        self.start_pt.x, self.start_pt.y = x, y
        self.redraw_on_image()
#         self.redraw()

    def on_new_xy1(self, msg):    # HEREIAM  need to update once have gotten xy0 version working
        if isinstance(msg, Message):
            x,y = msg.data
        else:
            x,y = msg
        self.end_pt.x, self.end_pt.y = x, y
        self.redraw_on_image()
#         self.redraw()

    def redraw_on_image(self):
        if self.primary_image_patch is not None:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.primary_image_patch)
        path = Path([self.start_pt, self.end_pt], [Path.MOVETO, Path.LINETO])
        self.primary_image_patch = PathPatch(path, color='orange', lw=1)
        self.ztv_frame.primary_image_panel.axes.add_patch(self.primary_image_patch)
        self.ztv_frame.primary_image_panel.figure.canvas.draw()

    def on_cancel(self, event):  # TODO link up to a button
        if self.primary_image_patch is not None:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.primary_image_patch)
        self.ztv_frame.primary_image_panel.figure.canvas.draw()
        self.primary_image_patch = None

  # HEREIAM
  # TODO: re-enable the default matplotlib zoom/etc controls for the plot panel
    def redraw(self, *args):
        # TODO:  better drawing with histo-style pixel boxes
        # TODO:  better drawing of diagonals that show actual length of pixel crossing
        xy_limits = self.ztv_frame.primary_image_panel.set_and_get_xy_limits()
        x_start = max([0., self.start_pt.x, xy_limits['xlim'][0]])
        x_start = min([self.ztv_frame.image.shape[1] - 1, x_start, xy_limits['xlim'][1]])
        y_start = max([0., self.start_pt.y, xy_limits['ylim'][0]])
        y_start = min([self.ztv_frame.image.shape[0] - 1, y_start, xy_limits['ylim'][1]])
        x_end = max([0., self.end_pt.x, xy_limits['xlim'][0]])
        x_end = min([self.ztv_frame.image.shape[1] - 1, x_end, xy_limits['xlim'][1]])
        y_end = max([0., self.end_pt.y, xy_limits['ylim'][0]])
        y_end = min([self.ztv_frame.image.shape[0] - 1, y_end, xy_limits['ylim'][1]])
        if x_start == x_end:
            x_end = x_start + 1
        if y_start == y_end:
            y_end = y_start + 1
        n_pts = 2000 # there's no need for this to be > # of pixels on display window.  2000 is nicely overkilled
        xs = np.linspace(x_start, x_end, n_pts)
        ys = np.linspace(y_start, y_end, n_pts)
        # TODO: if vertical/horizontal slice, use actual pixel numbers for horizontal axis of plot
        positions = np.sqrt( (xs - xs[0])**2 + (ys - ys[0])**2 )
        xs = xs.astype(np.int)
        ys = ys.astype(np.int)
        im_values = self.ztv_frame.image[ys, xs]
        self.axes.clear()
        self.line_plot = self.axes.plot(positions, im_values)
        self.axes.set_xlim([positions[0], positions[-1]])
        self.figure.canvas.draw()
