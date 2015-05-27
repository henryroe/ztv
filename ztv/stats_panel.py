from __future__ import absolute_import
import wx
from wx.lib.pubsub import Publisher
from matplotlib.patches import Rectangle
from matplotlib import cm
import numpy as np
from astropy.stats import sigma_clipped_stats
import sys
from .ztv_lib import set_textctrl_background_color, validate_textctrl_str

class StatsPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        # TODO: figure out why min size is not being respected by comparing with the framebuilder example
        self.SetSizeHintsSz( wx.Size( 1024,512 ), wx.DefaultSize )
        self.stats_info = None
        
        self.last_string_values = {'x0':'', 'xsize':'', 'x1':'', 'y0':'', 'ysize':'', 'y1':''}
        self.stats_rect = Rectangle((0, 0), 10, 10, color='magenta', fill=False, zorder=100)

        textentry_font = wx.Font(14, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT, False)
        
        values_sizer = wx.FlexGridSizer( 10, 5, 0, 0 )
        values_sizer.SetFlexibleDirection( wx.BOTH )
        values_sizer.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        self.low_static_text = wx.StaticText( self, wx.ID_ANY, u"Low", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.low_static_text.Wrap( -1 )
        values_sizer.Add(self.low_static_text, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 0)

        self.low_static_text = wx.StaticText( self, wx.ID_ANY, u"# pix", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.low_static_text.Wrap( -1 )
        values_sizer.Add(self.low_static_text, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 0)

        self.high_static_text = wx.StaticText( self, wx.ID_ANY, u"High", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.high_static_text.Wrap( -1 )
        values_sizer.Add(self.high_static_text, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL, 0)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        self.x_static_text = wx.StaticText( self, wx.ID_ANY, u"x", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.x_static_text.Wrap( -1 )
        values_sizer.Add(self.x_static_text, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 0)

        self.x0_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.x0_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.x0_textctrl, 0, wx.ALL, 2)
        self.x0_textctrl.Bind(wx.EVT_TEXT, self.x0_textctrl_changed)
        self.x0_textctrl.Bind(wx.EVT_TEXT_ENTER, self.x0_textctrl_entered)

        self.xsize_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                          wx.TE_PROCESS_ENTER)
        self.xsize_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.xsize_textctrl, 0, wx.ALL, 2)
        self.xsize_textctrl.Bind(wx.EVT_TEXT, self.xsize_textctrl_changed)
        self.xsize_textctrl.Bind(wx.EVT_TEXT_ENTER, self.xsize_textctrl_entered)

        self.x1_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.x1_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.x1_textctrl, 0, wx.ALL, 2)
        self.x1_textctrl.Bind(wx.EVT_TEXT, self.x1_textctrl_changed)
        self.x1_textctrl.Bind(wx.EVT_TEXT_ENTER, self.x1_textctrl_entered)

        self.npix_static_text = wx.StaticText( self, wx.ID_ANY, u"# pixels", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.npix_static_text.Wrap( -1 )
        values_sizer.Add(self.npix_static_text, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM, 0)

        self.y_static_text = wx.StaticText( self, wx.ID_ANY, u"y", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.y_static_text.Wrap( -1 )
        values_sizer.Add(self.y_static_text, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 0)

        self.y0_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.y0_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.y0_textctrl, 0, wx.ALL, 2)
        self.y0_textctrl.Bind(wx.EVT_TEXT, self.y0_textctrl_changed)
        self.y0_textctrl.Bind(wx.EVT_TEXT_ENTER, self.y0_textctrl_entered)

        self.ysize_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                          wx.TE_PROCESS_ENTER)
        self.ysize_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.ysize_textctrl, 0, wx.ALL, 2)
        self.ysize_textctrl.Bind(wx.EVT_TEXT, self.ysize_textctrl_changed)
        self.ysize_textctrl.Bind(wx.EVT_TEXT_ENTER, self.ysize_textctrl_entered)

        self.y1_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.y1_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.y1_textctrl, 0, wx.ALL, 2)
        self.y1_textctrl.Bind(wx.EVT_TEXT, self.y1_textctrl_changed)
        self.y1_textctrl.Bind(wx.EVT_TEXT_ENTER, self.y1_textctrl_entered)
        
        self.npix_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                         wx.TE_READONLY)
        self.npix_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.npix_textctrl, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT, 0)
  
        values_sizer.AddSpacer((0,15), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        self.median_static_text = wx.StaticText( self, wx.ID_ANY, u"Median", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.median_static_text.Wrap( -1 )
        values_sizer.Add(self.median_static_text, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 0)
        self.median_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.median_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.median_textctrl, 0, wx.ALL, 2)
        self.robust_static_text = wx.StaticText( self, wx.ID_ANY, u"Robust", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.robust_static_text.Wrap( -1 )
        values_sizer.Add(self.robust_static_text, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_CENTER_HORIZONTAL, 0)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        self.mean_static_text = wx.StaticText( self, wx.ID_ANY, u"Mean", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.mean_static_text.Wrap( -1 )
        values_sizer.Add(self.mean_static_text, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 0)
        self.mean_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.mean_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.mean_textctrl, 0, wx.ALL, 2)
        self.robust_mean_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.robust_mean_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.robust_mean_textctrl, 0, wx.ALL, 2)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        self.stdev_static_text = wx.StaticText( self, wx.ID_ANY, u"Stdev", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.stdev_static_text.Wrap( -1 )
        values_sizer.Add(self.stdev_static_text, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 0)
        self.stdev_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.stdev_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.stdev_textctrl, 0, wx.ALL, 2)
        self.robust_stdev_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.robust_stdev_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.robust_stdev_textctrl, 0, wx.ALL, 2)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,15), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        self.min_static_text = wx.StaticText( self, wx.ID_ANY, u"Min", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.min_static_text.Wrap( -1 )
        values_sizer.Add(self.min_static_text, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 0)
        self.minval_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_PROCESS_ENTER)
        self.minval_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.minval_textctrl, 0, wx.ALL, 2)
        self.minpos_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_PROCESS_ENTER)
        self.minpos_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.minpos_textctrl, 0, wx.ALL, 2)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        self.max_static_text = wx.StaticText( self, wx.ID_ANY, u"Max", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.max_static_text.Wrap( -1 )
        values_sizer.Add(self.max_static_text, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 0)
        self.maxval_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_PROCESS_ENTER)
        self.maxval_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.maxval_textctrl, 0, wx.ALL, 2)
        self.maxpos_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_PROCESS_ENTER)
        self.maxpos_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.maxpos_textctrl, 0, wx.ALL, 2)
             
        self.hideshow_button = wx.Button(self, wx.ID_ANY, u"Show", wx.DefaultPosition, wx.DefaultSize, 0)
        values_sizer.Add(self.hideshow_button, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.hideshow_button.Bind(wx.EVT_BUTTON, self.on_hideshow_button)

        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        v_sizer1.AddStretchSpacer(1.0)
        v_sizer1.Add(values_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL)
        v_sizer1.AddStretchSpacer(1.0)
        self.SetSizer(v_sizer1)
        Publisher().subscribe(self.update_stats, "redraw_image")

        # TODO: clean up in stats_box stuff whether ranges are pythonic or inclusive.  Might be that is pythonic behind scenes, but inclusive in some of the display of info?  There are trickinesses to getting this right, as sometimes need to flip x0/x1 and y0/y1 when range is negative

    def update_stats_box(self, x0=None, y0=None, x1=None, y1=None):
        if x0 is None:
            x0 = self.stats_rect.get_x()
        if y0 is None:
            y0 = self.stats_rect.get_y()
        if x1 is None:
            x1 = self.stats_rect.get_x() + self.stats_rect.get_width()
        if y1 is None:
            y1 = self.stats_rect.get_y() + self.stats_rect.get_height()
        x0 = min(max(0, x0), self.ztv_frame.display_image.shape[1])
        y0 = min(max(0, y0), self.ztv_frame.display_image.shape[0])
        x1 = min(max(0, x1), self.ztv_frame.display_image.shape[1])
        y1 = min(max(0, y1), self.ztv_frame.display_image.shape[0])
        self.stats_rect.set_bounds(x0, y0, x1 - x0, y1 - y0)
        self.ztv_frame.primary_image_panel.figure.canvas.draw()
        self.update_stats()

    def remove_overplot_on_image(self):
        if self.stats_rect in self.ztv_frame.primary_image_panel.axes.patches:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.stats_rect)
        self.ztv_frame.primary_image_panel.figure.canvas.draw()
        self.hideshow_button.SetLabel(u"Show")

    def redraw_overplot_on_image(self):
        if self.stats_rect not in self.ztv_frame.primary_image_panel.axes.patches:
            self.ztv_frame.primary_image_panel.axes.add_patch(self.stats_rect)
        self.ztv_frame.primary_image_panel.figure.canvas.draw()
        self.hideshow_button.SetLabel(u"Hide")        

    def on_hideshow_button(self, evt):
        if self.hideshow_button.GetLabel() == 'Hide':
            self.remove_overplot_on_image()
        else:
            self.redraw_overplot_on_image()

    def get_x0y0x1y1_from_stats_rect(self):
        x0 = self.stats_rect.get_x()
        y0 = self.stats_rect.get_y()
        x1 = x0 + self.stats_rect.get_width()
        y1 = y0 + self.stats_rect.get_height()
        return x0,y0,x1,y1
        
    def update_stats(self, *args):
        x0,y0,x1,y1 = self.get_x0y0x1y1_from_stats_rect()
        if x0 > x1:
            x0,x1 = x1,x0
        if y0 > y1:
            y0,y1 = y1,y0
        x0, y0 = int(np.round(x0)), int(np.round(y0))
        x1, y1 = int(np.round(x1)), int(np.round(y1))
        self.last_string_values['x0'] = str(int(x0))
        self.x0_textctrl.SetValue(self.last_string_values['x0'])
        self.last_string_values['y0'] = str(int(y0))
        self.y0_textctrl.SetValue(self.last_string_values['y0'])

        x_npix = int(x1 - x0 + 1)
        self.last_string_values['xsize'] = str(x_npix)
        self.xsize_textctrl.SetValue(self.last_string_values['xsize'])
        y_npix = int(y1 - y0 + 1)
        self.last_string_values['ysize'] = str(y_npix)
        self.ysize_textctrl.SetValue(self.last_string_values['ysize'])

        self.last_string_values['x1'] = str(int(x1))
        self.x1_textctrl.SetValue(self.last_string_values['x1'])
        self.last_string_values['y1'] = str(int(y1))
        self.y1_textctrl.SetValue(self.last_string_values['y1'])
    
        self.npix_textctrl.SetValue(str(x_npix * y_npix))

        stats_data = self.ztv_frame.display_image[y0:y1+1, x0:x1+1]
        self.stats_info = {'xrange':[x0,x1], 'yrange':[y0,y1],
                           'mean':stats_data.mean(), 'median':np.median(stats_data), 'std':stats_data.std(),
                           'min':stats_data.min(), 'max':stats_data.max()}
        self.mean_textctrl.SetValue("{:0.4g}".format(self.stats_info['mean']))
        self.median_textctrl.SetValue("{:0.4g}".format(self.stats_info['median']))
        self.stdev_textctrl.SetValue("{:0.4g}".format(self.stats_info['std']))
        robust_mean, robust_median, robust_std = sigma_clipped_stats(stats_data)
        self.stats_info['robust_mean'] = robust_mean
        self.stats_info['robust_median'] = robust_median
        self.stats_info['robust_std'] = robust_std
        self.robust_mean_textctrl.SetValue("{:0.4g}".format(robust_mean)) 
        self.robust_stdev_textctrl.SetValue("{:0.4g}".format(robust_std))
        self.minval_textctrl.SetValue("{:0.4g}".format(self.stats_info['min']))
        self.maxval_textctrl.SetValue("{:0.4g}".format(self.stats_info['max']))
        wmin = np.where(stats_data == stats_data.min())
        wmin = [(wmin[1][i] + x0,wmin[0][i] + y0) for i in np.arange(wmin[0].size)]
        if len(wmin) == 1:
            wmin = wmin[0]
        self.minpos_textctrl.SetValue("{}".format(wmin))
        self.stats_info['wmin'] = wmin
        wmax = np.where(stats_data == stats_data.max())
        wmax = [(wmax[1][i] + x0,wmax[0][i] + y0) for i in np.arange(wmax[0].size)]
        if len(wmax) == 1:
            wmax = wmax[0]
        self.maxpos_textctrl.SetValue("{}".format(wmax))
        self.stats_info['wmax'] = wmax
        set_textctrl_background_color(self.x0_textctrl, 'ok')
        set_textctrl_background_color(self.x1_textctrl, 'ok')
        set_textctrl_background_color(self.xsize_textctrl, 'ok')
        set_textctrl_background_color(self.y0_textctrl, 'ok')
        set_textctrl_background_color(self.y1_textctrl, 'ok')
        set_textctrl_background_color(self.ysize_textctrl, 'ok')
        
    def on_navigation_key(self, evt):
        # TODO: figure out how to make tab order work the way I want.  Currently the following code works partly, but is ignored by some tabs.  Weird. Looks like it's an issue that tab is triggering some *other* event when it's a button that has focus.  Might have to play around with catching all key-presses inside of ColorControlPanel & passing along the non-tab keypresses???
        tab_order = [self.x0_textctrl, self.xsize_textctrl, self.x1_textctrl,
                     self.y0_textctrl, self.ysize_textctrl, self.y1_textctrl]
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

    def x0_textctrl_changed(self, evt):
        validate_textctrl_str(self.x0_textctrl, int, self.last_string_values['x0'])

    def x0_textctrl_entered(self, evt):
        if validate_textctrl_str(self.x0_textctrl, int, self.last_string_values['x0']):
            self.last_string_values['x0'] = self.x0_textctrl.GetValue()
            self.update_stats_box(int(self.last_string_values['x0']), None, None, None)
            self.x0_textctrl.SetSelection(-1, -1)
            self.redraw_overplot_on_image()
            
    def xsize_textctrl_changed(self, evt):
        validate_textctrl_str(self.xsize_textctrl, int, self.last_string_values['xsize'])

    def xsize_textctrl_entered(self, evt):
        if validate_textctrl_str(self.xsize_textctrl, int, self.last_string_values['xsize']):
            self.last_string_values['xsize'] = self.xsize_textctrl.GetValue()
            xsize = int(self.last_string_values['xsize'])
            x0,y0,x1,y1 = self.get_x0y0x1y1_from_stats_rect()
            xc = int((x0 + x1)/2)
            x0 = int(xc - xsize/2)
            x1 = x0 + xsize  # TODO: as part of ensuring pythonic ranges behind scenes, but sensible ranges in GUI, need to re-examine this
            self.update_stats_box(x0, y0, x1, y1)
            self.xsize_textctrl.SetSelection(-1, -1)
            self.redraw_overplot_on_image()

    def x1_textctrl_changed(self, evt):
        validate_textctrl_str(self.x1_textctrl, int, self.last_string_values['x1'])

    def x1_textctrl_entered(self, evt):
        if validate_textctrl_str(self.x1_textctrl, int, self.last_string_values['x1']):
            self.last_string_values['x1'] = self.x1_textctrl.GetValue()
            self.update_stats_box(None, None, int(self.last_string_values['x1']), None)
            self.x1_textctrl.SetSelection(-1, -1)
            self.redraw_overplot_on_image()

    def y0_textctrl_changed(self, evt):
        validate_textctrl_str(self.y0_textctrl, int, self.last_string_values['y0'])

    def y0_textctrl_entered(self, evt):
        if validate_textctrl_str(self.y0_textctrl, int, self.last_string_values['y0']):
            self.last_string_values['y0'] = self.y0_textctrl.GetValue()
            self.update_stats_box(None, int(self.last_string_values['y0']), None, None)
            self.y0_textctrl.SetSelection(-1, -1)
            self.redraw_overplot_on_image()

    def ysize_textctrl_changed(self, evt):
        validate_textctrl_str(self.ysize_textctrl, int, self.last_string_values['ysize'])

    def ysize_textctrl_entered(self, evt):
        if validate_textctrl_str(self.ysize_textctrl, int, self.last_string_values['ysize']):
            self.last_string_values['ysize'] = self.ysize_textctrl.GetValue()
            ysize = int(self.last_string_values['ysize'])
            x0,y0,x1,y1 = self.get_x0y0x1y1_from_stats_rect()
            yc = int((y0 + y1)/2)
            y0 = int(yc - ysize/2)
            y1 = y0 + ysize  # TODO: as part of ensuring pythonic ranges behind scenes, but sensible ranges in GUI, need to re-examine this
            self.update_stats_box(x0, y0, x1, y1)
            self.ysize_textctrl.SetSelection(-1, -1)
            self.redraw_overplot_on_image()

    def y1_textctrl_changed(self, evt):
        validate_textctrl_str(self.y1_textctrl, int, self.last_string_values['y1'])

    def y1_textctrl_entered(self, evt):
        if validate_textctrl_str(self.y1_textctrl, int, self.last_string_values['y1']):
            self.last_string_values['y1'] = self.y1_textctrl.GetValue()
            self.update_stats_box(None, None, None, int(self.last_string_values['y1']))
            self.y1_textctrl.SetSelection(-1, -1)
            self.redraw_overplot_on_image()

