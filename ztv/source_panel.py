from __future__ import absolute_import
import wx
from wx.lib.pubsub import Publisher
from .file_picker import FilePicker
from .fits_header_dialog import FITSHeaderDialog
from .image_process_action import ImageProcessAction
import numpy as np
import os
import os.path
import sys
from .ztv_lib import set_textctrl_background_color

class SourcePanel(wx.Panel):
    def __init__(self, parent):
        self.sky_hdulist = None
        self.flat_hdulist = None
        self.sky_file_basename = ''
        self.flat_file_basename = ''
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.ztv_frame = self.GetTopLevelParent()
        Publisher().subscribe(self.on_fitsfile_loaded, "fitsfile-loaded")
        self.max_items_in_curfile_history = 20
        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        v_sizer1.AddSpacer((0, 0), 1, wx.EXPAND)

        h_current_file_picker_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.curfile_file_picker = FilePicker(self, title='')
        self.curfile_file_picker.on_load = self.ztv_frame.load_fits_file
        h_current_file_picker_sizer.Add(self.curfile_file_picker, 1, wx.EXPAND)
        self.cur_header_button = wx.Button(self, wx.ID_ANY, u"hdr", wx.DefaultPosition, wx.DefaultSize,
                                            style=wx.BU_EXACTFIT)
        h_current_file_picker_sizer.Add(self.cur_header_button, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 0)
        self.cur_header_button.Bind(wx.EVT_BUTTON, self.ztv_frame.primary_image_panel.on_display_cur_fits_header)
        v_sizer1.Add(h_current_file_picker_sizer, 0, wx.EXPAND)

        v_sizer1.AddSpacer((0, 5), 0, wx.EXPAND)
        self.sky_file_picker_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sky_checkbox = wx.CheckBox(self, -1, "")
        self.Bind(wx.EVT_CHECKBOX, self.on_sky_checkbox, self.sky_checkbox)
        self.sky_file_picker_sizer.Add(self.sky_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)
        self.skyfile_file_picker = FilePicker(self, title='Sky:', default_entry='', 
                                              maintain_default_entry_in_recents=0)
        self.skyfile_file_picker.on_load = self.load_sky_frame
        self.sky_file_picker_sizer.Add(self.skyfile_file_picker, 1, wx.EXPAND)
        self.sky_header_button = wx.Button(self, wx.ID_ANY, u"hdr", wx.DefaultPosition, wx.DefaultSize,
                                           style=wx.BU_EXACTFIT)
        self.sky_file_picker_sizer.Add(self.sky_header_button, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 0)
        self.sky_header_button.Bind(wx.EVT_BUTTON, self.on_display_sky_fits_header)
        v_sizer1.Add(self.sky_file_picker_sizer, 0, wx.EXPAND)

        self.flat_file_picker_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.flat_checkbox = wx.CheckBox(self, -1, "")
        self.Bind(wx.EVT_CHECKBOX, self.on_flat_checkbox, self.flat_checkbox)
        self.flat_file_picker_sizer.Add(self.flat_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)
        self.flatfile_file_picker = FilePicker(self, title='Flat:', default_entry='', 
                                               maintain_default_entry_in_recents=0)
        self.flatfile_file_picker.on_load = self.load_flat_frame
        self.flat_file_picker_sizer.Add(self.flatfile_file_picker, 1, wx.EXPAND)
        self.flat_header_button = wx.Button(self, wx.ID_ANY, u"hdr", wx.DefaultPosition, wx.DefaultSize,
                                            style=wx.BU_EXACTFIT)
        self.flat_file_picker_sizer.Add(self.flat_header_button, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 0)
        self.flat_header_button.Bind(wx.EVT_BUTTON, self.on_display_flat_fits_header)
        v_sizer1.Add(self.flat_file_picker_sizer, 0, wx.EXPAND)

        self.autoload_sizer = wx.BoxSizer(wx.VERTICAL)        
        self.autoload_sizer.AddSpacer((0, 5), 0, wx.EXPAND)
        self.autoload_sizer.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 5)
        self.autoload_sizer.AddSpacer((0, 5), 0, wx.EXPAND)

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
        self.autoload_sizer.Add(h_sizer, 0, wx.EXPAND)
        self.autoload_sizer.AddSpacer((0, 5), 0, wx.EXPAND)
