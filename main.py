#! /usr/bin/env python3.5

"""
This is a sample script that programmatically controls OSC1Lite using the API
"""

import ok        # The OpalKelly SDK, you may need to manually copy it to current folder
import osc1lite  # The OSC1Lite python interface
import time

import os

# Enable debug logging
import logging
logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))


def main():
    # Initialize OpalKelly
    dev = ok.okCFrontPanel()

    # Enumerate devices
    n_devices = dev.GetDeviceCount()
    for i in range(n_devices):
        logging.debug(
            'Device[{0}] Model: {1}'.format(i, dev.GetDeviceListModel(i)))
        logging.debug(
            'Device[{0}] Serial: {1}'.format(i, dev.GetDeviceListSerial(i)))
    assert n_devices, 'No connected device. Check the connection and make sure no other program is occupying the device.'

    # Open the default device
    #serial = '1740000JJK'
    serial = ''
    dev.OpenBySerial(serial)
    assert dev.IsOpen(), 'Device open failed. Is the FPGA dead?'

    # Load the calibration data (you need to fill in the serial of your board)
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
        # just use dummy data
        calib = [None for _ in range(12)]

    # Initialize OSC1Lite board
    osc = osc1lite.OSC1Lite(dev, calib=calib)
    osc.configure(bit_file='OSC1_LITE_Control.bit', ignore_hash_error=False)
    osc.reset()
    osc.init_dac()
    osc.enable_dac_output()

    # Enable all 12 channels
    osc.set_enable(range(12), True)

    # Set all channels to continuous mode
    osc.set_trigger_mode(range(12), True)

    # Configure the waveform parameters of each channel
    for ch in range(12):
        osc.set_channel(ch, osc1lite.ChannelInfo(
            osc1lite.SquareWaveform(0, 50, .1, .2)))

    # Send PC trigger to all channels
    osc.trigger_channel(range(12))

    input('Now LED on all channels should be flashing. Press enter to exit')

    # Disable channels
    osc.set_enable(range(12), False)

    # Disconnect the OpalKelly device
    dev.Close()


if __name__ == '__main__':
    print(__doc__)
    main()
