from __future__ import absolute_import
import wx
from wx.lib.pubsub import pub
import wx.lib.layoutf as layoutf
import numpy as np
import threading
import warnings
import psutil
import time
import os
import sys
import pickle
import glob
from astropy.io import fits
from astropy import wcs
from astropy.coordinates import ICRS
from astropy import units
import astropy.visualization
from astropy.stats import sigma_clipped_stats
 
import matplotlib
matplotlib.interactive(True)
try:
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
except IOError:
    # on some linux installations this import needs to be done twice as the first time raises an error:
    #   IOError: [Errno 2] No such file or directory: '/tmp/matplotlib-parallels/fontList.cache'
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure
from matplotlib.widgets import AxesWidget
from matplotlib.patches import Rectangle
from matplotlib import cm
from matplotlib.colors import Normalize

from .file_picker import FilePicker
from .fits_header_dialog import FITSHeaderDialog
# Intend: control panels are one per file with class name "MyPanel" in filename "my_panel.py"
from .source_panel import SourcePanel
from .plot_panel import PlotPanel
from .phot_panel import PhotPanel
from .stats_panel import StatsPanel
from .color_panel import ColorPanel
from .ztv_lib import send_to_stream, StreamListener, StreamListenerTimeOut
from .ztv_wx_lib import set_textctrl_background_color, validate_textctrl_str

import pdb

base_dir = os.path.abspath(os.path.dirname(__file__))
about = {}
with open(os.path.join(base_dir, "__about__.py")) as f:
    exec(f.read(), about)

class Error(Exception):
    pass


def clear_ticks_and_frame_from_axes(axes):
    """
    Remove ticks and frame from an axes.

    This is called out as a separate method so that sub-classes of ImagePanel can overload
    with their own version as needed.
    """
    if axes is None:
        axes = plt.gca()
    axes.xaxis.set_visible(False)
    axes.yaxis.set_visible(False)
    for spine in axes.spines.itervalues():
        spine.set_visible(False)


class ColorMaps():

    def basic(self):
        """
        return a selection of useful colormaps that is less overwhelming than ALL of them
        """
        return ['gray', 'bone', 'Blues_r', 'Greens_r', 'Oranges_r', 'RdPu_r', 'hot', 'gist_heat',
                'rainbow', 'hsv', 'spectral', 'gnuplot', 'jet']

    def all_except_reversed(self):
        return [a for a in cm.datad if not a.endswith('_r')]

    def all(self):
        return [a for a in cm.datad]


