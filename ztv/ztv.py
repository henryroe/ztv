import wx
from wx.lib.pubsub import Publisher
from wx.lib.pubsub.core.datamsg import Message
import  wx.lib.layoutf as layoutf
from FilePicker import FilePicker
import numpy as np
import threading
import psutil
import time
import os
import os.path
import sys
import pickle
import glob
import stomp
from astropy.io import fits
from astropy import wcs
from astropy.coordinates import ICRS
from astropy import units

import matplotlib
matplotlib.interactive(True)
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure
from matplotlib.widgets import AxesWidget
from matplotlib.patches import Rectangle
from matplotlib import cm
from matplotlib.colors import SymLogNorm, Normalize  #  TODO: add PowerNorm once upgraded to matplotlib 1.4

import pdb

# TODO:  fix that ctrl-c in ipython is killing ztv gui, even when run via a separate process with ztv_api

# TODO: add ability to do masked numpy arrays with different color value for masked positions

# TODO: design & implement global keyboard shortcuts, e.g. cmd-o for opening a file

# TODO (URGENT): work through lots of example fits file inputs and make more robust, e.g. barfing on nirspec and pharo data currently

# TODO:  re-consider which color maps to include, based on:  https://jakevdp.github.io/blog/2014/10/16/how-bad-is-your-colormap/

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


class FITSHeaderDialog(wx.Dialog):
    def __init__(self, parent, raw_header_str, caption,
                 pos=wx.DefaultPosition, size=(500,300),
                 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER):
        self.parent = parent
        wx.Dialog.__init__(self, parent, -1, caption, pos, size, style)
        x, y = pos
        if x == -1 and y == -1:
            self.CenterOnScreen(wx.BOTH)
        self.cur_selection = (0, 0)
        self.raw_header_str = raw_header_str
        self.text = text = wx.TextCtrl(self, -1, raw_header_str, style=wx.TE_MULTILINE | wx.TE_READONLY)

        font1 = wx.Font(12, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT, False)
        self.text.SetFont(font1)
        self.text.SetInitialSize((600,400))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, border=5)
        ok = wx.Button(self, wx.ID_OK, "OK")
        ok.SetDefault()
        ok.Bind(wx.EVT_BUTTON, self.on_close)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search = wx.SearchCtrl(self, size=(200, -1), style=wx.TE_PROCESS_ENTER)
        self.search.ShowSearchButton(True)
        self.search.ShowCancelButton(True)
        # TODO:  make layout of search & OK button prettier (OK should be right-aligned properly)
        buttons_sizer.Add(self.search, 0, wx.ALL | wx.EXPAND)
        buttons_sizer.Add((315, 0), 1, wx.EXPAND)
        buttons_sizer.Add(ok, 0, wx.ALL)
        main_sizer.Add(buttons_sizer, 0, wx.ALL, border=4)
        self.SetSizerAndFit(main_sizer)
        self.set_cur_selection()
        self.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.on_search, self.search)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_search, self.search)
        self.last_search_str = ''
        self.last_find_index = 0
        self.is_dialog_still_open = True
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, evt):
        self.is_dialog_still_open = False
        evt.Skip(True)

    def set_cur_selection(self):
        self.text.SetSelection(self.cur_selection[0], self.cur_selection[1])

    def on_search(self, evt):
        search_str = self.search.GetValue()
        if search_str != "":
            if search_str in self.raw_header_str:
                if search_str != self.last_search_str:
                    self.last_find_index = 0
                pos0 = self.raw_header_str.find(search_str, self.last_find_index)
                if pos0 == -1:
                    pos0 = self.raw_header_str.find(search_str)
                if pos0 - 80 < 0:
                    start_selection = 0
                else:
                    start_selection = self.raw_header_str.find('\n', pos0 - 80) + 1
                self.cur_selection = (start_selection,
                                      self.raw_header_str.find('\n', pos0))
                self.set_cur_selection()
                self.last_find_index = self.raw_header_str.find('\n', pos0)
                self.last_search_str = search_str
        else:
            self.last_search_str = ''


