from __future__ import absolute_import
import wx
from wx.lib.pubsub import pub
import matplotlib
from matplotlib.figure import Figure
try:
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
except IOError:
    # on some linux installations this import needs to be done twice as the first time raises an error:
    #   IOError: [Errno 2] No such file or directory: '/tmp/matplotlib-parallels/fontList.cache'
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.patches import PathPatch
from matplotlib.path import Path
import numpy as np
import sys
from matplotlib.widgets import AxesWidget
from .ztv_lib import send_to_stream
from .ztv_wx_lib import textctrl_output_only_background_color


class PlotPlotPanel(wx.Panel):
    def __init__(self, parent, dpi=None, **kwargs):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, **kwargs)
        self.ztv_frame = self.GetTopLevelParent()
        self.figure = Figure(dpi=None, figsize=(1.,1.))
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.Bind(wx.EVT_SIZE, self._onSize)
        self.axes_widget = AxesWidget(self.figure.gca())
        self.axes_widget.connect_event('motion_notify_event', self.on_motion)
        self.plot_point = None
        
    def on_motion(self, evt):
        if evt.xdata is not None:
            xarg = np.abs(self.ztv_frame.plot_panel.plot_positions - evt.xdata).argmin()
            ydata = self.ztv_frame.plot_panel.plot_im_values[xarg]
            self.ztv_frame.plot_panel.cursor_position_textctrl.SetValue('{0:.6g},{1:.6g}'.format(evt.xdata, ydata))
            if self.plot_point is None:
                self.plot_point, = self.axes.plot([evt.xdata], [ydata], 'xm')
            else:
                self.plot_point.set_data([[evt.xdata], [ydata]])
            self.figure.canvas.draw()

    def _onSize(self, event):
        self._SetSize()

    def _SetSize(self):
        pixels = tuple(self.GetClientSize())
        self.SetSize(pixels)
        self.canvas.SetSize(pixels)
        self.figure.set_size_inches(float(pixels[0])/self.figure.get_dpi(), float(pixels[1])/self.figure.get_dpi())


class PlotPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize)
        self.ztv_frame = self.GetTopLevelParent()
        self.ztv_frame.primary_image_panel.popup_menu_cursor_modes.append('Slice plot')
        self.ztv_frame.primary_image_panel.available_cursor_modes['Slice plot'] = {
                'set-to-mode':self.set_cursor_to_plot_mode,
                'on_button_press':self.on_button_press,
                'on_motion':self.on_motion,
                'on_button_release':self.on_button_release}
        for cur_key in ['c', 'C', 'v', 'V', 'y', 'Y']:
            self.ztv_frame.primary_image_panel.available_key_presses[cur_key] = self.do_column_plot
        for cur_key in ['r', 'R', 'h', 'H', 'x', 'X']:
            self.ztv_frame.primary_image_panel.available_key_presses[cur_key] = self.do_row_plot
        for cur_key in ['z', 'Z']:
            self.ztv_frame.primary_image_panel.available_key_presses[cur_key] = self.do_stack_plot

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.plot_panel = PlotPlotPanel(self)
        self.sizer.Add(self.plot_panel, 1, wx.LEFT | wx.TOP | wx.EXPAND)
        
        self.h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cursor_position_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, (200, -1),
                                                    wx.TE_READONLY)
        self.textentry_font = wx.Font(14, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT, False)
        self.cursor_position_textctrl.SetFont(self.textentry_font)
        self.cursor_position_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        self.h_sizer.Add(self.cursor_position_textctrl, 0)
        self.h_sizer.AddStretchSpacer(1)
        self.hideshow_button = wx.Button(self, wx.ID_ANY, u"Hide", wx.DefaultPosition, wx.DefaultSize, 0)
        self.h_sizer.Add(self.hideshow_button, 0)
        self.hideshow_button.Bind(wx.EVT_BUTTON, self.on_hideshow_button)

        self.sizer.Add(self.h_sizer, 0, wx.EXPAND)

        self.SetSizer(self.sizer)
        self.Fit()
        self.start_pt = wx.RealPoint(0., 0.)
        self.end_pt = wx.RealPoint(0., 0.)
        self.redraw()
        pub.subscribe(self.on_new_xy0, 'set-new-slice-plot-xy0')
        pub.subscribe(self.on_new_xy1, 'set-new-slice-plot-xy1')
        pub.subscribe(self.queue_redraw, 'primary-xy-limits-changed')
        pub.subscribe(self.queue_redraw, 'recalc-display-image-called')
        pub.subscribe(self.remove_overplot_on_image, 'hide-plot-panel-overplot')
        pub.subscribe(self.redraw_overplot_on_image, 'show-plot-panel-overplot')
        pub.subscribe(self.publish_xy0xy1_to_stream, 'get-slice-plot-coords')
        self.cursor_drag_active = False
        
    def publish_xy0xy1_to_stream(self, msg=None):
        wx.CallAfter(send_to_stream, sys.stdout, 
                     ('slice-plot-coords', [[self.start_pt.x, self.start_pt.y], [self.end_pt.x, self.end_pt.y]]))

    def on_button_press(self, event):
        self.select_panel()
        self.on_new_xy0((event.xdata, event.ydata))
        self.on_new_xy1((event.xdata, event.ydata))
        self.cursor_drag_active = True
        
    def on_motion(self, event):
        if not self.cursor_drag_active:
            return
        if event.key is not None and 'shift' in event.key:   # if shift key, align horizontally/vertically
            xdata, ydata = event.xdata, event.ydata
            if np.abs(xdata - self.start_pt.x) <= np.abs(ydata - self.start_pt.y):
                xdata = self.start_pt.x
            else:
                ydata = self.start_pt.y
            self.on_new_xy1((xdata, ydata))
        else:
            self.on_new_xy1((event.xdata, event.ydata))

    def on_button_release(self, event):
        self.cursor_drag_active = False

    def set_cursor_to_plot_mode(self, event):
        self.ztv_frame.primary_image_panel.cursor_mode = 'Slice plot'
        self.select_panel()
        self.highlight_panel()

    def do_column_plot(self, event):
        x = np.round(event.xdata)
        max_y = self.ztv_frame.display_image.shape[0] - 1
        ylim = self.ztv_frame.primary_image_panel.ylim
        self.update_line_plot_points(((x + 0.5, max(0, ylim[0])), (x + 0.5, min(max_y, ylim[1]))))

    def do_row_plot(self, event):
        y = np.round(event.ydata)
        max_x = self.ztv_frame.display_image.shape[1] - 1
        xlim = self.ztv_frame.primary_image_panel.xlim
        self.update_line_plot_points(((max(0, xlim[0]), y + 0.5), (min(max_x, xlim[1]), y + 0.5)))

    def do_stack_plot(self, event):
        x = np.round(event.xdata)
        y = np.round(event.ydata)
        self.update_line_plot_points(((x, y), (x, y)))

    def queue_redraw(self, msg=None):  
        """
        wrapper to call redraw from CallAfter in order to make GUI as responsive as possible.
        """
        wx.CallAfter(self.redraw, msg=None)

    def update_line_plot_points(self, msg):
        xy0, xy1 = msg
        self.start_pt.x, self.start_pt.y = xy0[0], xy0[1]
        self.end_pt.x, self.end_pt.y = xy1[0], xy1[1]
        self.redraw_overplot_on_image()
        self.redraw()

    def on_new_xy0(self, msg):
        self.start_pt.x, self.start_pt.y = msg
        self.redraw_overplot_on_image()
        self.redraw()

    def on_new_xy1(self, msg):   
        self.end_pt.x, self.end_pt.y = msg
        self.redraw_overplot_on_image()
        self.redraw()

    def redraw_overplot_on_image(self, msg=None):
        if self.start_pt == self.end_pt:
            path = Path([self.start_pt, self.start_pt + (0.5, 0.),
                         self.start_pt, self.start_pt + (-0.5, 0.), 
                         self.start_pt, self.start_pt + (0., 0.5), 
                         self.start_pt, self.start_pt + (0., -0.5), self.start_pt], 
                        [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO, Path.LINETO, 
                         Path.LINETO, Path.LINETO, Path.LINETO, Path.LINETO])
        else:
            path = Path([self.start_pt, self.end_pt], [Path.MOVETO, Path.LINETO])
        self.ztv_frame.primary_image_panel.add_patch('plot_panel:overlay', PathPatch(path, color='magenta', lw=1))
        self.hideshow_button.SetLabel(u"Hide")        

    def remove_overplot_on_image(self, msg=None):
        self.ztv_frame.primary_image_panel.remove_patch('plot_panel:overlay')
        self.hideshow_button.SetLabel(u"Show")

    def on_hideshow_button(self, event):
        if self.hideshow_button.GetLabel() == 'Hide':
            self.hideshow_button.SetLabel(u"Show")
            self.remove_overplot_on_image()
        else:
            self.hideshow_button.SetLabel(u"Hide")        
            self.redraw_overplot_on_image()
            
    def redraw(self, msg=None):
        if self.start_pt == self.end_pt:
            if self.ztv_frame.proc_image.ndim == 2:
                positions = np.array([-0.5, 0.5])
                im_values = np.array([self.ztv_frame.proc_image[self.start_pt.y, self.start_pt.x]] * 2)
                cur_im_num = 0
                cur_im_value = self.ztv_frame.proc_image[self.start_pt.y, self.start_pt.x]
            else:
                positions = np.array([np.arange(-0.5, self.ztv_frame.proc_image.shape[0] - 1), 
                                      np.arange(0.5, self.ztv_frame.proc_image.shape[0])]).transpose().ravel()
                im_values = np.array([self.ztv_frame.proc_image[:, self.start_pt.y, self.start_pt.x],
                                      self.ztv_frame.proc_image[:, self.start_pt.y, self.start_pt.x]]).transpose().ravel()
                cur_im_num = self.ztv_frame.cur_display_frame_num
                cur_im_value = self.ztv_frame.proc_image[cur_im_num, self.start_pt.y, self.start_pt.x]
            self.plot_panel.axes.clear()
            self.line_plot = self.plot_panel.axes.plot(positions, im_values)
            self.plot_positions = positions
            self.plot_im_values = im_values
            self.plot_panel.axes.plot([cur_im_num], [cur_im_value], 'xm')
            self.plot_panel.axes.set_xlim([positions[0], positions[-1]])
            self.plot_panel.plot_point = None
            self.plot_panel.figure.canvas.draw()
        else:
            xlim = self.ztv_frame.primary_image_panel.xlim
            ylim = self.ztv_frame.primary_image_panel.ylim
            oversample_factor = 10.
            n_pts = oversample_factor*np.max(self.ztv_frame.display_image.shape)
            xs = np.linspace(self.start_pt.x, self.end_pt.x, n_pts)
            ys = np.linspace(self.start_pt.y, self.end_pt.y, n_pts)
            mask = ((xs >= min(xlim)) & (xs <= max(xlim)) & 
                    (ys >= min(ylim)) & (ys <= max(ylim)) &
                    (xs >= 0.) & (ys >= 0.) &
                    (xs < self.ztv_frame.display_image.shape[1]) & 
                    (ys < self.ztv_frame.display_image.shape[0]))
            xs = xs[mask]
            ys = ys[mask]
            if len(xs) > 0:
                if (ys.max() - ys.min()) > (xs.max() - xs.min()):   # dominantly a vertical slice
                    if ys[0] > ys[1]:
                        xs = xs[-1::-1]
                        ys = ys[-1::-1]
                else:
                    if xs[0] > xs[1]:
                        xs = xs[-1::-1]
                        ys = ys[-1::-1]
                if np.min(np.round(xs)) == np.max(np.round(xs)):
                    positions = ys
                elif np.min(np.round(ys)) == np.max(np.round(ys)):
                    positions = xs
                else:
                    positions = np.sqrt( (xs - xs[0])**2 + (ys - ys[0])**2 )
                xs = xs.astype(np.int)
                ys = ys.astype(np.int)
                im_values = self.ztv_frame.display_image[ys, xs]
                self.plot_panel.axes.clear()
                self.plot_positions = positions
                self.plot_im_values = im_values
                if positions.min() != positions.max():
                    self.line_plot = self.plot_panel.axes.plot(positions, im_values)
                    self.plot_panel.axes.set_xlim([positions[0], positions[-1]])
                self.plot_panel.plot_point = None
                self.plot_panel.figure.canvas.draw()
            else:
                self.plot_panel.axes.clear()
                self.plot_panel.plot_point = None
                self.plot_panel.figure.canvas.draw()
        