from __future__ import absolute_import
import wx
from wx.lib.pubsub import pub
from .file_picker import FilePicker
from .fits_header_dialog import FITSHeaderDialog
from .image_process_action import ImageProcessAction
import numpy as np
import os
import glob
import sys
import time
import threading
from .ztv_wx_lib import set_textctrl_background_color
try:
    import stomp
    stomp_install_is_ok = True
except ImportError, e:
    stomp_install_is_ok = False


class ActiveMQListener(object):
    def __init__(self):
        pass
    def on_error(self, headers, message):
        sys.stderr.write("received an error: {}\n".format(message))
    def on_message(self, headers, message):
        try:
            msg = pickle.loads(message)
            if msg.has_key('image_data'):
                wx.CallAfter(pub.sendMessage, "load_numpy_array", msg=msg['image_data'])
        except UnpicklingError:
            sys.stderr.write('received an unhandled message ({})\n'.format(message))


class ActiveMQNotAvailable(Exception): pass


class ActiveMQListenerThread(threading.Thread):
    def __init__(self, source_panel, condition):
        if not stomp_install_is_ok:
            sys.stderr.write("ztv source_panel warning: stomp not installed OK, ActiveMQ functionality not available\n")
            raise ActiveMQNotAvailable
        threading.Thread.__init__(self)
        self.source_panel = source_panel
        self.condition = condition
        self.daemon = True
        self.start()

    def run(self):
        server = self.source_panel.activemq_instances_info[self.source_panel.activemq_selected_instance]['server']
        port = self.source_panel.activemq_instances_info[self.source_panel.activemq_selected_instance]['port']
        dest = self.source_panel.activemq_instances_info[self.source_panel.activemq_selected_instance]['destination']
        conn = stomp.Connection([(server, port)])
        activemq_listener = ActiveMQListener()
        conn.set_listener('', activemq_listener)
        conn.start()
        conn.connect()
        # browser='true' means leave the messages intact on server; 'false' means consume them destructively
        conn.subscribe(destination=dest, id=1, ack='auto', headers={'browser':'false'})
        with self.condition:
            self.condition.wait()
        conn.disconnect()


class AutoloadFileMatchWatcherThread(threading.Thread):
    def __init__(self, source_panel):
        threading.Thread.__init__(self)
        self.source_panel = source_panel
        self.keep_running = True
        self.daemon = True
        self.start()

    def run(self):
        latest_mtime = 0.0
        while self.keep_running:
            filename_to_open = None
            possible_matches = glob.glob(self.source_panel.autoload_match_string)
            if len(possible_matches) > 0:
                for cur_match in possible_matches:
                    cur_match_mtime = os.path.getmtime(cur_match)
                    if cur_match_mtime > latest_mtime:
                        filename_to_open = cur_match
                        latest_mtime = cur_match_mtime
                if filename_to_open is not None:
                    wx.CallAfter(pub.sendMessage, "load_fits_file", msg=filename_to_open)
            time.sleep(self.source_panel.autoload_pausetime)
            if self.source_panel.autoload_mode != 'file-match':
                self.keep_running = False


class UnrecognizedNumberOfDimensions(Exception): pass


