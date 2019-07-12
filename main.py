#! /usr/bin/env python35

import ok
import time

def SetAllZero(dev: ok.okCFrontPanel):
    dev.SetWireInValue(0x00, 0, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x01, 1, 0xffff)
    dev.UpdateWireIns()
    for channel in range(12):
        dev.SetWireInValue(0x03 + channel, 0, 0xffff)
        dev.UpdateWireIns()
        
def SetControlReg(dev):
    assert dev.IsOpen()
    print('Setting Control Register')
    dev.SetWireInValue(0x00, 0, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x01, 5, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x01, 3, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x01, 0, 0xffff)
    dev.UpdateWireIns()
    

def SysReset(dev: ok.okCFrontPanel):
    assert dev.IsOpen()
    
    print('Reseting system to default state')

    dev.SetWireInValue(0x01, 4, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x00, 1, 0xffff)
    dev.UpdateWireIns()

    dev.SetWireInValue(0x01, 0, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x02, 0, 0xffff)
    dev.UpdateWireIns()
    
    SetAllZero(dev)

    dev.SetWireInValue(0x00, 0, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x01, 0, 0xffff)
    dev.UpdateWireIns()
    dev.SetWireInValue(0x02, 0, 0xffff)
    dev.UpdateWireIns()


def WriteToWireIn(dev, channel, val, mask=0xffff, update=True):
    dev.SetWireInValue(channel, val, mask)
    if update:
        dev.UpdateWireIns()
    print('WriteToWireIn', channel, val)
    
    
class ChannelInfo():
    def __init__(self, mode=0, amp=0, pw=0, period=10):
        """
        mode controls the rising/falling edge width
        amp controls the wave amplitude
        """
        self.mode = mode
        self.amp = amp  # uA, range(0, 24000)
        #self.period = 10.23984375 # sec, cannot modify
        self.period = period
        self.pulse_width = pw # sec
    
    
def UpdateWaveform(dev, ch):
    """
    for i in range(12):
        if ch[i].mode not in range(5):
            print('Unknown mode {} in Channel #{}'.format(ch[i].mode, i))
    for i in range(0, 12, 4):
        WriteToWireIn(dev, 0x1e + i, ch[i].mode | (ch[i+1].mode << 4) | (ch[i+2].mode << 8) | (ch[i+3].mode << 12), update=False)
    for i in range(12):
        # Final amp = 24000uA / 65536 * ctlword
        # ctlword = mult * wirein
        
        # mode 0 1  2  3  4
        # mult 1 3 13 25 50
        wirein = ch[i].amp / 24000 * 65536 / (1,3,13,25,50)[ch[i].mode]
        WriteToWireIn(dev, 0x03+i, round(wirein), update=False)  # amplitude
        #                                                             PLL freq
        WriteToWireIn(dev, (0x0f+i) if i < 6 else ((0x18+i-6) if i != 11 else 0x20) ,round(ch[i].pulse_width / (2**11) * 13107200), update=False)  # pulse_width
        #                                                             PLL freq
        print(round(ch[i].period / (2**11) * 13107200))
        #WriteToWireIn(dev, (0x1f+i) if (i<2) else (0x21+i) ,round(ch[i].period / (2**11) * 13107200) - 1, update=False)  # period
        #WriteToWireIn(dev, 0x1f if i == 0 else 0x21+i , 0xfffe, update=False)  # period
    """
    for i in range(12):
        WriteToWireIn(dev, 0x03, round(ch[i].pulse_width / (2**11) * 13107200), update=False)
        WriteToWireIn(dev, 0x04, round(ch[i].period / (2**11) * 13107200), update=False)
        wirein = ch[i].amp / 24000 * 65536 / (1,3,13,25,50)[ch[i].mode]
        WriteToWireIn(dev, 0x05, round(wirein), update=False)
        WriteToWireIn(dev, 0x06, ch[i].mode | (i << 4), update=True)
        
        # Send trigger
        WriteToWireIn(dev, 0x06, 0x0100, mask=0x0100, update=True)\
        
    dev.UpdateWireIns()
        

def SetAll(dev):
    WriteToWireIn(dev, 0, 0)
    WriteToWireIn(dev, 1, 1)
    
    ch = [ChannelInfo(0, 1000, 1, 2) for i in range(1,13)]
    UpdateWaveform(dev, ch)

def Configure(dev):
    ret = dev.ConfigureFPGA("OSC1_LITE_Control.bit")
    if ret == dev.NoError:
        print('ConfigureFPGA() = NoError')
    elif ret == dev.DeviceNotOpen:
        print('ConfigureFPGA() = DeviceNotOpen')
    elif ret == dev.FileError:
        print('ConfigureFPGA() = FileError')
    elif ret == dev.InvalidBitstream:
        print('ConfigureFPGA() = InvalidBitstream')
    elif ret == dev.DoneNotHigh:
        print('ConfigureFPGA() = DoneNotHigh')
    elif ret == dev.TransferError:
        print('ConfigureFPGA() = TransferError')
    elif ret == dev.CommunicationError:
        print('ConfigureFPGA() = CommunicationError')
    elif ret == dev.UnsupportedFeature:
        print('ConfigureFPGA() = UnsupportedFeature')
    else:
        print('ConfigureFPGA() =', ret)
    assert ret == dev.NoError
    
    pll = ok.PLL22150()
    pll.SetReference(48.0, False)
    pll.SetVCOParameters(512, 125)
    pll.SetDiv1(pll.DivSrc_VCO, 15)
    pll.SetOutputSource(0, pll.ClkSrc_Div1ByN)
    pll.SetOutputEnable(0, True)
    pll.SetDiv2(pll.DivSrc_VCO, 8)
    pll.SetOutputSource(1, pll.ClkSrc_Div2ByN)
    pll.SetOutputEnable(1, True)
    dev.SetPLL22150Configuration(pll)
    for i in range(2):
        print('PLL output #', i, 'freq =', pll.GetOutputFrequency(i), 'MHz')
        # We are using PLL 0 here
    

def main():
    dev = ok.okCFrontPanel()
 
    # Enumerate devices
    deviceCount = dev.GetDeviceCount()
    for i in range(deviceCount):
            print('Device[{0}] Model: {1}'.format(i, dev.GetDeviceListModel(i)))
            print('Device[{0}] Serial: {1}'.format(i, dev.GetDeviceListSerial(i)))
    assert deviceCount
    # Open device
    dev.OpenBySerial("")
    time.sleep(0.01)
    assert dev.IsOpen()
    Configure(dev)
    time.sleep(0.01)
    SysReset(dev)
    time.sleep(0.01)
    SetControlReg(dev)
    time.sleep(0.01)
    dev.SetWireInValue(0x17, 0, 0xffff)
    time.sleep(0.01)
    dev.UpdateWireIns()
    time.sleep(0.01)
    SetAll(dev)
    while False:
        print('Hello, world')
        for i in range(2**8):
            print('Hello, world')
            time.sleep(0.3)
            WriteToWireIn(dev, 0x0f, i)
    
if __name__ == '__main__':
    main()