class PrimaryImagePanel(wx.Panel):
    def __init__(self, parent, dpi=None, **kwargs):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.Size(512,512), **kwargs)
        self.ztv_frame = self.GetTopLevelParent()
        self.accelerator_table = []
        self.center = wx.RealPoint()
        self.zoom_rect = None
        self.eventID_to_cmap = {wx.NewId(): x for x in self.ztv_frame.available_cmaps}
        self.cmap_to_eventID = {self.eventID_to_cmap[x]: x for x in self.eventID_to_cmap}
        self.eventID_to_scaling = {wx.NewId(): x for x in self.ztv_frame.available_scalings}
        self.scaling_to_eventID = {self.eventID_to_scaling[x]: x for x in self.eventID_to_scaling}
        cmap_bitmap_height = 15
        cmap_bitmap_width = 100
        self.cmap_bitmaps = {}
        for cmap in self.ztv_frame.available_cmaps:
            temp = cm.ScalarMappable(cmap=cmap)
            rgba = temp.to_rgba(np.outer(np.ones(cmap_bitmap_height, dtype=np.uint8),
                                         np.arange(cmap_bitmap_width, dtype=np.uint8)))
            self.cmap_bitmaps[cmap] = wx.BitmapFromBufferRGBA(cmap_bitmap_width, cmap_bitmap_height,
                                                              np.uint8(np.round(rgba*255)))
        self.available_cursor_modes = [# ('None', self.set_cursor_to_none_mode),
                                       ('Zoom', self.set_cursor_to_zoom_mode),
                                       ('Pan', self.set_cursor_to_pan_mode),
                                       ('Slice plot', self.set_cursor_to_plot_mode),
                                       ('Stats box', self.set_cursor_to_stats_box_mode),
                                       ('Phot', self.set_cursor_to_phot_mode)]
        self.cursor_mode = 'Zoom'
        self.max_doubleclick_millisec = 500  # needed to trap 'real' single clicks from the first click of a double click
        self.init_popup_menu()
        self.xlim = [-9e9, 9e9]
        self.ylim = [-9e9, 9e9]
        self.figure = Figure(None, dpi)
        self.axes = self.figure.add_axes([0., 0., 1., 1.])
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.Bind(wx.EVT_SIZE, self._onSize)
        self.axes_widget = AxesWidget(self.figure.gca())
        self.axes_widget.connect_event('motion_notify_event', self.on_motion)
        self.axes_widget.connect_event('figure_leave_event', self.on_cursor_leave)
        self.axes_widget.connect_event('figure_enter_event', self.on_cursor_enter)
        self.axes_widget.connect_event('button_press_event', self.on_button_press)
        self.axes_widget.connect_event('button_release_event', self.on_button_release)
        self.axes_widget.connect_event('key_press_event', self.on_key_press)
        wx.EVT_RIGHT_DOWN(self.figure.canvas, self.on_right_down)  # supercedes the above button_press_event
        pub.subscribe(self.redraw_primary_image, 'redraw-image')   
        pub.subscribe(self.reset_zoom_and_center, 'reset-zoom-and-center')
        pub.subscribe(self.set_zoom_factor, 'set-zoom-factor')
        pub.subscribe(self.set_xy_center, 'set-xy-center')
        self.SetAcceleratorTable(wx.AcceleratorTable(self.accelerator_table))

    def _append_menu_item(self, menu, wx_id, title, fxn):
        if wx_id is None:
            wx_id = wx.NewId()
        menu.Append(wx_id, title)
        wx.EVT_MENU(menu, wx_id, fxn)
        return wx_id

    def init_popup_menu(self):
        menu = wx.Menu()
        menu.Append(wx.NewId(), 'Cursor mode:').Enable(False)
        self.cursor_mode_to_eventID = {}
        cmd_num = 1
        for cursor_mode, fxn in self.available_cursor_modes:
            wx_id = wx.NewId()
            menu.AppendCheckItem(wx_id, '   ' + cursor_mode + '\tCtrl+' + str(cmd_num))
            wx.EVT_MENU(menu, wx_id, fxn)
            self.cursor_mode_to_eventID[cursor_mode] = wx_id
            self.Bind(wx.EVT_MENU, fxn, id=wx_id)
            self.accelerator_table.append((wx.ACCEL_CMD, ord(str(cmd_num)), wx_id))
            cmd_num += 1
        menu.AppendSeparator()
        image_cmap_submenu = wx.Menu()
        for cmap in self.ztv_frame.available_cmaps:
            menu_item = image_cmap_submenu.AppendCheckItem(self.cmap_to_eventID[cmap], cmap)
            wx.EVT_MENU(image_cmap_submenu, self.cmap_to_eventID[cmap], self.on_change_cmap_event)
            menu_item.SetBitmap(self.cmap_bitmaps[cmap])
        menu.AppendMenu(-1, 'Color Maps', image_cmap_submenu)
        wx_id = wx.NewId()
        self.menu_item_invert_map = menu.AppendCheckItem(wx_id, 'Invert Color Map')
        wx.EVT_MENU(menu, wx_id, self.ztv_frame.invert_cmap)
        self.menu_item_invert_map.Check(self.ztv_frame.is_cmap_inverted)
        image_scaling_submenu = wx.Menu()
        for scaling in self.ztv_frame.available_scalings:
            menu_item = image_scaling_submenu.AppendCheckItem(self.scaling_to_eventID[scaling], scaling)
            wx.EVT_MENU(image_scaling_submenu, self.scaling_to_eventID[scaling], self.on_change_scaling_event)
        menu.AppendMenu(-1, 'Scaling', image_scaling_submenu)
        menu.AppendSeparator()
        self.popup_menu_cur_fits_header_eventID = wx.NewId()
        self._append_menu_item(menu, self.popup_menu_cur_fits_header_eventID, 'FITS Header',
                               self.on_display_cur_fits_header)
        self.popup_menu = menu

    def on_display_cur_fits_header(self, event):
        raw_header_str = self.ztv_frame.cur_fits_hdulist[0].header.tostring()
        header_str = (('\n'.join([raw_header_str[i:i+80] for i in np.arange(0, len(raw_header_str), 80)
                                  if raw_header_str[i:i+80] != " "*80])) + '\n')
        if hasattr(self, 'cur_fits_header_dialog') and self.cur_fits_header_dialog.is_dialog_still_open:
            self.cur_fits_header_dialog.SetTitle(self.ztv_frame.cur_fitsfile_basename)
            self.cur_fits_header_dialog.text.SetValue(header_str)
            self.cur_fits_header_dialog.last_find_index = 0
            self.cur_fits_header_dialog.on_search(None)
        else:
            self.cur_fits_header_dialog = FITSHeaderDialog(self, header_str, self.ztv_frame.cur_fitsfile_basename)
            self.cur_fits_header_dialog.Show()

    def set_and_get_xy_limits(self):
        canvas_size = self.canvas.GetSize()
        num_x_pixels = canvas_size.x
        halfsize = (num_x_pixels / 2.0) / self.ztv_frame.zoom_factor
        xlim = (self.center.x - halfsize, self.center.x + halfsize)
        self.axes.set_xlim(xlim)
        num_y_pixels = canvas_size.y
        halfsize = (num_y_pixels / 2.0) / self.ztv_frame.zoom_factor
        ylim = (self.center.y - halfsize, self.center.y + halfsize)
        self.axes.set_ylim(ylim)
        self.figure.canvas.draw()  # bulk of time in method is spent in this line: TODO: look for ways to make faster
        send_change_message = True
        if xlim == self.xlim and ylim == self.ylim:
            send_change_message = False
        self.xlim, self.ylim = xlim, ylim
        if send_change_message:
            wx.CallAfter(pub.sendMessage, 'primary-xy-limits-changed', msg=None)
        return {'xlim':xlim, 'ylim':ylim}

    def set_cursor_to_none_mode(self, event):
        self.cursor_mode = 'None'
        self.ztv_frame.controls_notebook.clear_highlights()

    def set_cursor_to_zoom_mode(self, event):
        self.cursor_mode = 'Zoom'
        self.ztv_frame.controls_notebook.clear_highlights()

    def set_cursor_to_pan_mode(self, event):
        self.cursor_mode = 'Pan'
        self.ztv_frame.controls_notebook.clear_highlights()
        
    def set_cursor_to_plot_mode(self, event):
        self.cursor_mode = 'Slice plot'
        self.ztv_frame.plot_panel.select_panel()
        self.ztv_frame.plot_panel.highlight_panel()

    def set_cursor_to_stats_box_mode(self, event):
        self.cursor_mode = 'Stats box'
        self.ztv_frame.stats_panel.select_panel()
        self.ztv_frame.stats_panel.highlight_panel()

    def set_cursor_to_phot_mode(self, event):
        self.cursor_mode = 'Phot'
        self.ztv_frame.phot_panel.select_panel()
        self.ztv_frame.phot_panel.highlight_panel()

    def on_key_press(self, event):
        # TODO: figure out why keypresses are only recognized after a click in the matplotlib frame.
        if event.key in ['c', 'C', 'v', 'V', 'y', 'Y']:
            x = np.round(event.xdata)
            max_y = self.ztv_frame.display_image.shape[0] - 1
            wx.CallAfter(pub.sendMessage, 'update-line-plot-points', msg=((x + 0.5, max(0, self.ylim[0])), 
                                                                          (x + 0.5, min(max_y, self.ylim[1]))))
        elif event.key in ['r', 'R', 'h', 'H', 'x', 'X']:
            y = np.round(event.ydata)
            max_x = self.ztv_frame.display_image.shape[1] - 1
            wx.CallAfter(pub.sendMessage, 'update-line-plot-points', msg=((max(0, self.xlim[0]), y + 0.5), 
                                                                          (min(max_x, self.xlim[1]), y + 0.5)))
        elif event.key in ['z', 'Z']:
            x = np.round(event.xdata)
            y = np.round(event.ydata)
            wx.CallAfter(pub.sendMessage, 'update-line-plot-points', msg=((x, y), (x, y)))
        elif event.key == 'right':
            self.ztv_frame.set_cur_display_frame_num(1, relative=True)
        elif event.key == 'left':
            self.ztv_frame.set_cur_display_frame_num(-1, relative=True)

    def set_xy_center(self, msg):
        if self.center.x != msg[0] or self.center.y != msg[1]:
            self.center.x = msg[0]
            self.center.y = msg[1]
            self.set_and_get_xy_limits()

    def set_zoom_factor(self, msg):
        zoom_factor = msg
        old_zoom_factor = self.ztv_frame.zoom_factor
        if zoom_factor > 0.0:
            self.ztv_frame.zoom_factor = zoom_factor
        if old_zoom_factor != self.ztv_frame.zoom_factor:
            self.set_and_get_xy_limits()

    def reset_zoom_and_center(self, msg=None):
        self.center.x = (self.ztv_frame.display_image.shape[1] / 2.) - 0.5
        self.center.y = (self.ztv_frame.display_image.shape[0] / 2.) - 0.5
        max_zoom_x = self.canvas.GetSize().x / float(self.ztv_frame.display_image.shape[1])
        max_zoom_y = self.canvas.GetSize().y / float(self.ztv_frame.display_image.shape[0])
        self.ztv_frame.zoom_factor = min(max_zoom_x, max_zoom_y)
        self.set_and_get_xy_limits()

    def on_change_cmap_event(self, event):
        wx.CallAfter(pub.sendMessage, 'set-cmap', msg=(self.ztv_frame._pause_redraw_image,
                                                       self.eventID_to_cmap[event.GetId()]))

    def on_change_scaling_event(self, event):
        wx.CallAfter(pub.sendMessage, 'set-scaling', msg=(self.ztv_frame._pause_redraw_image,
                                                          self.eventID_to_scaling[event.GetId()]))

    def on_button_press(self, event):
        if event.button == 1:  # left button
            if self.cursor_mode == 'Zoom':
                if event.dblclick:
                    self.center = wx.RealPoint(event.xdata, event.ydata)
                    self.ztv_frame.zoom_factor /= 2.
                    self.set_and_get_xy_limits()
                else:
                    self.zoom_start_timestamp = event.guiEvent.GetTimestamp()  # millisec
                    self.zoom_rect = Rectangle((event.xdata, event.ydata), 0, 0,
                                               color='magenta', fill=False, zorder=100)
                    self.axes.add_patch(self.zoom_rect)
                    self.figure.canvas.draw()
            elif self.cursor_mode == 'Pan':
                self.center = wx.RealPoint(event.xdata, event.ydata)
                self.set_and_get_xy_limits()
            elif self.cursor_mode == 'Stats box':
                self.stats_start_timestamp = event.guiEvent.GetTimestamp()  # millisec
                self.ztv_frame.stats_panel.update_stats_box(event.xdata, event.ydata, event.xdata, event.ydata)
                self.ztv_frame.stats_panel.redraw_overplot_on_image()
                self.cursor_stats_box_x0, self.cursor_stats_box_y0 = event.xdata, event.ydata
            elif self.cursor_mode == 'Phot':
                self.ztv_frame.phot_panel.select_panel()
                wx.CallAfter(pub.sendMessage, 'new-phot-xy', msg=(event.xdata, event.ydata))
            elif self.cursor_mode == 'Slice plot':
                self.ztv_frame.plot_panel.select_panel()
                wx.CallAfter(pub.sendMessage, 'new-slice-plot-xy0', msg=(event.xdata, event.ydata))
                wx.CallAfter(pub.sendMessage, 'new-slice-plot-xy1', msg=(event.xdata, event.ydata))

    def on_motion(self, event):
        if event.xdata is None or event.ydata is None:
            return
        x = int(np.round(event.xdata))
        y = int(np.round(event.ydata))
        if event.button is not None:
            if self.cursor_mode == 'Zoom' and self.zoom_rect is not None:
                x0,y0 = self.zoom_rect.get_x(),self.zoom_rect.get_y()
                self.zoom_rect.set_bounds(x0, y0, event.xdata - x0, event.ydata - y0)
                self.figure.canvas.draw()
            elif self.cursor_mode == 'Stats box':
                self.ztv_frame.stats_panel.update_stats_box(self.cursor_stats_box_x0, self.cursor_stats_box_y0, 
                                                            event.xdata, event.ydata)
                self.ztv_frame.stats_panel.redraw_overplot_on_image()
                self.ztv_frame.stats_panel.update_stats()
            elif self.cursor_mode == 'Slice plot':
                wx.CallAfter(pub.sendMessage, 'new-slice-plot-xy1', msg=(event.xdata, event.ydata))
        if ((x >= 0) and (x < self.ztv_frame.display_image.shape[1]) and
            (y >= 0) and (y < self.ztv_frame.display_image.shape[0])):
            imval = self.ztv_frame.display_image[y, x]
            new_status_string = "x,y={},{}".format(x, y)
            if self.ztv_frame.image_radec is not None:
                c = self.ztv_frame.image_radec[y, x]
                new_status_string += "  radec={0} {1}".format(c.ra.to_string(units.hour, sep=':', precision=2, pad=True),
                                                              c.dec.to_string(sep=':', precision=2, alwayssign=True, 
                                                                              pad=True))
            new_status_string += "  val={:.5g}".format(imval)
            self.ztv_frame.status_bar.SetStatusText(new_status_string)
            self.ztv_frame.loupe_image_panel.set_xy_limits((x, y))
            # finally, catch for a situation where cursor should be active, but didn't enter, e.g. window launched under cursor
            if not hasattr(self, 'saved_cursor') or self.saved_cursor is None:
                self.on_cursor_enter(event)
        else:
            self.ztv_frame.status_bar.SetStatusText("")
            self.ztv_frame.loupe_image_panel.set_xy_limits()
  
    def on_button_release(self, event):
        if event.button == 1:  # left button
            if self.cursor_mode == 'Zoom':
                # this catches for the first click-release of a double-click
                if (event.guiEvent.GetTimestamp() - self.zoom_start_timestamp) > self.max_doubleclick_millisec:
                    # this catches for a long click-and-release without motion
                    x0,y0 = self.zoom_rect.get_x(),self.zoom_rect.get_y()
                    x1 = x0 + self.zoom_rect.get_width()
                    y1 = y0 + self.zoom_rect.get_height()
                    if hasattr(event, 'xdata') and event.xdata is not None:
                        x1 = event.xdata
                    if hasattr(event, 'ydata') and event.ydata is not None:
                        y1 = event.ydata
                    if abs(x0 - x1) >= 2 and abs(y0 - y1) >= 2:
                        self.center = wx.RealPoint((x0 + x1)/2., (y0 + y1)/2.)
                        panel_size = self.canvas.GetSize()
                        x_zoom_factor = panel_size.x / abs(x1 - x0)
                        y_zoom_factor = panel_size.y / abs(y1 - y0)
                        self.ztv_frame.zoom_factor = min(x_zoom_factor, y_zoom_factor)
                        self.set_and_get_xy_limits()
                if self.zoom_rect in self.axes.patches:
                    self.axes.patches.remove(self.zoom_rect)
                self.zoom_rect = None
                self.figure.canvas.draw()
            elif self.cursor_mode == 'Stats box':
                self.ztv_frame.stats_panel.redraw_overplot_on_image()
                self.ztv_frame.stats_panel.update_stats()
            elif self.cursor_mode == 'Slice plot':
                wx.CallAfter(pub.sendMessage, 'new-slice-plot-xy1', msg=(event.xdata, event.ydata))

    def on_right_down(self, event):
        for cursor_mode in self.cursor_mode_to_eventID:
            self.popup_menu.Check(self.cursor_mode_to_eventID[cursor_mode], False)
        self.popup_menu.Check(self.cursor_mode_to_eventID[self.cursor_mode], True)
        for cmap in self.ztv_frame.available_cmaps:
            self.popup_menu.Check(self.cmap_to_eventID[cmap], False)
        self.popup_menu.Check(self.cmap_to_eventID[self.ztv_frame.cmap], True)
        for scaling in self.ztv_frame.available_scalings:
            self.popup_menu.Check(self.scaling_to_eventID[scaling], False)
        self.popup_menu.Check(self.scaling_to_eventID[self.ztv_frame.scaling], True)
        if self.ztv_frame.cur_fits_hdulist is None:
            self.popup_menu.Enable(self.popup_menu_cur_fits_header_eventID, False)
        else:
            self.popup_menu.Enable(self.popup_menu_cur_fits_header_eventID, True)
        self.figure.canvas.PopupMenuXY(self.popup_menu, event.GetX() + 8,  event.GetY() + 8)

    def on_cursor_leave(self, event):
        self.ztv_frame.status_bar.SetStatusText('')
        self.ztv_frame.loupe_image_panel.set_xy_limits()
        if hasattr(self, 'saved_cursor') and self.saved_cursor is not None:
            self.figure.canvas.SetCursor(self.saved_cursor)
            self.saved_cursor = None

    def on_cursor_enter(self, event):
        self.saved_cursor = self.figure.canvas.GetCursor()
        self.figure.canvas.SetCursor(wx.StockCursor(wx.CURSOR_CROSS))

    def _onSize(self, event):
        self._SetSize()

    def _SetSize(self):
        pixels = tuple(self.GetClientSize())
        self.SetSize(pixels)
        self.canvas.SetSize(pixels)
        self.figure.set_size_inches(float(pixels[0])/self.figure.get_dpi(),
                                    float(pixels[1])/self.figure.get_dpi())
        self.set_and_get_xy_limits()

    def redraw_primary_image(self, msg=None):
        if msg is True or self.ztv_frame._pause_redraw_image:
            return
        if hasattr(self, 'axes_image'):
            if self.axes_image in self.axes.images:
                self.axes.images.remove(self.axes_image)
        self.axes_image = self.axes.imshow(self.ztv_frame.normalize(self.ztv_frame.display_image),
                                           interpolation='Nearest', 
                                           cmap=self.ztv_frame.get_cmap_to_display(), zorder=0)
        clear_ticks_and_frame_from_axes(self.axes)
        self.set_and_get_xy_limits()
        # self.figure.canvas.draw() is not needed here, b/c called from within set_and_get_xy_limits


