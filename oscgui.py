#! /usr/bin/env python3.5

import configparser
import json
import logging
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import threading
import time
from typing import List
import wx
import wx.lib.scrolledpanel

import ok
import osc1lite

__version__ = '2.0.3'

logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))
oscgui_config = configparser.ConfigParser()
oscgui_config.read('config.ini')


class LabeledCtrl(wx.BoxSizer):
    def __init__(self, control, parent=None, ident=-1, label=''):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        self.Add(wx.StaticText(parent, ident, label), 1, wx.EXPAND)
        self.Add(control, 1, wx.EXPAND)


class ChannelCtrl:
    _error_color = wx.Colour(255, 172, 172)
    _warning_color = wx.Colour(206, 206, 0)
    _normal_color = wx.Colour(91, 214, 255)
    _disabled_color = wx.NullColour

    def __init__(self, ch: int, channel_label: wx.StaticText,
                 waveform_choice: wx.Choice, trigger_choice: wx.Choice,
                 continuous_toggle: wx.ToggleButton, trigger_button: wx.Button,
                 stop_button: wx.Button, trigger_out_check: wx.CheckBox,
                 status_text: wx.TextCtrl, mf):
        self.ch = ch
        self.mf = mf
        self.channel_label = channel_label
        self.channel_name = channel_label.GetLabel()
        self.waveform_choice = waveform_choice
        self.waveform_choice.Bind(wx.EVT_CHOICE, self.on_waveform_choice)
        self.trigger_choice = trigger_choice
        self.trigger_choice.Bind(wx.EVT_CHOICE, self.on_trigger_source)
        self.continuous_toggle = continuous_toggle
        self.continuous_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle)
        self.trigger_button = trigger_button
        trigger_button.Bind(wx.EVT_BUTTON,
                            lambda _: mf.device.trigger_channel(ch))
        self.stop_button = stop_button
        if oscgui_config['OSCGUI']['channel_auto_enable'] == 'yes':
            self.stop_button.Bind(wx.EVT_BUTTON, self.on_stop)
        else:
            self.stop_button.Bind(wx.EVT_BUTTON,
                                  lambda evt: mf.device.set_enable(
                                      ch, stop_button.GetLabel() == 'Enable'))
        self.trigger_out_check = trigger_out_check
        self.trigger_out_check.Bind(wx.EVT_CHECKBOX, self.on_trigger_out)
        self.status_text = status_text

        self.waveform = 'Waveform 1'
        self.trigger = 0
        self.continuous = False
        self._enabled = False
        self.output = False
        self.warnings = []
        self.modified = False

    def on_connect(self):
        self.trigger_choice.Enable()
        self.continuous_toggle.Enable()
        self.stop_button.Enable()
        self.trigger_out_check.Enable()

    def on_disconnect(self):
        self.trigger = 0
        self.continuous = False
        self._enabled = False
        self.output = False
        self.warnings = []
        self.trigger_choice.Disable()
        self.trigger_choice.SetSelection(0)
        self.continuous_toggle.Disable()
        self.continuous_toggle.SetLabel('One-shot')
        self.continuous_toggle.SetValue(False)
        self.stop_button.Disable()
        if oscgui_config['OSCGUI']['channel_auto_enable'] != 'yes':
            self.stop_button.SetLabel('Enable')
        self.trigger_button.Disable()
        self.trigger_out_check.Disable()
        self.trigger_out_check.SetValue(False)

    def get_status_color_text(self):
        if self.warnings:
            warning = ', '.join(self.warnings)
            if warning == 'DAC open circuit or compliance voltage violation':
                warning = 'Open circuit'
            return self._error_color, warning
        if not self._enabled:
            if self.output:
                return self._error_color, 'Disabled Normal (Inconsistent State)'
            return self._disabled_color, 'Disabled'
        if self.output:
            return self._normal_color, 'Normal'
        if oscgui_config['OSCGUI']['channel_auto_enable'] == 'yes':
            return self._disabled_color, 'Stopped'
        return self._disabled_color, 'Paused (Ready for trigger)'

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, val):
        if self._enabled != val:
            self._enabled = val
            if oscgui_config['OSCGUI']['channel_auto_enable'] != 'yes':
                self.stop_button.SetLabel('Disable' if val else 'Enable')
            if val and not self.trigger:
                self.trigger_button.Enable()
            else:
                self.trigger_button.Disable()

    def log_trigger_overlap(self):
        ...

    def log_status(self):
        ...

    def on_toggle(self, event: wx.Event):
        obj = event.GetEventObject()
        val = obj.GetValue()
        obj.SetLabel('Continuous' if val else 'One-shot')
        self.mf.device.set_trigger_mode(self.ch, val)
        self.continuous = val

    def on_trigger_source(self, event: wx.Event):
        val = event.GetEventObject().GetSelection()
        self.trigger = val
        self.mf.device.set_trigger_source(self.ch, val)
        self.mf.Freeze()
        if val == 1:
            self.mf.device.set_trigger_mode(self.ch, 0)
            self.continuous = False
            self.continuous_toggle.Disable()
            self.continuous_toggle.SetLabel('One-shot')
            self.continuous_toggle.SetValue(False)
        else:
            self.continuous_toggle.Enable()
        self.trigger_button.Enable(self._enabled and not val)
        self.mf.Thaw()

    def update_param(self):
        self.waveform = self.waveform_choice.GetStringSelection()
        self.trigger = self.trigger_choice.GetSelection()
        self.continuous = self.continuous_toggle.GetValue()
        self.modified = False
        self.channel_label.SetLabel(self.channel_name)

    def to_dict(self):
        return {'channel_name': self.channel_name, 'waveform': self.waveform,
                'trigger': self.trigger, 'continuous': self.continuous,
                'trigger_out': self.trigger_out_check.GetValue()}

    def from_dict(self, d: dict):
        assert self.channel_name == d['channel_name'], 'Channel name mismatch'
        self.waveform_choice.SetSelection(
            self.waveform_choice.FindString(d['waveform'], caseSensitive=True))
        self.continuous_toggle.SetLabel(
            'Continuous' if d['continuous'] else 'One-shot')
        self.trigger_choice.SetSelection(d['trigger'])
        if d['trigger']:
            self.continuous_toggle.Disable()
            self.continuous_toggle.SetLabel('One-shot')
            self.continuous_toggle.SetValue(False)
        else:
            self.continuous_toggle.Enable()
        self.trigger_button.Enable(self._enabled and not d['trigger'])
        self.continuous_toggle.SetValue(d['continuous'])
        self.trigger_out_check.SetValue(d['trigger_out'])
        self.mf.device.set_trigger_out(self.ch, d['trigger_out'])
        self.set_modified()

    def set_modified(self):
        self.modified = True
        self.channel_label.SetLabel('*' + self.channel_name)

    def on_waveform_choice(self, event: wx.Event):
        self.set_modified()
        if oscgui_config['Waveform']['realtime_update'] == 'yes':
            self.mf.on_update(None)

    def on_stop(self, event: wx.Event):
        self.mf.device.set_channel(self.ch, osc1lite.ChannelInfo(
            osc1lite.SquareWaveform()))
        self.mf.device.set_trigger_source(self.ch, False)
        self.mf.device.set_trigger_mode(self.ch, False)
        self.stopped = True
        self.mf.device.trigger_channel(self.ch)

        wf = self.waveform_choice.GetSelection()
        data = self.mf.wfm.waveform_panels[wf].channel_info()
        self.mf.device.set_channel(self.ch, data)
        self.mf.device.set_trigger_source(self.ch, self.trigger)
        self.mf.device.set_trigger_mode(self.ch, self.continuous)

    def on_trigger_out(self, event: wx.Event):
        self.mf.device.set_trigger_out(self.ch, self.trigger_out_check.GetValue())


