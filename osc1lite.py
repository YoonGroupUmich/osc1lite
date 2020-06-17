#! /usr/bin/env python

import ok
import hashlib
import logging
import struct
import threading


class Waveform:
    pass


class SquareWaveform(Waveform):

    def __init__(self, mode=0, amp=0., pw=0., period=0.):
        """
        mode: controls the rising/falling edge width
        mode       rising edge width (ms)
          0                 0
          1                 0.1
          2                 0.5
          3                 1
          4                 2

        amp: controls the wave amplitude, unit: uA, range: [0, 155.9].
        amp=0 can be used to stop the channel

        period: controls the wave period, unit: second, range: [0, 17.98].
        pw: controls the wave pulse width, unit: second, range: [0, period]
        """
        self.mode = mode
        self.amp = amp
        self.period = period
        self.pulse_width = pw


class CustomWaveform(Waveform):
    def __init__(self, wave=None, clk_div=1, index=-1):
        if wave is None:
            self.wave = []
        else:
            self.wave = wave
        self.clk_div = clk_div
        self.index = index  # The index used on board to identify this custom waveform


class ChannelInfo:
    def __init__(self, waveform: SquareWaveform, n_pulses=1):
        """
        waveform: the waveform object. Currently we only support SquareWaveform
        n_pulses: positive integer. Number of pulses
        """
        self.wf = waveform
        self.n_pulses = n_pulses


