#! /usr/bin/env python

import ok
import hashlib
import logging
import time


class ChannelInfo:
    def __init__(self, mode=0, amp=0., pw=0., period=10., n_pulses=1,
                 ext_trig=0):
        """
        mode controls the rising/falling edge width
        amp controls the wave amplitude
        """
        self.mode = mode
        self.amp = amp  # uA, range: [0, 24000]. Use amp=0 to stop the channel
        self.period = period  # sec, range: [0, 10.23]
        self.pulse_width = pw  # sec
        self.n_pulses = n_pulses  # set n_pulses to 0 for continuous output
        self.ext_trig = ext_trig  # 0: PC trigger, 1: external trigger


class OSC1Lite:
    _bit_file_sha256sum = (
        '547c3d4190d5b846ce6e5d75fa90bddd5efc4465bdf8ff5528740ddd37f59918')

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

    def __init__(self, dev: ok.okCFrontPanel):
        assert dev.IsOpen(), 'Device is not opened'
        self.dev = dev

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
                    'Bit file sha256sum mismatch. ' +
                    'Expected: ' + self._bit_file_sha256sum + ', ' +
                    'Got: ' + sha256)

        # Configure the FPGA
        ret = self.dev.ConfigureFPGA(bit_file)
        if ret == ok.okCFrontPanel.NoError:
            pass
        elif ret == ok.okCFrontPanel.DeviceNotOpen:
            raise OSError('ConfigureFPGA() returned DeviceNotOpen')
        elif ret == ok.okCFrontPanel.FileError:
            raise OSError('ConfigureFPGA() returned FileError')
        elif ret == ok.okCFrontPanel.InvalidBitstream:
            raise OSError('ConfigureFPGA() returned InvalidBitstream')
        elif ret == ok.okCFrontPanel.DoneNotHigh:
            raise OSError('ConfigureFPGA() returned DoneNotHigh')
        elif ret == ok.okCFrontPanel.TransferError:
            raise OSError('ConfigureFPGA() returned TransferError')
        elif ret == ok.okCFrontPanel.CommunicationError:
            raise OSError('ConfigureFPGA() returned CommunicationError')
        elif ret == ok.okCFrontPanel.UnsupportedFeature:
            raise OSError('ConfigureFPGA() returned UnsupportedFeature')
        else:
            raise OSError('ConfigureFPGA() returned ' + str(ret))

        # Configure the PLL clock used by FPGA
        pll = ok.PLL22150()
        pll.SetReference(48.0, False)
        pll.SetVCOParameters(512, 125)
        pll.SetDiv1(pll.DivSrc_VCO, 15)
        pll.SetOutputSource(0, pll.ClkSrc_Div1ByN)
        pll.SetOutputEnable(0, True)
        pll.SetDiv2(pll.DivSrc_VCO, 8)
        pll.SetOutputSource(1, pll.ClkSrc_Div2ByN)
        pll.SetOutputEnable(1, True)
        self.dev.SetPLL22150Configuration(pll)
        for i in range(2):
            logging.getLogger('OSC1Lite.PLL').info(
                'PLL output #{i} freq = {freq}MHz'.format(
                    i=i, freq=pll.GetOutputFrequency(i)))

        logging.getLogger('OSC1Lite').info('OSC1Lite configured.')

    def _write_to_wire_in(self, channel, val, mask=0xffff, update=True):
        self.dev.SetWireInValue(channel, val, mask)
        if update:
            self.dev.UpdateWireIns()

    def reset_dac(self):
        self._write_to_wire_in(0x01, 4)
        self._write_to_wire_in(0x01, 0)

    def reset_pipe(self):
        self._write_to_wire_in(0x00, 1)
        self._write_to_wire_in(0x00, 0)

    def set_channel(self, channel, data: ChannelInfo):
        print('Sending params for channel', channel)
        print('amp =', data.amp, ', pw =', data.pulse_width, ', period =',
              data.period)
        word = round(data.pulse_width / (2 ** 11) * 13107200)
        word = 0 if word < 0 else 0xffff if word > 0xffff else word
        self._write_to_wire_in(0x03, word, update=False)
        word = round(data.period / (2 ** 11) * 13107200)
        word = 0 if word < 0 else 0xffff if word > 0xffff else word
        self._write_to_wire_in(0x04, word, update=False)
        word = round(data.amp / 24000 * 65536 / (1, 3, 13, 25, 50)[data.mode])
        word = 0 if word < 0 else 0xffff if word > 0xffff else word
        self._write_to_wire_in(0x05, word, update=False)
        self._write_to_wire_in(0x07, data.n_pulses, update=False)
        self._write_to_wire_in(
            0x06, data.mode | (channel << 4) | (data.ext_trig << 9),
            update=True)

        # Send data update trigger
        self._write_to_wire_in(0x06, 0x0100, mask=0x0100, update=True)

    def reset(self):
        for channel in range(0x20):
            self._write_to_wire_in(channel, 0, update=False)
        self.dev.UpdateWireIns()

        self.reset_dac()
        self.reset_pipe()
        for i in range(12):
            self.set_channel(i, ChannelInfo())
        print('Reset done')

    def init_dac(self):
        self._write_to_wire_in(0x01, 5)
        self._write_to_wire_in(0x01, 3)
        self._write_to_wire_in(0x01, 0)

    def enable_dac_output(self):
        self._write_to_wire_in(0x01, 1)

    def trigger_channel(self, ch):
        print('trigger', ch)
        channel_bit = 0
        try:
            for x in ch:
                channel_bit |= 1 << x
        except TypeError:
            channel_bit = 1 << ch
        self._write_to_wire_in(0x08, channel_bit, mask=channel_bit, update=True)
        self._write_to_wire_in(0x08, 0, mask=channel_bit, update=True)

    def set_trigger_out(self, ch, enable=True):
        print('trigger', ch)
        channel_bit = 0
        try:
            for x in ch:
                channel_bit |= 1 << x
        except TypeError:
            channel_bit = 1 << ch
        self._write_to_wire_in(0x09, channel_bit if enable else 0,
                               mask=channel_bit, update=True)

    def get_channel_warnings(self):
        self.dev.UpdateTriggerOuts()
        return [i for i in range(16) if self.dev.IsTriggered(0x6a, 1 << i)]
