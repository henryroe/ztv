from __future__ import absolute_import
import wx
from wx.lib.pubsub import pub
import matplotlib
from matplotlib.figure import Figure
from matplotlib.widgets import AxesWidget
try:
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
except IOError:
    # on some linux installations this import needs to be done twice as the first time raises an error:
    #   IOError: [Errno 2] No such file or directory: '/tmp/matplotlib-parallels/fontList.cache'
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.patches import Circle, Wedge
try:
    from scipy.optimize import curve_fit
    scipy_install_is_ok = True
except ImportError, e:
    scipy_install_is_ok = False
from .quick_phot import centroid, aperture_phot
from .ztv_wx_lib import validate_textctrl_str, textctrl_output_only_background_color, set_textctrl_background_color
from astropy import units
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
        self.axes_widget = AxesWidget(self.figure.gca())
        self.axes_widget.connect_event('motion_notify_event', self.on_motion)
        self.axes_widget.connect_event('button_press_event', self.on_button_press)
        self.axes_widget.connect_event('button_release_event', self.on_button_release)
        self.axes_widget.connect_event('figure_leave_event', self.on_cursor_leave)
        self.button_down = False
        
    def on_button_press(self, event):
        self.aper_names = ['aprad', 'skyradin', 'skyradout']
        self.aper_last_radii = np.array([self.ztv_frame.phot_panel.aprad, 
                                         self.ztv_frame.phot_panel.skyradin,
                                         self.ztv_frame.phot_panel.skyradout])
        self.button_press_xdata = event.xdata
        self.cur_aper_index = np.abs(self.aper_last_radii - event.xdata).argmin()
        self.cur_aper_name = self.aper_names[self.cur_aper_index]
        # but, click must be within +-N pix to be valid
        if np.abs(event.xdata - self.aper_last_radii[self.cur_aper_index]) <= 20:
            self.button_down = True

    def on_motion(self, event):
        if self.button_down:
            if event.xdata is not None:
                if self.cur_aper_name == 'aprad':
                    self.ztv_frame.phot_panel.aprad = (self.aper_last_radii[self.cur_aper_index] +
                                                       (event.xdata - self.button_press_xdata))
                    self.ztv_frame.phot_panel.aprad_textctrl.SetValue('{0:.2f}'.format(self.ztv_frame.phot_panel.aprad))
                    set_textctrl_background_color(self.ztv_frame.phot_panel.aprad_textctrl, 'ok')
                elif self.cur_aper_name == 'skyradin':
                    self.ztv_frame.phot_panel.skyradin = (self.aper_last_radii[self.cur_aper_index] +
                                                          (event.xdata - self.button_press_xdata))
                    self.ztv_frame.phot_panel.skyradin_textctrl.SetValue('{0:.2f}'.format( 
                                                                       self.ztv_frame.phot_panel.skyradin))
                    set_textctrl_background_color(self.ztv_frame.phot_panel.skyradin_textctrl, 'ok')
                elif self.cur_aper_name == 'skyradout':
                    self.ztv_frame.phot_panel.skyradout = (self.aper_last_radii[self.cur_aper_index] +
                                                           (event.xdata - self.button_press_xdata))
                    self.ztv_frame.phot_panel.skyradout_textctrl.SetValue('{0:.2f}'.format( 
                                                                       self.ztv_frame.phot_panel.skyradout))
                    set_textctrl_background_color(self.ztv_frame.phot_panel.skyradout_textctrl, 'ok')
                self.ztv_frame.phot_panel.recalc_phot()
                self.ztv_frame.phot_panel.redraw_overplot_on_image()

    def on_button_release(self, event):
        if self.button_down:
            if event.xdata is not None:
                if self.cur_aper_name == 'aprad':
                    self.ztv_frame.phot_panel.aprad = (self.aper_last_radii[self.cur_aper_index] +
                                                       (event.xdata - self.button_press_xdata))
                    self.ztv_frame.phot_panel.aprad_textctrl.SetValue('{0:.2f}'.format(self.ztv_frame.phot_panel.aprad))
                    set_textctrl_background_color(self.ztv_frame.phot_panel.aprad_textctrl, 'ok')
                elif self.cur_aper_name == 'skyradin':
                    self.ztv_frame.phot_panel.skyradin = (self.aper_last_radii[self.cur_aper_index] +
                                                          (event.xdata - self.button_press_xdata))
                    self.ztv_frame.phot_panel.skyradin_textctrl.SetValue('{0:.2f}'.format( 
                                                                       self.ztv_frame.phot_panel.skyradin))
                    set_textctrl_background_color(self.ztv_frame.phot_panel.skyradin_textctrl, 'ok')
                elif self.cur_aper_name == 'skyradout':
                    self.ztv_frame.phot_panel.skyradout = (self.aper_last_radii[self.cur_aper_index] +
                                                           (event.xdata - self.button_press_xdata))
                    self.ztv_frame.phot_panel.skyradout_textctrl.SetValue('{0:.2f}'.format( 
                                                                       self.ztv_frame.phot_panel.skyradout))
                    set_textctrl_background_color(self.ztv_frame.phot_panel.skyradout_textctrl, 'ok')
                self.ztv_frame.phot_panel.recalc_phot()
                self.ztv_frame.phot_panel.redraw_overplot_on_image()
        self.button_down = False
    
    def on_cursor_leave(self, event):
        if self.button_down:
            if self.cur_aper_name == 'aprad':
                self.ztv_frame.phot_panel.aprad = self.aper_last_radii[self.cur_aper_index]
                self.ztv_frame.phot_panel.aprad_textctrl.SetValue('{0:.2f}'.format(self.ztv_frame.phot_panel.aprad))
                set_textctrl_background_color(self.ztv_frame.phot_panel.aprad_textctrl, 'ok')
            elif self.cur_aper_name == 'skyradin':
                self.ztv_frame.phot_panel.skyradin = self.aper_last_radii[self.cur_aper_index]
                self.ztv_frame.phot_panel.skyradin_textctrl.SetValue('{0:.2f}'.format( 
                                                                   self.ztv_frame.phot_panel.skyradin))
                set_textctrl_background_color(self.ztv_frame.phot_panel.skyradin_textctrl, 'ok')
            elif self.cur_aper_name == 'skyradout':
                self.ztv_frame.phot_panel.skyradout = self.aper_last_radii[self.cur_aper_index]
                self.ztv_frame.phot_panel.skyradout_textctrl.SetValue('{0:.2f}'.format( 
                                                                   self.ztv_frame.phot_panel.skyradout))
                set_textctrl_background_color(self.ztv_frame.phot_panel.skyradout_textctrl, 'ok')
            self.ztv_frame.phot_panel.recalc_phot()
            self.ztv_frame.phot_panel.redraw_overplot_on_image()
        self.button_down=False

    def _onSize(self, event):
        self._SetSize()

    def _SetSize(self):
        pixels = tuple(self.GetClientSize())
        self.SetSize(pixels)
        self.canvas.SetSize(pixels)
        self.figure.set_size_inches(float(pixels[0])/self.figure.get_dpi(), float(pixels[1])/self.figure.get_dpi())