class OverviewImagePanel(wx.Panel):
    def __init__(self, parent, size=wx.Size(128,128), dpi=None, **kwargs):
        self.size = size
        self.dragging_curview_is_active = False
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, size, 0, **kwargs)
        self.ztv_frame = self.GetTopLevelParent()
        self.figure = Figure(None, dpi)
        self.axes = self.figure.add_axes([0., 0., 1., 1.])
        self.curview_rectangle = Rectangle((0, 0), 1, 1, color='green', fill=False, zorder=100)
        self.axes.add_patch(self.curview_rectangle)
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.overview_zoom_factor = 1.
        self._SetSize()
        self.set_xy_limits()
        self.axes_widget = AxesWidget(self.figure.gca())
        self.axes_widget.connect_event('button_press_event', self.on_button_press)
        self.axes_widget.connect_event('button_release_event', self.on_button_release)
        self.axes_widget.connect_event('motion_notify_event', self.on_motion)
        pub.subscribe(self.redraw_overview_image, 'redraw-image')   
        pub.subscribe(self.redraw_box, 'primary-xy-limits-changed')

    def redraw_box(self, msg=None):
        xlim = self.ztv_frame.primary_image_panel.xlim
        ylim = self.ztv_frame.primary_image_panel.ylim
        self.curview_rectangle.set_bounds(xlim[0], ylim[0], xlim[1] - xlim[0], ylim[1] - ylim[0])
        self.figure.canvas.draw()

    def on_button_press(self, event):
        if event.dblclick: 
            self.ztv_frame.primary_image_panel.reset_zoom_and_center()
        else:
            if self.curview_rectangle.contains(event)[0]:
                self.dragging_curview_is_active = True
                self.convert_x_to_xdata = lambda x: (x / self.overview_zoom_factor) + self.xlim[0]
                self.convert_y_to_ydata = lambda y: (y / self.overview_zoom_factor) + self.ylim[0]
                self.dragging_cursor_xdata0 = self.convert_x_to_xdata(event.x)
                self.dragging_cursor_ydata0 = self.convert_y_to_ydata(event.y)
                self.dragging_rect_xdata0 = self.ztv_frame.primary_image_panel.center.x
                self.dragging_rect_ydata0 = self.ztv_frame.primary_image_panel.center.y
                self.convert_dragging_x_to_new_center_x = lambda x: ((self.convert_x_to_xdata(x) -
                                                                      self.dragging_cursor_xdata0) +
                                                                     self.dragging_rect_xdata0)
                self.convert_dragging_y_to_new_center_y = lambda y: ((self.convert_y_to_ydata(y) -
                                                                      self.dragging_cursor_ydata0) +
                                                                     self.dragging_rect_ydata0)

    def on_button_release(self, event):
        self.dragging_curview_is_active = False

    def on_motion(self, event):
        if self.dragging_curview_is_active:
            new_center_x = self.convert_dragging_x_to_new_center_x(event.x)
            new_center_y = self.convert_dragging_y_to_new_center_y(event.y)
            new_center_x_constrained = min(max(new_center_x, self.xlim[0]), self.xlim[1])
            new_center_y_constrained = min(max(new_center_y, self.ylim[0]), self.ylim[1])
            if np.sqrt((new_center_x - new_center_x_constrained) ** 2 +
                       (new_center_y - new_center_y_constrained) ** 2) >= 100:
                new_center_x = self.dragging_rect_xdata0
                new_center_y = self.dragging_rect_ydata0
            else:
                new_center_x = new_center_x_constrained
                new_center_y = new_center_y_constrained
            self.ztv_frame.primary_image_panel.center.x = new_center_x
            self.ztv_frame.primary_image_panel.center.y = new_center_y
            self.ztv_frame.primary_image_panel.set_and_get_xy_limits()

    def _SetSize(self):
        self.SetSize(tuple(self.size))
        self.canvas.SetSize(tuple(self.size))
        self.figure.set_size_inches(float(self.size[0])/self.figure.get_dpi(),
                                    float(self.size[1])/self.figure.get_dpi())

    def set_xy_limits(self):
        max_zoom_x = self.size.x / float(self.ztv_frame.display_image.shape[1])
        max_zoom_y = self.size.y / float(self.ztv_frame.display_image.shape[0])
        self.overview_zoom_factor = min(max_zoom_x, max_zoom_y)
        x_cen = (self.ztv_frame.display_image.shape[1] / 2.) - 0.5
        y_cen = (self.ztv_frame.display_image.shape[0] / 2.) - 0.5
        halfXsize = self.size.x / (self.overview_zoom_factor * 2.)
        halfYsize = self.size.y / (self.overview_zoom_factor * 2.)
        self.xlim = (x_cen - halfXsize, x_cen + halfXsize)
        self.ylim = (y_cen - halfYsize, y_cen + halfYsize)
        self.axes.set_xlim(self.xlim)
        self.axes.set_ylim(self.ylim)
        
    def redraw_overview_image(self, msg=None):
        if msg is True or self.ztv_frame._pause_redraw_image:
            return
        if hasattr(self, 'axes_image'):
            if self.axes_image in self.axes.images:
                self.axes.images.remove(self.axes_image)
        # note that following is not an actual rebin, but a sub-sampling, which is what matplotlib ultimately
        # would do on its own anyway if we gave it the full image.  But, matplotlib takes longer.  For a 2Kx2K
        # image, this saves almost 0.3sec on a ~2014 MacBookProRetina
        max_rebin_x = float(self.ztv_frame.display_image.shape[1]) / self.size.x
        max_rebin_y = float(self.ztv_frame.display_image.shape[0]) / self.size.y
        rebin_factor = np.int(np.floor(min([max_rebin_x, max_rebin_y])))
        self.axes_image = self.axes.imshow(self.ztv_frame.normalize(self.ztv_frame.display_image)[::rebin_factor, 
                                                                                                  ::rebin_factor],
                                           interpolation='Nearest', vmin=0., vmax=1.,
                                           extent=[0., self.ztv_frame.display_image.shape[0], 
                                                   self.ztv_frame.display_image.shape[1], 0.],
                                           cmap=self.ztv_frame.get_cmap_to_display(), zorder=0)
        clear_ticks_and_frame_from_axes(self.axes)
        self.set_xy_limits()
        self.figure.canvas.draw()


