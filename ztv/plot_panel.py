import wx
from wx.lib.pubsub import Publisher
import matplotlib
matplotlib.interactive(True)
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
import numpy as np


class PlotPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
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
        Publisher().subscribe(self.update_line_plot_points, "update_line_plot_points")
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

    def update_line_plot_points(self, msg):
        if isinstance(msg, Message):
            pts = msg.data
        else:
            pts = msg
        self.start_pt = wx.RealPoint(*pts[0])
        self.end_pt = wx.RealPoint(*pts[1])
        self.redraw()

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
