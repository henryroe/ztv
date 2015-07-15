import wx

textctrl_output_only_background_color = (235, 235, 235)
        
def set_textctrl_background_color(textctrl, mode, tooltip=None):
    if mode == 'ok':
        color = (255,255,255)
    elif mode == 'enter-needed':
        color = (200,255,200)
    elif mode == 'invalid':
        color = (255,200,200)
    textctrl.SetBackgroundColour(color)
    textctrl.Refresh()
    if tooltip is not None and not isinstance(tooltip, wx.ToolTip):
        tooltip = wx.ToolTip(tooltip)
    textctrl.SetToolTip(tooltip)
    force_textctrl_color_update(textctrl)

def force_textctrl_color_update(textctrl):
    cur_focused_item = textctrl.GetParent().FindFocus()
    insertion_point = textctrl.GetInsertionPoint()
    children = textctrl.GetParent().GetChildren()
    can_accept_focus_mask = [(hasattr(a, 'CanAcceptFocus') and a.CanAcceptFocus() and 
                              (a is not textctrl)) for a in children]
    if True in can_accept_focus_mask:
        children[can_accept_focus_mask.index(True)].SetFocus()
    textctrl.SetFocus()
    textctrl.SetInsertionPoint(insertion_point)
    if cur_focused_item is not None:
        cur_focused_item.SetFocus()

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