class OSC1Lite:
    _bit_file_sha256sum = (
        '975ad5cc70c8b3ef2a74569ef6ff4ea5ff232201191ff4dc1aee4b397e86244a')

    @staticmethod
    def _sha256sum(filename: str, block_size=2 ** 22):
        sha256 = hashlib.sha256()
        with open(filename, 'rb') as fp:
            while True:
                data = fp.read(block_size)
                if not data:
                    break
                sha256.update(data)
            return sha256.hexdigest()

    def __init__(self, dev: ok.okCFrontPanel, calib):
        if not dev.IsOpen():
            logging.getLogger('OSC1Lite').fatal('Device is not opened')
            raise AssertionError('Device is not opened')
        self.dev = dev
        self.device_lock = threading.RLock()
        if calib is None:
            self.calib = [None for _ in range(12)]
        else:
            self.calib = calib

    def configure(self, bit_file='OSC1_LITE_Control.bit',
                  ignore_hash_error=False):
        """
        Configure OSC1Lite. Should be called right after connected to the device
        :param ignore_hash_error: Allow bit file integrity check to fail
        :type ignore_hash_error: bool
        :param bit_file: Path to bit file of FPGA
        :type bit_file: str
        """

        # Integrity check for bit file
        sha256 = self._sha256sum(bit_file)
        if sha256 != self._bit_file_sha256sum:
            logging.getLogger('OSC1Lite').error('Bit file hash mismatch')
            if not ignore_hash_error:
                raise ValueError(
                    'Bit file corrupted. ' +
                    'Expected SHA256: ' + self._bit_file_sha256sum + ', ' +
                    'Got: ' + sha256)

        # Configure the FPGA
        with self.device_lock:
            ret = self.dev.ConfigureFPGA(bit_file)
            if ret == ok.okCFrontPanel.NoError:
                pass
            elif ret == ok.okCFrontPanel.DeviceNotOpen:
                msg = 'ConfigureFPGA() returned DeviceNotOpen'
                logging.getLogger('OSC1Lite').fatal(msg)
                raise OSError(msg)
            elif ret == ok.okCFrontPanel.FileError:
                msg = 'ConfigureFPGA() returned FileError'
                logging.getLogger('OSC1Lite').fatal(msg)
                raise OSError(msg)
            elif ret == ok.okCFrontPanel.InvalidBitstream:
                msg = 'ConfigureFPGA() returned InvalidBitstream'
                logging.getLogger('OSC1Lite').fatal(msg)
                raise OSError(msg)
            elif ret == ok.okCFrontPanel.DoneNotHigh:
                msg = 'ConfigureFPGA() returned DoneNotHigh'
                logging.getLogger('OSC1Lite').fatal(msg)
                raise OSError(msg)
            elif ret == ok.okCFrontPanel.TransferError:
                msg = 'ConfigureFPGA() returned TransferError'
                logging.getLogger('OSC1Lite').fatal(msg)
                raise OSError(msg)
            elif ret == ok.okCFrontPanel.CommunicationError:
                msg = 'ConfigureFPGA() returned CommunicationError'
                logging.getLogger('OSC1Lite').fatal(msg)
                raise OSError(msg)
            elif ret == ok.okCFrontPanel.UnsupportedFeature:
                msg = 'ConfigureFPGA() returned UnsupportedFeature'
                logging.getLogger('OSC1Lite').fatal(msg)
                raise OSError(msg)
            else:
                msg = 'ConfigureFPGA() returned' + str(ret)
                logging.getLogger('OSC1Lite').fatal(msg)
                raise OSError(msg)

            # Configure the PLL clock used by FPGA
            # CLK = Ref / Q * P / div
            # Constraint: Ref / Q >= 0.25 MHz, Ref / Q * P >= 100 MHz
            pll = ok.PLL22150()

            #                 MHz
            pll.SetReference(48.0, False)

            #                     P    Q   P: [8, 2055], Q: [2, 129]
            pll.SetVCOParameters(125, 12)
            # pll.SetVCOParameters(512, 125)

            #                          div  div: [4, 127]
            pll.SetDiv1(pll.DivSrc_VCO, 67)
            # pll.SetDiv1(pll.DivSrc_VCO, 15)

            pll.SetOutputSource(0, pll.ClkSrc_Div1ByN)
            pll.SetOutputEnable(0, True)
            self.dev.SetPLL22150Configuration(pll)
            logging.getLogger('OSC1Lite.PLL').debug(
                'PLL output freq = {freq}MHz'.format(
                    freq=pll.GetOutputFrequency(0)))

            self._freq = pll.GetOutputFrequency(0) * (10 ** 6)

        logging.getLogger('OSC1Lite').info('OSC1Lite configured.')

    def _write_to_wire_in(self, channel, val, mask=0xffff, update=True):
        self.dev.SetWireInValue(channel, val, mask)
        if update:
            self.dev.UpdateWireIns()

    def reset_dac(self):
        with self.device_lock:
            self._write_to_wire_in(0x01, 4)
            self._write_to_wire_in(0x01, 0)

    def reset_pipe(self):
        with self.device_lock:
            self._write_to_wire_in(0x00, 1)
            self._write_to_wire_in(0x00, 0)

    def set_channel(self, channel, data: ChannelInfo):
        if isinstance(data.wf, SquareWaveform):
            logging.getLogger('OSC1Lite').debug(
                'Sending params for channel %d: mode=%d, amp=%.1f, pw=%f, '
                'period=%f', channel,
                data.wf.mode, data.wf.amp, data.wf.pulse_width, data.wf.period)
            word = round(data.wf.pulse_width / (2 ** 7) * self._freq)
            word_pw = 0 if word < 0 else 0xffff if word > 0xfffff else word
            word = round(data.wf.period / (2 ** 7) * self._freq)
            word_period = 0 if word < 0 else 0xffff if word > 0xfffff else word
            word = round(data.wf.amp / 20000 * 65536)
            word_amp = 0 if word < 0 else 0xffff if word > 0xffff else word
            with self.device_lock:
                self._write_to_wire_in(0x03, word_pw & 0xffff, update=False)
                self._write_to_wire_in(0x04, word_period & 0xffff, update=False)
                self._write_to_wire_in(0x05, word_amp, update=False)
                self._write_to_wire_in(0x07, data.n_pulses, update=False)
                self._write_to_wire_in(
                    0x0a, (word_pw >> 16) | ((word_period >> 8) & 0x0f00),
                    update=False)
                if self.calib[channel] is None:
                    gain = 0x8000
                    zero = 0x0000
                else:
                    t10, t90 = self.calib[channel]
                    # c10 = 33, c90 = 295
                    t90 = t90 / 20 * 65536
                    t10 = t10 / 20 * 65536
                    k = (t90 - t10) / 262
                    b = ((t90 + t10 + 655.36) - 328 * 3 * k) / 2
                    gain = 1 / k * (2 ** 16) - (2 ** 15)
                    zero = - b / k
                self._write_to_wire_in(0x0c, round(gain) & 0xffff, update=False)
                self._write_to_wire_in(0x0d, round(zero) & 0xffff, update=False)
                self._write_to_wire_in(0x06, data.wf.mode | (channel << 4),
                                       update=True)

                # Send data update trigger
                self._write_to_wire_in(0x06, 0x0100, mask=0x0100, update=True)
        else:  # CustomWaveform
            assert(data.wf.index > 0)
            logging.getLogger('OSC1Lite').debug(
                'Sending params for channel %d: custom_waveform #%d', channel,
                data.wf.index)
            with self.device_lock:
                self._write_to_wire_in(0x03, 0, update=False)
                self._write_to_wire_in(0x04, 0, update=False)
                self._write_to_wire_in(0x05, 0, update=False)
                self._write_to_wire_in(0x07, data.n_pulses, update=False)
                self._write_to_wire_in(0x0a, 0, update=False)
                if self.calib[channel] is None:
                    gain = 0x8000
                    zero = 0x0000
                else:
                    t10, t90 = self.calib[channel]
                    # c10 = 33, c90 = 295
                    t90 = t90 / 20 * 65536
                    t10 = t10 / 20 * 65536
                    k = (t90 - t10) / 262
                    b = ((t90 + t10 + 655.36) - 328 * 3 * k) / 2
                    gain = 1 / k * (2 ** 16) - (2 ** 15)
                    zero = - b / k
                self._write_to_wire_in(0x0c, round(gain) & 0xffff, update=False)
                self._write_to_wire_in(0x0d, round(zero) & 0xffff, update=False)
                self._write_to_wire_in(0x06, (channel << 4) | (data.wf.index << 9), update=True)

                # Send data update trigger
                self._write_to_wire_in(0x06, 0x0100, mask=0x0100, update=True)

    def reset(self):
        with self.device_lock:
            for channel in range(0x20):
                self._write_to_wire_in(channel, 0, update=False)
            self.dev.UpdateWireIns()

            self.reset_dac()
            self.reset_pipe()
            for i in range(12):
                self.set_channel(i, ChannelInfo(SquareWaveform()))
        logging.getLogger('OSC1Lite').info('Reset done')

    def init_dac(self):
        with self.device_lock:
            self._write_to_wire_in(0x01, 5)
            self._write_to_wire_in(0x01, 6)
            self._write_to_wire_in(0x01, 2)
            self._write_to_wire_in(0x01, 0)

    def enable_dac_output(self):
        with self.device_lock:
            self._write_to_wire_in(0x01, 1)

    def trigger_channel(self, ch):
        logging.getLogger('OSC1Lite').debug('triggering %s', str(ch))
        with self.device_lock:
            try:
                for x in ch:
                    self.dev.ActivateTriggerIn(0x55, x)
            except TypeError:
                self.dev.ActivateTriggerIn(0x55, ch)

    def set_trigger_out(self, ch, enable=True):
        channel_bit = 0
        try:
            for x in ch:
                channel_bit |= 1 << x
        except TypeError:
            channel_bit = 1 << ch
        with self.device_lock:
            self._write_to_wire_in(0x09, channel_bit if enable else 0,
                                   mask=channel_bit, update=True)

    def set_enable(self, ch, enable=True):
        logging.getLogger('OSC1Lite').debug('%sabling channel %s',
                                            'En' if enable else 'Dis', str(ch))
        addr = 0x53 if enable else 0x54
        with self.device_lock:
            try:
                for x in ch:
                    self.dev.ActivateTriggerIn(addr, x)
            except TypeError:
                self.dev.ActivateTriggerIn(addr, ch)

    def get_channel_warnings(self):
        with self.device_lock:
            self.dev.UpdateTriggerOuts()
            return (
                {
                    'DAC die temperature over 142 degC': [
                        i for i in range(12) if self.dev.IsTriggered(
                            0x6b + i // 3, 1 << (i % 3 * 5))],
                    'DAC code is slewing': [
                        i for i in range(12) if self.dev.IsTriggered(
                            0x6b + i // 3, 1 << (i % 3 * 5 + 1))],
                    'DAC open circuit or compliance voltage violation': [
                        i for i in range(12) if self.dev.IsTriggered(
                            0x6b + i // 3, 1 << (i % 3 * 5 + 2))],
                    'DAC watchdog timer timeout': [
                        i for i in range(12) if self.dev.IsTriggered(
                            0x6b + i // 3, 1 << (i % 3 * 5 + 3))],
                    'DAC SPI CRC error': [
                        i for i in range(12) if self.dev.IsTriggered(
                            0x6b + i // 3, 1 << (i % 3 * 5 + 4))]
                },
                # Trigger overlap
                [i for i in range(12) if self.dev.IsTriggered(0x6a, 1 << i)],
                # Idle timeout
                [i for i in range(12) if self.dev.IsTriggered(0x69, 1 << i)])

    def set_trigger_source(self, ch, source):
        channel_bit = 0
        try:
            for x in ch:
                channel_bit |= 1 << x
        except TypeError:
            channel_bit = 1 << ch
        with self.device_lock:
            self._write_to_wire_in(0x08, channel_bit if source else 0,
                                   mask=channel_bit, update=True)

    def set_trigger_mode(self, ch, continuous):
        channel_bit = 0
        try:
            for x in ch:
                channel_bit |= 1 << x
        except TypeError:
            channel_bit = 1 << ch
        with self.device_lock:
            self._write_to_wire_in(0x0b, channel_bit if continuous else 0,
                                   mask=channel_bit, update=True)

    def status(self):
        with self.device_lock:
            self.dev.UpdateWireOuts()
            # 0x21:  1: Output working, 0: Not triggered
            # 0x22:  1: Channel Enabled, 0: Channel Disabled
            return (self.dev.GetWireOutValue(0x21),
                    self.dev.GetWireOutValue(0x22))

    def send_custom_waveform(self, data: CustomWaveform):
        logging.getLogger('OSC1Lite').debug(
            'Sending custom_waveform #%d, len=%d', data.index, len(data.wave))
        buff = b'csw\n'
        buff += struct.pack('<BBH', data.index, data.clk_div, len(data.wave))
        for x in data.wave:
            word = round(x / 20000 * 65536)
            word_amp = 0 if word < 0 else 0xffff if word > 0xffff else word
            buff += struct.pack('<H', word_amp)
        with self.device_lock:
            self.dev.WriteToPipeIn(0x80, bytearray(buff))
