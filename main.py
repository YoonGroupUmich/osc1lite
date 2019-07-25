#! /usr/bin/env python35

import ok
import osc1lite
import time

import os
import logging

logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))


def main():
    dev = ok.okCFrontPanel()

    # Enumerate devices
    n_devices = dev.GetDeviceCount()
    for i in range(n_devices):
        logging.debug(
            'Device[{0}] Model: {1}'.format(i, dev.GetDeviceListModel(i)))
        logging.debug(
            'Device[{0}] Serial: {1}'.format(i, dev.GetDeviceListSerial(i)))
    assert n_devices

    # Open device
    dev.OpenBySerial("")
    time.sleep(0.01)
    assert dev.IsOpen()

    osc = osc1lite.OSC1Lite(dev)
    osc.configure(bit_file='OSC1_LITE_Control.bit', ignore_hash_error=True)
    osc.reset()
    osc.init_dac()

    ch = [osc1lite.ChannelInfo(osc1lite.SquareWaveform(0, 1000, .2, .4),
                               n_pulses=i, ext_trig=i % 2)
          for i in range(12)]
    for idx, data in enumerate(ch):
        osc.set_channel(idx, data)

    osc.enable_dac_output()
    for idx, data in enumerate(ch):
        if data.ext_trig == 0:
            osc.trigger_channel(idx)
    while True:
        time.sleep(1.5)
        for idx, data in enumerate(ch):
            if data.ext_trig == 0:
                osc.trigger_channel(idx)


if __name__ == '__main__':
    main()
