#! /usr/bin/env python3.5

import logging
import matplotlib.pyplot as plt
import os
import sys
import threading
import time
import wx
import wx.lib.scrolledpanel

import ok
import osc1lite

__version__ = '0.0.1'

logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))


class LabeledCtrl(wx.BoxSizer):
    def __init__(self, control, parent=None, ident=-1, label=''):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        self.Add(wx.StaticText(parent, ident, label), 1, wx.EXPAND)
        self.Add(control, 1, wx.EXPAND)


class ChannelCtrl:
    _error_color = wx.Colour(255, 172, 172)
    _warning_color = wx.Colour(206, 206, 0)
    _normal_color = wx.Colour(0, 243, 243)
    _disabled_color = wx.NullColour

    def __init__(self, ch: int, waveform_choice: wx.Choice,
                 trigger_choice: wx.Choice,
                 continuous_toggle: wx.ToggleButton, trigger_button: wx.Button,
                 stop_button: wx.Button, trigger_out_check: wx.CheckBox,
                 status_text: wx.TextCtrl):
        self.ch = ch
        self.waveform_choice = waveform_choice
        self.trigger_choice = trigger_choice
        self.continuous_toggle = continuous_toggle
        self.continuous_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle)
        self.trigger_button = trigger_button
        self.stop_button = stop_button
        self.trigger_out_check = trigger_out_check
        self.status_text = status_text

        self.waveform = 'Waveform 1'
        self.trigger = 0
        self.continuous = 0
        self._enabled = False
        self.output = False
        self.warnings = []

    def get_status_color_text(self):
        if self.warnings:
            return self._error_color, ', '.join(self.warnings)
        if not self._enabled:
            if self.output:
                return self._error_color, 'Disabled Normal ??!!??!'
            return self._disabled_color, 'Disabled'
        if self.output:
            return self._normal_color, 'Normal'
        return self._warning_color, 'Stopped (Not triggered)'

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, val):
        self._enabled = val
        target_label = 'Disable' if val else 'Enable'
        if self.stop_button.GetLabel() != target_label:
            self.stop_button.SetLabel(target_label)

    def log_trigger_overlap(self):
        ...

    def log_status(self):
        ...

    @staticmethod
    def on_toggle(event: wx.CommandEvent):
        obj = event.GetEventObject()
        obj.SetLabel('Continuous' if obj.GetValue() else 'One-shot')

    def update_param(self):
        self.waveform = self.waveform_choice.GetStringSelection()
        self.trigger = self.trigger_choice.GetSelection()
        self.continuous = self.continuous_toggle.GetValue()
        self.trigger_button.Enable(not self.trigger)


class SquareWavePanel(wx.FlexGridSizer):
    def __init__(self, parent):
        wx.FlexGridSizer.__init__(self, 2, 4, 5, 5)
        for i in range(4):
            self.AddGrowableCol(i, 1)
        self.Add(wx.StaticText(parent, -1, 'Amplitude (\u03bcA)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Pulse Width (ms)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Period (ms)'), 0, wx.EXPAND)
        self.Add(wx.StaticText(parent, -1, 'Rise Time (ms)'), 0, wx.EXPAND)
        self.amp_text = wx.TextCtrl(parent, -1, '2000')
        self.amp_text.SetToolTip(
            'Range: 0~100\u03bcA, Precision: \u00b10.19\u03bcA')
        self.Add(self.amp_text, 0, wx.EXPAND)
        self.amp_text.Bind(wx.EVT_TEXT, self.on_text)
        self.pw_text = wx.TextCtrl(parent, -1, '100')
        self.pw_text.SetToolTip(
            'Range: 0~period, Precision: \u00b18.6\u03bcs')
        self.Add(self.pw_text, 0, wx.EXPAND)
        self.pw_text.Bind(wx.EVT_TEXT, self.on_text)
        self.period_text = wx.TextCtrl(parent, -1, '200')
        self.period_text.SetToolTip(
            'Range: 0~17.9s, Precision: \u00b18.6\u03bcs')
        self.Add(self.period_text, 0, wx.EXPAND)
        self.period_text.Bind(wx.EVT_TEXT, self.on_text)
        self.rise_time_text = wx.TextCtrl(parent, -1, '0')
        self.rise_time_text.SetToolTip(
            'Possible values: 0, 0.1, 0.5, 1, 2ms')
        self.Add(self.rise_time_text, 0, wx.EXPAND)
        self.rise_time_text.Bind(wx.EVT_TEXT, self.on_text)

    def get_waveform(self) -> osc1lite.SquareWaveform:
        rise_time = float(self.rise_time_text.GetValue())
        mode = (0 if rise_time < .05 else
                1 if rise_time < .3 else
                2 if rise_time < .75 else 3 if rise_time < 1.5 else 4)
        return osc1lite.SquareWaveform(amp=float(self.amp_text.GetValue()),
                                       pw=float(self.pw_text.GetValue()) / 1000,
                                       period=float(
                                           self.period_text.GetValue()) / 1000,
                                       mode=mode)

    def on_text(self, event: wx.Event):
        ...


