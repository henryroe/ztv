import wx
from wx.lib.pubsub import Publisher
from matplotlib import cm
import numpy as np


class StatsPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        # TODO: figure out why min size is not being respected by comparing with the framebuilder example
        self.SetSizeHintsSz( wx.Size( 1024,512 ), wx.DefaultSize )
        
        self.last_string_values = {'x0':'', 'xsize':'', 'x1':'', 'y0':'', 'ysize':'', 'y1':''}

        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        textentry_font = wx.Font(14, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT, False)
        
        values_sizer = wx.FlexGridSizer( 7, 5, 0, 0 )
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

  # HEREIAM:  Next:  add non-editable text control fields.  space things out nicely 
  
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        self.median_static_text = wx.StaticText( self, wx.ID_ANY, u"Median", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.median_static_text.Wrap( -1 )
        values_sizer.Add(self.median_static_text, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_RIGHT, 0)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)  # placeholder for median field
        self.robust_static_text = wx.StaticText( self, wx.ID_ANY, u"Robust", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.robust_static_text.Wrap( -1 )
        values_sizer.Add(self.robust_static_text, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_CENTER_HORIZONTAL, 0)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        self.mean_static_text = wx.StaticText( self, wx.ID_ANY, u"Mean", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.mean_static_text.Wrap( -1 )
        values_sizer.Add(self.mean_static_text, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_RIGHT, 0)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)  # placeholder for mean field
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)  # placeholder for robust mean field
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)
        self.stdev_static_text = wx.StaticText( self, wx.ID_ANY, u"Stdev", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.stdev_static_text.Wrap( -1 )
        values_sizer.Add(self.stdev_static_text, 0, wx.ALL|wx.ALIGN_BOTTOM|wx.ALIGN_RIGHT, 0)
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)  # placeholder for stdev field
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)  # placeholder for robust stdev field
        values_sizer.AddSpacer((0,0), 0, wx.EXPAND)

        v_sizer1.Add(values_sizer, 0)
        self.SetSizer(v_sizer1)
        Publisher().subscribe(self.update_stats, "stats_rect_updated")

    def update_stats(self, *args):
        # NOTE: need to better document that we do inclusive range, NOT python style range here.
        # TODO: limit rect to within image box???
        x0,y0 = self.ztv_frame.primary_image_panel.stats_rect.xy
        x1 = x0 + self.ztv_frame.primary_image_panel.stats_rect.get_width()
        y1 = y0 + self.ztv_frame.primary_image_panel.stats_rect.get_height()
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

    def force_textctrl_color_update(self, textctrl):
        cur_focused_item = self.FindFocus()
        insertion_point = textctrl.GetInsertionPoint()
        textctrl.SetFocus()
        textctrl.SetInsertionPoint(insertion_point)
        if cur_focused_item is not None:
            cur_focused_item.SetFocus()

    def set_textctrl_background_color(self, textctrl, mode, tooltip=None):
        if mode == 'ok':
            color = (255,255,255)
        elif mode == 'enter-needed':
            color = (200,255,200)
        elif mode == 'invalid':
            # TODO:  implement: escape key brings up last valid value??
            color = (255,200,200)
        textctrl.SetBackgroundColour(color)
        textctrl.Refresh()
        if tooltip is not None and not isinstance(tooltip, wx.ToolTip):
            tooltip = wx.ToolTip(tooltip)
        textctrl.SetToolTip(tooltip)
        self.force_textctrl_color_update(textctrl)

    def validate_textctrl_str(self, textctrl, validate_fxn, last_value):
        """
        can accept arbitrary functions in validate_fxn.  They just need to raise a ValueError if
        they don't like the input.
        """
        try:
            newval = validate_fxn(textctrl.GetValue())
            if textctrl.GetValue() == last_value:
                self.set_textctrl_background_color(textctrl, 'ok')
            else:
                self.set_textctrl_background_color(textctrl, 'enter-needed',
                                                   'Press enter in this field to set new minimum value')
            return True
        except ValueError:
            # TODO: figure out some (clever?) way of having validate_fxn give info about itself that is more useful in the following error tooltip message
            self.set_textctrl_background_color(textctrl, 'invalid', 
                                               'Entry cannot be converted to {}'.format(str(validate_fxn)))
            return False

    def x0_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.x0_textctrl, int, self.last_string_values['x0'])

    def x0_textctrl_entered(self, evt):
        if self.validate_x0_str():
            self.last_x0_string = self.x0_textctrl.GetValue()
              # HEREIAM:  TK: need to DO something with x0!
            self.x0_textctrl.SetSelection(-1, -1)

    def xsize_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.xsize_textctrl, int, self.last_string_values['xsize'])

    def xsize_textctrl_entered(self, evt):
        if self.validate_xsize_str():
            self.last_xsize_string = self.xsize_textctrl.GetValue()
              # HEREIAM:  TK: need to DO something with xsize!
            self.xsize_textctrl.SetSelection(-1, -1)

    def x1_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.x1_textctrl, int, self.last_string_values['x1'])

    def x1_textctrl_entered(self, evt):
        if self.validate_x1_str():
            self.last_x1_string = self.x1_textctrl.GetValue()
              # HEREIAM:  TK: need to DO something with x1!
            self.x1_textctrl.SetSelection(-1, -1)

    def y0_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.y0_textctrl, int, self.last_string_values['y0'])

    def y0_textctrl_entered(self, evt):
        if self.validate_y0_str():
            self.last_y0_string = self.y0_textctrl.GetValue()
              # HEREIAM:  TK: need to DO something with y0!
            self.y0_textctrl.SetSelection(-1, -1)

    def ysize_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.ysize_textctrl, int, self.last_string_values['ysize'])

    def ysize_textctrl_entered(self, evt):
        if self.validate_ysize_str():
            self.last_ysize_string = self.ysize_textctrl.GetValue()
              # HEREIAM:  TK: need to DO something with y0!
            self.ysize_textctrl.SetSelection(-1, -1)

    def y1_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.y1_textctrl, int, self.last_string_values['y1'])

    def y1_textctrl_entered(self, evt):
        if self.validate_y1_str():
            self.last_y1_string = self.y1_textctrl.GetValue()
              # HEREIAM:  TK: need to DO something with y1!
            self.y1_textctrl.SetSelection(-1, -1)