class PrimaryImagePanel(wx.Panel):
    def __init__(self, parent, dpi=None, **kwargs):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.Size(512,512), **kwargs)
        self.ztv_frame = self.GetTopLevelParent()
        self.center = wx.RealPoint()
        self.zoom_factor = 2.0
        self.zoom_box_active = False
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
        self.available_cursor_modes = [('None', self.set_cursor_to_none_mode),
                                       ('Zoom', self.set_cursor_to_zoom_mode),
                                       ('Pan', self.set_cursor_to_pan_mode)]
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
        Publisher().subscribe(self.redraw_image, "redraw_image")
        Publisher().subscribe(self.reset_zoom_and_center, "reset_zoom_and_center")
        Publisher().subscribe(self.set_zoom_factor, "set_zoom_factor")
        Publisher().subscribe(self.set_xy_center, "set_xy_center")

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
        for cursor_mode, fxn in self.available_cursor_modes:
            wx_id = wx.NewId()
            menu.AppendCheckItem(wx_id, '   ' + cursor_mode)
            wx.EVT_MENU(menu, wx_id, fxn)
            self.cursor_mode_to_eventID[cursor_mode] = wx_id
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
        self.popup_menu_fits_header_eventID = wx.NewId()
        self._append_menu_item(menu, self.popup_menu_fits_header_eventID, 'FITS Header',
                               self.on_display_fits_header)
        self.popup_menu = menu

    def on_display_fits_header(self, event):
        raw_header_str = self.ztv_frame.fits_header.tostring()
        header_str = (('\n'.join([raw_header_str[i:i+80] for i in np.arange(0, len(raw_header_str), 80)
                                  if raw_header_str[i:i+80] != " "*80])) + '\n')
        if hasattr(self, 'fits_header_dialog') and self.fits_header_dialog.is_dialog_still_open:
            self.fits_header_dialog.SetTitle(self.ztv_frame.cur_fitsfile_basename)
            self.fits_header_dialog.text.SetValue(header_str)
            self.fits_header_dialog.last_find_index = 0
            self.fits_header_dialog.on_search(None)
        else:
            self.fits_header_dialog = FITSHeaderDialog(self, header_str, self.ztv_frame.cur_fitsfile_basename)
            self.fits_header_dialog.Show()

    def set_and_get_xy_limits(self):
        num_x_pixels = self.canvas.GetSize().x
        halfsize = (num_x_pixels / 2.0) / self.zoom_factor
        xlim = (self.center.x - halfsize, self.center.x + halfsize)
        self.axes.set_xlim(xlim)
        num_y_pixels = self.canvas.GetSize().y
        halfsize = (num_y_pixels / 2.0) / self.zoom_factor
        ylim = (self.center.y - halfsize, self.center.y + halfsize)
        self.axes.set_ylim(ylim)
        self.figure.canvas.draw()
        send_change_message = True
        if xlim == self.xlim and ylim == self.ylim:
            send_change_message = False
        self.xlim, self.ylim = xlim, ylim
        if send_change_message:
            wx.CallAfter(Publisher().sendMessage, "primary_xy_limits-changed", None)
        return {'xlim':xlim, 'ylim':ylim}

    def set_cursor_to_none_mode(self, event):
        self.cursor_mode = 'None'

    def set_cursor_to_zoom_mode(self, event):
        self.cursor_mode = 'Zoom'

    def set_cursor_to_pan_mode(self, event):
        self.cursor_mode = 'Pan'

    def on_key_press(self, event):
        # TODO: figure out why keypresses are only recognized after a click in the matplotlib frame.
        if event.key in ['c', 'C', 'v', 'V', 'y', 'Y']:
            x = np.round(event.xdata)
            wx.CallAfter(Publisher().sendMessage, "update_line_plot_points", ((x + 0.5, -9e9), (x + 0.5, 9e9)))
        elif event.key in ['r', 'R', 'h', 'H', 'x', 'X']:
            y = np.round(event.ydata)
            wx.CallAfter(Publisher().sendMessage, "update_line_plot_points", ((-9e9, y + 0.5), (9e9, y + 0.5)))

    def set_xy_center(self, msg):
        if isinstance(msg, Message):
            xy = msg.data
        else:
            xy = msg
        self.center.x = xy[0]
        self.center.y = xy[1]
        self.set_and_get_xy_limits()

    def set_zoom_factor(self, msg):
        if isinstance(msg, Message):
            zoom_factor = msg.data
        else:
            zoom_factor = msg
        old_zoom_factor = self.zoom_factor
        if zoom_factor > 0.0:
            self.zoom_factor = zoom_factor
        if old_zoom_factor != self.zoom_factor:
            self.set_and_get_xy_limits()

    def reset_zoom_and_center(self, *args, **kwargs):
        self.center.x = (self.ztv_frame.image.shape[1] / 2.) - 0.5
        self.center.y = (self.ztv_frame.image.shape[0] / 2.) - 0.5
        max_zoom_x = self.canvas.GetSize().x / float(self.ztv_frame.image.shape[1])
        max_zoom_y = self.canvas.GetSize().y / float(self.ztv_frame.image.shape[0])
        self.zoom_factor = min(max_zoom_x, max_zoom_y)
        self.set_and_get_xy_limits()

    def on_change_cmap_event(self, event):
        wx.CallAfter(Publisher().sendMessage, "set_cmap", self.eventID_to_cmap[event.GetId()])

    def on_change_scaling_event(self, event):
        wx.CallAfter(Publisher().sendMessage, "set_scaling", self.eventID_to_scaling[event.GetId()])

    def on_motion(self, event):
        if event.xdata is None or event.ydata is None:
            return
        x = int(np.round(event.xdata))
        y = int(np.round(event.ydata))
        if self.zoom_box_active:
            self.zoom_rect.set_bounds(self.zoom_x0, self.zoom_y0,
                                      event.xdata - self.zoom_x0, event.ydata - self.zoom_y0)
            self.figure.canvas.draw()
        if ((x >= 0) and (x < self.ztv_frame.image.shape[1]) and
            (y >= 0) and (y < self.ztv_frame.image.shape[0])):
            imval = self.ztv_frame.image[y, x]
            new_status_string = "x,y={},{}".format(x, y)
            if self.ztv_frame.image_radec is not None:
                c = self.ztv_frame.image_radec[y, x]
                new_status_string += "  radec={0} {1}".format(c.ra.to_string(units.hour, sep=':', precision=2, pad=True),
                                                              c.dec.to_string(sep=':', precision=2, alwayssign=True, pad=True))
            new_status_string += "  val={:.5g}".format(imval)
            self.ztv_frame.status_bar.SetStatusText(new_status_string)
            self.ztv_frame.loupe_image_panel.set_xy_limits((x, y))
            # finally, catch for a situation where cursor should be active, but didn't enter, e.g. window launched under cursor
            if not hasattr(self, 'saved_cursor') or self.saved_cursor is None:
                self.on_cursor_enter(event)
        else:
            self.ztv_frame.status_bar.SetStatusText("")
            self.ztv_frame.loupe_image_panel.set_xy_limits()

    def on_button_press(self, event):
        if event.button == 1:  # left button
            if self.cursor_mode is 'Zoom':
                if event.dblclick:
                    self.center = wx.RealPoint(event.xdata, event.ydata)
                    self.zoom_factor /= 2.
                    self.set_and_get_xy_limits()
                else:
                    self.zoom_start_timestamp = event.guiEvent.GetTimestamp()  # millisec
                    self.zoom_box_active = True
                    self.zoom_x0 = event.xdata
                    self.zoom_y0 = event.ydata
                    self.zoom_rect = Rectangle((self.zoom_x0, self.zoom_y0), 0, 0,
                                               color='magenta', fill=False, zorder=100)
                    self.axes.add_patch(self.zoom_rect)
                    self.figure.canvas.draw()
            elif self.cursor_mode is 'Pan':
                self.center = wx.RealPoint(event.xdata, event.ydata)
                self.set_and_get_xy_limits()

    def on_button_release(self, event):
        if event.button == 1:  # left button
            if self.zoom_box_active:
                # this catches for the first click-release of a double-click
                if (event.guiEvent.GetTimestamp() - self.zoom_start_timestamp) > self.max_doubleclick_millisec:
                    # this catches for a long click-and-release without motion
                    if abs(self.zoom_x0 - event.xdata) >= 2 and abs(self.zoom_y0 - event.ydata) >= 2:
                        self.center = wx.RealPoint((self.zoom_x0 + event.xdata)/2., (self.zoom_y0 + event.ydata)/2.)
                        panel_size = self.canvas.GetSize()
                        x_zoom_factor = panel_size.x / abs(event.xdata - self.zoom_x0)
                        y_zoom_factor = panel_size.y / abs(event.ydata - self.zoom_y0)
                        self.zoom_factor = min(x_zoom_factor, y_zoom_factor)
                        self.set_and_get_xy_limits()
                self.zoom_box_active = False
                self.axes.patches.remove(self.zoom_rect)
                self.zoom_rect = None
                self.figure.canvas.draw()

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
        if self.ztv_frame.fits_header is None:
            self.popup_menu.Enable(self.popup_menu_fits_header_eventID, False)
        else:
            self.popup_menu.Enable(self.popup_menu_fits_header_eventID, True)
        self.figure.canvas.PopupMenuXY(self.popup_menu, event.x + 8,  event.y + 8)

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

    def redraw_image(self, *args):
        if hasattr(self, 'axes_image'):
            if self.axes_image in self.axes.images:
                self.axes.images.remove(self.axes_image)
        self.axes_image = self.axes.imshow(self.ztv_frame.image, interpolation='Nearest', norm=self.ztv_frame.norm,
                                           cmap=self.ztv_frame.get_cmap_to_display(), zorder=0)
        clear_ticks_and_frame_from_axes(self.axes)
        self.set_and_get_xy_limits()
        self.figure.canvas.draw()


