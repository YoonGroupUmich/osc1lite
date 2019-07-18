#! /usr/bin/env python3.5

import wx
import sys

__version__ = '0.0.1'


class MainFrame(wx.Frame):

    def __init__(self, parent=None, ident=-1):
        wx.Frame.__init__(self, parent, ident,
                          'OSC1Lite Stimulate Control v' + __version__)
        p = wx.Panel(self, -1)

        # Setup frame
        setup_sizer = wx.StaticBoxSizer(wx.HORIZONTAL, p, 'Setup')
        file_selector_box = wx.BoxSizer(wx.VERTICAL)
        file_selector_box.Add(wx.StaticText(p, -1, 'Select your OSC1Lite'),
                              1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 3)
        self.device_choice = wx.Choice(p, -1,
                                       choices=['[No connected devices]'])
        self.device_choice.SetSelection(0)
        file_selector_box.Add(self.device_choice,
                              1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 3)
        setup_sizer.Add(file_selector_box)
        self.connect_button = wx.Button(p, -1, 'Connect')
        setup_sizer.Add(self.connect_button, 1, wx.EXPAND | wx.ALL, 3)

        channel_panel = wx.StaticBoxSizer(wx.VERTICAL, p)
        channel_box = wx.FlexGridSizer(7, 5, 5)
        self.channels_ui = []
        for i in range(1, 7):
            channel_box.AddGrowableCol(i, 1)
        for i in range(12):
            channel_box.Add(wx.StaticText(p, -1, 'Channel %2d' % (i + 1)),
                            0, wx.ALIGN_CENTER_VERTICAL)

            waveform_choice = wx.Choice(p, -1,
                                        choices=['Waveform %d' % (x + 1) for x
                                                 in range(4)])
            waveform_choice.SetSelection(0)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(waveform_choice, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_choice = wx.Choice(p, -1,
                                choices=['PC trigger', 'External trigger'])
            trigger_choice.SetSelection(0)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_choice, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            continuous_toggle = wx.ToggleButton(p, -1, 'One-shot Mode')
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(continuous_toggle, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_button = wx.Button(p, -1, 'Trigger Channel #%d' % (i+1))
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_button, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            stop_button = wx.Button(p, -1, 'Stop Channel #%d' % (i+1))
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(stop_button, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_out_toggle = wx.ToggleButton(p, -1, 'Trigger Out Disabled')
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_out_toggle, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND | wx.LEFT, 5)

            self.channels_ui.append({
                'waveform_choice': waveform_choice.GetId(),
                'trigger_choice': trigger_choice.GetId(),
                'continuous_toggle': continuous_toggle.GetId(),
                'trigger_button': trigger_button.GetId(),
                'stop_button': stop_button.GetId(),
                'trigger_out_toggle': trigger_out_toggle.GetId(),
            })

            channel_box.AddGrowableRow(i, 1)
        self.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle)
        channel_panel.Add(channel_box, 1, wx.EXPAND)

        box = wx.BoxSizer(wx.HORIZONTAL)
        box.Add(setup_sizer, 0, wx.ALL, 5)
        box.Add(channel_panel, 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 5)
        p.SetSizer(box)
        box.Fit(p)
        self.Fit()

    def on_toggle(self, event: wx.Event):
        ident = event.GetId()
        obj = event.GetEventObject()
        assert isinstance(obj, wx.ToggleButton)
        for x in self.channels_ui:
            if ident == x['continuous_toggle']:
                obj.SetLabel('Continuous Mode' if obj.GetValue()
                             else 'One-shot Mode')
                break
            elif ident == x['trigger_out_toggle']:
                obj.SetLabel('Trigger Out Enabled' if obj.GetValue()
                             else 'Trigger Out Disabled')
                break


if __name__ == '__main__':
    app = wx.App()
    MainFrame().Show()
    exit(app.MainLoop())