class LoupeImagePanel(wx.Panel):
    def __init__(self, parent, size=wx.Size(128,128), dpi=None, **kwargs):
        self.size = size
        self.size_npix_xy = wx.Size(11, 11)
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, size, 0, **kwargs)
        self.ztv_frame = self.GetTopLevelParent()
        self.figure = Figure(None, dpi)
        self.axes = self.figure.add_axes([0., 0., 1., 1.])
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self._SetSize()
        self.set_xy_limits()
        pub.subscribe(self.redraw_loupe_image, 'redraw-image') 

    def _SetSize(self):
        self.SetSize(tuple(self.size))
        self.canvas.SetSize(tuple(self.size))
        self.figure.set_size_inches(float(self.size[0])/self.figure.get_dpi(),
                                    float(self.size[1])/self.figure.get_dpi())

    def set_xy_limits(self, center=wx.Point(-9999, -9999)):
        self.axes.set_xlim([center[0] - self.size_npix_xy[0]/2.0, center[0] + self.size_npix_xy[0]/2.0])
        self.axes.set_ylim([center[1] - self.size_npix_xy[1]/2.0, center[1] + self.size_npix_xy[1]/2.0])
        if getattr(self, "crosshair", None) is None:
            self.crosshair = self.axes.plot([center[0]], [center[1]], 'gx', zorder=100, markersize=7)
        else:
            self.crosshair[0].set_data([center[0]], [center[1]])
        self.figure.canvas.draw()

    def redraw_loupe_image(self, msg=None):
        if msg is True or self.ztv_frame._pause_redraw_image:
            return
        if hasattr(self, 'axes_image'):
            if self.axes_image in self.axes.images:
                self.axes.images.remove(self.axes_image)
        self.axes_image = self.axes.imshow(self.ztv_frame.normalize(self.ztv_frame.display_image),
                                           interpolation='Nearest',
                                           cmap=self.ztv_frame.get_cmap_to_display(), zorder=0)
        clear_ticks_and_frame_from_axes(self.axes)
        self.figure.canvas.draw()  # bulk of time in method is spent in this line: TODO: look for ways to make faster


class ControlsNotebook(wx.Notebook):
    # see "Book" Controls -> Notebook example in wxpython demo
    def __init__(self, parent):
        wx.Notebook.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0)  
        self.highlight_char = unichr(0x2022)
        self._prior_notebook_page_change = (None, None)
        self.ztv_frame = self.GetTopLevelParent()
        self.ztv_frame.control_panels = []  # list of currently loaded/visible control panels, in order of display
        for cur_title, cur_panel in self.ztv_frame.control_panels_to_load:
            self.AddPanelAndStoreID(cur_panel(self), cur_title)
        
    def AddPanelAndStoreID(self, panel, text, **kwargs):
        new_page_image_id = len(self.ztv_frame.control_panels)
        setattr(panel, 'ztv_page_id', new_page_image_id)
        setattr(panel, 'ztv_display_name', text)
        setattr(panel, 'ztv_ref_name', text.lower() + '_panel')
        setattr(panel, 'highlight_panel', lambda : self._highlight_page(panel))
        setattr(panel, 'select_panel', lambda : self.SetSelection(panel.ztv_page_id))
        setattr(self.ztv_frame, text.lower() + '_panel', panel)
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.notebook_page_changed)
        self.AddPage(panel, text)
        self.ztv_frame.control_panels.append(panel)
    
    def notebook_page_changed(self, evt):
        oldnew = (evt.GetOldSelection(), evt.GetSelection())
        # EVT_NOTEBOOK_PAGE_CHANGED seems to be called 4-5 or more times per actual change, with identical
        #     OldSelection,Selection; so, need to filter those additional calls out after first one
        if oldnew != self._prior_notebook_page_change:
            if hasattr(self.ztv_frame.control_panels[oldnew[1]], 'on_activate'):
                self.ztv_frame.control_panels[oldnew[1]].on_activate()
            self._prior_notebook_page_change = oldnew
        evt.Skip()
    
    def clear_highlights(self):
        for cur_id in range(len(self.ztv_frame.control_panels)):
            if self.GetPageText(cur_id).startswith(self.highlight_char):
                self.SetPageText(cur_id, self.GetPageText(cur_id)[1:])

    def _highlight_page(self, panel=None):
        self.clear_highlights()
        if panel is not None:
            new_name = self.highlight_char + self.GetPageText(panel.ztv_page_id)
            self.SetPageText(panel.ztv_page_id, new_name)

            