#         self.autoload_curdir_file_picker = FilePicker(self, title='Dir:', is_files_not_dirs=False)
#         self.autoload_sizer.Add(self.autoload_curdir_file_picker, 0, wx.EXPAND)
#         self.autoload_curfile_file_picker = FilePicker(self, title='Filename Pattern:', allow_glob_matching=True,
#                                                        assumed_prefix=os.path.expanduser('~/'))
#         self.autoload_curdir_file_picker.on_load = self.autoload_curfile_file_picker.set_assumed_prefix
#         self.autoload_curfile_file_picker.on_load = self.autoload_curfile_file_picker_on_load
        self.autoload_curfile_file_picker = FilePicker(self, title='Filename Pattern:', allow_glob_matching=True)
        self.autoload_curfile_file_picker.on_load = self.autoload_curfile_file_picker_on_load
        self.autoload_sizer.Add(self.autoload_curfile_file_picker, 0, wx.EXPAND)
        v_sizer1.Add(self.autoload_sizer, 0, wx.EXPAND)
        
        self.activemq_sizer = wx.BoxSizer(wx.VERTICAL)        
        self.activemq_sizer.AddSpacer((0, 10), 0, wx.EXPAND)
        self.activemq_sizer.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 5)
        self.activemq_sizer.AddSpacer((0, 5), 0, wx.EXPAND)

        h_queue_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.message_queue_checkbox = wx.CheckBox(self, -1, "ActiveMQ")
        self.Bind(wx.EVT_CHECKBOX, self.on_message_queue_checkbox, self.message_queue_checkbox)
        h_queue_sizer.Add(self.message_queue_checkbox, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)

        self.message_queue_choice = wx.Choice(self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize,
                                              ['No message queues available'], 0)
        h_queue_sizer.Add(self.message_queue_choice, 1, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
        Publisher().subscribe(self.on_activemq_instances_info_changed, "activemq_instances_info-changed")
        self.Bind(wx.EVT_CHOICE, self.on_message_queue_choice, self.message_queue_choice)
        self.activemq_sizer.Add(h_queue_sizer, 0, wx.EXPAND)
        v_sizer1.Add(self.activemq_sizer, 0, wx.EXPAND)
        
        v_sizer1.AddSpacer((0, 0), 1, wx.EXPAND)
        
        bottom_sizer = wx.BoxSizer(wx.VERTICAL)        
        self.init_settings_popup_menu()
        gear_bitmap = wx.EmptyBitmap( 20, 20 )
        self.settings_button = wx.Button(self, wx.ID_ANY, u'\u2699', wx.DefaultPosition, wx.DefaultSize, 
                                         style=wx.BU_EXACTFIT|wx.BORDER_NONE)
        self.settings_button.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, 
                                             wx.FONTWEIGHT_NORMAL, True))
        self.settings_button.Bind(wx.EVT_LEFT_DOWN, self.on_settings_button)
        bottom_sizer.Add(self.settings_button, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM, 0)
        v_sizer1.Add(bottom_sizer, 0, wx.EXPAND)
        self.SetSizer(v_sizer1)
        self.sky_header_button.Disable()
        self.flat_header_button.Disable()
        Publisher().subscribe(self.update_cur_header_button_status, "redraw_image")
        
