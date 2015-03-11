import wx
from wx.lib.pubsub import Publisher
from .filepicker import FilePicker

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