class ZTVFrame(wx.Frame):
    def __init__(self, title=None, launch_listen_thread=False, control_panels_to_load=None,
                 default_data_dir=None, default_autoload_pattern=None):
        self.__version__ = version=about["__version__"]
        self.ztv_frame_pid = os.getpid()  # some add-on control panels will want this to pass to subprocs for knowing when to kill themselves, but NOTE: currently (as of 2015-04-13) on OS X is not working right as process doesn't die fully until uber-python session is killed.
        if title is None:
            self.base_title = 'ztv'
        else:
            self.base_title = title
        if default_data_dir is None:
            default_data_dir = os.getcwd()
        if default_autoload_pattern is None:
            default_autoload_pattern = os.getcwd()        
        self.default_data_dir = default_data_dir
        self.default_autoload_pattern = default_autoload_pattern
        if control_panels_to_load is None:
            from .default_panels import control_panels_to_load
        self.control_panels_to_load = control_panels_to_load
        wx.Frame.__init__(self, None, title=self.base_title, pos=wx.DefaultPosition, size=wx.Size(1024,512),
                          style = wx.DEFAULT_FRAME_STYLE)
        pub.subscribe(self.kill_ztv, 'kill-ztv')
        pub.subscribe(self.load_numpy_array, 'load-numpy-array')
        pub.subscribe(self.load_fits_file, 'load-fits-file')
        pub.subscribe(self.load_default_image, 'load-default-image')
        self._pause_redraw_image = False
        self.cur_fitsfile_basename = ''
        self.cur_fitsfile_path = ''
        self.image_process_functions_to_apply = []  # list of tuples of ('NameOrLabelIdentifier', fxn), where fxn must accept the image and return the processed image
        self.raw_image = np.zeros([2, 2])   # underlying raw data, can be 2-d [y,x] or 3-d [z,y,x]
        self.proc_image = self.raw_image.copy()     # raw_image processed with currently selected flat/sky/etc
        self.cur_display_frame_num = 0              # ignored if raw_image/proc_image is 2-d, otherwise 
                                                    # display_image is proc_image[self.cur_display_frame_num,:,:]
        self.display_image = self.proc_image.copy()  # 2-d array of what is currently displayed on-screen
        # display_image is primarily different from proc_image in that proc_image can be 3-d, while 
        # display_image is always 2-d
        self.normalized_image = None  # this will be display_image clipped to clim and scaled (e.g. Linear/Log)
        self._need_to_recalc_normalization = False
        self._norm = None
        self._scaling = None
        self.available_cmaps = ColorMaps().basic()
        self.cmap = 'jet'  # will go back to gray later
        self.is_cmap_inverted = False
        self.accelerator_table = []  # keyboard accelerators, e.g. cmd-Q
        self.zoom_factor = 2.0
        pub.subscribe(self.invert_cmap, 'invert-cmap')
        pub.subscribe(self.set_cmap, 'set-cmap')
        pub.subscribe(self.set_cmap_inverted, 'set-cmap-inverted')
        self.clim = [0.0, 1.0]
        pub.subscribe(self.set_clim_to_minmax, 'set-clim-to-minmax')
        pub.subscribe(self.set_clim_to_auto, 'set-clim-to-auto')
        pub.subscribe(self.set_clim_to_auto_stats_box, 'set-clim-to-auto-stats-box')
        pub.subscribe(self.set_clim, 'set-clim')
        pub.subscribe(self.set_scaling, 'set-scaling')
        pub.subscribe(self.set_norm, 'clim-changed')
        pub.subscribe(self.set_norm, 'scaling-changed')
        pub.subscribe(self.recalc_proc_image, 'image-process-functions-to-apply-changed')
        pub.subscribe(self.set_cur_display_frame_num, 'set-cur-display-frame-num') 
        pub.subscribe(self.set_window_title, 'set-window-title')
        self.scaling = 'Linear'
        self.available_scalings = ['Linear', 'Asinh', 'Log', 'PowerDist', 'Sinh', 'Sqrt', 'Squared']
        # scalings that require inputs & need additional work to implement:  
        #      'AsymmetricPercentile', 'ContrastBias', 'HistEq', 'Power'
        # don't bother implementing these unless strong case is made they're needed in a way that existing can't satisfy
        self.available_value_modes_on_new_image = ['data-min/max', 'auto', 'auto-stats-box', 'constant']
        self.min_value_mode_on_new_image = 'data-min/max'
        self.max_value_mode_on_new_image = 'data-min/max'
        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.primary_image_panel = PrimaryImagePanel(self)
        self.primary_image_panel.SetMinSize(wx.Size(256, 256))
        self.main_sizer.Add(self.primary_image_panel, 1, wx.EXPAND | wx.ALL, border=5)
        self.controls_sizer = wx.BoxSizer(wx.VERTICAL)
        self.controls_sizer.SetMinSize(wx.Size(512, -1))
        self.controls_images_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.overview_image_panel = OverviewImagePanel(self)
        self.controls_images_sizer.Add(self.overview_image_panel, 0, wx.ALL, border=5)
        self.loupe_image_panel = LoupeImagePanel(self)
        self.controls_images_sizer.Add(self.loupe_image_panel, 0, wx.BOTTOM|wx.RIGHT|wx.TOP, border=5)
        
        self.frame_number_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.frame_number_fullleft_button = wx.Button(self, -1, unichr(0x21e4), style=wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, lambda x: self.set_cur_display_frame_num(0), self.frame_number_fullleft_button)
        self.frame_number_sizer.Add(self.frame_number_fullleft_button, 0, wx.ALIGN_CENTER_VERTICAL)

        self.frame_number_left_button = wx.Button(self, -1, unichr(0x2190), style=wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, lambda x: self.set_cur_display_frame_num(-1, True), self.frame_number_left_button)
        self.frame_number_sizer.Add(self.frame_number_left_button, 0, wx.ALIGN_CENTER_VERTICAL)

        textentry_font = wx.Font(14, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT, False)
        self.frame_number_textctrl = wx.TextCtrl(self, wx.ID_ANY, '0', wx.DefaultPosition, wx.Size(40, 21),
                                       wx.TE_PROCESS_ENTER|wx.TE_CENTRE)
        self.frame_number_textctrl.SetFont(textentry_font)
        self.frame_number_sizer.Add(self.frame_number_textctrl, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.frame_number_textctrl.Bind(wx.EVT_TEXT, self.frame_number_textctrl_changed)
        self.frame_number_textctrl.Bind(wx.EVT_TEXT_ENTER, self.frame_number_textctrl_entered)

        self.frame_number_right_button = wx.Button(self, -1, unichr(0x2192), style=wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, lambda x: self.set_cur_display_frame_num(1, True), self.frame_number_right_button)
        self.frame_number_sizer.Add(self.frame_number_right_button, 0, wx.ALIGN_CENTER_VERTICAL)

        self.frame_number_fullright_button = wx.Button(self, -1, unichr(0x21e5), style=wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, lambda x: self.set_cur_display_frame_num(-1), self.frame_number_fullright_button)
        self.frame_number_sizer.Add(self.frame_number_fullright_button, 0, wx.ALIGN_CENTER_VERTICAL)

        self.total_frame_numbers_text = wx.StaticText(self, wx.ID_ANY, u"of 9999", wx.DefaultPosition, 
                                                      wx.DefaultSize, 0 )
        self.total_frame_numbers_text.Wrap( -1 )
        self.frame_number_sizer.Add(self.total_frame_numbers_text, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.controls_images_sizer.AddSpacer((0, 0), 1, wx.EXPAND, 0)
        self.controls_images_sizer.Add(self.frame_number_sizer, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM, 5)
        
        self.controls_sizer.Add(self.controls_images_sizer, 0, wx.EXPAND, border=5)
        self.controls_notebook_sizer = wx.BoxSizer(wx.VERTICAL)
        self.controls_notebook = ControlsNotebook(self)        
        self.controls_notebook_sizer.Add(self.controls_notebook, 1, wx.EXPAND | wx.ALL, border=0)
        self.controls_sizer.Add(self.controls_notebook_sizer, 1, wx.EXPAND, border=0)
        self.main_sizer.Add(self.controls_sizer, 0, wx.EXPAND, border=5)
        self.SetSizer(self.main_sizer)
        self.status_bar = self.CreateStatusBar()
        rw, rh = self.primary_image_panel.GetSize()
        sw, sh = self.controls_sizer.GetSize()
        fw, fh = self.GetSize()
        h = max(512, fh)
        w = h + fw - rw - (fh - rh)   # (fh - rh) accounts for status bar and window bar
        self.SetSize((w, h))
        self.Layout()
        self.Centre(wx.BOTH)
        self.load_default_image()
        self.cur_fits_hdulist = None
        if launch_listen_thread:
            self.command_listener_thread = CommandListenerThread(self)
        self.set_cmap((False, 'gray'))
        temp_id = wx.NewId()
        self.Bind(wx.EVT_MENU, self.kill_ztv, id=temp_id)
        self.accelerator_table.append((wx.ACCEL_CMD, ord('Q'), temp_id))
        self.accelerator_table.append((wx.ACCEL_CMD, ord('W'), temp_id))
        rightarrow_id = wx.NewId()
        self.Bind(wx.EVT_MENU, self.on_cmd_right_arrow, id=rightarrow_id)
        self.accelerator_table.append((wx.ACCEL_CMD, ord(']'), rightarrow_id))
        leftarrow_id = wx.NewId()
        self.Bind(wx.EVT_MENU, self.on_cmd_left_arrow, id=leftarrow_id)
        self.accelerator_table.append((wx.ACCEL_CMD, ord('['), leftarrow_id))
        for n in np.arange(1,10):
            new_id = wx.NewId()
            self.Bind(wx.EVT_MENU, self.create_on_cmd_alt_number(n), id=new_id)
            self.accelerator_table.append((wx.ACCEL_CMD|wx.ACCEL_ALT, ord(str(n)), new_id))
        self.SetAcceleratorTable(wx.AcceleratorTable(self.accelerator_table))
        self.Show()
                
    def create_on_cmd_alt_number(self, n):
        def on_cmd_alt_number(evt):
            try:
                self.controls_notebook.SetSelection(n - 1)
            except:
                pass  # if this page # doesn't exist...
        return on_cmd_alt_number

    def kill_ztv(self, msg=None):
        self.Close()

    def on_cmd_left_arrow(self, evt):
        self.controls_notebook.SetSelection((self.controls_notebook.GetSelection() - 1) % len(self.control_panels))

    def on_cmd_right_arrow(self, evt):
        self.controls_notebook.SetSelection((self.controls_notebook.GetSelection() + 1) % len(self.control_panels))

    def get_cmap_to_display(self):
        if self.is_cmap_inverted:
            if self.cmap.endswith('_r'):
                return self.cmap.replace('_r', '')
            else:
                return self.cmap + '_r'
        else:
            return self.cmap

    # Any method that calls redraw_image (or, more often, uses wx.CallAfter 
    # to send a redraw-image message) should accept a tuple msg input where
    # msg[0] is True/False of pause_redraw_image.
    # Routines should test (pause_redraw_image or self._pause_redraw_image) 
    # and *only* send redraw-image message if nothing is calling for Pause.
      
    def set_cmap_inverted(self, msg):
        """
        msg is tuple of two booleans:  (pause_redraw_image, is_cmap_inverted)
        """
        old_is_cmap_inverted = self.is_cmap_inverted
        pause_redraw_image, self.is_cmap_inverted = msg
        if old_is_cmap_inverted != self.is_cmap_inverted:
            wx.CallAfter(pub.sendMessage, 'is-cmap-inverted-changed', msg=None)
            if not (pause_redraw_image or self._pause_redraw_image):
                wx.CallAfter(pub.sendMessage, 'redraw-image', msg=False)

    def invert_cmap(self, msg=(False,)):
        """
        msg is (pause_redraw_image, )
        """
        self.set_cmap_inverted(((msg[0] or self._pause_redraw_image), not self.is_cmap_inverted))

    def set_cmap(self, msg):
        """
        Verify that requested cmap is in the list (or it's reversed equivalent) and set it

        msg is tuple:  (pause_redraw_image, new_cmap)
        """
        pause_redraw_image, new_cmap = msg
        old_cmap = self.cmap
        lower_available_cmaps = [a.lower() for a in self.available_cmaps]
        if new_cmap.lower() in lower_available_cmaps:
            self.cmap = self.available_cmaps[lower_available_cmaps.index(new_cmap.lower())]
            self.set_cmap_inverted(((pause_redraw_image or self._pause_redraw_image), False))
        elif new_cmap.replace('_r', '').lower() in lower_available_cmaps:
            self.cmap = self.available_cmaps[lower_available_cmaps.index(new_cmap.lower().replace('_r', ''))]
            self.set_cmap_inverted(((pause_redraw_image or self._pause_redraw_image), True))
        elif (new_cmap.lower() + '_r') in lower_available_cmaps:
            self.cmap = self.available_cmaps[lower_available_cmaps.index(new_cmap.lower() + '_r')]
            self.set_cmap_inverted(((pause_redraw_image or self._pause_redraw_image), True))
        else:
            sys.stderr.write("unrecognized cmap ({}) requested\n".format(new_cmap))
        if self.cmap != old_cmap:
            wx.CallAfter(pub.sendMessage, 'cmap-changed', msg=None)
            if not (pause_redraw_image or self._pause_redraw_image):
                wx.CallAfter(pub.sendMessage, 'redraw-image', msg=False)

    def set_clim(self, msg):
        """
        msg is tuple:  (pause_redraw_image, (clim[0], clim[1]))
        """
        pause_redraw_image, clim = msg
        old_clim = self.clim
        if clim[0] is None:
            clim[0] = self.clim[0]
        if clim[1] is None:
            clim[1] = self.clim[1]
        if clim[0] > clim[1]:
            self.clim = [clim[1], clim[0]]
            self.set_cmap_inverted(((pause_redraw_image or self._pause_redraw_image), not self.is_cmap_inverted))
        else:
            self.clim = clim
        if old_clim != self.clim:
            wx.CallAfter(pub.sendMessage, 'clim-changed', msg=((pause_redraw_image or self._pause_redraw_image),))

    def set_clim_to_minmax(self, msg=(False,)):
        """
        msg is tuple:  (pause_redraw_image, )
        """
        self.set_clim(((msg[0] or self._pause_redraw_image), 
                      [self.display_image.min(), self.display_image.max()]))

    def get_auto_clim_values(self, *args):
        """
        Set min/max of display to n_sigma_below and n_sigma_above background
        
        'cheat' for speed by sampling only a subset of pts
        """
        n_pts = 1000
        stepsize = self.display_image.size/n_pts
        robust_mean, robust_median, robust_stdev = sigma_clipped_stats(self.display_image.ravel()[0::stepsize])
        n_sigma_below = 1.0
        n_sigma_above = 6.
        return (robust_mean - n_sigma_below * robust_stdev, robust_mean + n_sigma_above * robust_stdev)

    def get_auto_stats_box_clim_values(self, *args):
        """
        Set min/max of display to n_sigma_below and n_sigma_above background in stats box
        
        'cheat' for speed by sampling only a subset of pts
        """
        n_pts = 1000
        if (isinstance(self.stats_panel.stats_info, dict) and 
            self.stats_panel.stats_info.has_key('xrange') and
            self.stats_panel.stats_info.has_key('yrange')):
            temp_image = self.display_image[min(self.stats_panel.stats_info['yrange']):
                                            max(self.stats_panel.stats_info['yrange']),
                                            min(self.stats_panel.stats_info['xrange']):
                                            max(self.stats_panel.stats_info['xrange'])] 
        else:
            temp_image = self.display_image
        stepsize = max([1, temp_image.size/n_pts])
        robust_mean, robust_median, robust_stdev = sigma_clipped_stats(temp_image.ravel()[0::stepsize])
        n_sigma_below = 1.0
        n_sigma_above = 6.
        return (robust_mean - n_sigma_below * robust_stdev, robust_mean + n_sigma_above * robust_stdev)

    def set_clim_to_auto_stats_box(self, msg=(False,)):
        """
        msg is tuple:  (pause_redraw_image, )
        """
        auto_clim = self.get_auto_stats_box_clim_values()
        self.set_clim(((msg[0] or self._pause_redraw_image), [auto_clim[0], auto_clim[1]]))

    def set_clim_to_auto(self, msg=(False,)):
        """
        msg is tuple:  (pause_redraw_image, )
        """
        auto_clim = self.get_auto_clim_values()
        self.set_clim(((msg[0] or self._pause_redraw_image), [auto_clim[0], auto_clim[1]]))

    def set_norm(self, msg=(False,)):
        """
        msg is tuple:  (pause_redraw_image, )
        """
        if self._norm is None or self.clim != self._set_norm_old_clim:
            self._norm = Normalize(vmin=self.clim[0], vmax=self.clim[1])
            self._set_norm_old_clim = self.clim
            self._need_to_recalc_normalization = True
        if self._scaling is None or self.scaling != self._set_norm_old_scaling:
            self._scaling = eval('astropy.visualization.' + self.scaling + 'Stretch()')
            self._set_norm_old_scaling = self.scaling
            self._need_to_recalc_normalization = True
        if not (msg[0] or self._pause_redraw_image):
            wx.CallAfter(pub.sendMessage, 'redraw-image', msg=False)

    def normalize(self, im):
        if self._need_to_recalc_normalization or self.normalized_image is None:
            self.normalized_image = self._scaling(self._norm(self.display_image))
            self._need_to_recalc_normalization = False
        return self.normalized_image

    def set_scaling(self, msg):
        """
        msg is (pause_redraw_image, scaling)
        """
        pause_redraw_image, scaling = msg
        available_scalings_lowercase = [a.lower() for a in self.available_scalings]
        if scaling.lower() in available_scalings_lowercase:
            self.scaling = self.available_scalings[available_scalings_lowercase.index(scaling.lower())]
            wx.CallAfter(pub.sendMessage, 'scaling-changed', msg=((pause_redraw_image or self._pause_redraw_image),))
        else:
            sys.stderr.write("unrecognized scaling ({}) requested\n".format(scaling))

    def frame_number_textctrl_changed(self, evt):
        validate_textctrl_str(self.frame_number_textctrl, int, str(self.cur_display_frame_num))
        
    def frame_number_textctrl_entered(self, evt):
        if validate_textctrl_str(self.frame_number_textctrl, int, str(self.cur_display_frame_num)):
            self.set_cur_display_frame_num(int(self.frame_number_textctrl.GetValue()))
            self.frame_number_textctrl.SetSelection(-1, -1)
        
    def set_cur_display_frame_num(self, msg, relative=False):
        """
        sets self.cur_display_frame_num to n  (with -1 meaning last, -2 second to last, etc)
        if relative=True, then increments by n.
        Will automatically bound to existing number of frames
        
        To ensure proper error checking & notifications, *all* changes to self.cur_display_frame_num
        should come through this method
        """
        if len(msg) == 2:
            n, flag = msg
            if flag == 'relative':
                relative = True
            elif flag == 'absolute':
                relative = False
        else:
            n = msg
        if self.proc_image.ndim == 2:
            cur_total_frames = 1
        else:
            cur_total_frames = self.proc_image.shape[0]
        if relative:
            n = self.cur_display_frame_num + n
        else:
            if n < 0:
                n = cur_total_frames + n
        n = min(max(0, n), cur_total_frames - 1)
        self.cur_display_frame_num = n
        self.frame_number_textctrl.SetValue("{}".format(n))
        set_textctrl_background_color(self.frame_number_textctrl, 'ok')
        self.recalc_display_image()

    def recalc_proc_image(self, msg=(False,)):
        """
        msg is (pause_redraw_image, )
        """
        self.proc_image = self.raw_image.copy()
        for cur_imageproc_label, cur_imageproc_fxn in self.image_process_functions_to_apply:
            self.proc_image = cur_imageproc_fxn(self.proc_image)
        self.recalc_display_image(msg=((msg[0] or self._pause_redraw_image),))
        wx.CallAfter(pub.sendMessage, 'recalc-proc-image-called',
                     msg=((msg[0] or self._pause_redraw_image),))

    def recalc_display_image(self, msg=(False,)):
        if self.proc_image.ndim == 2:
            self.display_image = self.proc_image.copy()
        elif self.proc_image.ndim == 3:
            # clip self.cur_display_frame_num to allowed range
            self.display_image = self.proc_image[min(max(0, self.cur_display_frame_num), 
                                                     self.proc_image.shape[0] - 1), :, :]
        else:
            raise Error("proc_image must be 2-d or 3-d, was instead {}-d".format(self.proc_image.ndim))
        new_min, new_max = None, None
        if self.min_value_mode_on_new_image == 'data-min/max':
            new_min = self.display_image.min()
        elif self.min_value_mode_on_new_image == 'auto':
            auto_clim_values = self.get_auto_clim_values()
            new_min = auto_clim_values[0]
        elif self.min_value_mode_on_new_image == 'auto-stats-box':
            auto_stats_box_clim_values = self.get_auto_stats_box_clim_values()
            new_min = auto_stats_box_clim_values[0]
        if self.max_value_mode_on_new_image == 'data-min/max':
            new_max = self.display_image.max()
        elif self.max_value_mode_on_new_image == 'auto':
            if self.min_value_mode_on_new_image != 'auto':  # only calculate if didn't already calculate above
                auto_clim_values = self.get_auto_clim_values()
            new_max = auto_clim_values[1]
        elif self.max_value_mode_on_new_image == 'auto-stats-box':
            if self.min_value_mode_on_new_image != 'auto-stats-box':  # only calculate if didn't already calculate above
                auto_stats_box_clim_values = self.get_auto_stats_box_clim_values()
            new_max = auto_stats_box_clim_values[1]
        self._need_to_recalc_normalization = True
        self.set_clim(((msg[0] or self._pause_redraw_image), [new_min, new_max]))
  
    def load_numpy_array(self, msg, is_fits_file=False):
        self._pause_redraw_image = True  # pause redrawing during loading so that don't redraw for every step of the way
        image = msg
        if not is_fits_file:
            self.cur_fits_hdulist = None
        if (image.ndim != 2) and (image.ndim != 3):
            sys.stderr.write("Only supports numpy arrays of 2-d or 3-d; " +
                             "tried to load a {}-d numpy array".format(image.ndim))
        else:
            need_to_reset_zoom_and_center = False
            self.cur_display_frame_num = 0
            old_2d_shape = self.raw_image.shape[-2:]
            new_2d_shape = image.shape[-2:]
            if new_2d_shape != old_2d_shape:
                need_to_reset_zoom_and_center = True
            self.raw_image = image  
            self.image_radec = None
            self.cur_fitsfile_basename = ''
            self.recalc_proc_image(msg=(self._pause_redraw_image,))
            if need_to_reset_zoom_and_center:
                self.primary_image_panel.reset_zoom_and_center()
            self.SetTitle(self.base_title)
            if self.raw_image.ndim == 2:
                self.frame_number_sizer.ShowItems(False)
            else:
                self.frame_number_sizer.ShowItems(True)
                self.frame_number_textctrl.SetValue('0')
                self.total_frame_numbers_text.SetLabel('of {}'.format(self.raw_image.shape[0]))
        self._pause_redraw_image = False
        wx.CallAfter(pub.sendMessage, 'redraw-image', msg=(self._pause_redraw_image,))

    def load_hdulist_from_fitsfile(self, filename):
        """
        The purpose of wrapping fits.open inside this routine is to put 
        all the warning suppressions, flags, etc in one place.
        """
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            max_n_tries = 5
            pause_time_between_tries_sec = 1.
            cur_try = 0
            not_yet_successful = True
            while (cur_try < max_n_tries) and not_yet_successful:
                try:
                    hdulist = fits.open(filename, ignore_missing_end=True)
                    not_yet_successful = False
                except:  # I've only seen IOerror, but might as well catch for all errors and re-try
                    time.sleep(pause_time_between_tries_sec)
                cur_try += 1
        return hdulist

    def set_window_title(self, msg=None):
        new_title = 'ztv'
        if len(self.cur_fitsfile_basename) > 0:
            sky_subtraction = 'sky-subtraction' in [a[0] for a in self.image_process_functions_to_apply]
            flat_division = 'flat-division' in [a[0] for a in self.image_process_functions_to_apply]
            new_title += ': ' 
            if flat_division:
                new_title += '('
            new_title += self.cur_fitsfile_basename            
            if sky_subtraction:
                new_title += ' - ' + os.path.basename(self.source_panel.sky_file_fullname)
            if flat_division:
                new_title += ') / ' + os.path.basename(self.source_panel.flat_file_fullname)
        self.SetTitle(new_title)

    def load_fits_file(self, msg):
        filename = msg
        if isinstance(filename, str) or isinstance(filename, unicode):
            if filename.lower().endswith('.fits') or filename.lower().endswith('.fits.gz'):
                if os.path.isfile(filename):
                    # TODO: be more flexible about hdulist where image data is NOT just [0].data
                    # TODO also, in case of extended fits files need to deal with additional header info
                    # following try/except handles situation when autoloading files tries to autoload a file 
                    #     before it's been fully written to disk.
                    max_n_tries = 5
                    pause_time_between_tries_sec = 1.
                    cur_try = 0
                    not_yet_successful = True
                    while (cur_try < max_n_tries) and not_yet_successful:
                        try:
                            self.cur_fits_hdulist = self.load_hdulist_from_fitsfile(filename)
                            self.load_numpy_array(self.cur_fits_hdulist[0].data, is_fits_file=True)
                            not_yet_successful = False
                        except:  # I've only seen ValueError, but might as well catch for all errors and re-try
                            time.sleep(pause_time_between_tries_sec)
                        cur_try += 1
                    self.cur_fitsfile_basename = os.path.basename(filename)
                    self.cur_fitsfile_path = os.path.abspath(os.path.dirname(filename))
                    self.set_window_title()
                    if (hasattr(self.primary_image_panel, 'cur_fits_header_dialog') and 
                        self.primary_image_panel.cur_fits_header_dialog.is_dialog_still_open):
                        raw_header_str = self.cur_fits_hdulist[0].header.tostring()
                        header_str = (('\n'.join([raw_header_str[i:i+80] for i in np.arange(0, len(raw_header_str), 80)
                                                  if raw_header_str[i:i+80] != " "*80])) + '\n')
                        self.primary_image_panel.cur_fits_header_dialog.SetTitle(self.cur_fitsfile_basename)
                        self.primary_image_panel.cur_fits_header_dialog.text.SetValue(header_str)
                        self.primary_image_panel.cur_fits_header_dialog.last_find_index = 0
                        self.primary_image_panel.cur_fits_header_dialog.on_search(None)
                    # TODO: better error handling for if WCS not available or partially available
                    try:
                        w = wcs.WCS(self.cur_fits_hdulist[0].header)
                        # TODO: (urgent) need to check ones/arange in following, do I have this reversed?
                        a = w.all_pix2world(
                                  np.outer(np.ones(self.raw_image.shape[-2]), 
                                           np.arange(self.raw_image.shape[-1])),
                                  np.outer(np.arange(self.raw_image.shape[-2]), 
                                           np.ones(self.raw_image.shape[-1])),
                                  0)
                        self.image_radec = ICRS(a[0]*units.degree, a[1]*units.degree)
                    except:  # just ignore radec if anything at all goes wrong.
                        self.image_radec = None
                    wx.CallAfter(pub.sendMessage, 'fitsfile-loaded', msg=filename)
                else:
                    raise Error("Cannot find file: {}".format(filename))
            else:
                raise Error("Requested filename ({}) does not end with .fits, .fits.gz, " +
                            "or other capitalization of those".format(filename))
        else:
            raise Error("load_fits_file requires string input, not type: {}".format(type(filename)))

    def get_default_image(self):
        imsize_x = 256
        imsize_y = 256
        im = np.sin(np.outer(np.arange(imsize_y), np.ones(imsize_x)) * np.pi / (imsize_y - 1.0))**3
        im *= np.sin(np.outer(np.ones(imsize_y), np.arange(imsize_x)) * np.pi / (imsize_x - 1.0))**3
        im *= np.angle(np.fft.fft2(np.sin(np.outer(np.arange(imsize_y), np.arange(imsize_x)) * 12*np.pi / min(imsize_x, imsize_y))))
        return im

    def load_default_image(self, msg=None):
        self.load_numpy_array(self.get_default_image())
        self.primary_image_panel.reset_zoom_and_center()


class WatchMasterPIDThread(threading.Thread):
    def __init__(self, masterPID):
        if masterPID > 0:  # don't start unless there's a valid process ID
            threading.Thread.__init__(self)
            self.masterPID = masterPID
            self.daemon = True
            self.start()

    def run(self):
        time.sleep(60)  # wait a full minute for launch before beginning to check for PID
        while psutil.pid_exists(self.masterPID):
            time.sleep(2)
        sys.stderr.write("\n\n----\nlooks like python session that owned this instance of the " +
                         "ZTV gui is gone, so disposing of the window\n----\n")
        wx.CallAfter(pub.sendMessage, 'kill-ztv', msg=None)


class CommandListenerThread(threading.Thread):
    def __init__(self, ztv_frame):
        """
        CommandListenerThread expects to be passed the main ZTVFrame object.  Access to the ZTVFrame must be used
        *very* carefully.  Essentially view this access as "readonly".  It's easy to screw things up with the gui if
        CommandListenerThread starts messing with parameters in ZTVFrame.  The appropriate way for CommandListenerThread
        to send commands to ZTVFrame is with a wx.CallAfter(pub.sendMessage....   call, e.g.:
            wx.CallAfter(pub.sendMessage, 'load-default-image', None)
        """
        threading.Thread.__init__(self)
        self.ztv_frame = ztv_frame
        self.daemon = True
        self.keep_running = True
        self.start()

    def run(self):
        stream_listener = StreamListener(sys.stdin)
        while self.keep_running:
            try:
                x = stream_listener.read_pickled_message(timeout=1.)
            except EOFError:  # means we are done here...
                return
            except StreamListenerTimeOut:
                pass
            else:
                if not isinstance(x, tuple):
                    raise Error("ListenThread only accepts tuples")
                wx.GetApp().ProcessIdle() # give time for any parameter changes to take effect
                if (x[0].startswith('get-') and 
                    hasattr(self.ztv_frame, x[0][4:].replace('-', '_')) and
                    not callable(getattr(self.ztv_frame, x[0][4:].replace('-', '_')))):
                    # catch the easiest cases where we just want some parameter out of ztv_frame, e.g.:
                    # ztv.frame_cmap is returned by the request message 'get-cmap'
                    wx.CallAfter(send_to_stream, sys.stdout, (x[0][4:], 
                                                              getattr(self.ztv_frame, x[0][4:].replace('-', '_'))))
                elif x[0] == 'get-xy-center':
                    wx.CallAfter(send_to_stream, sys.stdout, 
                                 (x[0][4:], (self.ztv_frame.primary_image_panel.center.x,
                                             self.ztv_frame.primary_image_panel.center.y)))
                # TODO: the following N elif statements accessing/controlling source_panel elements is ripe for some sort of sensible refactoring
                elif x[0] == 'set-sky-subtraction-status':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        if x[1]:
                            self.ztv_frame.source_panel.load_sky_subtraction_to_process_stack()
                        else:
                            self.ztv_frame.source_panel.unload_sky_subtraction_from_process_stack()
                elif x[0] == 'set-sky-subtraction-filename':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        self.ztv_frame.source_panel.load_sky_frame(x[1])
                elif x[0] == 'get-sky-subtraction-status-and-filename':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        sky_subtraction_loaded = False
                        if 'sky-subtraction' in [a[0] for a in self.ztv_frame.image_process_functions_to_apply]:
                            sky_subtraction_loaded = True
                        wx.CallAfter(send_to_stream, sys.stdout, 
                                     (x[0][4:], (sky_subtraction_loaded, 
                                                 self.ztv_frame.source_panel.sky_file_fullname)))
                    else:
                        send_to_stream(sys.stdout, (x[0][4:], 'source_panel not available'))
                elif x[0] == 'set-flat-division-status':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        if x[1]:
                            self.ztv_frame.source_panel.load_flat_division_to_process_stack()
                        else:
                            self.ztv_frame.source_panel.unload_flat_division_from_process_stack()
                elif x[0] == 'set-flat-division-filename':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        self.ztv_frame.source_panel.load_flat_frame(x[1])
                elif x[0] == 'get-flat-division-status-and-filename':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        flat_division_loaded = False
                        if 'flat-division' in [a[0] for a in self.ztv_frame.image_process_functions_to_apply]:
                            flat_division_loaded = True
                        wx.CallAfter(send_to_stream, sys.stdout, 
                                     (x[0][4:], 
                                      (flat_division_loaded, 
                                       self.ztv_frame.source_panel.flatfile_file_picker.current_textctrl_GetValue())))
                    else:
                        send_to_stream(sys.stdout, (x[0][4:], 'source_panel not available'))
                elif x[0] == 'set-autoload-filename-pattern-status':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        if x[1]:
                            self.ztv_frame.source_panel.launch_autoload_filematch_thread()
                            self.ztv_frame.source_panel.autoload_mode = 'file-match'
                        else:
                            self.ztv_frame.source_panel.kill_autoload_filematch_thread()
                            self.ztv_frame.source_panel.autoload_mode = None
                elif x[0] == 'set-autoload-filename-pattern':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        self.ztv_frame.source_panel.autoload_curfile_file_picker_on_load(x[1])
                elif x[0] == 'get-autoload-status-and-filename-pattern':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        wx.CallAfter(send_to_stream, sys.stdout, 
                                     (x[0][4:], 
                                      (self.ztv_frame.source_panel.autoload_mode == 'file-match',
                                       self.ztv_frame.source_panel.autoload_match_string)))
                    else:
                        send_to_stream(sys.stdout, (x[0][4:], 'source_panel not available'))
                elif x[0] == 'set-autoload-pausetime':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        i = np.abs(np.array(self.ztv_frame.source_panel.autoload_pausetime_choices) - 
                                   float(x[1])).argmin()
                        self.ztv_frame.source_panel.autoload_pausetime = self.ztv_frame.source_panel.autoload_pausetime_choices[i]
                        self.ztv_frame.source_panel.autoload_pausetime_choice.SetSelection(i)
                elif x[0] == 'get-autoload-pausetime':
                    if hasattr(self.ztv_frame, 'source_panel'):
                        wx.CallAfter(send_to_stream, sys.stdout, 
                                     (x[0][4:], self.ztv_frame.source_panel.autoload_pausetime))
                    else:
                        send_to_stream(sys.stdout, (x[0][4:], 'source_panel not available'))
                elif x[0] == 'set-new-slice-plot-xy0':
                    if hasattr(self.ztv_frame, 'plot_panel'):
                        wx.CallAfter(pub.sendMessage, 'new-slice-plot-xy0', msg=x[1])
                elif x[0] == 'set-new-slice-plot-xy1':
                    if hasattr(self.ztv_frame, 'plot_panel'):
                        wx.CallAfter(pub.sendMessage, 'new-slice-plot-xy1', msg=x[1])
                elif x[0] == 'get-slice-plot-coords':
                    if hasattr(self.ztv_frame, 'plot_panel'):
                        wx.CallAfter(send_to_stream, sys.stdout, 
                                     (x[0][4:], [[self.ztv_frame.plot_panel.start_pt.x, 
                                                  self.ztv_frame.plot_panel.start_pt.y], 
                                                 [self.ztv_frame.plot_panel.end_pt.x, 
                                                  self.ztv_frame.plot_panel.end_pt.y]]))
                    else:
                        send_to_stream(sys.stdout, (x[0][4:], 'plot_panel not available'))
                elif x[0] == 'hide-plot-panel-overplot':
                    if hasattr(self.ztv_frame, 'plot_panel'):
                        wx.CallAfter(self.ztv_frame.plot_panel.remove_overplot_on_image)
                elif x[0] == 'show-plot-panel-overplot':
                    if hasattr(self.ztv_frame, 'plot_panel'):
                        wx.CallAfter(self.ztv_frame.plot_panel.redraw_overplot_on_image)
                elif x[0] == 'set-stats-box-parameters':
                    if hasattr(self.ztv_frame, 'stats_panel'):
                        x0,x1,y0,y1 = [None]*4
                        if x[1]['xrange'] is not None:
                            x0,x1 = x[1]['xrange']
                        if x[1]['yrange'] is not None:
                            y0,y1 = x[1]['yrange']
                        if x[1]['xrange'] is not None or x[1]['yrange'] is not None:
                            wx.CallAfter(self.ztv_frame.stats_panel.update_stats_box, *[x0, y0, x1, y1])
                        if x[1]['show_overplot'] is not None:
                            if x[1]['show_overplot']:
                                self.ztv_frame.stats_panel.redraw_overplot_on_image()
                            else:
                                self.ztv_frame.stats_panel.remove_overplot_on_image()
                    send_to_stream(sys.stdout, (x[0] + '-done', True))
                elif x[0] == 'get-stats-box-info':
                    if hasattr(self.ztv_frame, 'stats_panel'):
                        wx.CallAfter(send_to_stream, sys.stdout, (x[0][4:], self.ztv_frame.stats_panel.stats_info))
                    else:
                        send_to_stream(sys.stdout, (x[0][4:], 'stats_panel not available'))
                elif x[0] == 'set-aperture-phot-parameters':
                    if hasattr(self.ztv_frame, 'phot_panel'):
                        if x[1]['xclick'] is not None:
                            self.ztv_frame.phot_panel.xclick = x[1]['xclick']
                        if x[1]['yclick'] is not None:
                            self.ztv_frame.phot_panel.yclick = x[1]['yclick']
                        if x[1]['radius'] is not None:
                            self.ztv_frame.phot_panel.aprad = x[1]['radius']
                        if x[1]['inner_sky_radius'] is not None:
                            self.ztv_frame.phot_panel.skyradin = x[1]['inner_sky_radius']
                        if x[1]['outer_sky_radius'] is not None:
                            self.ztv_frame.phot_panel.skyradout = x[1]['outer_sky_radius']
                        self.ztv_frame.phot_panel.recalc_phot()
                        if x[1]['show_overplot'] is not None:
                            if x[1]['show_overplot']:
                                self.ztv_frame.phot_panel.redraw_overplot_on_image()
                            else:
                                self.ztv_frame.phot_panel.remove_overplot_on_image()
                    send_to_stream(sys.stdout, (x[0] + '-done', True))
                elif x[0] == 'get-aperture-phot-info':
                    if hasattr(self.ztv_frame, 'phot_panel'):
                        phot_info = self.ztv_frame.phot_panel.phot_info.copy()
                        phot_info.pop('distances', None)
                        wx.CallAfter(send_to_stream, sys.stdout, (x[0][4:], phot_info))
                    else:
                        send_to_stream(sys.stdout, (x[0][4:], 'phot_panel not available'))
                elif x[0] == 'switch-to-control-panel':
                    name_lower = x[1].lower()
                    display_names_lower = [a.ztv_display_name.lower() for a in self.ztv_frame.control_panels]
                    if name_lower in display_names_lower:
                        self.ztv_frame.control_panels[display_names_lower.index(name_lower)].select_panel()
                else:
                    wx.CallAfter(pub.sendMessage, x[0], msg=x[1])


class ZTVMain():
    def __init__(self, title=None, masterPID=-1, launch_listen_thread=False, control_panels_to_load=None,
                 default_data_dir=None, default_autoload_pattern=None):
        self.__version__ = version=about["__version__"]
        WatchMasterPIDThread(masterPID)
        app = wx.App(False)
        self.frame = ZTVFrame(title=title, launch_listen_thread=launch_listen_thread,
                              control_panels_to_load=control_panels_to_load,
                              default_data_dir=default_data_dir, 
                              default_autoload_pattern=default_autoload_pattern)
        app.MainLoop()
        # TODO: need to figure out why ztvframe_pid is being left alive

if __name__ == '__main__':
    ZTVMain()