class OverviewImagePanel(wx.Panel):
    def __init__(self, parent, size=wx.Size(128,128), dpi=None, **kwargs):
        self.size = size
        self.dragging_curview_is_active = False
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, size, 0, **kwargs)
        self.ztv_frame = self.GetTopLevelParent()
        self.figure = Figure(None, dpi)
        self.axes = self.figure.add_axes([0., 0., 1., 1.])
        self.curview_rectangle = Rectangle((0, 0), self.ztv_frame.image.shape[1], self.ztv_frame.image.shape[0],
                                           color='green', fill=False, zorder=100)
        self.axes.add_patch(self.curview_rectangle)
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self._SetSize()
        self.set_xy_limits()
        self.axes_widget = AxesWidget(self.figure.gca())
        self.axes_widget.connect_event('button_press_event', self.on_button_press)
        self.axes_widget.connect_event('button_release_event', self.on_button_release)
        self.axes_widget.connect_event('motion_notify_event', self.on_motion)
        Publisher().subscribe(self.redraw_image, "redraw_image")
        Publisher().subscribe(self.redraw_box, "primary_xy_limits-changed")

    def redraw_box(self, *args):
        xlim = self.ztv_frame.primary_image_panel.xlim
        ylim = self.ztv_frame.primary_image_panel.ylim
        self.curview_rectangle.set_bounds(xlim[0], ylim[0], xlim[1] - xlim[0], ylim[1] - ylim[0])
        self.figure.canvas.draw()

    def on_button_press(self, event):
        if event.dblclick:  # reset to fill primary_image_panel
            self.ztv_frame.primary_image_panel.reset_zoom_and_center()
        else:
            if self.curview_rectangle.contains(event)[0]:
                self.dragging_curview_is_active = True
                self.convert_x_to_xdata = lambda x: (x / self.zoom_factor) + self.xlim[0]
                self.convert_y_to_ydata = lambda y: (y / self.zoom_factor) + self.ylim[0]
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
        max_zoom_x = self.size.x / float(self.ztv_frame.image.shape[1])
        max_zoom_y = self.size.y / float(self.ztv_frame.image.shape[0])
        self.zoom_factor = min(max_zoom_x, max_zoom_y)
        x_cen = (self.ztv_frame.image.shape[1] / 2.) - 0.5
        y_cen = (self.ztv_frame.image.shape[0] / 2.) - 0.5
        halfXsize = self.size.x / (self.zoom_factor * 2.)
        halfYsize = self.size.y / (self.zoom_factor * 2.)
        self.xlim = (x_cen - halfXsize, x_cen + halfXsize)
        self.ylim = (y_cen - halfYsize, y_cen + halfYsize)
        self.axes.set_xlim(self.xlim)
        self.axes.set_ylim(self.ylim)

    def redraw_image(self, *args):
        if hasattr(self, 'axes_image'):
            if self.axes_image in self.axes.images:
                self.axes.images.remove(self.axes_image)
        self.axes_image = self.axes.imshow(self.ztv_frame.image, interpolation='Nearest', norm=self.ztv_frame.norm,
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
        Publisher().subscribe(self.redraw_image, "redraw_image")

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

    def redraw_image(self, *args):
        if hasattr(self, 'axes_image'):
            if self.axes_image in self.axes.images:
                self.axes.images.remove(self.axes_image)
        self.axes_image = self.axes.imshow(self.ztv_frame.image, interpolation='Nearest', norm=self.ztv_frame.norm,
                                           cmap=self.ztv_frame.get_cmap_to_display(), zorder=0)
        clear_ticks_and_frame_from_axes(self.axes)
        self.figure.canvas.draw()


class ColorControlPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        # TODO: figure out why min size is not being respected by comparing with the framebuilder example
        self.SetSizeHintsSz( wx.Size( 1024,512 ), wx.DefaultSize )
        self.eventID_to_cmap = {wx.NewId(): x for x in self.ztv_frame.available_cmaps}
        self.cmap_to_eventID = {self.eventID_to_cmap[x]: x for x in self.eventID_to_cmap}

        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        # TODO: add a histogram panel with click-and-drag min/max markers
        values_sizer = wx.FlexGridSizer( 3, 5, 0, 0 )
        values_sizer.SetFlexibleDirection( wx.BOTH )
        values_sizer.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

        self.minval_static_text = wx.StaticText( self, wx.ID_ANY, u"Min", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.minval_static_text.Wrap( -1 )
        values_sizer.Add(self.minval_static_text, 0, wx.ALL, 0)

        textentry_font = wx.Font(14, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT, False)

        self.minval_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_PROCESS_ENTER)
        self.minval_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.minval_textctrl, 0, wx.ALL, 2)
        self.minval_textctrl.Bind(wx.EVT_TEXT, self.minval_textctrl_changed)
        self.minval_textctrl.Bind(wx.EVT_TEXT_ENTER, self.minval_textctrl_entered)

        self.set_min_button = wx.Button(self, wx.ID_ANY, u"Min", wx.DefaultPosition, wx.DefaultSize, 0)
        values_sizer.Add(self.set_min_button, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.set_min_button.Bind(wx.EVT_BUTTON, self.on_set_min_button)
        # TODO: italicize "min" text on button if limits are at Auto
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        temp_list = self.ztv_frame.available_value_modes_on_new_image[:]
        temp_list[temp_list.index('data-min/max')] = 'min'
        self.choose_min_value_mode_on_new_image = wx.Choice(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                                            temp_list, 0)
        self.choose_min_value_mode_on_new_image.SetSelection(0)
        values_sizer.Add(self.choose_min_value_mode_on_new_image, 0,
                         wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.Bind(wx.EVT_CHOICE, self.on_choose_min_value_mode_on_new_image, self.choose_min_value_mode_on_new_image)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        self.auto_set_minmax_button = wx.Button(self, wx.ID_ANY, u"Auto", wx.DefaultPosition, wx.DefaultSize, 0)
        values_sizer.Add(self.auto_set_minmax_button, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.auto_set_minmax_button.Bind(wx.EVT_BUTTON, self.on_auto_set_minmax_button)
        # TODO: italicize "auto" text on button if limits are at Auto

        self.set_minmax_button = wx.Button(self, wx.ID_ANY, u"Min/Max", wx.DefaultPosition, wx.DefaultSize, 0)
        values_sizer.Add(self.set_minmax_button, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.set_minmax_button.Bind(wx.EVT_BUTTON, self.on_set_minmax_button)
        # TODO: italicize "min/max" text on button if limits are at Auto

        self.minval_static_text = wx.StaticText(self, wx.ID_ANY, u"On load image:",
                                                wx.DefaultPosition, wx.DefaultSize, 0 )
        self.minval_static_text.Wrap( -1 )
        values_sizer.Add(self.minval_static_text, 0, wx.ALL, 2)
        temp_list = self.ztv_frame.available_value_modes_on_new_image[:]
        temp_list[temp_list.index('data-min/max')] = 'min/max'
        temp_list.insert(0, '-'),
        self.choose_minmax_value_mode_on_new_image = wx.Choice(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                                               temp_list, 0)
        self.choose_minmax_value_mode_on_new_image.SetSelection(1)
        values_sizer.Add(self.choose_minmax_value_mode_on_new_image, 0,
                         wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.Bind(wx.EVT_CHOICE, self.on_choose_minmax_value_mode_on_new_image,
                  self.choose_minmax_value_mode_on_new_image)

        maxval_static_text = wx.StaticText( self, wx.ID_ANY, u"Max", wx.DefaultPosition, wx.DefaultSize, 0 )
        maxval_static_text.Wrap( -1 )
        values_sizer.Add(maxval_static_text, 0, wx.ALL, 2)

        self.maxval_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_PROCESS_ENTER)
        self.maxval_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.maxval_textctrl, 0, wx.ALL, 2)
        self.maxval_textctrl.Bind(wx.EVT_TEXT, self.maxval_textctrl_changed)
        self.maxval_textctrl.Bind(wx.EVT_TEXT_ENTER, self.maxval_textctrl_entered)

        self.set_max_button = wx.Button(self, wx.ID_ANY, u"Max", wx.DefaultPosition, wx.DefaultSize, 0)
        values_sizer.Add(self.set_max_button, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.set_max_button.Bind(wx.EVT_BUTTON, self.on_set_max_button)
        # TODO: italicize "max" text on button if limits are at Auto
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        temp_list = self.ztv_frame.available_value_modes_on_new_image[:]
        temp_list[temp_list.index('data-min/max')] = 'max'
        self.choose_max_value_mode_on_new_image = wx.Choice(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                                            temp_list, 0)
        self.choose_max_value_mode_on_new_image.SetSelection(0)
        values_sizer.Add(self.choose_max_value_mode_on_new_image, 0,
                         wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.Bind(wx.EVT_CHOICE, self.on_choose_max_value_mode_on_new_image, self.choose_max_value_mode_on_new_image)

        v_sizer1.Add(values_sizer, 0)
        v_sizer1.AddSpacer((0, 6), 0, 0)
        v_sizer1.Add(wx.StaticLine(self), flag=wx.EXPAND)
        v_sizer1.AddSpacer((0, 6), 0, 0)
        cmap_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.init_cmap_popup_menu()
        self.cmap_button = wx.Button(self, wx.ID_ANY, 'X'*max([len(a) for a in self.ztv_frame.available_cmaps]),
                                     wx.DefaultPosition, wx.DefaultSize, 0)
        self.cmap_button.SetBitmap(self.cmap_button_bitmaps[self.ztv_frame.cmap])
        cmap_sizer.Add(self.cmap_button, 0, wx.ALL|wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, 2)
        self.cmap_button.Bind(wx.EVT_LEFT_DOWN, self.on_cmap_button)
        cmap_options_sizer = wx.BoxSizer(wx.VERTICAL)
        self.is_cmap_inverted_checkbox = wx.CheckBox(self, -1, 'inverted', wx.DefaultPosition, wx.DefaultSize, 0)
        cmap_options_sizer.Add(self.is_cmap_inverted_checkbox, 0)
        self.Bind(wx.EVT_CHECKBOX, self.on_is_cmap_inverted_checkbox, self.is_cmap_inverted_checkbox)
        self.choose_scaling = wx.Choice(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                        self.ztv_frame.available_scalings, 0)
        self.choose_scaling.SetSelection(0)
        scaling_sizer = wx.BoxSizer(wx.HORIZONTAL)
        scaling_sizer.Add(wx.StaticText( self, wx.ID_ANY, u"Scaling", wx.DefaultPosition, wx.DefaultSize, 0 ), 0)
        scaling_sizer.Add(self.choose_scaling, 0)
        cmap_options_sizer.Add(scaling_sizer, 0)
        self.Bind(wx.EVT_CHOICE, self.on_choose_scaling, self.choose_scaling)
        cmap_sizer.Add(cmap_options_sizer, 0)
        v_sizer1.Add(cmap_sizer, 0)
        v_sizer1.AddSpacer((0, 0), 0, wx.EXPAND)
        self.SetSizer(v_sizer1)
        self.last_minval_string = ''
        self.last_maxval_string = ''
        Publisher().subscribe(self.on_clim_changed, "clim-changed")
        Publisher().subscribe(self.on_cmap_changed, "cmap-changed")
        Publisher().subscribe(self.on_is_cmap_inverted_changed, "is_cmap_inverted-changed")
        Publisher().subscribe(self.on_scaling_changed, "scaling-changed")
        self.Bind(wx.EVT_NAVIGATION_KEY, self.on_navigation_key)

    def on_choose_scaling(self, evt):
        wx.CallAfter(Publisher().sendMessage, "set_scaling", evt.GetString())

    def init_cmap_popup_menu(self):
        cmap_button_bitmap_height = 30
        cmap_button_bitmap_width = 200
        cmap_menu_bitmap_height = 20
        cmap_menu_bitmap_width = 200
        self.cmap_button_bitmaps = {}
        self.cmap_menu_bitmaps = {}
        for cmap in self.ztv_frame.available_cmaps:
            temp = cm.ScalarMappable(cmap=cmap)
            rgba = temp.to_rgba(np.outer(np.ones(cmap_button_bitmap_height, dtype=np.uint8),
                                         np.arange(cmap_button_bitmap_width, dtype=np.uint8)))
            self.cmap_button_bitmaps[cmap] = wx.BitmapFromBufferRGBA(cmap_button_bitmap_width, cmap_button_bitmap_height,
                                                                     np.uint8(np.round(rgba*255)))
            rgba = temp.to_rgba(np.outer(np.ones(cmap_menu_bitmap_height, dtype=np.uint8),
                                         np.arange(cmap_menu_bitmap_width, dtype=np.uint8)))
            self.cmap_menu_bitmaps[cmap] = wx.BitmapFromBufferRGBA(cmap_menu_bitmap_width, cmap_menu_bitmap_height,
                                                                   np.uint8(np.round(rgba*255)))
        menu = wx.Menu()
        for cmap in self.ztv_frame.available_cmaps:
            menu_item = menu.AppendCheckItem(self.cmap_to_eventID[cmap], cmap)
            wx.EVT_MENU(menu, self.cmap_to_eventID[cmap], self.on_change_cmap_event)
            menu_item.SetBitmap(self.cmap_menu_bitmaps[cmap])
        self.cmap_popup_menu = menu

    def on_change_cmap_event(self, event):
        wx.CallAfter(Publisher().sendMessage, "set_cmap", self.eventID_to_cmap[event.GetId()])

    def on_navigation_key(self, evt):
        # TODO: figure out how to make tab order work the way I want.  Currently the following code works partly, but is ignored by some tabs.  Weird. Looks like it's an issue that tab is triggering some *other* event when it's a button that has focus.  Might have to play around with catching all key-presses inside of ColorControlPanel & passing along the non-tab keypresses???
        tab_order = [self.minval_textctrl, self.maxval_textctrl,
                     self.auto_set_minmax_button,
                     self.set_min_button, self.set_minmax_button, self.set_max_button,
                     self.choose_min_value_mode_on_new_image,
                     self.choose_minmax_value_mode_on_new_image,
                     self.choose_max_value_mode_on_new_image]
        if evt.GetCurrentFocus() not in tab_order:
            new_focus = tab_order[0]
        else:
            if evt.GetDirection():
                direction = 1
            else:
                direction = -1
            new_focus = tab_order[(tab_order.index(evt.GetCurrentFocus()) + direction) % len(tab_order)]
        # following debugging line demonstrates that on_navigation_key is only being called when focus is on a textctrl, not when on a button or dropdown menu
#         sys.stderr.write("\n\nnew_focus = {}\n\n".format(new_focus))
        new_focus.SetFocus()

    def on_is_cmap_inverted_checkbox(self, evt):
        wx.CallAfter(Publisher().sendMessage, "set_cmap_inverted", evt.IsChecked())

    def on_is_cmap_inverted_changed(self, *args):
        self.is_cmap_inverted_checkbox.SetValue(self.ztv_frame.is_cmap_inverted)

    def on_scaling_changed(self, *args):
        self.choose_scaling.SetSelection(self.ztv_frame.available_scalings.index(self.ztv_frame.scaling))

    def on_cmap_button(self, evt):
        for cmap in self.ztv_frame.available_cmaps:
            self.cmap_popup_menu.Check(self.cmap_to_eventID[cmap], False)
        self.cmap_popup_menu.Check(self.cmap_to_eventID[self.ztv_frame.cmap], True)
        pos = self.ScreenToClient(wx.GetMousePosition())
        pos.y -= 90
        self.cmap_button.PopupMenu(self.cmap_popup_menu, pos)

    def on_choose_min_value_mode_on_new_image(self, evt):
        new_val = [a for a in self.ztv_frame.available_value_modes_on_new_image if
                   evt.GetString() in a][0]
        self.ztv_frame.min_value_mode_on_new_image = new_val
        if (self.choose_min_value_mode_on_new_image.GetSelection() ==
            self.choose_max_value_mode_on_new_image.GetSelection()):
            self.choose_minmax_value_mode_on_new_image.SetSelection( \
                        self.choose_min_value_mode_on_new_image.GetSelection() + 1)
        else:
            self.choose_minmax_value_mode_on_new_image.SetSelection(0)

    def on_choose_max_value_mode_on_new_image(self, evt):
        new_val = [a for a in self.ztv_frame.available_value_modes_on_new_image if
                   evt.GetString() in a][0]
        self.ztv_frame.max_value_mode_on_new_image = new_val
        if (self.choose_min_value_mode_on_new_image.GetSelection() ==
            self.choose_max_value_mode_on_new_image.GetSelection()):
            self.choose_minmax_value_mode_on_new_image.SetSelection( \
                        self.choose_min_value_mode_on_new_image.GetSelection() + 1)
        else:
            self.choose_minmax_value_mode_on_new_image.SetSelection(0)

    def on_choose_minmax_value_mode_on_new_image(self, evt):
        if evt.GetString != '':
            new_val = [a for a in self.ztv_frame.available_value_modes_on_new_image if
                       evt.GetString() in a][0]
            self.ztv_frame.min_value_mode_on_new_image = new_val
            self.ztv_frame.max_value_mode_on_new_image = new_val
            new_index = self.ztv_frame.available_value_modes_on_new_image.index(new_val)
            self.choose_min_value_mode_on_new_image.SetSelection(new_index)
            self.choose_max_value_mode_on_new_image.SetSelection(new_index)

    def on_auto_set_minmax_button(self, evt):
        self.ztv_frame.set_clim_to_auto()

    def on_set_minmax_button(self, evt):
        self.ztv_frame.set_clim_to_minmax()

    def on_set_min_button(self, evt):
        self.ztv_frame.set_clim([self.ztv_frame.image.min(), None])
        if self.FindFocus() == self.minval_textctrl:
            self.minval_textctrl.SetSelection(-1, -1)

    def on_set_max_button(self, evt):
        self.ztv_frame.set_clim([None, self.ztv_frame.image.max()])
        if self.FindFocus() == self.maxval_textctrl:
            self.maxval_textctrl.SetSelection(-1, -1)

    def force_textctrl_color_update(self, textctrl):
        cur_focused_item = self.FindFocus()
        insertion_point = textctrl.GetInsertionPoint()
        if textctrl == self.minval_textctrl:
            self.maxval_textctrl.SetFocus()
        else:
            self.minval_textctrl.SetFocus()
        textctrl.SetFocus()
        textctrl.SetInsertionPoint(insertion_point)
        if cur_focused_item is not None:
            cur_focused_item.SetFocus()

    def set_textctrl_background_color(self, textctrl_name, mode, tooltip=None):
        if mode == 'ok':
            color = (255,255,255)
        elif mode == 'enter-needed':
            color = (200,255,200)
        elif mode == 'invalid':
            # TODO:  implement: escape key brings up last valid value??
            color = (255,200,200)
        if textctrl_name == 'minval':
            cur_textctrl = self.minval_textctrl
        elif textctrl_name == 'maxval':
            cur_textctrl = self.maxval_textctrl
        cur_textctrl.SetBackgroundColour(color)
        cur_textctrl.Refresh()
        if tooltip is not None and not isinstance(tooltip, wx.ToolTip):
            tooltip = wx.ToolTip(tooltip)
        cur_textctrl.SetToolTip(tooltip)
        self.force_textctrl_color_update(cur_textctrl)

    def on_clim_changed(self, *args):
        new_minval_str = "{: .9g}".format(self.ztv_frame.clim[0])
        new_maxval_str = "{: .9g}".format(self.ztv_frame.clim[1])
        if new_minval_str != self.last_minval_string:
            self.minval_textctrl.SetValue(new_minval_str)
            self.set_textctrl_background_color('minval', 'ok')
            self.last_minval_string = new_minval_str
        if new_maxval_str != self.last_maxval_string:
            self.maxval_textctrl.SetValue(new_maxval_str)
            self.set_textctrl_background_color('maxval', 'ok')
            self.last_maxval_string = new_maxval_str

    def on_cmap_changed(self, *args):
        self.cmap_button.SetBitmap(self.cmap_button_bitmaps[self.ztv_frame.cmap])
        self.cmap_button.SetLabel(self.ztv_frame.cmap)

    def validate_minval_str(self):
        try:
            newval = float(self.minval_textctrl.GetValue())
            if self.minval_textctrl.GetValue() == self.last_minval_string:
                self.set_textctrl_background_color('minval', 'ok')
            else:
                self.set_textctrl_background_color('minval', 'enter-needed',
                                                   'Press enter in this field to set new minimum value')
            return True
        except ValueError:
            self.set_textctrl_background_color('minval', 'invalid', 'Entry cannot be converted to float')
            return False

    def minval_textctrl_changed(self, evt):
        self.validate_minval_str()

    def minval_textctrl_entered(self, evt):
        if self.validate_minval_str():
            self.last_minval_string = self.minval_textctrl.GetValue()
            self.ztv_frame.set_clim([float(self.minval_textctrl.GetValue()), None])
            self.minval_textctrl.SetSelection(-1, -1)

    def validate_maxval_str(self):
        try:
            newval = float(self.maxval_textctrl.GetValue())
            if self.maxval_textctrl.GetValue() == self.last_maxval_string:
                self.set_textctrl_background_color('maxval', 'ok')
            else:
                self.set_textctrl_background_color('maxval', 'enter-needed',
                                                   'Press enter in this field to set new maximum value')
            return True
        except ValueError:
            self.set_textctrl_background_color('maxval', 'invalid', 'Entry cannot be converted to float')
            return False

    def maxval_textctrl_changed(self, evt):
        self.validate_maxval_str()

    def maxval_textctrl_entered(self, evt):
        if self.validate_maxval_str():
            self.ztv_frame.set_clim([None, float(self.maxval_textctrl.GetValue())])
            self.maxval_textctrl.SetSelection(-1, -1)


class SourcePanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        Publisher().subscribe(self.on_fitsfile_loaded, "fitsfile-loaded")
        self.max_items_in_curfile_history = 20
        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        current_fits_file_static_text = wx.StaticText(self, wx.ID_ANY, u"Current FITS file:",
                                                      wx.DefaultPosition, wx.DefaultSize, 0 )
        current_fits_file_static_text.Wrap( -1 )
        v_sizer1.Add(current_fits_file_static_text, 0, wx.ALL, 0)
        self.curfile_filepicker = FilePicker(self, title='')
        self.curfile_filepicker.on_load = self.ztv_frame.load_fits_file
        v_sizer1.Add(self.curfile_filepicker, 0, wx.EXPAND)

        self.show_header_button = wx.Button(self, wx.ID_ANY, u"Show header", wx.DefaultPosition, wx.DefaultSize, 0)
        v_sizer1.Add(self.show_header_button, 0, wx.ALL|wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.show_header_button.Bind(wx.EVT_BUTTON, self.ztv_frame.primary_image_panel.on_display_fits_header)

        v_sizer1.AddSpacer((0, 10), 0, wx.EXPAND)
        v_sizer1.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 5)
        v_sizer1.AddSpacer((0, 5), 0, wx.EXPAND)

        self.autoload_checkbox = wx.CheckBox(self, -1, "Auto-load file")
        self.Bind(wx.EVT_CHECKBOX, self.on_autoload_checkbox, self.autoload_checkbox)
        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        h_sizer.Add(self.autoload_checkbox, 0)
        h_sizer.AddStretchSpacer(1)
        pausetime_index = self.ztv_frame.autoload_pausetime_choices.index(self.ztv_frame.autoload_pausetime)
        self.autoload_pausetime_choice = wx.Choice(self, wx.ID_ANY, wx.DefaultPosition, (50, -1),
                                                   [str(a) for a in self.ztv_frame.autoload_pausetime_choices], 0)
        self.autoload_pausetime_choice.SetSelection(pausetime_index)
        self.autoload_pausetime_choice.Bind(wx.EVT_CHOICE, self.on_choose_autoload_pausetime)
        h_sizer.Add(wx.StaticText(self, -1, u"Pause"), 0)
        h_sizer.Add(self.autoload_pausetime_choice, 0)
        h_sizer.Add(wx.StaticText(self, -1, u"sec"), 0)
        v_sizer1.Add(h_sizer, 0, wx.EXPAND)
        v_sizer1.AddSpacer((0, 5), 0, wx.EXPAND)
        self.autoload_curdir_filepicker = FilePicker(self, title='Dir:', is_files_not_dirs=False)
        v_sizer1.Add(self.autoload_curdir_filepicker, 0, wx.EXPAND)
        self.autoload_curfile_filepicker = FilePicker(self, title='Filename Pattern:', allow_glob_matching=True,
                                                      assumed_prefix='/Users/hroe/') # TODO: fix hardwiring of assumed_prefix
        self.autoload_curdir_filepicker.on_load = self.autoload_curfile_filepicker.set_assumed_prefix
        self.autoload_curfile_filepicker.on_load = self.autoload_curfile_filepicker_on_load

        v_sizer1.Add(self.autoload_curfile_filepicker, 0, wx.EXPAND)

        v_sizer1.AddSpacer((0, 10), 0, wx.EXPAND)
        v_sizer1.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 5)
        v_sizer1.AddSpacer((0, 5), 0, wx.EXPAND)

        self.message_queue_checkbox = wx.CheckBox(self, -1, "ActiveMQ")
        self.Bind(wx.EVT_CHECKBOX, self.on_message_queue_checkbox, self.message_queue_checkbox)
        v_sizer1.Add(self.message_queue_checkbox, 0)
        v_sizer1.AddSpacer((0, 5), 0, wx.EXPAND)

        self.message_queue_choice = wx.Choice(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                              ['No message queues available'], 0)
        v_sizer1.Add(self.message_queue_choice, 0, wx.EXPAND)
        Publisher().subscribe(self.on_activemq_instances_info_changed, "activemq_instances_info-changed")
        self.Bind(wx.EVT_CHOICE, self.on_message_queue_choice, self.message_queue_choice)

        v_sizer1.AddSpacer((0, 0), 0, wx.EXPAND)
        self.SetSizer(v_sizer1)

    def enable_show_header_button(self):
        self.show_header_button.Enable()

    def disable_show_header_button(self):
        self.show_header_button.Disable()

    def on_activemq_instances_info_changed(self, msg):
        self.message_queue_choice.Clear()
        new_keys = sorted(self.ztv_frame.activemq_instances_info.keys())
        self.ztv_frame.activemq_instances_available = new_keys
        if len(new_keys) == 0:
            self.message_queue_choice.AppendItems(['No message queues available'])
            self.ztv_frame.activemq_selected_instance = None
        else:
            self.message_queue_choice.AppendItems(new_keys)
        if ((self.ztv_frame.activemq_selected_instance not in new_keys) or (len(new_keys) == 1)):
            self.ztv_frame.activemq_selected_instance = new_keys[0]
        if self.ztv_frame.activemq_selected_instance is None:
            cur_selection = 0
        else:
            cur_selection = self.ztv_frame.activemq_instances_available.index(self.ztv_frame.activemq_selected_instance)
        self.message_queue_choice.SetSelection(cur_selection)

    def on_message_queue_choice(self, evt):
        new_choice = evt.GetString()
        if new_choice != self.ztv_frame.activemq_selected_instance:
            self.ztv_frame.activemq_selected_instance = new_choice
            if self.ztv_frame.autoload_mode == 'activemq-stream':
                self.ztv_frame.launch_activemq_listener_thread()

    def on_choose_autoload_pausetime(self, evt):
        self.ztv_frame.autoload_pausetime = float(evt.GetString())

    # TODO: look into what happens when change autoload_curdir, but not autoload_curfile.  Need to validate whether autoload_curfile is still valid and handle correclty, including updating ztv_frame.autoload_match_string

    def autoload_curfile_filepicker_on_load(self, new_entry):
        new_path = os.path.dirname(new_entry) + '/'
        self.autoload_curdir_filepicker.set_current_entry(new_path)
        self.autoload_curdir_filepicker.prepend_to_history(new_path)
        self.autoload_curdir_filepicker.set_textctrl_background_color('ok')
        self.autoload_curfile_filepicker.set_current_entry(os.path.basename(new_entry))
        self.autoload_curfile_filepicker.set_assumed_prefix(new_path)
        self.ztv_frame.autoload_match_string = new_entry

    def on_autoload_checkbox(self, evt):
        if evt.IsChecked():
            self.message_queue_checkbox.SetValue(False)
            self.ztv_frame.kill_activemq_listener_thread()
            self.ztv_frame.autoload_mode = 'file-match'
            self.ztv_frame.launch_autoload_filematch_thread()
        else:
            self.ztv_frame.autoload_mode = None

    def on_message_queue_checkbox(self, evt):
        if evt.IsChecked():
            self.autoload_checkbox.SetValue(False)
            self.ztv_frame.kill_autoload_filematch_thread()
            self.ztv_frame.autoload_mode = 'activemq-stream'
            self.ztv_frame.launch_activemq_listener_thread()
        else:
            self.ztv_frame.autoload_mode = None
            self.ztv_frame.kill_activemq_listener_thread()

    def on_fitsfile_loaded(self, msg):
        self.curfile_filepicker.pause_on_current_textctrl_changed = True
        self.curfile_filepicker.set_current_entry(os.path.join(self.ztv_frame.cur_fitsfile_path,
                                                               self.ztv_frame.cur_fitsfile_basename))
        self.curfile_filepicker.pause_on_current_textctrl_changed = False


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
        sys.stderr.write("\n\nx_start, y_start = {}\n\n".format((x_start, y_start)))
        sys.stderr.write("\n\nx_end, y_end = {}\n\n".format((x_end, y_end)))
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

class ControlsNotebook(wx.Notebook):
    # see "Book" Controls -> Notebook example in wxpython demo
    def __init__(self, parent):
        self.parent = parent
        wx.Notebook.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0)
        self.source_panel = SourcePanel(self)
        self.AddPage(self.source_panel, "Source")
        self.AddPage(wx.Panel(self, -1), "Phot")
        self.AddPage(wx.Panel(self, -1), "Stats")
        self.plot_panel = PlotPanel(self)
        self.AddPage(self.plot_panel, "Plot")
        self.color_control_panel = ColorControlPanel(self)
        self.AddPage(self.color_control_panel, "Color")


class ZTVFrame(wx.Frame):
    # TODO: create __init__ input parameters for essentially every adjustable parameter
    def __init__(self, title=None, launch_listen_thread=False):
        if title is None:
            title = 'ztv'
        wx.Frame.__init__(self, None, title=title, pos=wx.DefaultPosition, size=wx.Size(1024,512),
                          style = wx.DEFAULT_FRAME_STYLE)
        Publisher().subscribe(self.kill_ztv, 'kill_ztv')
        Publisher().subscribe(self.load_numpy_array, "load_numpy_array")
        Publisher().subscribe(self.load_fits_file, "load_fits_file")
        Publisher().subscribe(self.load_default_image, "load_default_image")
        self.cur_fitsfile_basename = ''
        self.cur_fitsfile_path = ''
        self.default_image_loaded = False
        self.autoload_mode = None # other options are "file-match" and "activemq-stream"
        # TODO:  implement autoloading based on self.autoload_mode
        self.autoload_pausetime_choices = [0.1, 0.5, 1, 2, 5, 10]
        # NOTE: Mac OS X truncates file modification times to integer seconds, so ZTV cannot distinguish a newer file
        #       unless it appears in the next integer second from the prior file.  The <1 sec pausetimes may still be
        #       desirable to minimize latency.
        self.autoload_pausetime = self.autoload_pausetime_choices[2]
        self.autoload_match_string = ''
        self.autoload_filematch_thread = None
        self.image = self.get_default_image()
        self.available_cmaps = ColorMaps().basic()
        self.cmap = 'jet'  # will go back to gray later
        self.is_cmap_inverted = False
        Publisher().subscribe(self.invert_cmap, "invert_cmap")
        Publisher().subscribe(self.set_cmap, "set_cmap")
        Publisher().subscribe(self.set_cmap_inverted, "set_cmap_inverted")
        self.clim = [0.0, 1.0]
        Publisher().subscribe(self.set_clim_to_minmax, "set_clim_to_minmax")
        Publisher().subscribe(self.set_clim_to_auto, "set_clim_to_auto")
        Publisher().subscribe(self.set_clim, "set_clim")
        self.norm = Normalize(vmin=self.clim[0], vmax=self.clim[1])
        Publisher().subscribe(self.set_scaling, "set_scaling")
        Publisher().subscribe(self.set_norm, "clim-changed")
        Publisher().subscribe(self.set_norm, "scaling-changed")
        self.scaling = 'Linear'
        self.available_scalings = ['Linear', 'Log']  # TODO:  add 'PowerNorm' to this list once upgraded to matplotlib 1.4
        # TODO: implement additional parameters on scaling, e.g. gamma for PowerNorm
        self.available_value_modes_on_new_image = ['data-min/max', 'auto', 'constant']
        self.min_value_mode_on_new_image = 'data-min/max'
        self.max_value_mode_on_new_image = 'data-min/max'
        # TODO:  consider an additional mode_on_new_image of N-sigma above(below) median
        Publisher().subscribe(self._add_activemq_instance, "add_activemq_instance")
        self.activemq_instances_info = {}  # will be dict of dicts of, e.g.:
                                           # {'server':'s1.me.com', 'port':61613, 'destination':'my.queue.name'}
                                           # with the top level keys looking like:  server:port:destination
        self.activemq_instances_available = []
        self.activemq_selected_instance = None
        self.activemq_listener_thread = None
        self.activemq_listener_condition = threading.Condition()
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
        self.controls_images_sizer.AddSpacer((0, 0), 0, wx.EXPAND, 5)
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
        self.fits_header = None
        if launch_listen_thread:
            CommandListenerThread(self)
        self.set_cmap('gray')
        self.Show()

    def kill_ztv(self, *args):
        self.Close()

    def _add_activemq_instance(self, msg):
        server, port, destination = msg.data
        new_key = str(server) + ':' + str(port) + ':' + str(destination)
        self.activemq_instances_info[new_key] = {'server':server, 'port':port, 'destination':destination}
        wx.CallAfter(Publisher().sendMessage, "activemq_instances_info-changed", None)

    def get_cmap_to_display(self):
        if self.is_cmap_inverted:
            if self.cmap.endswith('_r'):
                return self.cmap.replace('_r', '')
            else:
                return self.cmap + '_r'
        else:
            return self.cmap

    def set_cmap_inverted(self, msg):
        old_is_cmap_inverted = self.is_cmap_inverted
        if isinstance(msg, Message):
            self.is_cmap_inverted = msg.data
        else:
            self.is_cmap_inverted = msg
        if old_is_cmap_inverted != self.is_cmap_inverted:
            wx.CallAfter(Publisher().sendMessage, "is_cmap_inverted-changed", None)
            wx.CallAfter(Publisher().sendMessage, "redraw_image", None)

    def invert_cmap(self, *args):
        self.set_cmap_inverted(not self.is_cmap_inverted)

    def set_cmap(self, msg):
        """
        Verify that requested cmap is in the list (or it's reversed equivalent) and set it
        """
        if isinstance(msg, Message):
            new_cmap = msg.data
        else:
            new_cmap = msg
        old_cmap = self.cmap
        if new_cmap in self.available_cmaps:
            self.cmap = new_cmap
            self.set_cmap_inverted(False)
        elif new_cmap.replace('_r', '') in self.available_cmaps:
            self.cmap = new_cmap.replace('_r', '')
            self.set_cmap_inverted(True)
        elif (new_cmap + '_r') in self.available_cmaps:
            self.cmap = new_cmap + '_r'
            self.set_cmap_inverted(True)
        else:
            sys.stderr.write("unrecognized cmap ({}) requested\n".format(new_cmap))
        if self.cmap != old_cmap:
            wx.CallAfter(Publisher().sendMessage, "cmap-changed", None)
            wx.CallAfter(Publisher().sendMessage, "redraw_image", None)

    def set_clim(self, msg):
        if isinstance(msg, Message):
            clim = msg.data
        else:
            clim = msg
        old_clim = self.clim
        if clim[0] is None:
            clim[0] = self.clim[0]
        if clim[1] is None:
            clim[1] = self.clim[1]
        if clim[0] > clim[1]:
            self.clim = [clim[1], clim[0]]
            self.set_cmap_inverted(not self.is_cmap_inverted)
        else:
            self.clim = clim
        if old_clim != self.clim:
            wx.CallAfter(Publisher().sendMessage, "clim-changed", None)
            wx.CallAfter(Publisher().sendMessage, "redraw_image", None)

    def set_clim_to_minmax(self, *args):
        self.set_clim([self.image.min(), self.image.max()])

    def get_auto_clim_values(self, *args):
        quartile = (self.image.max() - self.image.min()) / 4.0
        return (self.image.min() + quartile, self.image.max() - quartile)

    def set_clim_to_auto(self, *args):
        # TODO:  Need to implement a sensible auto-minmax setting algorithm
        # TODO: need to add calling this from ztv_api
        sys.stderr.write("\nNeed to implement a sensible auto-minmax setting algorithm\n")
        auto_clim = self.get_auto_clim_values()
        self.set_clim([auto_clim[0], auto_clim[1]])

    def set_norm(self, *args):
        if self.scaling == 'Linear':
            self.norm = Normalize(vmin=self.clim[0], vmax=self.clim[1])
        elif self.scaling == 'Log':
            # TODO: figure out some algorithm for guessing at a reasonable linthresh
            self.norm = SymLogNorm(linthresh=1.0, vmin=self.clim[0], vmax=self.clim[1])
        # TODO:  add PowerNorm scaling once upgraded to matplotlib 1.4 & think about some way of setting gamma parameter
        wx.CallAfter(Publisher().sendMessage, "redraw_image", None)

    def set_scaling(self, msg):
        if isinstance(msg, Message):
            scaling = msg.data
        else:
            scaling = msg
        if scaling in self.available_scalings:
            self.scaling = scaling
            wx.CallAfter(Publisher().sendMessage, "scaling-changed", None)
        else:
            sys.stderr.write("unrecognized scaling ({}) requested\n".format(scaling))

    def load_numpy_array(self, msg):
        if isinstance(msg, Message):
            image = msg.data
        else:
            image = msg
        if image.ndim != 2:
            sys.stderr.write("Currently only support numpy arrays of 2-d; tried to load a {}-d numpy array".format(image.ndim))
        else:
            self.image = image
            self.image_radec = None
            new_min, new_max = None, None
            if self.min_value_mode_on_new_image == 'data-min/max':
                new_min = self.image.min()
            elif self.min_value_mode_on_new_image == 'auto':
                auto_clim = self.get_auto_clim_values()
                new_min = auto_clim[0]
            if self.max_value_mode_on_new_image == 'data-min/max':
                new_max = self.image.max()
            elif self.max_value_mode_on_new_image == 'auto':
                if self.min_value_mode_on_new_image != 'auto':
                    auto_clim = self.get_auto_clim_values()
                new_max = auto_clim[1]
            self.set_clim([new_min, new_max])
            # TODO:  do we want the next line uncommented?  issue:  in some very manual cases (i'm looking at a sequence of manually loaded disparate images, I probably do want reset_zoom_and_center.  BUT, when autoloading fits files from disk or listening to an activemq stream, I distinctly do NOT want to call reset_zoom_and_center.  Could create a parameter to control whether is called, but may be easier to just never call.  Think about it.
#             self.primary_image_panel.reset_zoom_and_center()
            self.fits_header = None
            self.controls_notebook.source_panel.disable_show_header_button()
            self.cur_fitsfile_basename = ''
            self.redisplay_image()
            if self.default_image_loaded:  # last image loaded was the default, so:
                self.primary_image_panel.reset_zoom_and_center()
            self.default_image_loaded = False
            wx.CallAfter(Publisher().sendMessage, "new-image-loaded", None)


    def load_fits_file(self, msg):
        if isinstance(msg, Message):
            filename = msg.data
        else:
            filename = msg
        if isinstance(filename, str) or isinstance(filename, unicode):
            if filename.lower().endswith('.fits') or filename.lower().endswith('.fits.gz'):
                if os.path.isfile(filename):
                    # TODO: store full hdulist so that we can do other things with header
                    hdulist = fits.open(filename, ignore_missing_end=True)
                    # TODO: be more flexible about hdulist where image data is NOT just [0].data
                    # TODO also, in case of extended fits files need to deal with additional header info
                    self.load_numpy_array(hdulist[0].data)
                    self.fits_header = hdulist[0].header
                    self.controls_notebook.source_panel.enable_show_header_button()
                    self.cur_fitsfile_basename = os.path.basename(filename)
                    self.cur_fitsfile_path = os.path.abspath(os.path.dirname(filename))
                    # TODO: better error handling for if WCS not available or partially available
                    try:
                        w = wcs.WCS(hdulist[0].header)
                        # TODO: (urgent) need to check ones/arange in following, do I have this reversed?
                        a = w.all_pix2world(
                                  np.outer(np.ones(self.image.shape[0]), np.arange(self.image.shape[1])),
                                  np.outer(np.arange(self.image.shape[0]), np.ones(self.image.shape[1])),
                                  0)
                        self.image_radec = ICRS(a[0]*units.degree, a[1]*units.degree)
                    except:  # just ignore radec if anything at all goes wrong.
                        self.image_radec = None
                    wx.CallAfter(Publisher().sendMessage, "fitsfile-loaded", None)
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

    def load_default_image(self, *args):
        self.load_numpy_array(self.get_default_image())
        self.primary_image_panel.reset_zoom_and_center()
        self.default_image_loaded = True

    def redisplay_image(self):
        wx.CallAfter(Publisher().sendMessage, "redraw_image")

    def kill_autoload_filematch_thread(self):
        if self.autoload_filematch_thread is not None:
            self.autoload_filematch_thread.keep_running = False

    def launch_autoload_filematch_thread(self):
        self.kill_autoload_filematch_thread()
        self.autoload_filematch_thread = AutoloadFileMatchWatcherThread(self)

    def kill_activemq_listener_thread(self):
        if self.activemq_listener_thread is not None:
            with self.activemq_listener_condition:
                self.activemq_listener_condition.notifyAll()
            self.activemq_listener_thread = None

    def launch_activemq_listener_thread(self):
        self.kill_activemq_listener_thread()
        self.activemq_listener_thread = ActiveMQListenerThread(self, condition=self.activemq_listener_condition)


class ActiveMQListener(object):
    def __init__(self, ztv_frame):
        self.ztv_frame = ztv_frame
    def on_error(self, headers, message):
        print('received an error %s' % message)
    def on_message(self, headers, message):
        try:
            msg = pickle.loads(message)
            if msg.has_key('image_data'):
                wx.CallAfter(Publisher().sendMessage, "load_numpy_array", msg['image_data'])
        except UnpicklingError:
            print('received an unhandled message ({})'.format(message))


class ActiveMQListenerThread(threading.Thread):
    def __init__(self, ztv_frame, condition):
        threading.Thread.__init__(self)
        self.ztv_frame = ztv_frame
        self.condition = condition
        self.daemon = True
        self.start()

    def run(self):
        server = self.ztv_frame.activemq_instances_info[self.ztv_frame.activemq_selected_instance]['server']
        port = self.ztv_frame.activemq_instances_info[self.ztv_frame.activemq_selected_instance]['port']
        dest = self.ztv_frame.activemq_instances_info[self.ztv_frame.activemq_selected_instance]['destination']
        conn = stomp.Connection([(server, port)])
        activemq_listener = ActiveMQListener(self.ztv_frame)
        conn.set_listener('', activemq_listener)
        conn.start()
        conn.connect()
        # browser='true' means leave the messages intact on server; 'false' means consume them destructively
        conn.subscribe(destination=dest, id=1, ack='auto', headers={'browser':'false'})
        with self.condition:
            self.condition.wait()
        conn.disconnect()


class AutoloadFileMatchWatcherThread(threading.Thread):
    def __init__(self, ztv_frame):
        threading.Thread.__init__(self)
        self.ztv_frame = ztv_frame
        self.keep_running = True
        self.daemon = True
        self.start()

    def run(self):
        latest_mtime = 0.0
        while self.keep_running:
            filename_to_open = None
            possible_matches = glob.glob(self.ztv_frame.autoload_match_string)
            if len(possible_matches) > 0:
                for cur_match in possible_matches:
                    cur_match_mtime = os.path.getmtime(cur_match)
                    if cur_match_mtime > latest_mtime:
                        filename_to_open = cur_match
                        latest_mtime = cur_match_mtime
                if filename_to_open is not None:
                    wx.CallAfter(Publisher().sendMessage, "load_fits_file", filename_to_open)
            time.sleep(self.ztv_frame.autoload_pausetime)
            if self.ztv_frame.autoload_mode != 'file-match':
                self.keep_running = False


class WatchMasterPIDThread(threading.Thread):
    def __init__(self, masterPID):
        if masterPID > 0:  # don't start unless there's a valid process ID
            threading.Thread.__init__(self)
            self.masterPID = masterPID
            self.daemon = True
            self.start()

    def run(self):
        while psutil.pid_exists(self.masterPID):
            time.sleep(2)
        sys.stderr.write("\n\n----\nlooks like python session that owned this instance of the ZTV gui is gone, so disposing of the window\n----\n")
        wx.CallAfter(Publisher().sendMessage, "kill_ztv", None)


class CommandListenerThread(threading.Thread):
    def __init__(self, ztv_frame):
        """
        CommandListenerThread expects to be passed the main ZTVFrame object.  Access to the ZTVFrame must be used
        *very* carefully.  Essentially view this access as "readonly".  It's easy to screw things up with the gui if
        CommandListenerThread starts messing with parameters in ZTVFrame.  The appropriate way for CommandListenerThread
        to send commands to ZTVFrame is with a wx.CallAfter(Publisher().sendMessage....   call, e.g.:
            wx.CallAfter(Publisher().sendMessage, "load_default_image", None)
        """
        threading.Thread.__init__(self)
        self.ztv_frame = ztv_frame
        self.daemon = True
        self.start()

    def _send(self, x):
        if isinstance(x, str):
            x = (x,)
        pkl = pickle.dumps(x).replace("\n", "\\()")
        sys.stdout.write(pkl + '\n')
        sys.stdout.flush()

    def run(self):
        keep_running = True
        while keep_running:
            in_str = sys.stdin.readline()
            try:
                x = pickle.loads(in_str.replace("\\()", "\n"))
            except EOFError:  # means we are done here...
                return
            if not isinstance(x, tuple):
                raise Error("ListenThread only accepts tuples")
            if x[0] == 'get_available_cmaps':
                self._send(('available_cmaps', self.ztv_frame.available_cmaps))
            else:
                wx.CallAfter(Publisher().sendMessage, x[0], *x[1:])


class ZTVMain():
    def __init__(self, title=None, masterPID=-1, launch_listen_thread=False):
        WatchMasterPIDThread(masterPID)
        app = wx.App(False)
        self.frame = ZTVFrame(title=title, launch_listen_thread=launch_listen_thread)
        app.MainLoop()

if __name__ == '__main__':
    ZTVMain()
