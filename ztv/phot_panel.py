import wx
from wx.lib.pubsub import Publisher
from wx.lib.pubsub.core.datamsg import Message
import matplotlib
matplotlib.interactive(True)
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from .quick_phot import centroid, aperture_phot
import numpy as np

import sys

class PhotPlotPanel(wx.Panel):
    def __init__(self, parent, dpi=None, **kwargs):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, **kwargs)
        self.ztv_frame = self.GetTopLevelParent()
        self.figure = Figure(dpi=None, figsize=(1.,1.))
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.Bind(wx.EVT_SIZE, self._onSize)

    def _onSize(self, event):
        self._SetSize()

    def _SetSize(self):
        pixels = tuple(self.GetClientSize())
        self.SetSize(pixels)
        self.canvas.SetSize(pixels)
        self.figure.set_size_inches(float(pixels[0])/self.figure.get_dpi(), float(pixels[1])/self.figure.get_dpi())


class PhotPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        # TODO: figure out why min size is not being respected by comparing with the framebuilder example
        self.SetSizeHintsSz( wx.Size( 1024,512 ), wx.DefaultSize )
        
        self.last_string_values = {'aprad':'', 'skyradin':'', 'skyradout':''}
        self.xclicked = 0.
        self.yclicked = 0.
        self.xcentroid = 0.
        self.ycentroid = 0.
        self.aprad = 10.
        self.skyradin = 20.
        self.skyradout = 30.
        
        textentry_font = wx.Font(14, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT, False)
        values_sizer = wx.FlexGridSizer( 3, 5, 0, 0 )
        values_sizer.SetFlexibleDirection( wx.BOTH )
        values_sizer.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

        self.aprad_static_text = wx.StaticText( self, wx.ID_ANY, u"Aperture radius", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.aprad_static_text.Wrap( -1 )
        values_sizer.Add(self.aprad_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.aprad_textctrl = wx.TextCtrl(self, wx.ID_ANY, str(self.aprad), wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.aprad_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.aprad_textctrl, 0, wx.ALL, 2)
        self.aprad_textctrl.Bind(wx.EVT_TEXT, self.aprad_textctrl_changed)
        self.aprad_textctrl.Bind(wx.EVT_TEXT_ENTER, self.aprad_textctrl_entered)
        values_sizer.AddSpacer((30,0), 0, wx.EXPAND)
        self.clicked_static_text = wx.StaticText( self, wx.ID_ANY, u"Clicked", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
        self.clicked_static_text.Wrap( -1 )
        values_sizer.Add(self.clicked_static_text, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM, 0)
        self.centroid_static_text = wx.StaticText( self, wx.ID_ANY, u"Centroid", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER_HORIZONTAL )
        self.centroid_static_text.Wrap( -1 )
        values_sizer.Add(self.centroid_static_text, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM, 0)

        self.skyradin_static_text = wx.StaticText( self, wx.ID_ANY, u"Sky inner radius", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.skyradin_static_text.Wrap( -1 )
        values_sizer.Add(self.skyradin_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.skyradin_textctrl = wx.TextCtrl(self, wx.ID_ANY, str(self.skyradin), wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.skyradin_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.skyradin_textctrl, 0, wx.ALL, 2)
        self.skyradin_textctrl.Bind(wx.EVT_TEXT, self.skyradin_textctrl_changed)
        self.skyradin_textctrl.Bind(wx.EVT_TEXT_ENTER, self.skyradin_textctrl_entered)
        self.x_static_text = wx.StaticText( self, wx.ID_ANY, u"x", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.x_static_text.Wrap( -1 )
        values_sizer.Add(self.x_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.xclicked_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.xclicked_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.xclicked_textctrl, 0, wx.ALL, 2)
        self.xcentroid_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.xcentroid_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.xcentroid_textctrl, 0, wx.ALL, 2)

        self.skyradout_static_text = wx.StaticText( self, wx.ID_ANY, u"Sky outer radius", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.skyradout_static_text.Wrap( -1 )
        values_sizer.Add(self.skyradout_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.skyradout_textctrl = wx.TextCtrl(self, wx.ID_ANY, str(self.skyradout), wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.skyradout_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.skyradout_textctrl, 0, wx.ALL, 2)
        self.skyradout_textctrl.Bind(wx.EVT_TEXT, self.skyradout_textctrl_changed)
        self.skyradout_textctrl.Bind(wx.EVT_TEXT_ENTER, self.skyradout_textctrl_entered)
        self.y_static_text = wx.StaticText( self, wx.ID_ANY, u"y", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.y_static_text.Wrap( -1 )
        values_sizer.Add(self.y_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.yclicked_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.yclicked_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.yclicked_textctrl, 0, wx.ALL, 2)
        self.ycentroid_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.ycentroid_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.ycentroid_textctrl, 0, wx.ALL, 2)


        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        v_sizer1.Add(values_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL)
#         v_sizer1.AddSpacer((0, 1), 0, wx.EXPAND)
        v_sizer1.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 5)
#         v_sizer1.AddSpacer((0, 1), 0, wx.EXPAND)

        h_sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.sky_static_text = wx.StaticText( self, wx.ID_ANY, u"Sky", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.sky_static_text.Wrap( -1 )
        h_sizer1.Add(self.sky_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.sky_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                        wx.TE_PROCESS_ENTER)
        self.sky_textctrl.SetFont(textentry_font)
        h_sizer1.Add(self.sky_textctrl, 0, wx.ALL, 2)
        # TODO: look up how to do nice plus/minus symbol
        self.pm_static_text = wx.StaticText( self, wx.ID_ANY, u"+-", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.pm_static_text.Wrap( -1 )
        h_sizer1.Add(self.pm_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.skyerr_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                        wx.TE_PROCESS_ENTER)
        self.skyerr_textctrl.SetFont(textentry_font)
        h_sizer1.Add(self.skyerr_textctrl, 0, wx.ALL, 2)
        self.perpixel_static_text = wx.StaticText( self, wx.ID_ANY, u"/pixel", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.perpixel_static_text.Wrap( -1 )
        h_sizer1.Add(self.perpixel_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        v_sizer1.Add(h_sizer1, 0, wx.ALIGN_LEFT)
        
        h_sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.object_static_text = wx.StaticText( self, wx.ID_ANY, u"Object", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.object_static_text.Wrap( -1 )
        h_sizer2.Add(self.object_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.flux_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                        wx.TE_PROCESS_ENTER)
        self.flux_textctrl.SetFont(textentry_font)
        h_sizer2.Add(self.flux_textctrl, 0, wx.ALL, 2)
        self.cts_static_text = wx.StaticText( self, wx.ID_ANY, u"cts with FWHM", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.cts_static_text.Wrap( -1 )
        h_sizer2.Add(self.cts_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.fwhm_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                        wx.TE_PROCESS_ENTER)
        self.fwhm_textctrl.SetFont(textentry_font)
        h_sizer2.Add(self.fwhm_textctrl, 0, wx.ALL, 2)
        self.pix_static_text = wx.StaticText( self, wx.ID_ANY, u"pix", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.pix_static_text.Wrap( -1 )
        h_sizer2.Add(self.pix_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        v_sizer1.Add(h_sizer2, 0, wx.ALIGN_LEFT)

        self.plot_panel = PhotPlotPanel(self)
        v_sizer1.Add(self.plot_panel, 1, wx.LEFT | wx.TOP | wx.EXPAND)

        self.SetSizer(v_sizer1)
        Publisher().subscribe(self.update_phot_xy, "new_phot_xy")

    def force_textctrl_color_update(self, textctrl):
        cur_focused_item = self.FindFocus()
        insertion_point = textctrl.GetInsertionPoint()
        self.xclicked_textctrl.SetFocus()  # need to shift focus away & then back to force color update in GUI
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

    def update_phot_xy(self, msg):
        if isinstance(msg, Message):
            x,y = msg.data
        else:
            x,y = msg
        self.xclicked, self.yclicked = x,y
        self.recalc_phot()
        
    def recalc_phot(self):
        self.xclicked_textctrl.SetValue("{:8.2f}".format(self.xclicked))
        self.yclicked_textctrl.SetValue("{:8.2f}".format(self.yclicked))
        self.xcentroid,self.ycentroid = centroid(self.ztv_frame.image, self.xclicked, self.yclicked)
        self.xcentroid_textctrl.SetValue("{:8.2f}".format(self.xcentroid))
        self.ycentroid_textctrl.SetValue("{:8.2f}".format(self.ycentroid))
        phot = aperture_phot(self.ztv_frame.image, self.xcentroid, self.ycentroid, 
                             self.aprad, self.skyradin, self.skyradout, return_distances=True)
        aprad = phot['star_radius']
        skyradin = phot['sky_inner_radius']
        skyradout = phot['sky_outer_radius']
        self.flux_textctrl.SetValue("{:0.6g}".format(phot['flux']))
        self.sky_textctrl.SetValue("{:0.6g}".format(phot['sky_per_pixel']))
        self.skyerr_textctrl.SetValue("{:0.6g}".format(phot['sky_per_pixel_err']))
        aprad_color = 'blue'
        skyradin_color = 'red'
        skyradout_color = 'red'
        self.plot_panel.axes.cla()
          # HEREIAM:  need radial profile plot
        self.plot_panel.axes.plot(phot['distances'].ravel(), self.ztv_frame.image.ravel(), 'ko', markersize=1)
        ylim = self.plot_panel.axes.get_ylim()
        unrounded_xmax = max([aprad*2, skyradin*2, skyradout + (skyradout - skyradin)])
        nice_factor = 10./5.
        sensible_xmax = ((nice_factor*10**np.floor(np.log10(unrounded_xmax))) * 
                         np.ceil(unrounded_xmax / (nice_factor*10**np.floor(np.log10(unrounded_xmax)))))
        n_sigma = 10.
        if (phot['sky_per_pixel'] - n_sigma*phot['sky_per_pixel_err']) > 0.:
            ylim = (phot['sky_per_pixel'] - n_sigma*phot['sky_per_pixel_err'], ylim[1])
        self.plot_panel.axes.plot([aprad, aprad], ylim, '--', color=aprad_color)
        self.plot_panel.axes.plot([skyradin, skyradin], ylim, '.-', color=skyradin_color)
        self.plot_panel.axes.plot([skyradout, skyradout], ylim, '--', color=skyradout_color)
        self.plot_panel.axes.set_xlim([0, sensible_xmax])
        self.plot_panel.axes.plot([0, sensible_xmax], [phot['sky_per_pixel'], phot['sky_per_pixel']], '-r')
        self.plot_panel.axes.plot([0, sensible_xmax], [phot['sky_per_pixel'] - phot['sky_per_pixel_err'], 
                                                       phot['sky_per_pixel'] - phot['sky_per_pixel_err']], '..r')
        self.plot_panel.axes.plot([0, sensible_xmax], [phot['sky_per_pixel'] + phot['sky_per_pixel_err'], 
                                                       phot['sky_per_pixel'] + phot['sky_per_pixel_err']], '..r')
        self.plot_panel.figure.canvas.draw()
        #TODO: FWHM
        
        pass
        # TODO: recalc phot & update circles on image

    def aprad_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.aprad_textctrl, float, self.last_string_values['aprad'])

    def aprad_textctrl_entered(self, evt):
        if self.validate_textctrl_str(self.aprad_textctrl, float, self.last_string_values['aprad']):
            self.last_string_values['aprad'] = self.aprad_textctrl.GetValue()
            self.aprad = float(self.last_string_values['aprad'])
            self.recalc_phot()
            self.validate_textctrl_str(self.aprad_textctrl, float, self.last_string_values['aprad'])
            self.aprad_textctrl.SetSelection(-1, -1)

    def skyradin_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.skyradin_textctrl, float, self.last_string_values['skyradin'])

    def skyradin_textctrl_entered(self, evt):
        if self.validate_textctrl_str(self.skyradin_textctrl, float, self.last_string_values['skyradin']):
            self.last_string_values['skyradin'] = self.skyradin_textctrl.GetValue()
            self.skyradin = float(self.last_string_values['skyradin'])
            self.recalc_phot()
            self.validate_textctrl_str(self.skyradin_textctrl, float, self.last_string_values['skyradin'])
            self.skyradin_textctrl.SetSelection(-1, -1)

    def skyradout_textctrl_changed(self, evt):
        self.validate_textctrl_str(self.skyradout_textctrl, float, self.last_string_values['skyradout'])

    def skyradout_textctrl_entered(self, evt):
        if self.validate_textctrl_str(self.skyradout_textctrl, float, self.last_string_values['skyradout']):
            self.last_string_values['skyradout'] = self.skyradout_textctrl.GetValue()
            self.skyradout = float(self.last_string_values['skyradout'])
            self.recalc_phot()
            self.validate_textctrl_str(self.skyradout_textctrl, float, self.last_string_values['skyradout'])
            self.skyradout_textctrl.SetSelection(-1, -1)
            
#TODO: set up reasonable defaults for aprad, skyradin, & skyradout
# TODO; clear button?  or just toggle switch for turning circles on/off?  maybe latter?