class SourcePanel(wx.Panel):
    def __init__(self, parent):
        self.autoload_mode = None # other options are "file-match" and "activemq-stream"
        self.autoload_pausetime_choices = [0.1, 0.5, 1, 2, 5, 10]
        # NOTE: Mac OS X truncates file modification times to integer seconds, so ZTV cannot distinguish a newer file
        #       unless it appears in the next integer second from the prior file.  The <1 sec pausetimes may still be
        #       desirable to minimize latency.
        self.autoload_pausetime = self.autoload_pausetime_choices[0]
        self.autoload_match_string = ''
        self.autoload_filematch_thread = None
        pub.subscribe(self._add_activemq_instance, "add_activemq_instance")
        self.stomp_install_is_ok = stomp_install_is_ok
        self.activemq_instances_info = {}  # will be dict of dicts of, e.g.:
                                           # {'server':'s1.me.com', 'port':61613, 'destination':'my.queue.name'}
                                           # with the top level keys looking like:  server:port:destination
        self.activemq_instances_available = []
        self.activemq_selected_instance = None
        self.activemq_listener_thread = None
        self.activemq_listener_condition = threading.Condition()
        self.sky_hdulist = None
        self.flat_hdulist = None
        self.sky_file_fullname = ''
        self.flat_file_fullname = ''
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize)
        self.ztv_frame = self.GetTopLevelParent()
        pub.subscribe(self.on_fitsfile_loaded, "fitsfile-loaded")
        self.max_items_in_curfile_history = 20
        v_sizer1 = wx.BoxSizer(wx.VERTICAL)
        v_sizer1.AddSpacer((0, 0), 1, wx.EXPAND)

        h_current_file_picker_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.curfile_file_picker = FilePicker(self, title='', default_entry=self.ztv_frame.default_data_dir)
        self.curfile_file_picker.on_load = self.ztv_frame.load_fits_file
        h_current_file_picker_sizer.Add(self.curfile_file_picker, 1, wx.EXPAND)
        self.cur_header_button = wx.Button(self, wx.ID_ANY, u"hdr", wx.DefaultPosition, wx.DefaultSize,
                                            style=wx.BU_EXACTFIT)
        h_current_file_picker_sizer.Add(self.cur_header_button, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 0)
        self.cur_header_button.Bind(wx.EVT_BUTTON, self.ztv_frame.primary_image_panel.on_display_cur_fits_header)
        v_sizer1.Add(h_current_file_picker_sizer, 0, wx.EXPAND)

        self.load_current_to_sky_button = wx.Button(self, wx.ID_ANY, 
                                                    u"\u2193\u2193Make current image the sky frame\u2193\u2193", 
                                                    wx.DefaultPosition, wx.DefaultSize)
        self.load_current_to_sky_button.Bind(wx.EVT_BUTTON, self.on_load_current_to_sky)
        v_sizer1.Add(self.load_current_to_sky_button, 0, wx.CENTER)

        v_sizer1.AddSpacer((0, 5), 0, wx.EXPAND)
        self.sky_file_picker_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sky_checkbox = wx.CheckBox(self, -1, "")
        self.Bind(wx.EVT_CHECKBOX, self.on_sky_checkbox, self.sky_checkbox)
        self.sky_file_picker_sizer.Add(self.sky_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)
        self.skyfile_file_picker = FilePicker(self, title='Sky:', default_entry=self.ztv_frame.default_data_dir, 
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
        self.flatfile_file_picker = FilePicker(self, title='Flat:', default_entry=self.ztv_frame.default_data_dir, 
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
        pausetime_index = self.autoload_pausetime_choices.index(self.autoload_pausetime)
        self.autoload_pausetime_choice = wx.Choice(self, wx.ID_ANY, wx.DefaultPosition, (50, -1),
                                                   [str(a) for a in self.autoload_pausetime_choices], 0)
        self.autoload_pausetime_choice.SetSelection(pausetime_index)
        self.autoload_pausetime_choice.Bind(wx.EVT_CHOICE, self.on_choose_autoload_pausetime)
        h_sizer.Add(wx.StaticText(self, -1, u"Pause"), 0)
        h_sizer.Add(self.autoload_pausetime_choice, 0)
        h_sizer.Add(wx.StaticText(self, -1, u"sec"), 0)
        self.autoload_sizer.Add(h_sizer, 0, wx.EXPAND)
        self.autoload_sizer.AddSpacer((0, 5), 0, wx.EXPAND)
        self.autoload_curfile_file_picker = FilePicker(self, title='Filename Pattern:', allow_glob_matching=True, 
                                                       default_entry=self.ztv_frame.default_autoload_pattern)
        if self.ztv_frame.default_autoload_pattern is not None:
            self.autoload_match_string = self.ztv_frame.default_autoload_pattern
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
        pub.subscribe(self.on_activemq_instances_info_changed, "activemq_instances_info-changed")
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
        pub.subscribe(self.update_cur_header_button_status, "redraw_image")
        if not self.stomp_install_is_ok: # deactivate activeMQ option if stomp not installed OK
            try:  # wrap in a try, just in case source_panel wasn't loaded.
                wx.CallAfter(self.settings_menu_activemq_item.Check, False)
                wx.CallAfter(self.activemq_sizer.ShowItems, False)
            except:
                pass
        # TODO: eventually want to be able to pass a flag parameter for whether to 
        #       show activemq (and/or fits auto-load) at startup.  
        # For now, just hide activemq as default.  (user can always unhide with gear-tools menu)
# 2015-04-22 13:15MST:  comment out next two lines and add one stderr while debugging github issue #1
#         wx.CallAfter(self.settings_menu_activemq_item.Check, False)
#         wx.CallAfter(self.activemq_sizer.ShowItems, False)
  
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
        new_title = "Sky: " + os.path.basename(self.sky_file_fullname)
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
        new_title = "Flat: " + os.path.basename(self.flat_file_fullname)
        if hasattr(self, 'flat_fits_header_dialog') and self.flat_fits_header_dialog.is_dialog_still_open:
            self.flat_fits_header_dialog.SetTitle(new_title)
            self.flat_fits_header_dialog.text.SetValue(header_str)
            self.flat_fits_header_dialog.last_find_index = 0
            self.flat_fits_header_dialog.on_search(None)
        else:
            self.flat_fits_header_dialog = FITSHeaderDialog(self, header_str, new_title)
            self.flat_fits_header_dialog.Show()

    def update_cur_header_button_status(self, msg=None):
        if self.ztv_frame.cur_fits_hdulist is not None:
            self.cur_header_button.Enable()
        else:
            self.cur_header_button.Disable()

    def unload_sky_subtraction_from_process_stack(self):
        proc_labels = [x[0] for x in self.ztv_frame.image_process_functions_to_apply]
        if 'sky_subtraction' in proc_labels:
            self.ztv_frame.image_process_functions_to_apply.pop(proc_labels.index('sky_subtraction'))
            wx.CallAfter(pub.sendMessage, "image_process_functions_to_apply-changed", msg=None)
            wx.CallAfter(pub.sendMessage, "set_window_title", msg=None)
        self.sky_checkbox.SetValue(False)

    def load_sky_subtraction_to_process_stack(self):
        """
        Load sky subtraction into image processing stack
        If sky image is 3-d ([n,x,y]), then collapse to 2-d ([x,y]) by doing a median on axis=0
        """
        self.unload_sky_subtraction_from_process_stack()
        if self.sky_hdulist is not None:
            if self.sky_hdulist[0].data.ndim == 2:
                process_fxn = ImageProcessAction(np.subtract, self.sky_hdulist[0].data)
            elif self.sky_hdulist[0].data.ndim == 3:
                process_fxn = ImageProcessAction(np.subtract, np.median(self.sky_hdulist[0].data, axis=0))
            else:
                raise UnrecognizedNumberOfDimensions("Tried to load sky image with {} dimensions, " + 
                                                     "when can only handle 2-d or 3-d".format(
                                                     self.sky_hdulist[0].data.ndim))
            # assume that sky subtraction should always be first in processing stack.
            self.ztv_frame.image_process_functions_to_apply.insert(0, ('sky_subtraction', process_fxn))
            wx.CallAfter(pub.sendMessage, "image_process_functions_to_apply-changed", msg=None)
            wx.CallAfter(pub.sendMessage, "set_window_title", msg=None)
        self.sky_checkbox.SetValue(True)

    def load_sky_frame(self, filename, start_sky_correction=True):
        """
        Load sky frame from fits file.
        """
        if len(filename) == 0:
            self.sky_hdulist = None
            self.sky_header_button.Disable()
            self.unload_sky_subtraction_from_process_stack()
            self.sky_checkbox.SetValue(False)
        else:
            self.sky_hdulist = self.ztv_frame.load_hdulist_from_fitsfile(filename)
            self.sky_file_fullname = filename
            raw_header_str = self.sky_hdulist[0].header.tostring()
            header_str = (('\n'.join([raw_header_str[i:i+80] for i in np.arange(0, len(raw_header_str), 80)
                                      if raw_header_str[i:i+80] != " "*80])) + '\n')
            new_title = "Sky: " + os.path.basename(self.sky_file_fullname)
            if hasattr(self, 'sky_fits_header_dialog') and self.sky_fits_header_dialog.is_dialog_still_open:
                self.sky_fits_header_dialog.SetTitle(new_title)
                self.sky_fits_header_dialog.text.SetValue(header_str)
                self.sky_fits_header_dialog.last_find_index = 0
                self.sky_fits_header_dialog.on_search(None)
            self.sky_header_button.Enable()
            if start_sky_correction:
                self.load_sky_subtraction_to_process_stack()
                self.sky_checkbox.SetValue(True)
            self.skyfile_file_picker.pause_on_current_textctrl_changed = True
            self.skyfile_file_picker.set_current_entry(filename)
            self.skyfile_file_picker.pause_on_current_textctrl_changed = False

    def on_load_current_to_sky(self, msg):
        self.load_sky_frame(os.path.join(self.ztv_frame.cur_fitsfile_path, self.ztv_frame.cur_fitsfile_basename))

    def on_sky_checkbox(self, evt):
        if evt.IsChecked():
            self.load_sky_subtraction_to_process_stack()
        else:
            self.unload_sky_subtraction_from_process_stack()

    def unload_flat_division_from_process_stack(self):
        proc_labels = [x[0] for x in self.ztv_frame.image_process_functions_to_apply]
        if 'flat_division' in proc_labels:
            self.ztv_frame.image_process_functions_to_apply.pop(proc_labels.index('flat_division'))
            wx.CallAfter(pub.sendMessage, "image_process_functions_to_apply-changed", msg=None)
            wx.CallAfter(pub.sendMessage, "set_window_title", msg=None)
        self.flat_checkbox.SetValue(False)

    def load_flat_division_to_process_stack(self):
        self.unload_flat_division_from_process_stack()
        if self.flat_hdulist is not None:
            process_fxn = ImageProcessAction(np.divide, self.flat_hdulist[0].data)
            # assume that flat division should always be last in processing stack.
            self.ztv_frame.image_process_functions_to_apply.insert(99999, ('flat_division', process_fxn))
            wx.CallAfter(pub.sendMessage, "image_process_functions_to_apply-changed", msg=None)
            wx.CallAfter(pub.sendMessage, "set_window_title", msg=None)
        self.flat_checkbox.SetValue(True)

    def load_flat_frame(self, filename, start_flat_correction=True):
        if len(filename) == 0:
            self.flat_hdulist = None
            self.flat_header_button.Disable()
            self.unload_flat_division_from_process_stack()
            self.flat_checkbox.SetValue(False)
        else:
            self.flat_hdulist = self.ztv_frame.load_hdulist_from_fitsfile(filename)
            self.flat_file_fullname = filename
            raw_header_str = self.flat_hdulist[0].header.tostring()
            header_str = (('\n'.join([raw_header_str[i:i+80] for i in np.arange(0, len(raw_header_str), 80)
                                      if raw_header_str[i:i+80] != " "*80])) + '\n')
            new_title = "Flat: " + os.path.basename(self.flat_file_fullname)
            if hasattr(self, 'flat_fits_header_dialog') and self.flat_fits_header_dialog.is_dialog_still_open:
                self.flat_fits_header_dialog.SetTitle(new_title)
                self.flat_fits_header_dialog.text.SetValue(header_str)
                self.flat_fits_header_dialog.last_find_index = 0
                self.flat_fits_header_dialog.on_search(None)
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

    def on_activemq_instances_info_changed(self, msg=None):
        self.message_queue_choice.Clear()
        new_keys = sorted(self.activemq_instances_info.keys())
        self.activemq_instances_available = new_keys
        if len(new_keys) == 0:
            self.message_queue_choice.AppendItems(['No message queues available'])
            self.activemq_selected_instance = None
        else:
            self.message_queue_choice.AppendItems(new_keys)
        if ((self.activemq_selected_instance not in new_keys) or (len(new_keys) == 1)):
            self.activemq_selected_instance = new_keys[0]
        if self.activemq_selected_instance is None:
            cur_selection = 0
        else:
            cur_selection = self.activemq_instances_available.index(self.activemq_selected_instance)
        self.message_queue_choice.SetSelection(cur_selection)

    def on_message_queue_choice(self, evt):
        new_choice = evt.GetString()
        if new_choice != self.activemq_selected_instance:
            self.activemq_selected_instance = new_choice
            if self.autoload_mode == 'activemq-stream':
                self.launch_activemq_listener_thread()

    def on_choose_autoload_pausetime(self, evt):
        self.autoload_pausetime = float(evt.GetString())

    def autoload_curfile_file_picker_on_load(self, new_entry):
        new_path = os.path.dirname(new_entry) + '/'
        self.autoload_curfile_file_picker.set_current_entry(new_entry)
        self.autoload_match_string = new_entry
        self.message_queue_checkbox.SetValue(False)
        self.autoload_checkbox.SetValue(True)
        self.kill_activemq_listener_thread()
        self.autoload_mode = 'file-match'
        self.launch_autoload_filematch_thread()
        set_textctrl_background_color(self.autoload_curfile_file_picker.current_textctrl, 'ok')

    def on_autoload_checkbox(self, evt):
        if evt.IsChecked():
            self.message_queue_checkbox.SetValue(False)
            self.kill_activemq_listener_thread()
            self.autoload_mode = 'file-match'
            self.launch_autoload_filematch_thread()
        else:
            self.autoload_mode = None

    def on_message_queue_checkbox(self, evt):
        if evt.IsChecked():
            self.autoload_checkbox.SetValue(False)
            self.kill_autoload_filematch_thread()
            self.autoload_mode = 'activemq-stream'
            self.launch_activemq_listener_thread()
        else:
            self.autoload_mode = None
            self.kill_activemq_listener_thread()

    def on_fitsfile_loaded(self, msg=None):
        self.curfile_file_picker.pause_on_current_textctrl_changed = True
        self.curfile_file_picker.set_current_entry(os.path.join(self.ztv_frame.cur_fitsfile_path,
                                                                self.ztv_frame.cur_fitsfile_basename))
        self.curfile_file_picker.pause_on_current_textctrl_changed = False

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
        try:
            self.activemq_listener_thread = ActiveMQListenerThread(self, condition=self.activemq_listener_condition)
        except ActiveMQNotAvailable:
            sys.stderr.write("ztv warning: stomp not installed OK, ActiveMQ functionality not available\n")

    def _add_activemq_instance(self, msg):
        server, port, destination = msg
        new_key = str(server) + ':' + str(port) + ':' + str(destination)
        self.activemq_instances_info[new_key] = {'server':server, 'port':port, 'destination':destination}
        wx.CallAfter(pub.sendMessage, "activemq_instances_info-changed", msg=None)
        