class CustomWavePanel(wx.BoxSizer):
    def __init__(self, parent):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        self.Add(wx.StaticText(parent, -1, 'Custom Waveform File'), 0,
                 wx.EXPAND)
        self.file_picker = wx.FilePickerCtrl(parent, -1, wildcard='*.cwave')
        self.file_picker.Bind(wx.EVT_FILEPICKER_CHANGED, self.on_file)
        self.Add(self.file_picker, 0, wx.EXPAND)
        self.wave = []

    def on_file(self, event: wx.Event):
        with open(self.file_picker.GetPath()) as fp:
            self.wave = [float(x) for x in fp.read().split()]

    def get_waveform(self) -> osc1lite.CustomWaveform:
        return osc1lite.CustomWaveform(self.wave)


class WaveFormPanel(wx.StaticBoxSizer):
    def __init__(self, parent, label):
        wx.StaticBoxSizer.__init__(self, wx.VERTICAL, parent, label)
        p = self.GetStaticBox()
        font = wx.Font(wx.FontInfo(10).Bold())
        self.label = label
        common = wx.BoxSizer(wx.HORIZONTAL)
        waveform_type_choice = wx.Choice(p, -1, choices=['Square Wave'])
        #                                choices=['Square Wave', 'Custom Wave'])
        waveform_type_choice.SetSelection(0)
        waveform_type_choice.Bind(wx.EVT_CHOICE, self.on_type)
        common.Add(LabeledCtrl(waveform_type_choice, p,
                               -1, 'Waveform Type'), 0, wx.ALL, 3)
        self.num_of_pulses = wx.SpinCtrl(p, -1, min=1, max=0xffff)
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
        self.p_square = SquareWavePanel(p)
        self.p_custom = CustomWavePanel(p)
        self.Add(self.p_square, 0, wx.EXPAND | wx.ALL, 3)
        self.Add(self.p_custom, 0, wx.EXPAND | wx.ALL, 3)
        self.Hide(self.p_custom)
        # self.Layout()
        self.detail = self.p_square
        p.SetFont(font)

    def channel_info(self) -> osc1lite.ChannelInfo:
        wf = self.detail.get_waveform()
        return osc1lite.ChannelInfo(wf, n_pulses=self.num_of_pulses.GetValue())

    def on_preview(self, event: wx.Event):
        x_limit = 10
        n_pulses = self.num_of_pulses.GetValue()
        plt.figure(num='Preview for ' + self.label)
        wf = self.detail.get_waveform()
        if isinstance(wf, osc1lite.SquareWaveform):
            if wf.period <= 0:
                xs = [0, x_limit]
                ys = [0, 0]
            else:
                xs = [0]
                ys = [0]
                for i in range(n_pulses):
                    x_offset = xs[-1]
                    rise_time = (0, 0.1, 0.5, 1, 2)[wf.mode]
                    xs.extend((x_offset + rise_time,
                               x_offset + wf.pulse_width * 1000 - rise_time,
                               x_offset + wf.pulse_width * 1000,
                               x_offset + wf.period * 1000))
                    ys.extend((wf.amp, wf.amp, 0, 0))
        elif isinstance(wf, osc1lite.CustomWaveform):
            xs = range(len(wf.wave))
            ys = wf.wave
        else:
            raise TypeError('Waveform type not supported')
        print(xs, ys)
        plt.plot(xs, ys, label=self.label)
        plt.xlabel('time (ms)')
        plt.ylabel('amplitude (\u03bcA)')
        plt.show()

    def on_type(self, event: wx.Event):
        obj = event.GetEventObject()
        assert isinstance(obj, wx.Choice)
        if obj.GetSelection() == 0:  # Square Wave
            self.Hide(self.p_custom)
            self.Show(self.p_square)
            self.Layout()
            self.detail = self.p_square
        else:
            self.Hide(self.p_square)
            self.Show(self.p_custom)
            self.Layout()
            self.detail = self.p_custom


