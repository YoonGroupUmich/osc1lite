#! /usr/bin/env python35

import ok
import osc1lite
import time

import os
import logging

logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))


def SetControlReg(dev):
    assert dev.IsOpen()
    print('Setting Control Register')
    dev.SetWireInValue(0x00, 0, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x01, 5, 0xffff)
    dev.UpdateWireIns()
    time.sleep(0.1)
    dev.SetWireInValue(0x01, 3, 0xffff)
    dev.UpdateWireIns()
    time.sleep(0.1)
    dev.SetWireInValue(0x01, 0, 0xffff)
    dev.UpdateWireIns()


def main():
    dev = ok.okCFrontPanel()

    # Enumerate devices
    deviceCount = dev.GetDeviceCount()
    for i in range(deviceCount):
        logging.debug(
            'Device[{0}] Model: {1}'.format(i, dev.GetDeviceListModel(i)))
        logging.debug(
            'Device[{0}] Serial: {1}'.format(i, dev.GetDeviceListSerial(i)))
    assert deviceCount

    # Open device
    dev.OpenBySerial("")
    time.sleep(0.01)
    assert dev.IsOpen()

    osc = osc1lite.OSC1Lite(dev)
    osc.configure(bit_file='OSC1_LITE_Control_bak.bit', ignore_hash_error=True)
    osc.reset()
    osc.init_dac()

    ch = [osc1lite.ChannelInfo(0, 1000, .01, .02) for i in range(1, 13)]
    for idx, data in enumerate(ch):
        osc.set_channel(idx, data)

    osc.enable_dac_output()


if __name__ == '__main__':
    main()