class SquareWavePanel(wx.FlexGridSizer):
    def __init__(self, parent, modify_callback, init_dict=None):
        wx.FlexGridSizer.__init__(self, 2, 4, 5, 5)
        for i in range(4):
            self.AddGrowableCol(i, 1)
        self.Add(wx.StaticText(parent, -1, 'Amplitude (\u03bcA)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Period (ms)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Pulse Width (ms)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Rise Time (ms)'), 0, wx.EXPAND)

        try:
            self.amp = init_dict['amp']
        except (TypeError, KeyError, ValueError):
            self.amp = 0  # uA
        try:
            self.pulse_width = init_dict['pulse_width']
        except (TypeError, KeyError, ValueError):
            self.pulse_width = 0  # ms
        try:
            self.period = init_dict['period']
        except (TypeError, KeyError, ValueError):
            self.period = 0  # ms
        try:
            self.rise_time = init_dict['rise_time']
        except (TypeError, KeyError, ValueError):
            self.rise_time = 0  # ms

        self.amp_text = wx.TextCtrl(parent, -1, '%.1f' % self.amp,
                                    style=wx.TE_PROCESS_ENTER)
        self.amp_text.SetToolTip(
            'Range: 0~100\u03bcA, Precision: \u00b10.31\u03bcA')
        self.amp_text.Bind(wx.EVT_KILL_FOCUS, self.on_amp)
        self.amp_text.Bind(wx.EVT_TEXT_ENTER, self.on_amp)
        self.Add(self.amp_text, 0, wx.EXPAND)
        self.period_text = wx.TextCtrl(parent, -1, '%.3f' % self.period,
                                       style=wx.TE_PROCESS_ENTER)
        self.period_text.SetToolTip(
            'Range: 0~17.9s, Precision: \u00b18.6\u03bcs')
        self.period_text.Bind(wx.EVT_KILL_FOCUS, self.on_period)
        self.period_text.Bind(wx.EVT_TEXT_ENTER, self.on_period)
        self.Add(self.period_text, 0, wx.EXPAND)
        self.pw_text = wx.TextCtrl(parent, -1, '%.3f' % self.pulse_width,
                                   style=wx.TE_PROCESS_ENTER)
        self.pw_text.SetToolTip(
            'Range: 0~period, Precision: \u00b18.6\u03bcs')
        self.pw_text.Bind(wx.EVT_KILL_FOCUS, self.on_pulse_width)
        self.pw_text.Bind(wx.EVT_TEXT_ENTER, self.on_pulse_width)
        self.Add(self.pw_text, 0, wx.EXPAND)
        self.rise_time_text = wx.TextCtrl(parent, -1, str(self.rise_time),
                                          style=wx.TE_PROCESS_ENTER)
        self.rise_time_text.SetToolTip(
            'Possible values: 0, 0.1, 0.5, 1, 2ms')
        self.rise_time_text.Bind(wx.EVT_KILL_FOCUS, self.on_rise_time)
        self.rise_time_text.Bind(wx.EVT_TEXT_ENTER, self.on_rise_time)
        self.Add(self.rise_time_text, 0, wx.EXPAND)

        self.modify_callback = modify_callback

    def get_waveform(self) -> osc1lite.SquareWaveform:
        mode = (0 if self.rise_time < .05 else
                1 if self.rise_time < .3 else
                2 if self.rise_time < .75 else 3 if self.rise_time < 1.5 else 4)
        return osc1lite.SquareWaveform(amp=self.amp,
                                       pw=self.pulse_width / 1000,
                                       period=self.period / 1000,
                                       mode=mode)

    def to_dict(self):
        return {'amp': self.amp, 'pulse_width': self.pulse_width,
                'period': self.period, 'rise_time': self.rise_time}

    def on_amp(self, event: wx.Event):
        try:
            val = float(self.amp_text.GetValue())
        except ValueError:
            self.amp_text.SetValue(str(self.amp))
            event.Skip()
            return
        word = round(val / 20000 * 65536)
        amp_limit = 327
        word = 0 if word < 0 else amp_limit if word > amp_limit else word
        val = word / 65536 * 20000
        if self.amp != val:
            self.amp = val
            self.modify_callback()
        self.amp_text.SetValue('%.1f' % self.amp)
        event.Skip()

    def on_pulse_width(self, event: wx.Event):
        try:
            val = float(self.pw_text.GetValue())
        except ValueError:
            self.pw_text.SetValue(str(self.pulse_width))
            event.Skip()
            return
        if val > self.period:
            val = self.period
        word = round(val / .017152)
        word = 0 if word < 0 else 0xfffff if word > 0xfffff else word
        val = word * .017152
        if self.pulse_width != val:
            self.pulse_width = val
            self.modify_callback()
        self.pw_text.SetValue('%.3f' % self.pulse_width)
        event.Skip()

    def on_period(self, event: wx.Event):
        try:
            val = float(self.period_text.GetValue())
        except ValueError:
            self.period_text.SetValue(str(self.period))
            event.Skip()
            return
        word = round(val / .017152)
        word = 0 if word < 0 else 0xfffff if word > 0xfffff else word
        val = word * .017152
        if self.period != val:
            self.period = val
            if val < self.pulse_width:
                self.pulse_width = val
                self.pw_text.SetValue('%.3f' % self.pulse_width)
            self.modify_callback()
        self.period_text.SetValue('%.3f' % self.period)
        event.Skip()

    def on_rise_time(self, event: wx.Event):
        try:
            val = float(self.rise_time_text.GetValue())
        except ValueError:
            self.rise_time_text.SetValue(str(self.rise_time))
            event.Skip()
            return
        val = (0 if val < .05 else
               .1 if val < .3 else
               .5 if val < .75 else 1 if val < 1.5 else 2)
        if self.rise_time != val:
            self.rise_time = val
            self.modify_callback()
        self.rise_time_text.SetValue(str(self.rise_time))
        event.Skip()


