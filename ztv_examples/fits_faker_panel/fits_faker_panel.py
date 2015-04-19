from __future__ import absolute_import
import wx
from .fake_fits_maker import FakeFitsMaker
from wx.lib.pubsub import Publisher

class FitsFakerPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        v_sizer1.AddSpacer((0, 0), 1, wx.EXPAND)

        static_text = wx.StaticText(self, wx.ID_ANY, u"Fits Faker", wx.DefaultPosition, wx.DefaultSize, 
                                    wx.ALIGN_CENTER )
        static_text.Wrap( -1 )
        v_sizer1.Add(static_text, 0, wx.ALL|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 0)

        static_text = wx.StaticText(self, wx.ID_ANY, u"Example of a panel added-on to ztv", wx.DefaultPosition, 
                                    wx.DefaultSize, wx.ALIGN_CENTER )
        static_text.Wrap( -1 )
        v_sizer1.Add(static_text, 0, wx.ALL|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 0)

        self.launch_button = wx.Button(self, wx.ID_ANY, u"Launch Fake Fits Maker", wx.DefaultPosition, wx.DefaultSize, 0)
        v_sizer1.Add(self.launch_button, 0, wx.ALL|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 2)
        self.launch_button.Bind(wx.EVT_BUTTON, self.on_launch_button)

        self.halt_button = wx.Button(self, wx.ID_ANY, u"Halt Fake Fits Maker", wx.DefaultPosition, wx.DefaultSize, 0)
        v_sizer1.Add(self.halt_button, 0, wx.ALL|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 2)
        self.halt_button.Bind(wx.EVT_BUTTON, self.on_halt_button)
        self.halt_button.Disable()
        
        static_text = wx.StaticText(self, wx.ID_ANY, u"Note: clicking 'Halt' will delete files in /tmp/ for you", wx.DefaultPosition, 
                                    wx.DefaultSize, wx.ALIGN_CENTER )
        static_text.Wrap( -1 )
        v_sizer1.Add(static_text, 0, wx.ALL|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 0)
        static_text = wx.StaticText(self, wx.ID_ANY, u"If you don't click Halt, you may want to go clean up *.fits in /tmp/", 
                                    wx.DefaultPosition, wx.DefaultSize, wx.ALIGN_CENTER )
        static_text.Wrap( -1 )
        v_sizer1.Add(static_text, 0, wx.ALL|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 0)

        v_sizer1.AddSpacer((0, 0), 1, wx.EXPAND)
        self.SetSizer(v_sizer1)
        Publisher().subscribe(self.on_launch_button, "fits-faker-start")
        Publisher().subscribe(self.on_halt_button, "fits-faker-stop")

    def on_launch_button(self, evt=None):
        self.fake_fits_maker = FakeFitsMaker(ztv_frame_pid=self.ztv_frame.ztv_frame_pid)
        self.fake_fits_maker.start()
        self.launch_button.Disable()
        self.halt_button.Enable()
        self.ztv_frame.source_panel.load_sky_frame('/tmp/sky_frame.fits', False)
        self.ztv_frame.source_panel.load_flat_frame('/tmp/flat_frame.fits', False)
        self.ztv_frame.source_panel.autoload_curfile_file_picker_on_load('/tmp/n*.fits')    

    def on_halt_button(self, evt=None):
        self.launch_button.Enable()
        self.halt_button.Disable()
        self.fake_fits_maker.keep_running = False