def fixed_gauss(x, fwhm, peakval):
    """
    Fit FWHM & peakval for a gaussian fixed at 0 and that baseline is 0.
    """
    c = fwhm / (2. * np.sqrt(2. * np.log(2.)))
    xc = 0.
    return peakval * np.exp(-((x - xc)**2) / (2.*c**2))


class PhotPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize)
        self.ztv_frame = self.GetTopLevelParent()
        self.star_center_patch = None
        self.star_aperture_patch = None
        self.sky_aperture_patch = None

        self.last_string_values = {'aprad':'', 'skyradin':'', 'skyradout':''}
        self.xclick = 0.
        self.yclick = 0.
        self.xcentroid = 0.
        self.ycentroid = 0.
        self.aprad = 10.
        self.skyradin = 20.
        self.skyradout = 30.
        self.phot_info = None
        
        self.aprad_color = 'blue'
        self.skyrad_color = 'red'
        self.alpha = 0.25
        
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
        values_sizer.Add(self.aprad_textctrl, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.aprad_textctrl.Bind(wx.EVT_TEXT, self.aprad_textctrl_changed)
        self.aprad_textctrl.Bind(wx.EVT_TEXT_ENTER, self.aprad_textctrl_entered)
        values_sizer.AddSpacer((30,0), 0, wx.EXPAND)
        self.x_static_text = wx.StaticText(self, wx.ID_ANY, u"x", wx.DefaultPosition, wx.DefaultSize, 
                                           wx.ALIGN_CENTER_HORIZONTAL )
        self.x_static_text.Wrap( -1 )
        values_sizer.Add(self.x_static_text, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM, 0)
        self.y_static_text = wx.StaticText(self, wx.ID_ANY, u"y", wx.DefaultPosition, wx.DefaultSize, 
                                           wx.ALIGN_CENTER_HORIZONTAL )
        self.y_static_text.Wrap( -1 )
        values_sizer.Add(self.y_static_text, 0, wx.ALL|wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM, 0)

        self.skyradin_static_text = wx.StaticText(self, wx.ID_ANY, u"Sky inner radius", 
                                                  wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.skyradin_static_text.Wrap( -1 )
        values_sizer.Add(self.skyradin_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.skyradin_textctrl = wx.TextCtrl(self, wx.ID_ANY, str(self.skyradin), wx.DefaultPosition, wx.DefaultSize,
                                       wx.TE_PROCESS_ENTER)
        self.skyradin_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.skyradin_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        self.skyradin_textctrl.Bind(wx.EVT_TEXT, self.skyradin_textctrl_changed)
        self.skyradin_textctrl.Bind(wx.EVT_TEXT_ENTER, self.skyradin_textctrl_entered)
        self.clicked_static_text = wx.StaticText(self, wx.ID_ANY, u"Clicked", wx.DefaultPosition, 
                                                 wx.DefaultSize, wx.ALIGN_RIGHT )
        self.clicked_static_text.Wrap( -1 )
        values_sizer.Add(self.clicked_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.xclick_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_READONLY)
        self.xclick_textctrl.SetFont(textentry_font)
        self.xclick_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        values_sizer.Add(self.xclick_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        self.yclick_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_READONLY)
        self.yclick_textctrl.SetFont(textentry_font)
        self.yclick_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        values_sizer.Add(self.yclick_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)

        self.skyradout_static_text = wx.StaticText(self, wx.ID_ANY, u"Sky outer radius", wx.DefaultPosition, 
                                                   wx.DefaultSize, wx.ALIGN_RIGHT )
        self.skyradout_static_text.Wrap( -1 )
        values_sizer.Add(self.skyradout_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.skyradout_textctrl = wx.TextCtrl(self, wx.ID_ANY, str(self.skyradout), wx.DefaultPosition, wx.DefaultSize,
                                              wx.TE_PROCESS_ENTER)
        self.skyradout_textctrl.SetFont(textentry_font)
        values_sizer.Add(self.skyradout_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        self.skyradout_textctrl.Bind(wx.EVT_TEXT, self.skyradout_textctrl_changed)
        self.skyradout_textctrl.Bind(wx.EVT_TEXT_ENTER, self.skyradout_textctrl_entered)
        self.centroid_static_text = wx.StaticText(self, wx.ID_ANY, u"Centroid", wx.DefaultPosition, 
                                                  wx.DefaultSize, wx.ALIGN_RIGHT )
        self.centroid_static_text.Wrap( -1 )
        values_sizer.Add(self.centroid_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.xcentroid_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                              wx.TE_READONLY)
        self.xcentroid_textctrl.SetFont(textentry_font)
        self.xcentroid_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        values_sizer.Add(self.xcentroid_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        self.ycentroid_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                              wx.TE_READONLY)
        self.ycentroid_textctrl.SetFont(textentry_font)
        self.ycentroid_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        values_sizer.Add(self.ycentroid_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)


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
                                        wx.TE_READONLY)
        self.sky_textctrl.SetFont(textentry_font)
        self.sky_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        h_sizer1.Add(self.sky_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        # TODO: look up how to do nice plus/minus symbol
        self.pm_static_text = wx.StaticText( self, wx.ID_ANY, u"+-", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.pm_static_text.Wrap( -1 )
        h_sizer1.Add(self.pm_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.skyerr_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                           wx.TE_READONLY)
        self.skyerr_textctrl.SetFont(textentry_font)
        self.skyerr_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        h_sizer1.Add(self.skyerr_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        self.perpixel_static_text = wx.StaticText( self, wx.ID_ANY, u"cts/pixel", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.perpixel_static_text.Wrap( -1 )
        h_sizer1.Add(self.perpixel_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        v_sizer1.Add(h_sizer1, 0, wx.ALIGN_LEFT)
        
        h_sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.flux_static_text = wx.StaticText( self, wx.ID_ANY, u"Flux", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.flux_static_text.Wrap( -1 )
        h_sizer2.Add(self.flux_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.flux_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                         wx.TE_READONLY)
        self.flux_textctrl.SetFont(textentry_font)
        self.flux_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        h_sizer2.Add(self.flux_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        self.cts_static_text = wx.StaticText( self, wx.ID_ANY, u"cts with FWHM", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.cts_static_text.Wrap( -1 )
        h_sizer2.Add(self.cts_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.fwhm_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                         wx.TE_READONLY)
        self.fwhm_textctrl.SetFont(textentry_font)
        self.fwhm_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        h_sizer2.Add(self.fwhm_textctrl, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        self.pix_static_text = wx.StaticText( self, wx.ID_ANY, u"pix", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.pix_static_text.Wrap( -1 )
        h_sizer2.Add(self.pix_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        v_sizer1.Add(h_sizer2, 0, wx.ALIGN_LEFT)

        h_sizer3 = wx.BoxSizer(wx.HORIZONTAL)
        self.radec_static_text = wx.StaticText( self, wx.ID_ANY, u"RADec", wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_RIGHT )
        self.radec_static_text.Wrap( -1 )
        h_sizer3.Add(self.radec_static_text, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 0)
        self.radec_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                          wx.TE_READONLY)
        self.radec_textctrl.SetFont(textentry_font)
        self.radec_textctrl.SetBackgroundColour(textctrl_output_only_background_color)
        h_sizer3.Add(self.radec_textctrl, 1, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 2)
        h_sizer3.AddSpacer([30, 0], 0, 0)
        self.hideshow_button = wx.Button(self, wx.ID_ANY, u"Hide", wx.DefaultPosition, wx.DefaultSize, 0)
        h_sizer3.Add(self.hideshow_button, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 2)
        self.hideshow_button.Bind(wx.EVT_BUTTON, self.on_hideshow_button)
        v_sizer1.Add(h_sizer3, 0, wx.ALIGN_LEFT)

        self.plot_panel = PhotPlotPanel(self)
        v_sizer1.Add(self.plot_panel, 1, wx.LEFT | wx.TOP | wx.EXPAND)

        self.SetSizer(v_sizer1)
        pub.subscribe(self.update_phot_xy, "new_phot_xy")
        pub.subscribe(self.recalc_phot, "redraw_image")

    def on_hideshow_button(self, evt):
        if self.hideshow_button.GetLabel() == 'Hide':
            self.remove_overplot_on_image()
        else:
            self.redraw_overplot_on_image()

    def remove_overplot_on_image(self, *args):
        if self.star_center_patch is not None:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.star_center_patch)
            self.star_center_patch = None
        if self.star_aperture_patch is not None:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.star_aperture_patch)
            self.star_aperture_patch = None
        if self.sky_aperture_patch is not None:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.sky_aperture_patch)
            self.sky_aperture_patch = None
        self.ztv_frame.primary_image_panel.figure.canvas.draw()
        self.hideshow_button.SetLabel(u"Show")

    def redraw_overplot_on_image(self, *args):
        if self.star_center_patch is not None:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.star_center_patch)
        if self.star_aperture_patch is not None:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.star_aperture_patch)
        if self.sky_aperture_patch is not None:
            self.ztv_frame.primary_image_panel.axes.patches.remove(self.sky_aperture_patch)
        self.star_center_patch = Circle([self.xcentroid, self.ycentroid], 0.125, color=self.aprad_color)
        self.ztv_frame.primary_image_panel.axes.add_patch(self.star_center_patch)
        self.star_aperture_patch = Circle([self.xcentroid, self.ycentroid], self.aprad, color=self.aprad_color, alpha=self.alpha)
        self.ztv_frame.primary_image_panel.axes.add_patch(self.star_aperture_patch)
        self.sky_aperture_patch = Wedge([self.xcentroid, self.ycentroid], self.skyradout, 0., 360., 
                                        width=self.skyradout - self.skyradin, color=self.skyrad_color, alpha=self.alpha)
        self.ztv_frame.primary_image_panel.axes.add_patch(self.sky_aperture_patch)
        self.ztv_frame.primary_image_panel.figure.canvas.draw()
        self.hideshow_button.SetLabel(u"Hide")

    def update_phot_xy(self, msg):
        self.xclick, self.yclick = msg
        self.recalc_phot()
        self.redraw_overplot_on_image()
        
    def recalc_phot(self, msg=None):
        self.xclick_textctrl.SetValue("{:8.2f}".format(self.xclick))
        self.yclick_textctrl.SetValue("{:8.2f}".format(self.yclick))
        self.xcentroid,self.ycentroid = centroid(self.ztv_frame.display_image, self.xclick, self.yclick)
        self.xcentroid_textctrl.SetValue("{:8.2f}".format(self.xcentroid))
        self.ycentroid_textctrl.SetValue("{:8.2f}".format(self.ycentroid))
        self.phot_info = aperture_phot(self.ztv_frame.display_image, self.xcentroid, self.ycentroid, 
                             self.aprad, self.skyradin, self.skyradout, return_distances=True)
        self.phot_info['xclick'] = self.xclick
        self.phot_info['yclick'] = self.yclick
        self.phot_info['xcentroid'] = self.xcentroid
        self.phot_info['ycentroid'] = self.ycentroid
        self.flux_textctrl.SetValue("{:0.6g}".format(self.phot_info['flux']))
        self.sky_textctrl.SetValue("{:0.6g}".format(self.phot_info['sky_per_pixel']))
        self.skyerr_textctrl.SetValue("{:0.6g}".format(self.phot_info['sky_per_pixel_err']))
        if (self.ztv_frame.image_radec is not None and
            np.isfinite(self.xcentroid) and np.isfinite(self.ycentroid)):
            c = self.ztv_frame.image_radec[self.ycentroid, self.xcentroid]
            radec_string = "{0} {1}".format(c.ra.to_string(units.hour, sep=':', precision=2, pad=True),
                                            c.dec.to_string(sep=':', precision=2, alwayssign=True, pad=True))
            self.radec_textctrl.SetValue(radec_string)
        else:
            self.radec_textctrl.SetValue(' ')
        self.plot_panel.axes.cla()
        if len(self.phot_info['distances']) > 5:
            unrounded_xmax = self.skyradout + 0.2 * (self.skyradout - self.skyradin)
            nice_factor = 10./5.
            sensible_xmax = ((nice_factor*10**np.floor(np.log10(unrounded_xmax))) * 
                             np.ceil(unrounded_xmax / (nice_factor*10**np.floor(np.log10(unrounded_xmax)))))
            mask = self.phot_info['distances'] <= sensible_xmax
            self.plot_panel.axes.plot(self.phot_info['distances'][mask].ravel(), 
                                      self.ztv_frame.display_image[mask].ravel(), 'ko', markersize=1)
            ylim = self.plot_panel.axes.get_ylim()
            n_sigma = 6.
            if (self.phot_info['sky_per_pixel'] - 
                n_sigma*self.phot_info['sky_per_pixel_err']*np.sqrt(self.phot_info['n_sky_pix'])) > 0.:
                ylim = (self.phot_info['sky_per_pixel'] - 
                        n_sigma*self.phot_info['sky_per_pixel_err']*np.sqrt(self.phot_info['n_sky_pix']), ylim[1])
            self.plot_panel.axes.set_ylim(ylim)
            self.plot_panel.axes.fill_between([0., self.aprad], [ylim[0], ylim[0]], [ylim[1], ylim[1]], 
                                              facecolor=self.aprad_color, alpha=self.alpha)
            self.plot_panel.axes.fill_between([self.skyradin, self.skyradout], [ylim[0], ylim[0]], [ylim[1], ylim[1]], 
                                              facecolor=self.skyrad_color, alpha=self.alpha)
            self.plot_panel.axes.plot([0, sensible_xmax], [self.phot_info['sky_per_pixel'], 
                                                           self.phot_info['sky_per_pixel']], '-r')
            self.plot_panel.axes.plot([0, sensible_xmax], [self.phot_info['sky_per_pixel'] - 
                                                           self.phot_info['sky_per_pixel_err'], 
                                                           self.phot_info['sky_per_pixel'] - 
                                                           self.phot_info['sky_per_pixel_err']], ':r')
            self.plot_panel.axes.plot([0, sensible_xmax], [self.phot_info['sky_per_pixel'] + 
                                                           self.phot_info['sky_per_pixel_err'], 
                                                           self.phot_info['sky_per_pixel'] + 
                                                           self.phot_info['sky_per_pixel_err']], ':r')
            self.plot_panel.axes.set_xlim([0, sensible_xmax])
            mask = self.phot_info['distances'] <= self.aprad
            xs = self.phot_info['distances'][mask]
            vals = self.ztv_frame.display_image[mask] - self.phot_info['sky_per_pixel']
            p0 = [self.aprad*0.3, vals.max()]
            if scipy_install_is_ok:
                popt, pcov = curve_fit(fixed_gauss, xs, vals, p0=p0)
                xs = np.arange(0, self.aprad+0.1, 0.1)
                c = popt[0] / (2. * np.sqrt(2. * np.log(2.)))
                self.plot_panel.axes.plot(xs, self.phot_info['sky_per_pixel'] + 
                                              popt[1] * np.exp(-((xs)**2) / (2.*c**2)), '-', color=self.aprad_color)
                self.fwhm_textctrl.SetValue("{:0.3g}".format(np.abs(popt[0])))
            else:
                self.fwhm_textctrl.SetValue("n/a")
                sys.stderr.write("ztv.phot_panel warning: scipy not installed OK. " + 
                                 "Gaussfit to PSF radial profile unavailable\n")
        self.plot_panel.figure.canvas.draw()

    def aprad_textctrl_changed(self, evt):
        validate_textctrl_str(self.aprad_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                              self.last_string_values['aprad'])

    def aprad_textctrl_entered(self, evt):
        if validate_textctrl_str(self.aprad_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                                 self.last_string_values['aprad']):
            self.last_string_values['aprad'] = self.aprad_textctrl.GetValue()
            self.aprad = float(self.last_string_values['aprad'])
            self.recalc_phot()
            self.redraw_overplot_on_image()
            validate_textctrl_str(self.aprad_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                                  self.last_string_values['aprad'])
            self.aprad_textctrl.SetSelection(-1, -1)

    def skyradin_textctrl_changed(self, evt):
        validate_textctrl_str(self.skyradin_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                              self.last_string_values['skyradin'])

    def skyradin_textctrl_entered(self, evt):
        if validate_textctrl_str(self.skyradin_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                                 self.last_string_values['skyradin']):
            self.last_string_values['skyradin'] = self.skyradin_textctrl.GetValue()
            self.skyradin = float(self.last_string_values['skyradin'])
            self.recalc_phot()
            self.redraw_overplot_on_image()
            validate_textctrl_str(self.skyradin_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                                  self.last_string_values['skyradin'])
            self.skyradin_textctrl.SetSelection(-1, -1)

    def skyradout_textctrl_changed(self, evt):
        validate_textctrl_str(self.skyradout_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                              self.last_string_values['skyradout'])

    def skyradout_textctrl_entered(self, evt):
        if validate_textctrl_str(self.skyradout_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                                 self.last_string_values['skyradout']):
            self.last_string_values['skyradout'] = self.skyradout_textctrl.GetValue()
            self.skyradout = float(self.last_string_values['skyradout'])
            self.recalc_phot()
            self.redraw_overplot_on_image()
            validate_textctrl_str(self.skyradout_textctrl, lambda x: float(x) if float(x) > 0 else float('x'), 
                                  self.last_string_values['skyradout'])
            self.skyradout_textctrl.SetSelection(-1, -1)
            