#         TODO: while hidden is the correct default for activemq, this should be handled with an argument
# TODO: but, following two lines of code fail, because layout is then messed up
#         self.settings_menu_activemq_item.Check(False)
#         self.activemq_sizer.ShowItems(False)

    def init_settings_popup_menu(self):
        menu = wx.Menu()
        menu.Append(wx.NewId(), 'Show in GUI:').Enable(False)
        wx_id = wx.NewId()
        self.settings_menu_sky_item = menu.AppendCheckItem(wx_id, '   Sky')
        wx.EVT_MENU(menu, wx_id, self.on_settings_menu_sky_item)
        self.settings_menu_sky_item.Check(True)
        wx_id = wx.NewId()
        self.settings_menu_flat_item = menu.AppendCheckItem(wx_id, '   Flat')
        wx.EVT_MENU(menu, wx_id, self.on_settings_menu_flat_item)
        self.settings_menu_flat_item.Check(True)
        wx_id = wx.NewId()
        self.settings_menu_autoload_item = menu.AppendCheckItem(wx_id, '   Auto-load')
        wx.EVT_MENU(menu, wx_id, self.on_settings_menu_autoload_item)
        self.settings_menu_autoload_item.Check(True)
        wx_id = wx.NewId()
        self.settings_menu_activemq_item = menu.AppendCheckItem(wx_id, '   ActiveMQ')
        wx.EVT_MENU(menu, wx_id, self.on_settings_menu_activemq_item)
        self.settings_menu_activemq_item.Check(True)
        self.settings_popup_menu = menu

    def on_settings_menu_sky_item(self, evt):
        if evt.IsChecked():
            self.sky_file_picker_sizer.ShowItems(True)
        else:
            self.sky_file_picker_sizer.ShowItems(False)

    def on_settings_menu_flat_item(self, evt):
        if evt.IsChecked():
            self.flat_file_picker_sizer.ShowItems(True)
        else:
            self.flat_file_picker_sizer.ShowItems(False)

    def on_settings_menu_autoload_item(self, evt):
        if evt.IsChecked():
            self.autoload_sizer.ShowItems(True)
        else:
            self.autoload_sizer.ShowItems(False)

    def on_settings_menu_activemq_item(self, evt):
        if evt.IsChecked():
            self.activemq_sizer.ShowItems(True)
        else:
            self.activemq_sizer.ShowItems(False)

    def on_settings_button(self, evt):
        pos = self.ScreenToClient(wx.GetMousePosition())
        self.PopupMenu(self.settings_popup_menu, pos)

    def on_display_sky_fits_header(self, event):
        raw_header_str = self.sky_hdulist[0].header.tostring()
        header_str = (('\n'.join([raw_header_str[i:i+80] for i in np.arange(0, len(raw_header_str), 80)
                                  if raw_header_str[i:i+80] != " "*80])) + '\n')
        new_title = "Sky: " + self.sky_file_basename
        if hasattr(self, 'sky_fits_header_dialog') and self.sky_fits_header_dialog.is_dialog_still_open:
            self.sky_fits_header_dialog.SetTitle(new_title)
            self.sky_fits_header_dialog.text.SetValue(header_str)
            self.sky_fits_header_dialog.last_find_index = 0
            self.sky_fits_header_dialog.on_search(None)
        else:
            self.sky_fits_header_dialog = FITSHeaderDialog(self, header_str, new_title)
            self.sky_fits_header_dialog.Show()

    def on_display_flat_fits_header(self, event):
        raw_header_str = self.flat_hdulist[0].header.tostring()
        header_str = (('\n'.join([raw_header_str[i:i+80] for i in np.arange(0, len(raw_header_str), 80)
                                  if raw_header_str[i:i+80] != " "*80])) + '\n')
        new_title = "Flat: " + self.flat_file_basename
        if hasattr(self, 'flat_fits_header_dialog') and self.flat_fits_header_dialog.is_dialog_still_open:
            self.flat_fits_header_dialog.SetTitle(new_title)
            self.flat_fits_header_dialog.text.SetValue(header_str)
            self.flat_fits_header_dialog.last_find_index = 0
            self.flat_fits_header_dialog.on_search(None)
        else:
            self.flat_fits_header_dialog = FITSHeaderDialog(self, header_str, new_title)
            self.flat_fits_header_dialog.Show()

    def update_cur_header_button_status(self, msg):
        if self.ztv_frame.cur_fits_hdulist is not None:
            self.cur_header_button.Enable()
        else:
            self.cur_header_button.Disable()

    def unload_sky_subtraction_from_process_stack(self):
        proc_labels = [x[0] for x in self.ztv_frame.image_process_functions_to_apply]
        if 'sky_subtraction' in proc_labels:
            self.ztv_frame.image_process_functions_to_apply.pop(proc_labels.index('sky_subtraction'))
            self.ztv_frame.redisplay_image()

    def load_sky_subtraction_to_process_stack(self):
        self.unload_sky_subtraction_from_process_stack()
        if self.sky_hdulist is not None:
            process_fxn = ImageProcessAction(np.subtract, self.sky_hdulist[0].data)
            # assume that sky subtraction should always be first in processing stack.
            self.ztv_frame.image_process_functions_to_apply.insert(0, ('sky_subtraction', process_fxn))
            self.ztv_frame.redisplay_image()

    def load_sky_frame(self, filename, start_sky_correction=True):
        if len(filename) == 0:
            self.sky_hdulist = None
            self.sky_header_button.Disable()
            self.unload_sky_subtraction_from_process_stack()
            self.sky_checkbox.SetValue(False)
        else:
            self.sky_hdulist = self.ztv_frame.load_hdulist_from_fitsfile(filename)
            self.sky_file_basename = os.path.basename(filename)
            self.sky_header_button.Enable()
            if start_sky_correction:
                self.load_sky_subtraction_to_process_stack()
                self.sky_checkbox.SetValue(True)
            self.skyfile_file_picker.pause_on_current_textctrl_changed = True
            self.skyfile_file_picker.set_current_entry(filename)
            self.flatfile_file_picker.pause_on_current_textctrl_changed = False

    def on_sky_checkbox(self, evt):
        if evt.IsChecked():
            self.load_sky_subtraction_to_process_stack()
        else:
            self.unload_sky_subtraction_from_process_stack()

    def unload_flat_division_from_process_stack(self):
        proc_labels = [x[0] for x in self.ztv_frame.image_process_functions_to_apply]
        if 'flat_division' in proc_labels:
            self.ztv_frame.image_process_functions_to_apply.pop(proc_labels.index('flat_division'))
            self.ztv_frame.redisplay_image()

    def load_flat_division_to_process_stack(self):
        self.unload_flat_division_from_process_stack()
        if self.flat_hdulist is not None:
            process_fxn = ImageProcessAction(np.divide, self.flat_hdulist[0].data)
            # assume that flat division should always be last in processing stack.
            self.ztv_frame.image_process_functions_to_apply.insert(99999, ('flat_division', process_fxn))
            self.ztv_frame.redisplay_image()

    def load_flat_frame(self, filename, start_flat_correction=True):
        if len(filename) == 0:
            self.flat_hdulist = None
            self.flat_header_button.Disable()
            self.unload_flat_division_from_process_stack()
            self.flat_checkbox.SetValue(False)
        else:
            self.flat_hdulist = self.ztv_frame.load_hdulist_from_fitsfile(filename)
            self.flat_file_basename = os.path.basename(filename)
            self.flat_header_button.Enable()
            if start_flat_correction:
                self.load_flat_division_to_process_stack()
                self.flat_checkbox.SetValue(True)
            self.flatfile_file_picker.pause_on_current_textctrl_changed = True
            self.flatfile_file_picker.set_current_entry(filename)
            self.flatfile_file_picker.pause_on_current_textctrl_changed = False

    def on_flat_checkbox(self, evt):
        if evt.IsChecked():
            self.load_flat_division_to_process_stack()
        else:
            self.unload_flat_division_from_process_stack()

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

    def autoload_curfile_file_picker_on_load(self, new_entry):
        new_path = os.path.dirname(new_entry) + '/'
        self.autoload_curfile_file_picker.set_current_entry(new_entry)
        self.ztv_frame.autoload_match_string = new_entry
        self.message_queue_checkbox.SetValue(False)
        self.autoload_checkbox.SetValue(True)
        self.ztv_frame.kill_activemq_listener_thread()
        self.ztv_frame.autoload_mode = 'file-match'
        self.ztv_frame.launch_autoload_filematch_thread()
        set_textctrl_background_color(self.autoload_curfile_file_picker.current_textctrl, 'ok')

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
        self.curfile_file_picker.pause_on_current_textctrl_changed = True
        self.curfile_file_picker.set_current_entry(os.path.join(self.ztv_frame.cur_fitsfile_path,
                                                                self.ztv_frame.cur_fitsfile_basename))
        self.curfile_file_picker.pause_on_current_textctrl_changed = False