class CustomWavePanel(wx.FlexGridSizer):
    "CustomWavePanel manages GUI logic related to custom wave. It handles open and read custom waveform from cwave file."

    def __init__(self, parent, modify_callback, mf, init_dict=None):
        wx.FlexGridSizer.__init__(self, 2, 2, 5, 5)
        self.AddGrowableCol(0, 4)
        self.AddGrowableCol(1, 1)
        self.Add(wx.StaticText(parent, -1, 'Custom Waveform File'), 0,
                 wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Sample Interval'), 0, wx.EXPAND)

        self.wave = []
        self.index = 0
        self.mf = mf
        try:
            self.clk_div = init_dict['clk_div']
        except (TypeError, KeyError, ValueError):
            self.clk_div = 1

        self.file_picker = wx.FilePickerCtrl(parent, -1, wildcard='*.cwave')
        self.file_picker.Bind(wx.EVT_FILEPICKER_CHANGED, self.on_file)
        self.Add(self.file_picker, 0, wx.EXPAND)
        self.sample_rate_text = wx.Choice(parent, -1, choices=['%.3f \u03bcs (%.1f kHz)' % (17.152 * x, 1000 / 17.152 / x) for x in osc1lite.custom_waveform_div_range])
        self.sample_rate_text.SetSelection(self.clk_div - 1)
        self.sample_rate_text.Bind(wx.EVT_CHOICE, self.on_sample_rate)
        self.Add(self.sample_rate_text, 0, wx.EXPAND)

        self.modify_callback = modify_callback

    def on_file(self, event: wx.Event):
        try:
            with open(self.file_picker.GetPath()) as fp:
                self.wave = [float(x) for x in fp.read().split()]
        except ValueError:
            wx.MessageBox(
                    'Error parsing cwave file. Please check file format.',
                    'Error', wx.ICON_ERROR | wx.OK | wx.CENTRE)
            self.file_picker.SetPath('')
        if 0 < len(self.wave) <= osc1lite.custom_waveform_max_len:
            self.modify_callback()
            self.send_custom_waveform()
        else:
            wx.MessageBox(
                    'Error parsing cwave file. Number of samples in custom waveform must between 1 and %d.' % osc1lite.custom_waveform_max_len,
                    'Error', wx.ICON_ERROR | wx.OK | wx.CENTRE)
            self.file_picker.SetPath('')

    def on_sample_rate(self, event: wx.CommandEvent):
        self.clk_div = event.GetInt() + 1
        self.modify_callback()
        self.send_custom_waveform()
        event.Skip()

    def get_waveform(self) -> osc1lite.CustomWaveform:
        return osc1lite.CustomWaveform(self.wave, self.clk_div, self.index)

    def to_dict(self):
        return {'clk_div': self.clk_div}

    def send_custom_waveform(self):
        wf = self.get_waveform()
        if wf.wave and self.mf.device:
            self.mf.device.send_custom_waveform(wf)


class WaveFormPanel(wx.StaticBoxSizer):
    def __init__(self, parent: wx.ScrolledWindow, label, modify_callback, init_dict=None):
        wx.StaticBoxSizer.__init__(self, wx.VERTICAL, parent, label)
        self.parent = parent
        p = self.GetStaticBox()
        font = wx.Font(wx.FontInfo(10).Bold())
        self.label = label
        common = wx.BoxSizer(wx.HORIZONTAL)
        wf_types = ['Square / Trapezoid', 'Custom']
        self.waveform_type_choice = wx.Choice(p, -1, choices=wf_types)
        try:
            sel = wf_types.index(init_dict['type'])
        except (TypeError, KeyError, ValueError):
            sel = 0
        self.waveform_type_choice.SetSelection(sel)
        self.waveform_type_choice.Bind(wx.EVT_CHOICE, self.on_type)
        common.Add(LabeledCtrl(self.waveform_type_choice, p,
                               -1, 'Waveform Type'), 0, wx.ALL, 3)
        try:
            n_pulses = int(init_dict['n_pulses'])
            n_pulses = (1 if n_pulses < 1 else
                        0xffff if n_pulses > 0xffff else n_pulses)
        except (TypeError, KeyError, ValueError):
            n_pulses = 1
        self.num_of_pulses = wx.SpinCtrl(p, -1, min=1, max=0xffff,
                                         value=str(n_pulses),
                                         style=wx.TE_PROCESS_ENTER)
        self.num_of_pulses.Bind(wx.EVT_SPINCTRL,
                                lambda _: modify_callback(self.label))
        self.num_of_pulses.Bind(wx.EVT_TEXT_ENTER, self.on_num_of_pulses)
        self.num_of_pulses.SetToolTip('Range: 1~65535')

        common.Add(
            LabeledCtrl(self.num_of_pulses, p, -1, 'Number of Pulses'),
            0, wx.ALL, 3)
        common.AddStretchSpacer(1)
        preview_button = wx.Button(p, -1, 'Preview', style=wx.BU_EXACTFIT)
        preview_button.Bind(wx.EVT_BUTTON, self.on_preview)
        common.Add(preview_button, 0, wx.ALIGN_TOP | wx.ALL, 3)
        self.delete_button = wx.Button(p, -1, 'X', style=wx.BU_EXACTFIT)
        self.delete_button.SetToolTip(wx.ToolTip('Delete waveform'))
        common.Add(self.delete_button, 0, wx.ALIGN_TOP | wx.ALL, 3)
        self.Add(common, 0, wx.EXPAND)
        self.p_square = SquareWavePanel(p, lambda: modify_callback(self.label),
                                        init_dict=init_dict)
        self.p_custom = CustomWavePanel(p, lambda: modify_callback(self.label), self.parent.mf,
                                        init_dict=init_dict)
        self.Add(self.p_square, 0, wx.EXPAND | wx.ALL, 3)
        self.Add(self.p_custom, 0, wx.EXPAND | wx.ALL, 3)
        self.Hide(self.p_custom)
        # self.Layout()
        self.detail = self.p_square
        self.modify_callback = modify_callback
        p.SetFont(font)

    def on_num_of_pulses(self, event: wx.Event):
        self.num_of_pulses.SetValue(self.num_of_pulses.GetValue())
        self.modify_callback(self.label)
        event.Skip()

    def channel_info(self) -> osc1lite.ChannelInfo:
        wf = self.detail.get_waveform()
        return osc1lite.ChannelInfo(wf, n_pulses=self.num_of_pulses.GetValue())

    def to_dict(self) -> dict:
        ret = {'label': self.label,
               'type': self.waveform_type_choice.GetStringSelection(),
               'n_pulses': self.num_of_pulses.GetValue()}
        ret.update(self.detail.to_dict())
        return ret

    def on_preview(self, event: wx.Event):
        n_pulses = self.num_of_pulses.GetValue()
        wf = self.detail.get_waveform()
        if isinstance(wf, osc1lite.SquareWaveform):
            if wf.period <= 0:
                wx.MessageBox(
                    'Error: invalid period %.3f. Period should be positive.' % wf.period,
                    'Preview for ' + self.label)
                return
            else:
                xs = [0]
                for i in range(n_pulses):
                    x_offset = xs[-1]
                    rise_time = (0, 0.1, 0.5, 1, 2)[wf.mode]
                    xs.extend((x_offset + rise_time,
                               x_offset + wf.pulse_width * 1000 - rise_time,
                               x_offset + wf.pulse_width * 1000,
                               x_offset + wf.period * 1000))
                ys = np.append(np.tile([0, wf.amp, wf.amp, 0], n_pulses), 0)
        elif isinstance(wf, osc1lite.CustomWaveform):
            xs = np.arange(n_pulses * len(wf.wave)) * wf.clk_div *0.017152
            ys = np.tile(wf.wave, n_pulses)
        else:
            raise TypeError('Waveform type not supported')
        plt.figure(num='Preview for ' + self.label)
        plt.plot(xs, ys, label=self.label)
        plt.xlabel('time (ms)')
        plt.ylabel('amplitude (\u03bcA)')
        plt.show()

    def on_type(self, event: wx.Event):
        obj = event.GetEventObject()
        assert isinstance(obj, wx.Choice)
        if obj.GetSelection() == 0:  # Square Wave
            self.Hide(self.p_custom)
            self.p_custom.index = 0
            self.Show(self.p_square)
            self.Layout()
            self.detail = self.p_square
        else:
            custom_index = self.parent.get_available_custom_index()
            if custom_index == 0:
                wx.MessageBox(
                        'Cannot add more custom waveform.\n'
                        'Maximum number of different custom waveforms has reached.',
                        'Error', wx.ICON_ERROR | wx.OK | wx.CENTRE, self.parent.mf)
                obj.SetSelection(0)  # Set selection back to Square wave
                return
            self.Hide(self.p_square)
            self.p_custom.index = custom_index
            self.Show(self.p_custom)
            self.Layout()
            self.detail = self.p_custom
        self.parent.Layout()
        self.modify_callback(self.label)


class WaveformManager(wx.ScrolledWindow):
    def __init__(self, parent, mf, ident=-1):
        self.parent = parent
        self.mf = mf
        wx.ScrolledWindow.__init__(self, parent, ident,
                                   style=wx.VSCROLL | wx.ALWAYS_SHOW_SB)
        self.box = wx.BoxSizer(wx.VERTICAL)

        new_wf = wx.Button(self, -1, 'Add New Waveform')
        new_wf.Bind(wx.EVT_BUTTON, self.on_new_wf)

        self.box.Add(new_wf, wx.SizerFlags().Right())

        self.cnt = 4
        self.waveform_panels = [WaveFormPanel(self, 'Waveform %d' % (x + 1),
                                              mf.set_wf_modified)
                                for x in range(self.cnt)]
        for wf in self.waveform_panels:
            self.box.Add(wf, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        self.SetSizerAndFit(self.box)
        # self.box.SetSizeHints(self)
        self.SetScrollRate(5, 5)

        self.Bind(wx.EVT_BUTTON, self.on_delete)

    def on_delete(self, event: wx.Event):
        ident = event.GetId()
        obj = event.GetEventObject()
        assert isinstance(obj, wx.Button)
        for idx, x in enumerate(self.waveform_panels):
            if ident == x.delete_button.GetId():
                ch = self.mf.is_wf_using(x.label)
                if ch != -1:
                    wx.MessageBox(
                        'Cannot delete waveform.\n'
                        'Waveform is being used by channel %d.' % ch,
                        'Error', wx.ICON_ERROR | wx.OK | wx.CENTRE, self.mf)
                    return
                self.parent.Freeze()
                del self.waveform_panels[idx]
                self.box.Detach(x)
                x.GetStaticBox().DestroyChildren()
                x.Destroy()
                break
        self.mf.update_wf_list()
        self.parent.Layout()
        self.parent.Thaw()

    def from_dict(self, d: List[dict]):
        self.parent.Freeze()
        for x in self.waveform_panels:
            self.box.Detach(x)
            x.GetStaticBox().DestroyChildren()
            x.Destroy()
        self.waveform_panels = []
        self.cnt = 0
        for x in d:
            # FIXME: get the cnt the dirty way
            if x['label'].startswith('Waveform '):
                try:
                    self.cnt = max(self.cnt, int(x['label'][9:]))
                except ValueError:
                    pass
            wf = WaveFormPanel(self, x['label'], self.mf.set_wf_modified,
                               init_dict=x)
            self.waveform_panels.append(wf)
            self.box.Add(wf, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        self.box.SetSizeHints(self)
        self.mf.update_wf_list()
        self.parent.Layout()
        self.parent.Thaw()

    def on_new_wf(self, event: wx.Event):
        self.parent.Freeze()
        self.cnt += 1
        wf = WaveFormPanel(
            self, 'Waveform %d' % self.cnt, self.mf.set_wf_modified)
        self.waveform_panels.append(wf)
        self.box.Add(wf, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        self.box.SetSizeHints(self)
        self.mf.update_wf_list()
        self.parent.Layout()
        self.parent.Thaw()

    def get_available_custom_index(self):
        custom_index = set()
        for x in self.waveform_panels:
            custom_index.add(x.p_custom.index)
        for i in osc1lite.custom_waveform_index_range:
            if i not in custom_index:
                return i
        return 0


class MainFrame(wx.Frame):
    daemon_lock = threading.RLock()

    def daemon(self) -> None:
        logging.getLogger('OSCGUI').debug('daemon started')
        while True:
            with self.daemon_lock:
                if self.device is None:
                    self.device_lister()
                else:
                    self.device_watcher()
            time.sleep(0.1)

    def device_lister(self) -> None:
        devices = {}
        self._dev = ok.okCFrontPanel()
        for i in range(self._dev.GetDeviceCount()):
            model = self._dev.GetDeviceListModel(i)
            serial = self._dev.GetDeviceListSerial(i)
            if model and serial:
                devices[serial] = model
            else:
                break
        if devices != self.devices:
            self.devices = devices
            curr = self.device_choice.GetStringSelection()
            if devices:
                l_devices = list(devices)
                self.device_choice.Set(l_devices)
                try:
                    sel = l_devices.index(curr)
                except ValueError:
                    sel = 0
                self.device_choice.SetSelection(sel)
                self.connect_button.Enable()
            else:
                self.device_choice.Set(['[No connected device]'])
                self.device_choice.SetSelection(0)
                self.connect_button.Disable()

    def device_watcher(self) -> None:
        assert isinstance(self.device, osc1lite.OSC1Lite)
        if not self._dev.IsOpen():
            logging.getLogger('OSCGUI').error(
                'device closed unexpectedly')
            self.on_connect_worker(connect=False)
            return
        warn, overlap, inactivity = self.device.get_channel_warnings()
        overlap = [x for x in overlap if
                   self.channels_ui[x].trigger == 1 or
                   not self.channels_ui[x].continuous]
        channel_warnings = [[] for _ in range(16)]
        for x, chs in warn.items():
            for ch in chs:
                logging.getLogger('OSCGUI').debug(
                    'Board reported: [Channel %d] %s' % (ch, x))
                channel_warnings[ch].append(x)
        for ch, x in enumerate(channel_warnings):
            if ch >= 12:
                continue
            if x != self.channels_ui[ch].warnings:
                self.channels_ui[ch].warnings = x
                if x:
                    logging.getLogger('OSCGUI').warning(
                        '%s alerts: %s' % (self.channels_ui[ch].channel_name,
                                           ', '.join(x)))
                else:
                    logging.getLogger('OSCGUI').info(
                        '%s back to normal' % self.channels_ui[ch].channel_name)

        status = self.device.status()
        for ch in range(12):
            self.channels_ui[ch].output = bool(status[0] & (1 << ch))
            self.channels_ui[ch].enabled = not bool(status[1] & (1 << ch))

        if overlap and oscgui_config['OSCGUI']['channel_auto_enable'] != 'yes':
            logging.getLogger('OSCGUI').warning(
                'Waveform restarted due to '
                'asynchronous trigger on: %s',
                ', '.join(
                    self.channels_ui[x].channel_name for x in overlap))

        for ch in range(12):
            target_color, target_text = self.channels_ui[
                ch].get_status_color_text()
            if (target_color !=
                    self.channels_ui[ch].status_text.GetBackgroundColour()):
                self.channels_ui[ch].status_text.SetBackgroundColour(
                    target_color)
            current_text = self.channels_ui[ch].status_text.GetValue()
            if target_text != current_text:
                self.channels_ui[ch].status_text.SetValue(target_text)
        if inactivity:
            logging.getLogger('OSCGUI').info(
                'Channel disabled due to 20s inactivity: %s',
                ', '.join(self.channels_ui[x].channel_name for x in inactivity
                          if x < 12))

    def __init__(self, parent=None, ident=-1):
        wx.Frame.__init__(
            self, parent, ident,
            'OSC1Lite Stimulate GUI v' + __version__)
        self.device = None
        self.devices = {}

        self.board_relative_controls = []

        p = wx.Panel(self, -1)

        # Setup frame
        setup_sizer = wx.StaticBoxSizer(wx.HORIZONTAL, p, 'Setup')
        self.device_choice = wx.Choice(p, -1,
                                       choices=['[No connected device]'])
        self.device_choice.SetSelection(0)
        self.device_choice.SetSize(
            self.device_choice.GetSizeFromTextSize(self.device_choice.GetTextExtent('[No connected device]')))
        self.connect_button = wx.Button(p, -1, 'Connect')
        self.connect_button.Disable()
        self.connect_button.Bind(
            wx.EVT_BUTTON,
            lambda _: threading.Thread(target=self.on_connect_worker).start())
        threading.Thread(target=self.daemon, daemon=True).start()
        setup_sizer.Add(LabeledCtrl(self.device_choice, p, -1,
                                    'Select your OSC1Lite'),
                        0, wx.EXPAND | wx.ALL, 3)
        setup_sizer.AddStretchSpacer(1)
        setup_sizer.Add(self.connect_button, 0, wx.EXPAND | wx.ALL, 3)

        left_box = wx.BoxSizer(wx.VERTICAL)
        left_box.Add(setup_sizer, 0, wx.EXPAND)

        # Config frame
        config_sizer = wx.StaticBoxSizer(wx.HORIZONTAL, p,
                                         'Waveform and Channel Config')
        config_sizer.AddStretchSpacer(1)
        save_config_button = wx.Button(p, -1, 'Save config to file')
        save_config_button.Bind(wx.EVT_BUTTON, self.on_save_config)
        config_sizer.Add(save_config_button, wx.SizerFlags().Expand())
        config_sizer.AddStretchSpacer(1)
        load_config_button = wx.Button(p, -1, 'Load config from file')
        load_config_button.Bind(wx.EVT_BUTTON, self.on_load_config)
        config_sizer.Add(load_config_button, wx.SizerFlags().Expand())
        config_sizer.AddStretchSpacer(1)
        self.board_relative_controls.extend(
            (save_config_button, load_config_button))

        left_box.Add(config_sizer, wx.SizerFlags().Expand())
        left_box.AddSpacer(50)

        self.wfm = WaveformManager(p, self)
        left_box.Add(self.wfm, 1, wx.EXPAND)

        channel_panel = wx.StaticBoxSizer(wx.VERTICAL, p)
        channel_box = wx.FlexGridSizer(8, 5, 5)
        channel_box.Add(wx.StaticText(p, -1, 'Channel #'), 0, wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Waveform'), 0, wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Trigger Source'), 0,
                        wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Mode'), 0,
                        wx.ALIGN_CENTER)
        if oscgui_config['OSCGUI']['channel_auto_enable'] == 'yes':
            channel_box.Add(wx.StaticText(p, -1, 'PC Trigger'), 0,
                            wx.ALIGN_CENTER)
            channel_box.Add(wx.StaticText(p, -1, 'Stop'), 0,
                            wx.ALIGN_CENTER)
        else:
            channel_box.AddSpacer(0)
            channel_box.Add(wx.StaticText(p, -1, 'PC Trigger'), 0,
                            wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Trigger Out'), 0, wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Status'), 0, wx.ALIGN_CENTER)
        channels_ui = []
        channel_box.AddGrowableCol(7, 1)
        for i in range(12):

            if oscgui_config['Channel']['order'] == 'shank':
                ch = (7, 2, 8, 0, 6, 1, 10, 5, 11, 3, 9, 4)[i]
                channel_label = wx.StaticText(
                    p, -1, 'S%dL%d' % (i // 3 + 1, i % 3 + 1))
            else:
                ch = i
                channel_label = wx.StaticText(p, -1, 'Channel %d' % i)
            channel_box.Add(channel_label, 0, wx.ALIGN_CENTER)

            waveform_choice = wx.Choice(p, -1,
                                        choices=['Waveform %d' % (x + 1) for x
                                                 in range(4)])
            waveform_choice.SetSelection(0)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(waveform_choice, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_choice = wx.Choice(p, -1, choices=['PC trigger',
                                                       'External trigger'])
            trigger_choice.SetSelection(0)

            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_choice, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            continuous_toggle = wx.ToggleButton(p, -1, 'One-shot')
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(continuous_toggle, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            if oscgui_config['OSCGUI']['channel_auto_enable'] != 'yes':
                stop_button = wx.Button(p, -1, 'Enable', style=wx.BU_EXACTFIT)
                wrap_box = wx.BoxSizer(wx.HORIZONTAL)
                wrap_box.Add(stop_button, 1, wx.ALIGN_CENTER_VERTICAL)
                channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_button = wx.Button(p, -1, 'Trigger', style=wx.BU_EXACTFIT)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_button, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            if oscgui_config['OSCGUI']['channel_auto_enable'] == 'yes':
                stop_button = wx.Button(p, -1, 'Stop', style=wx.BU_EXACTFIT)
                wrap_box = wx.BoxSizer(wx.HORIZONTAL)
                wrap_box.Add(stop_button, 1, wx.ALIGN_CENTER_VERTICAL)
                channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_out_check = wx.CheckBox(p, -1)
            channel_box.Add(trigger_out_check, 0, wx.ALIGN_CENTER)

            status_text = wx.TextCtrl(p, -1, 'Board not connected',
                                      style=wx.TE_READONLY)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(status_text, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND | wx.LEFT, 5)

            channel = ChannelCtrl(
                ch, channel_label, waveform_choice, trigger_choice,
                continuous_toggle, trigger_button, stop_button,
                trigger_out_check, status_text, self)
            channel.on_disconnect()
            channels_ui.append(channel)
            channel_box.AddGrowableRow(i, 1)
        if oscgui_config['Channel']['order'] == 'shank':
            self.channels_ui = [channels_ui[x] for x in
                                (3, 5, 1, 9, 11, 7, 4, 0, 2, 10, 6, 8)]
        else:
            self.channels_ui = channels_ui
        channel_panel.Add(channel_box, 1, wx.EXPAND)

        right_box = wx.BoxSizer(wx.VERTICAL)
        right_box.Add(channel_panel, 0, wx.EXPAND | wx.BOTTOM, 5)

        extra_buttons = wx.BoxSizer(wx.HORIZONTAL)

        if oscgui_config['Waveform']['realtime_update'] != 'yes':
            update_all = wx.Button(p, -1, 'Update all channel parameters')
            update_all.SetToolTip(
                'This will update all waveform parameters, '
                'trigger source, and trigger mode for all modified channel(s).'
                '\nModified channel(s) are marked with asterisk.')
            update_all.Bind(wx.EVT_BUTTON, self.on_update)
            extra_buttons.Add(update_all)
            self.board_relative_controls.append(update_all)

        if oscgui_config['OSCGUI']['channel_auto_enable'] != 'yes':
            enable_all = wx.Button(p, -1, 'Enable All')
            enable_all.Bind(wx.EVT_BUTTON,
                            lambda _: self.device.set_enable(range(12), True))
            extra_buttons.Add(enable_all)
            disable_all = wx.Button(p, -1, 'Disable All')
            disable_all.Bind(wx.EVT_BUTTON,
                             lambda _: self.device.set_enable(range(12), False))
            extra_buttons.Add(disable_all)
            self.board_relative_controls.extend((enable_all, disable_all))
        trigger_all = wx.Button(p, -1, 'Trigger All')
        trigger_all.Bind(wx.EVT_BUTTON,
                         lambda _: self.device.trigger_channel(range(12)))
        extra_buttons.Add(trigger_all)
        self.board_relative_controls.append(trigger_all)
        right_box.Add(extra_buttons, 0, wx.EXPAND | wx.BOTTOM, 50)

        log_text = wx.TextCtrl(p, -1, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.log_sh = logging.StreamHandler(log_text)
        self.log_sh.setLevel(logging.DEBUG if oscgui_config['OSCGUI']['verbose_log'] == 'yes' else logging.INFO)
        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_sh.setFormatter(self.formatter)
        logging.getLogger().addHandler(self.log_sh)
        log_box = wx.StaticBoxSizer(wx.VERTICAL, p, 'Log')
        log_box.Add(log_text, 1, wx.EXPAND)

        log_options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        log_options_sizer.AddStretchSpacer(1)

        verbose_log_checkbox = wx.CheckBox(p, -1, 'Enable verbose logging')
        verbose_log_checkbox.Bind(wx.EVT_CHECKBOX, self.on_verbose_log)
        save_log_checkbox = wx.CheckBox(p, -1, 'Save log to file')
        save_log_checkbox.Bind(wx.EVT_CHECKBOX, self.on_save_log)

        if oscgui_config['OSCGUI']['save_log_to_file'] == 'yes':
            save_log_checkbox.SetValue(True)
            self.log_fh = logging.FileHandler(
                time.strftime('oscgui-%Y%m%d.log'), delay=True)
            self.log_fh.setLevel(logging.DEBUG if oscgui_config['OSCGUI']['verbose_log'] == 'yes' else logging.INFO)
            self.log_fh.setFormatter(self.formatter)
            logging.getLogger().addHandler(self.log_fh)
        else:
            self.log_fh = None
        verbose_log_checkbox.SetValue(oscgui_config['OSCGUI']['verbose_log'] == 'yes')

        clear_log_button = wx.Button(p, -1, 'Clear Log')
        clear_log_button.Bind(wx.EVT_BUTTON, lambda _: log_text.Clear())
        log_options_sizer.Add(verbose_log_checkbox, wx.SizerFlags().Expand())
        log_options_sizer.Add(save_log_checkbox, wx.SizerFlags().Expand())
        log_options_sizer.Add(clear_log_button, wx.SizerFlags().Expand())
        log_box.Add(log_options_sizer, wx.SizerFlags().Expand())
        right_box.Add(log_box, 1, wx.EXPAND)

        box = wx.BoxSizer(wx.HORIZONTAL)
        box.Add(left_box, 0, wx.EXPAND | wx.ALL, 5)
        box.AddSpacer(50)
        box.Add(right_box, 1, wx.EXPAND | wx.ALL, 5)

        for x in self.board_relative_controls:
            x.Disable()

        p.SetSizerAndFit(box)
        self.Fit()
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_save_log(self, event: wx.Event):
        obj = event.GetEventObject()
        assert isinstance(obj, wx.CheckBox)
        if obj.GetValue():
            oscgui_config['OSCGUI']['save_log_to_file'] = 'yes'
            with open('config.ini', 'w') as fp:
                oscgui_config.write(fp)
            if self.log_fh is None:
                self.log_fh = logging.FileHandler(
                    time.strftime('oscgui-%Y%m%d.log'), delay=True)
                self.log_fh.setLevel(logging.INFO)
                self.log_fh.setFormatter(self.formatter)
                logging.getLogger().addHandler(self.log_fh)

        else:
            oscgui_config['OSCGUI']['save_log_to_file'] = 'no'
            with open('config.ini', 'w') as fp:
                oscgui_config.write(fp)
            if self.log_fh:
                logging.getLogger().removeHandler(self.log_fh)
                self.log_fh.close()
                self.log_fh = None

    def on_verbose_log(self, event: wx.Event):
        obj = event.GetEventObject()
        assert isinstance(obj, wx.CheckBox)
        if obj.GetValue():
            oscgui_config['OSCGUI']['verbose_log'] = 'yes'
            with open('config.ini', 'w') as fp:
                oscgui_config.write(fp)
            self.log_sh.setLevel(logging.DEBUG)
            if self.log_fh is not None:
                self.log_fh.setLevel(logging.DEBUG)

        else:
            oscgui_config['OSCGUI']['verbose_log'] = 'no'
            with open('config.ini', 'w') as fp:
                oscgui_config.write(fp)
            self.log_sh.setLevel(logging.INFO)
            if self.log_fh is not None:
                self.log_fh.setLevel(logging.INFO)

    def on_update(self, event: wx.Event):
        chs = [ch for ch in range(12) if self.channels_ui[ch].modified]
        if chs:
            if self.device is not None:
                if oscgui_config['OSCGUI']['channel_auto_enable'] == 'yes':
                    for ch in chs:
                        self.device.set_channel(ch, osc1lite.ChannelInfo(
                            osc1lite.SquareWaveform()))
                    self.device.set_trigger_source(chs, False)
                    self.device.set_trigger_mode(chs, False)
                    self.device.trigger_channel(chs)
                else:
                    self.device.set_enable(chs, False)
            for ch, x in enumerate(self.channels_ui):
                if x.modified:
                    x.update_param()
                    wf = x.waveform_choice.GetSelection()
                    data = self.wfm.waveform_panels[wf].channel_info()
                    if self.device is not None:
                        self.device.set_channel(ch, data)
                        if oscgui_config['OSCGUI'][
                            'channel_auto_enable'] == 'yes':
                            self.device.set_trigger_source(ch, x.trigger)
                            self.device.set_trigger_mode(ch, x.continuous)

            if oscgui_config['Waveform']['realtime_update'] != 'yes':
                logging.getLogger('OSCGUI').info(
                    'Waveform updated: %s',
                    ', '.join(self.channels_ui[ch].channel_name for ch in chs))
            else:
                disabled_list = [self.channels_ui[ch].channel_name for ch in chs
                                 if self.channels_ui[ch].enabled]
                if disabled_list and oscgui_config['OSCGUI']['channel_auto_enable'] != 'yes':
                    logging.getLogger('OSCGUI').info(
                        'Channel(s) disabled due to waveform change: %s',
                        ', '.join(disabled_list))
        elif oscgui_config['Waveform']['realtime_update'] != 'yes':
            logging.getLogger('OSCGUI').info(
                'Channels already up to date')

    def on_connect_worker(self, connect=None):
        if connect is None:
            connect = self.connect_button.GetLabel() == 'Connect'
        with self.daemon_lock:
            if connect:
                if self.device is not None:
                    return
                serial = self.device_choice.GetStringSelection()
                self._dev.OpenBySerial(serial)
                if not self._dev.IsOpen():
                    logging.getLogger('OSCGUI').fatal(
                        'Device not open. Maybe you have connected to a new '
                        'board but have not restarted OSCGUI?')
                    return
                try:
                    with open('calib/' + serial + '.calib') as fp:
                        calib = []
                        for _ in range(12):
                            s = next(fp).strip().split(None, 2)
                            s[0] = float(s[0])
                            s[1] = float(s[1])
                            if len(s) == 3:
                                s[2] = float(s[2])
                                s[0] /= s[2]
                                s[1] /= s[2]
                            else:
                                s[0] /= 100
                                s[1] /= 100
                            calib.append(s[0:2])
                except:
                    calib = [None for _ in range(12)]
                    logging.getLogger('OSCGUI').warning(
                        'Calibration data for board %s not found. '
                        'Running in uncalibrated mode.', serial)
                self.device = osc1lite.OSC1Lite(self._dev, calib=calib)
                try:
                    self.device.configure(
                        bit_file='OSC1_LITE_Control.bit',
                        ignore_hash_error=
                        oscgui_config['OSC1Lite'][
                            'bitfile_integrity_check'] != 'yes')
                except OSError as e:
                    wx.MessageBox(str(e), 'Connect failed',
                                  wx.OK | wx.CENTRE | wx.ICON_ERROR)
                    self.device = None
                    self._dev.Close()
                    return
                except ValueError as e:
                    wx.MessageBox(str(e), 'Connect failed',
                                  wx.OK | wx.CENTRE | wx.ICON_ERROR)
                    self.device = None
                    self._dev.Close()
                    return
                self.device.reset()
                self.device.init_dac()
                self.device.enable_dac_output()
                self.Freeze()
                for x in self.channels_ui:
                    x.set_modified()
                    x.on_connect()
                self.device_choice.Disable()
                self.connect_button.SetLabel('Disconnect')
                for x in self.board_relative_controls:
                    x.Enable()
                logging.getLogger('OSCGUI').info('Connected')
                if oscgui_config['Waveform']['realtime_update'] == 'yes':
                    self.on_update(None)
                if oscgui_config['OSCGUI']['channel_auto_enable'] == 'yes':
                    self.device.set_enable(range(12), True)
                if oscgui_config['OSCGUI']['trigger_out_auto_enable'] == 'yes':
                    for x in self.channels_ui:
                        x.trigger_out_check.SetValue(True)
                    self.device.set_trigger_out(range(12), True)
                for x in self.wfm.waveform_panels:
                    if isinstance(x.detail, CustomWavePanel):
                        x.detail.send_custom_waveform()
                self.Thaw()
            else:
                if self.device is None:
                    return
                self.device.set_enable(range(12), False)
                self._dev.Close()
                self.device = None
                self.Freeze()
                self.device_choice.Enable()
                self.connect_button.SetLabel('Connect')
                for x in self.channels_ui:
                    x.on_disconnect()
                    x.status_text.SetBackgroundColour(wx.NullColour)
                    x.status_text.SetValue('Board not connected')
                for x in self.board_relative_controls:
                    x.Disable()
                logging.getLogger('OSCGUI').info('Disconnected')
                self.Thaw()

    def is_wf_using(self, waveform: str):
        for ch, x in enumerate(self.channels_ui):
            wf = x.waveform_choice.GetStringSelection()
            if waveform == wf:
                return ch
        return -1

    def set_wf_modified(self, waveform: str):
        self.Freeze()
        for ch, x in enumerate(self.channels_ui):
            wf = x.waveform_choice.GetStringSelection()
            if waveform == wf:
                x.set_modified()
        if oscgui_config['Waveform']['realtime_update'] == 'yes':
            self.on_update(None)
        self.Thaw()

    def update_wf_list(self):
        self.Freeze()
        wfs = [x.label for x in self.wfm.waveform_panels]
        for x in self.channels_ui:
            wf = x.waveform_choice.GetStringSelection()
            x.waveform_choice.Set(wfs)
            x.waveform_choice.SetSelection(wfs.index(wf))
        self.Thaw()

    def on_close(self, event: wx.CloseEvent):
        threading.Thread(target=self.on_close_worker).start()
        event.Skip()

    def on_close_worker(self):
        with self.daemon_lock:
            if self.connect_button.GetLabel() != 'Connect':
                self.device.set_enable(range(12), False)
                self._dev.Close()

    def on_save_config(self, event: wx.Event):
        with wx.FileDialog(self, "Save config file",
                           wildcard="JSON config files (*.json)|*.json",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
            if fd.ShowModal() == wx.ID_CANCEL:
                return
            pathname = fd.GetPath()
            try:
                with open(pathname, 'w') as fp:
                    config = {'__version__': __version__,
                              'waveforms': [x.to_dict()
                                            for x in self.wfm.waveform_panels],
                              'channels': [x.to_dict()
                                           for x in self.channels_ui]}
                    json.dump(config, fp)
                    logging.getLogger('OSCGUI').info(
                        'Saved config file to ' + pathname)
            except IOError:
                logging.getLogger('OSCGUI').warning(
                    'Failed to save config file')

    def on_load_config(self, event: wx.Event):
        with wx.FileDialog(self, "Load config file",
                           wildcard="JSON config files (*.json)|*.json",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
            if fd.ShowModal() == wx.ID_CANCEL:
                return
            pathname = fd.GetPath()
            self.Freeze()
            try:
                with open(pathname, 'r') as fp:
                    config = json.load(fp)
                if config['__version__'] != __version__:
                    raise ValueError('Config file has incompatible version (config version: ' + config[
                        '__version__'] + ', software version: ' + __version__ + ')')
                self.wfm.from_dict(config['waveforms'])
                for x, y in zip(self.channels_ui, config['channels']):
                    x.from_dict(y)
            except (IOError, ValueError, KeyError, AssertionError) as e:
                logging.getLogger('OSCGUI').error(
                    'Failed to load config file: ' + str(e))
            if oscgui_config['Waveform']['realtime_update'] == 'yes':
                self.on_update(None)
            self.Thaw()


if __name__ == '__main__':
    app = wx.App()
    if oscgui_config['OSCGUI']['warning_on_startup'] == 'yes':
        dlg = wx.RichMessageDialog(
            None,
            'Do not turn off the power on board before clicking the Disconnect '
            'button.\nOtherwise it will damage the uLED.', 'CAUTION',
            style=wx.OK | wx.CENTRE | wx.ICON_EXCLAMATION)
        dlg.ShowCheckBox("Don't show again")
        dlg.ShowModal()
        if dlg.IsCheckBoxChecked():
            oscgui_config['OSCGUI']['warning_on_startup'] = 'no'
            with open('config.ini', 'w') as fp:
                oscgui_config.write(fp)
    MainFrame().Show()
    sys.exit(app.MainLoop())