class WaveformManager(wx.ScrolledWindow):
    def __init__(self, parent, mf, ident=-1):
        wx.ScrolledWindow.__init__(self, parent, ident,
                                   style=wx.VSCROLL | wx.ALWAYS_SHOW_SB)
        self.box = wx.BoxSizer(wx.VERTICAL)

        new_wf = wx.Button(self, -1, 'Add New Waveform')
        new_wf.Bind(wx.EVT_BUTTON, self.on_new_wf)
        self.box.Add(new_wf, 0, wx.ALIGN_RIGHT)

        self.cnt = 4
        self.waveform_panels = [WaveFormPanel(self, 'Waveform %d' % (x + 1))
                                for x in range(self.cnt)]
        for wf in self.waveform_panels:
            self.box.Add(wf, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        self.SetSizerAndFit(self.box)
        # self.box.SetSizeHints(self)
        self.SetScrollRate(5, 5)

        self.Bind(wx.EVT_BUTTON, self.on_delete)
        self.parent = parent
        self.mf = mf

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
                self.box.Hide(x)
                break
        self.mf.update_wf_list()
        self.parent.Layout()
        self.parent.Thaw()

    def on_new_wf(self, event: wx.Event):
        self.parent.Freeze()
        self.cnt += 1
        wf = WaveFormPanel(self, 'Waveform %d' % self.cnt)
        self.waveform_panels.append(wf)
        self.box.Add(wf, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        self.box.SetSizeHints(self)
        self.mf.update_wf_list()
        self.parent.Layout()
        self.parent.Thaw()


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
            return
        warn = self.device.get_channel_warnings()
        status = self.device.status()
        overlap = [x for x in warn['Trigger Overlap'] if
                   self.channels_ui[x].trigger_choice.GetSelection() == 1 or
                   not self.channels_ui[x].continuous_toggle.GetValue()]
        if overlap:
            logging.getLogger('OSCGUI').warning(
                'Waveform restarted due to '
                'asynchronous trigger on channel(s): %s',
                ', '.join(str(x) for x in overlap))
        channel_warnings = [[] for _ in range(12)]
        for x, chs in warn.items():
            for ch in chs:
                logging.getLogger('OSCGUI').debug(
                    'Board reported: [Channel %d] %s' % (ch, x))
                if x != 'Trigger Overlap':
                    channel_warnings[ch].append(x)
        for ch, x in enumerate(channel_warnings):
            if x != self.channels_ui[ch].warnings:
                self.channels_ui[ch].warnings = x
                if x:
                    logging.getLogger('OSCGUI').warning(
                        'Channel %d alerts: %s' % (ch, ', '.join(x)))
                else:
                    logging.getLogger('OSCGUI').info(
                        'No alerts on Channel %d' % ch)
            self.channels_ui[ch].output = bool(status[0] & (1 << ch))
            self.channels_ui[ch].enabled = not bool(status[1] & (1 << ch))
            target_color, target_text = self.channels_ui[
                ch].get_status_color_text()
            if (target_color !=
                    self.channels_ui[ch].status_text.GetBackgroundColour()):
                self.channels_ui[ch].status_text.SetBackgroundColour(
                    target_color)
            current_text = self.channels_ui[ch].status_text.GetValue()
            if target_text != current_text:
                self.channels_ui[ch].status_text.SetValue(target_text)

    def __init__(self, parent=None, ident=-1):
        wx.Frame.__init__(self, parent, ident,
                          'OSC1Lite Stimulate GUI v' + __version__)
        self._dev = ok.okCFrontPanel()
        self.device = None
        self.devices = {}

        self.board_relative_controls = []

        p = wx.Panel(self, -1)

        # Setup frame
        setup_sizer = wx.StaticBoxSizer(wx.HORIZONTAL, p, 'Setup')
        self.device_choice = wx.Choice(p, -1,
                                       choices=['[No connected device]'])
        self.device_choice.SetSelection(0)
        self.device_choice.SetSize(self.device_choice.GetBestSize())
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
        left_box.AddSpacer(50)

        self.wfm = WaveformManager(p, self)
        left_box.Add(self.wfm, 1, wx.EXPAND)

        channel_panel = wx.StaticBoxSizer(wx.VERTICAL, p)
        channel_box = wx.FlexGridSizer(8, 5, 5)
        channel_box.Add(wx.StaticText(p, -1, 'Channel #'), 0, wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Waveform'), 0, wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Trigger Source'), 0,
                        wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Trigger Mode'), 0,
                        wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'PC Trigger'), 0, wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Stimulate Output'), 0,
                        wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Trigger Out'), 0, wx.ALIGN_CENTER)
        channel_box.Add(wx.StaticText(p, -1, 'Status'), 0, wx.ALIGN_CENTER)
        self.channels_ui = []
        channel_box.AddGrowableCol(7, 1)
        for i in range(12):
            channel_box.Add(wx.StaticText(p, -1, 'Channel %2d' % i),
                            0, wx.ALIGN_CENTER_VERTICAL)

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

            trigger_button = wx.Button(p, -1, 'Trigger', style=wx.BU_EXACTFIT)
            trigger_button.Bind(wx.EVT_BUTTON,
                                lambda _, i=i: self.device.trigger_channel(i))
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(trigger_button, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            stop_button = wx.Button(p, -1, 'Enable', style=wx.BU_EXACTFIT)
            stop_button.Bind(wx.EVT_BUTTON, self.on_stop)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(stop_button, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND)

            trigger_out_check = wx.CheckBox(p, -1)
            trigger_out_check.Bind(wx.EVT_CHECKBOX, self.on_trigger_out)
            channel_box.Add(trigger_out_check, 0, wx.ALIGN_CENTER)

            status_text = wx.TextCtrl(p, -1, 'Board not connected',
                                      style=wx.TE_READONLY)
            wrap_box = wx.BoxSizer(wx.HORIZONTAL)
            wrap_box.Add(status_text, 1, wx.ALIGN_CENTER_VERTICAL)
            channel_box.Add(wrap_box, 0, wx.EXPAND | wx.LEFT, 5)

            self.channels_ui.append(
                ChannelCtrl(i, waveform_choice, trigger_choice,
                            continuous_toggle, trigger_button, stop_button,
                            trigger_out_check, status_text))
            self.board_relative_controls.extend(
                (trigger_button, stop_button, trigger_out_check))
            channel_box.AddGrowableRow(i, 1)
        channel_panel.Add(channel_box, 1, wx.EXPAND)

        right_box = wx.BoxSizer(wx.VERTICAL)
        right_box.Add(channel_panel, 0, wx.EXPAND | wx.BOTTOM, 5)

        extra_buttons = wx.BoxSizer(wx.HORIZONTAL)
        update_all = wx.Button(p, -1, 'Update all channel parameters')
        update_all.SetToolTip(
            'This will update all waveform parameters, '
            'trigger source, and trigger mode for all channels.')
        update_all.Bind(wx.EVT_BUTTON, self.on_update)
        extra_buttons.Add(update_all)
        trigger_all = wx.Button(p, -1, 'Trigger All')
        trigger_all.Bind(wx.EVT_BUTTON,
                         lambda _: self.device.trigger_channel(range(12)))
        extra_buttons.Add(trigger_all)
        enable_all = wx.Button(p, -1, 'Enable All')
        enable_all.Bind(wx.EVT_BUTTON,
                        lambda _: self.device.set_enable(range(12), True))
        extra_buttons.Add(enable_all)
        disable_all = wx.Button(p, -1, 'Disable All')
        disable_all.Bind(wx.EVT_BUTTON,
                         lambda _: self.device.set_enable(range(12), False))
        extra_buttons.Add(disable_all)
        self.board_relative_controls.extend(
            (update_all, trigger_all, enable_all, disable_all))
        right_box.Add(extra_buttons, 0, wx.EXPAND | wx.BOTTOM, 50)

        log_text = wx.TextCtrl(p, -1, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sh = logging.StreamHandler(log_text)
        sh.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        sh.setFormatter(formatter)
        logging.getLogger().addHandler(sh)
        log_box = wx.StaticBoxSizer(wx.VERTICAL, p, 'Log')
        log_box.Add(log_text, 1, wx.EXPAND)
        clear_log_button = wx.Button(p, -1, 'Clear Log')
        clear_log_button.Bind(wx.EVT_BUTTON, lambda _: log_text.Clear())
        log_box.Add(clear_log_button, 0, wx.EXPAND)
        right_box.Add(log_box, 1, wx.EXPAND)

        box = wx.BoxSizer(wx.HORIZONTAL)
        box.Add(left_box, 0, wx.EXPAND | wx.ALL, 5)
        box.AddSpacer(50)
        box.Add(right_box, 1, wx.EXPAND | wx.ALL, 5)

        for x in self.board_relative_controls:
            x.Disable()

        p.SetSizerAndFit(box)
        self.Fit()

    def on_trigger_out(self, event: wx.Event):
        ident = event.GetId()
        obj = event.GetEventObject()
        assert isinstance(obj, wx.CheckBox)
        for ch, x in enumerate(self.channels_ui):
            if ident == x.trigger_out_check.GetId():
                assert isinstance(self.device, osc1lite.OSC1Lite)
                self.device.set_trigger_out(ch, x.trigger_out_check.GetValue())
                break

    def on_update(self, event: wx.Event):
        for ch, x in enumerate(self.channels_ui):
            wf = x.waveform_choice.GetSelection()
            data = self.wfm.waveform_panels[wf].channel_info()
            data.ext_trig = x.trigger_choice.GetSelection()
            if x.continuous_toggle.GetValue():
                data.n_pulses = 0
            self.device.set_channel(ch, data)
            x.update_param()

    def on_stop(self, event: wx.Event):
        ident = event.GetId()
        obj = event.GetEventObject()
        assert isinstance(obj, wx.Button)
        assert isinstance(self.device, osc1lite.OSC1Lite)
        for ch, x in enumerate(self.channels_ui):
            if ident == x.stop_button.GetId():
                self.device.set_enable(ch, obj.GetLabel() == 'Enable')
                break

    def on_connect_worker(self):
        with self.daemon_lock:
            if self.connect_button.GetLabel() == 'Connect':
                assert self.device is None
                self._dev.OpenBySerial(self.device_choice.GetStringSelection())
                self.device = osc1lite.OSC1Lite(self._dev)
                self.device.configure(bit_file='OSC1_LITE_Control.bit',
                                      ignore_hash_error=True)
                self.device.reset()
                self.device.init_dac()
                self.device.enable_dac_output()
                self.Freeze()
                self.device_choice.Disable()
                self.connect_button.SetLabel('Disconnect')
                for x in self.board_relative_controls:
                    x.Enable()
                logging.getLogger('OSCGUI').info('Connected')
                self.Thaw()
            else:
                self.device.disable_dac()
                self._dev.Close()
                self.device = None
                self.Freeze()
                self.device_choice.Enable()
                self.connect_button.SetLabel('Connect')
                for x in self.channels_ui:
                    x.trigger_out_check.SetValue(False)
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

    def update_wf_list(self):
        wfs = [x.label for x in self.wfm.waveform_panels]
        for x in self.channels_ui:
            wf = x.waveform_choice.GetStringSelection()
            x.waveform_choice.Set(wfs)
            x.waveform_choice.SetSelection(wfs.index(wf))


if __name__ == '__main__':
    app = wx.App()
    MainFrame().Show()
    sys.exit(app.MainLoop())
