import wx
            
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

#         self.clear_button = wx.Button(self, wx.ID_ANY, u"Clear", wx.DefaultPosition, wx.DefaultSize, 0)
#         h_sizer2.Add(self.clear_button, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 2)
#         self.clear_button.Bind(wx.EVT_BUTTON, self.on_clear_button)

        v_sizer1.AddSpacer((0, 0), 1, wx.EXPAND)
        self.SetSizer(v_sizer1)
