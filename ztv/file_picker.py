from __future__ import absolute_import
import wx
import os
import glob
import sys
import subprocess
import pdb
from .ztv_wx_lib import set_textctrl_background_color

# TODO:  fix tab order through controls
# TODO:  fix alignment in text field, ideally would be right aligned, but may not be able to do that on OSX
# TODO: limit default allowed_extensions to .fits/.fits.gz  (rather than .fits/.gz)
# TODO: fix that is currently hardwired to .fits/.gz file endings and allow calling code to specify other options

# TODO: implement a None option? or that None is italixiszed in text box and dropdown menu as a special thing?

class Error(Exception):
    pass


class FilePicker(wx.Panel):
    def __init__(self, parent,
                 is_files_not_dirs=True,  # True to look for files, False to look for dirs
                 max_history_items=20,
                 history=None,  # pre-load items into history
                 sticky_history=None,  # force one or more history items to be 'sticky' and remain at the top of the list
                 allowed_extensions="FITS files (.fits)|.fits|gzipped files (.gz)|.gz", # ignored in the dir case
                 title=None,  # None leads to a default, for NO title, use:  ''
                 assumed_prefix=None, #  can add a prefix to the file/dir name that will not be shown
                                      # assumed_prefix can be changed with:   self.set_assumed_prefix
                                      # Note that if an entry starts with /, then abspath is assumed and assumed_prefix is ignored
                                      # Basically, the interface just "hides" assumed_prefix from the user in the GUI
                 allow_glob_matching=False,  # if true, then entries can be, e.g.:   image*_[0-9][0-9][0-9].fits
                                             # allow_glob_matching is NOT compatible with is_files_not_dirs=False
                 default_entry=None,
                 maintain_default_entry_in_recents=False,  # can be True, or an integer to indicate where to put in list (e.g. 0, 1, -1)
                 ):
        wx.Panel.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.is_files_not_dirs = is_files_not_dirs
        self.max_history_items = max_history_items
        if history is None:
            self.history = []
        else:
            self.history = [a + '/' if (os.path.isdir(a) and not a.endswith('/')) else a for a in history]
        if sticky_history is None:
            self.sticky_history = []
        else:
            self.sticky_history = [a + '/' if (os.path.isdir(a) and not a.endswith('/')) else a for a in sticky_history]
        self.allowed_extensions = allowed_extensions
        if title is None:
            if self.is_files_not_dirs:
                title = 'File:'
            else:
                title = 'Dir:'
        self.assumed_prefix = assumed_prefix
        self.allow_glob_matching = allow_glob_matching
        if self.allow_glob_matching and not self.is_files_not_dirs:
            raise Error("allow_glob_matching=True and is_files_not_dirs=False is not compatible")
        if default_entry is None:
            default_entry = os.path.expanduser('~') + '/'
        self.default_entry = default_entry
        self.maintain_default_entry_in_recents = maintain_default_entry_in_recents
        self.title = title
        self.last_valid_entry = ''
        self.reset_auto_completion_info()
        self.current_textctrl_mode_is_ok = True
        self.pause_on_current_textctrl_changed = False

        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.recent_choice = wx.Choice(self, -1, size=(24, -1), choices=self.get_history())
        self.Bind(wx.EVT_CHOICE, self.on_recent_choice, self.recent_choice)
        textentry_font = wx.Font(14, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT, False)
        self.current_textctrl = wx.TextCtrl(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize,
                                            wx.TE_PROCESS_ENTER | wx.TE_RIGHT)
        # note that wx.TE_RIGHT has no effect on Mac OSX, but is worthwhile leaving in for other systems
        self.current_textctrl.SetFont(textentry_font)
        self.current_textctrl.Bind(wx.EVT_TEXT, self.on_current_textctrl_changed)
        self.current_textctrl.Bind(wx.EVT_TEXT_ENTER, self.on_current_textctrl_entered)
        self.current_textctrl.Bind(wx.EVT_CHAR, self.on_key_press_textctrl, self.current_textctrl)
        h_sizer.Add(wx.StaticText(self, -1, title), 0, wx.ALIGN_CENTER_VERTICAL)
        h_sizer.Add(self.current_textctrl, 1, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
        h_sizer.AddSpacer((2, 0), 0)
        h_sizer.Add(self.recent_choice, 0, wx.ALIGN_CENTER_VERTICAL)
        h_sizer.AddSpacer((2, 0), 0)
        self.browser_button = wx.Button(self, -1, '...', style=wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.on_browser_button, self.browser_button)
        h_sizer.Add(self.browser_button, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(h_sizer)
        self.current_textctrl_SetValue(self.default_entry)
        self._on_load(self.current_textctrl_GetValue())

    def on_load(self, new_entry):
        # this is really a placeholder method, to be replaced when this class is implemented with a method that actually does something
        pass
        
    def set_assumed_prefix(self, new_prefix):
        self.assumed_prefix = new_prefix
        self.update_recent_choice()

    def strip_assumed_prefix(self, entry):
        if self.assumed_prefix is not None and entry.startswith(self.assumed_prefix):
            return entry.replace(self.assumed_prefix, '', 1)
        else:
            return entry

    def addback_assumed_prefix(self, entry):
        if not entry.startswith('/') and not entry.startswith('~') and self.assumed_prefix is not None:
            return os.path.join(self.assumed_prefix, entry)
        else:
            return entry

    def current_textctrl_SetValue(self, entry):
        self.current_textctrl.SetValue(self.strip_assumed_prefix(entry))

    def current_textctrl_GetValue(self):
        return self.addback_assumed_prefix(self.current_textctrl.GetValue())

    def set_current_entry(self, new_entry):
        """
        This provides an external hook to call from external code to load an entry.
        It is not used internally.
        """
        self.current_textctrl_SetValue(new_entry)
        self.prepend_to_history(new_entry)
        cur_history = self.update_recent_choice()
        self.recent_choice.SetSelection(cur_history.index(new_entry))

    def update_recent_choice(self):
        self.recent_choice.Clear()
        cur_history = self.get_history()
        self.recent_choice.AppendItems(cur_history)
        return cur_history

    def prepend_to_history(self, new_entry):
        if new_entry in self.history:  # pop if necessary so we can reinsert at start of list
            self.history.pop(self.history.index(new_entry))
        self.history.insert(0, new_entry)
        self.update_recent_choice()

    def _on_load(self, new_entry):
        """
        this is a private method that just updates the internals and then calls self.on_load
        """
        self.last_valid_entry = new_entry
        if not self.is_files_not_dirs and not self.last_valid_entry.endswith('/'):
            self.last_valid_entry += '/'
        self.current_textctrl_SetValue(self.last_valid_entry)
        self.current_textctrl.SetSelection(-1, -1)
        self.prepend_to_history(self.last_valid_entry)
        self.update_recent_choice()
        self.on_load(self.last_valid_entry)
        set_textctrl_background_color(self.current_textctrl, 'ok')

    def get_history(self):
        """
        returns what the current history should be, taking in to account:
            self.history (the actual history, trimmed to self.max_history_items)
            self.sticky_history (items to stick at the top of the generated history)
            self.max_history (trim the output to this length)
            self.assumed_prefix (stripped off as necessary)
        """
        history = self.history[:]  # want a copy
        for cur_sticky in self.sticky_history[::-1]:
            if cur_sticky in history:
                history.pop(history.index(cur_sticky))
            history.insert(0, cur_sticky)
        history = history[:self.max_history_items]
        if self.maintain_default_entry_in_recents is not False:
            if type(self.maintain_default_entry_in_recents) is int:
                if self.default_entry in self.history:
                    self.history.pop(self.history.index(self.default_entry))
                self.history.insert(self.maintain_default_entry_in_recents, self.default_entry)
            else:
                if self.default_entry not in self.history:
                    self.history.insert(999999, self.default_entry)
        if self.assumed_prefix is None:
            return history[:self.max_history_items]
        else:
            return [self.strip_assumed_prefix(a) for a in history[:self.max_history_items]]

    def on_browser_button(self, evt):
        cur_entry = self.current_textctrl_GetValue()
        if len(cur_entry) == 0:
            cur_entry = self.default_entry
        cur_entry = os.path.abspath(os.path.expanduser(cur_entry))
        cur_entry_parts = [a for a in ['/'] + cur_entry.split('/') if len(a) > 0]
        while (len(cur_entry_parts) >= 1 and
               not (os.path.isdir(os.path.join(*cur_entry_parts)) or
                    os.path.isfile(os.path.join(*cur_entry_parts)))):
            cur_entry_parts = cur_entry_parts[:-1]
        if len(cur_entry_parts) > 1:
            cur_entry = os.path.join(*cur_entry_parts)
        else:
            cur_entry = os.path.expanduser('~')
        if os.path.isdir(cur_entry):
            cur_basename = ''
            cur_dirname = cur_entry
        else:
            cur_basename = os.path.basename(cur_entry)
            cur_dirname = os.path.dirname(cur_entry)
        if self.is_files_not_dirs:
            dlg = wx.FileDialog(self, "Choose a file:", style=wx.DD_DEFAULT_STYLE,
                                defaultDir=cur_dirname, defaultFile=cur_basename, wildcard=self.allowed_extensions)
            # TODO: defaultFile is not being set to cur_basename in the dialog box
        else:
            dlg = wx.DirDialog(self, "Choose a directory:", style=wx.DD_DEFAULT_STYLE, defaultPath=cur_dirname)
        if dlg.ShowModal() == wx.ID_OK:
            self._on_load(dlg.GetPath())
        dlg.Destroy()

    def reset_auto_completion_info(self):
        self.auto_completion_info = {'current_base':'', 'possible_completions':[],
                                     'current_completion':'', 'current_selection':(0, 0)}

    def validate_current_textctrl_value(self):
        is_entry_valid = False
        if (self.current_textctrl_GetValue() == self.default_entry):
            is_entry_valid = True   # catch for case of default_entry == '' and nothing in field
        new_entry = os.path.abspath(os.path.expanduser(self.current_textctrl_GetValue()))
        if self.is_files_not_dirs:
            if self.allow_glob_matching:
                if len(glob.glob(new_entry)) > 0:
                    is_entry_valid = True
            elif os.path.isfile(new_entry):
                    is_entry_valid = True
        else:
            if os.path.isdir(new_entry):
                is_entry_valid = True
        if new_entry == self.default_entry:
            is_entry_valid = True
        self.current_textctrl_mode_is_ok = False
        if is_entry_valid:
            if self.last_valid_entry == new_entry:
                set_textctrl_background_color(self.current_textctrl, 'ok')
                self.current_textctrl_mode_is_ok = True
            else:
                set_textctrl_background_color(self.current_textctrl, 'enter-needed', 
                                              'Press enter in this field to load')
            return True
        else:
            set_textctrl_background_color(self.current_textctrl, 'invalid', 'Not found on disk')
            return False

    def on_key_press_textctrl(self, evt):
        if evt.GetKeyCode() == wx.WXK_TAB:
            if self.current_textctrl_mode_is_ok:
                if evt.ShiftDown():
                    evt.Skip()
                else:
                    self.recent_choice.SetFocus()
            else:  # try auto completion
                new_entry = self.current_textctrl_GetValue()
                add_on = ''  # hack to add back the trailing / as needed
                if new_entry.endswith('/'):
                    add_on = '/'
                new_entry = (os.path.abspath(os.path.expanduser(new_entry)) + add_on).replace('//', '/')
                if ((not new_entry.startswith(self.auto_completion_info['current_base'])) or
                    (new_entry not in self.auto_completion_info['possible_completions']) or
                    (self.auto_completion_info['current_selection'] != self.current_textctrl.GetSelection())):
                    self.reset_auto_completion_info()
                if len(self.auto_completion_info['possible_completions']) == 0:
                    self.auto_completion_info['current_base'] = new_entry
                    possible_completions = glob.glob(new_entry + '*')
                    if self.is_files_not_dirs:
                        # TODO: un-hardwire the endswith fits/gz and connect as a parameter to the FileDialog filter parameter
                        if len(possible_completions) == 1 and os.path.isdir(possible_completions[0]):
                            self.auto_completion_info['current_base'] = possible_completions[0] + '/'
                            possible_completions = glob.glob(possible_completions[0] + '/*')
                        possible_completions = [a for a in possible_completions if
                                                (os.path.isdir(a) or
                                                 (os.path.isfile(a) and
                                                  (a.endswith(".fits") or a.endswith(".fits.gz"))))]
                    else:
                        possible_completions = [a for a in possible_completions if os.path.isdir(a)]
                        possible_completions = [a if a.endswith('/') else a + '/' for a in possible_completions]
                    self.auto_completion_info['possible_completions'] = possible_completions
                    if len(possible_completions) > 0:
                        self.auto_completion_info['current_completion'] = possible_completions[-1]
                    else:
                        self.reset_auto_completion_info()
                if len(self.auto_completion_info['possible_completions']) > 0:
                    if len(self.auto_completion_info['possible_completions']) == 1:
                        new_entry = self.auto_completion_info['possible_completions'][0]
                        self.current_textctrl_SetValue(new_entry)
                        self.current_textctrl.SetInsertionPoint(999)
                        self.reset_auto_completion_info()
                    else:
                        cur_index = self.auto_completion_info['possible_completions'].index(self.auto_completion_info['current_completion'])
                        step = 1
                        if evt.ShiftDown:
                            step = -1
                        cur_index = (cur_index + step) % len(self.auto_completion_info['possible_completions'])
                        new_entry = self.auto_completion_info['possible_completions'][cur_index]
                        self.auto_completion_info['current_completion'] = new_entry
                        s1 = len(self.auto_completion_info['current_base'])
                        s2 = len(self.auto_completion_info['current_completion'])
                        self.pause_on_current_textctrl_changed = True
                        if self.assumed_prefix is not None and new_entry.startswith(self.assumed_prefix):
                            s1 -= len(self.assumed_prefix)
                            s2 -= len(self.assumed_prefix)
                        self.auto_completion_info['current_selection'] = (s1, s2)
                        self.current_textctrl_SetValue(new_entry)
                        self.current_textctrl.SetSelection(s1, s2)
                        self.pause_on_current_textctrl_changed = False
                        self.validate_current_textctrl_value()
        else:
            evt.Skip()

    def on_current_textctrl_changed(self, evt):
        if not self.pause_on_current_textctrl_changed:
            new_entry = self.current_textctrl_GetValue()
            if ((not new_entry.startswith(self.auto_completion_info['current_base'])) or
                (new_entry not in self.auto_completion_info['possible_completions']) or
                (self.auto_completion_info['current_selection'] != self.current_textctrl.GetSelection())):
                self.reset_auto_completion_info()
            self.validate_current_textctrl_value()

    def on_current_textctrl_entered(self, evt):
        if self.validate_current_textctrl_value():
            self.reset_auto_completion_info()
            new_entry = self.current_textctrl_GetValue()
            if new_entry == self.default_entry:
                self._on_load(new_entry)
            else:
                self._on_load(os.path.abspath(new_entry))

    def on_recent_choice(self, event):
        new_choice = event.GetString()
        if not new_choice.startswith('/') and self.assumed_prefix is not None:
            new_choice = os.path.join(self.assumed_prefix, new_choice)
        self._on_load(new_choice)



class MyFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, wx.ID_ANY, title='Testcase')
        v_sizer = wx.BoxSizer(wx.VERTICAL)
        v_sizer.Add(wx.StaticText(self, -1, "Some misc information"), 0)
        v_sizer.AddSpacer((0, 20), 0)
        v_sizer.Add(FilePicker(self), 0, wx.EXPAND)
        v_sizer.AddSpacer((0, 0), 1, wx.EXPAND)
        sticky_history = [os.path.expanduser('~'), os.path.expanduser('~/Dropbox'), os.path.expanduser('~/Documents')]
        v_sizer.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 5)
        file_picker1 = FilePicker(self, allow_glob_matching=True, title='glob match')
        v_sizer.Add(file_picker1, 0, wx.EXPAND)

        history = sticky_history[:]
        v_sizer.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 5)
        self.dir_picker = FilePicker(self, is_files_not_dirs=False, history=history)
        self.file_picker = FilePicker(self, assumed_prefix=os.path.expanduser('~/'), allow_glob_matching=True, 
                                      title='glob match')
        self.dir_picker.on_load = self.file_picker.set_assumed_prefix
        self.file_picker.on_load = self.file_picker_on_load

        v_sizer.Add(self.dir_picker, 0, wx.EXPAND)
        v_sizer.AddSpacer((0, 10), 0, wx.EXPAND)
        v_sizer.Add(self.file_picker, 0, wx.EXPAND)
        v_sizer.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 5)

        v_sizer.AddSpacer((0, 0), 1, wx.EXPAND)
        v_sizer.Add(FilePicker(self, sticky_history=sticky_history), 0, wx.EXPAND)
        v_sizer.AddSpacer((0, 0), 1, wx.EXPAND)

        self.SetSizer(v_sizer)

    def file_picker_on_load(self, new_entry):
        new_path = os.path.dirname(new_entry) + '/'
        self.dir_picker.set_current_entry(new_path)
        self.dir_picker.prepend_to_history(new_path)
        set_textctrl_background_color(self.dir_picker.current_textctrl, 'ok')
        self.file_picker.set_current_entry(os.path.basename(new_entry))
        self.file_picker.set_assumed_prefix(new_path)

if __name__ == '__main__':
    app=wx.App(False)
    myFrame = MyFrame()
    myFrame.Show()
    app.MainLoop()

