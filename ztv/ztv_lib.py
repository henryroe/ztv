import wx
import sys
import pickle

def force_textctrl_color_update(textctrl):
    cur_focused_item = textctrl.GetParent().FindFocus()
    insertion_point = textctrl.GetInsertionPoint()
    children = textctrl.GetParent().GetChildren()
    can_accept_focus_mask = [(a.CanAcceptFocus() and (a is not textctrl)) for a in children]
    if True in can_accept_focus_mask:
        children[can_accept_focus_mask.index(True)].SetFocus()
    textctrl.SetFocus()
    textctrl.SetInsertionPoint(insertion_point)
    if cur_focused_item is not None:
        cur_focused_item.SetFocus()

def set_textctrl_background_color(textctrl, mode, tooltip=None):
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
    force_textctrl_color_update(textctrl)

def validate_textctrl_str(textctrl, validate_fxn, last_value):
    """
    can accept arbitrary functions in validate_fxn.  They just need to raise a ValueError if
    they don't like the input.
    """
    try:
        newval = validate_fxn(textctrl.GetValue())
        if textctrl.GetValue() == last_value:
            set_textctrl_background_color(textctrl, 'ok')
        else:
            set_textctrl_background_color(textctrl, 'enter-needed',
                                         'Press enter in this field to set new minimum value')
        return True
    except ValueError:
        # TODO: figure out some (clever?) way of having validate_fxn give info about itself that is more useful in the following error tooltip message
        set_textctrl_background_color(textctrl, 'invalid', 
                                      'Entry cannot be converted to {}'.format(str(validate_fxn)))
        return False

# point is to make improbably that would ever happen to appear inside a pickled image and be mistaken
end_of_message_message = ("---EndOfMessage---"*10) + "\n"   

def send_to_pipe(pipe, msg): 
    """
    Pickle & send to stdout a message.
    Used primarily to communicate back-and-forth with a separately launched ztv process.
    """
    if isinstance(msg, str):
        msg = (msg,)
    pkl = pickle.dumps(msg)
    pipe.write(pkl + '\n' + end_of_message_message)
    pipe.flush()

def listen_to_pipe(pipe):
    """
    Will listen on pipe until has seen end_of_message_message, then strip the 
    end_of_message_message and return the unpickled version of the preceding message
    """
    in_str = ""
    while not in_str.endswith('\n' + end_of_message_message):
        in_str += pipe.readline()
    return pickle.loads(in_str.replace('\n' + end_of_message_message, ''))