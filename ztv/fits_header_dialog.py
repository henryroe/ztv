import wx

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
        self.raw_header_str_lower = raw_header_str.lower()
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
        new_id = wx.NewId()
        self.Bind(wx.EVT_MENU, self.on_cmd_w, id=new_id)
        self.SetAcceleratorTable(wx.AcceleratorTable([(wx.ACCEL_CMD, ord(str('w')), new_id)]))

    def on_cmd_w(self, evt):
        self.is_dialog_still_open = False
        self.Close()

    def on_close(self, evt):
        self.is_dialog_still_open = False
        evt.Skip(True)

    def set_cur_selection(self):
        self.text.SetSelection(self.cur_selection[0], self.cur_selection[1])

    def on_search(self, evt):
        # search case-agnostic by converting everything to lower
        search_str = self.search.GetValue().lower()
        if search_str != "":
            if search_str in self.raw_header_str_lower:
                if search_str != self.last_search_str:
                    self.last_find_index = 0
                pos0 = self.raw_header_str_lower.find(search_str, self.last_find_index)
                if pos0 == -1:
                    pos0 = self.raw_header_str_lower.find(search_str)
                if pos0 - 80 < 0:
                    start_selection = 0
                else:
                    start_selection = self.raw_header_str_lower.find('\n', pos0 - 80) + 1
                self.cur_selection = (start_selection,
                                      self.raw_header_str_lower.find('\n', pos0))
                self.set_cur_selection()
                self.last_find_index = self.raw_header_str_lower.find('\n', pos0)
                self.last_search_str = search_str
        else:
            self.last_search_str = ''

