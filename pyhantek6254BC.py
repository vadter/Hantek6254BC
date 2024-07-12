import usb.core
import usb.util
import time
import struct
import numpy as np
import pprint

#%% Class

class Hantek:
    
    def __init__(self):
        
        dev = usb.core.find(idVendor = 0x04b5,
                            idProduct = 0x6cde)

        if dev is None:
            
            raise ValueError('Device not found')
        
        else:
            
            print('Device Hantek 6254BC is connected')

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        dev.set_configuration()
        
        # get an endpoint instance
        cfg = dev.get_active_configuration()
        
        intf = cfg[(0,0)]
        
        dev.set_interface_altsetting(interface = 0, alternate_setting = 0)
        
        self.ep2 = usb.util.find_descriptor(
            intf,
            custom_match = \
            lambda e: \
                e.bEndpointAddress == 0x02)
        
        self.ep6 = usb.util.find_descriptor(
            intf,
            custom_match = \
            lambda e: \
                e.bEndpointAddress == 0x86)
        
        assert self.ep2 is not None
        assert self.ep6 is not None

        self.dev = dev

        # Длина буфера данных каждого канала в АЦП
        self.buf_len = 16 * 1024 # 8 * 1024, 4 * 1024
        self.buf_lens = [4 * 1024, 8 * 1024, 16 * 1024]
        
        # Настройки триггера
        self.trig_source = 0 # 0 - Ch1, 1 - Ch2, ...
        self.h_trig_level = 50 # позиция горизонтального триггера, 0 - центр буфера, 50 - начало буфера
        self.v_trig_level = 127 # позиция вертикального триггера, 0 - 255 ?
        self.trig_slope = 0 # наклон 0 - RISE, 1 - FALL
        self.trig_sweep_mode = 'NORMAL' # 'AUTO', 'SINGLE'
        self.trig_sweep_modes = ['NORMAL', 'AUTO', 'SINGLE']
        
        # VDiv, вольт на деление для каждого канала
        self.dictVDiv_N = {0: 0.002, 1: 0.005, 2: 0.01, 3: 0.02, 4: 0.05,
                           5: 0.1, 6: 0.2, 7: 0.5, 8: 1, 9: 2, 10: 5,
                           11: 10}
        self.dictN_VDiv = dict(map(reversed, self.dictVDiv_N.items()))

        self.ChVDiv = [1, 1, 1, 1]

        # TDiv, время на деление, Ms / s
        self.dictSR_N = {8: 250_000_000, 9: 125_000_000, 10: 50_000_000,
                         11: 25_000_000, 12: 12_500_000, 13: 5_000_000,
                         14: 2_500_000, 15: 1_250_000, 16: 500_000,
                         17: 250_000, 18: 125_000, 19: 50_000, 20: 25_000,
                         21: 12_500, 22: 5_000, 23: 2_500, 24: 1_250,
                         25: 500, 26: 250, 27: 125}
        self.dictN_SR = dict(map(reversed, self.dictSR_N.items()))
        
        # self.TDiv = 8
        self.TBase = 8
        self.samplerate = self.dictSR_N[self.TBase]

        # Время отсчетов
        self.time = np.linspace(0., self.buf_len - 1, self.buf_len) / self.samplerate

        # YT формат вывода
        self.YTFormat = 0 # 0 - NORMAL, 1 - SCAN, 2 - ROLL
        
        self.InitHard()
        self.ADCCHModGain()

        self.Configure()
    
    def Configure(self):
        
        self.SetSampleRate()
        self.SetCHAndTrigger()
        self.SetRamAndTrigerControl()
        self.SetCHsPos()
        self.SetVTriggerLevel()
        self.SetTrigerMode() # EDGE

    # USB communication
    def ctrl(self, rtype, req, data, error = None, wValue = 0):
        
        try:

            ret = self.dev.ctrl_transfer(rtype, req, wValue, 0, data)

        except usb.core.USBError as e:

            print("got", e.errno, e)

            if e.errno == error:

                return

            else:

                raise e

        return ret

    def bwrite(self, data, without_rst = False):
        
        if not without_rst:
            
            self.rst()
            
        self.ep2.write(data)
        
        time.sleep(0.001)

    def bread(self, length):
        
        timeout = 1000
        
        return self.dev.read(self.ep6.bEndpointAddress, length, timeout)

    def rst(self):
        
        self.ctrl(0x40, 179, b"\x0f\x03\x03\x03\x00\x00\x00\x00\x00\x00")
        
        self.ctrl(0xc0, 178, 10)
        
    def getrlen(self):
        
        data = self.ctrl(0xc0, 178, 10)
        
        rlen = 64
        
        if data[0] > 0:
            
            rlen = 512
            
        return rlen

    def InitHard(self):
        
        # self.ctrl(0x40, 234, [ 0x00 ] * 10, 32)
        
        self.bwrite([0x0C, 0x00])
    
        ver = self.bwrite([0x0C, 0x00])
    
        data = self.bread(self.getrlen())
        # fpgaVersion = data[1,0
        # print(data[0:10])
    
        verB = self.ctrl(0xC0, 162, 71, 0, 0x1580)
        ver = bytearray(verB)
        # print(ver)
        
        self.rst()
        
        # 49 eeprom f5f0 - driver version
        self.ctrl(0xC0, 162, 8, 0, 0x15e0)
        
        self.bwrite(b"\x08\x00\x00\x77\x47\x12\x04\x00")
    
        self.bwrite(b"\x08\x00\x00\x03\x00\x33\x04\x00")
    
        # init ADC start
        self.bwrite(b"\x08\x00\x00\x65\x00\x30\x02\x00")
    
        self.bwrite(b"\x08\x00\x00\x28\xF1\x0F\x02\x00")
    
        self.bwrite(b"\x08\x00\x00\x12\x38\x01\x02\x00")
        
    def ADCCHModGain(self):
        
        self.bwrite(b"\x08\x00\x00\x3F\x00\x55\x04\x00")
        
    def SetSampleRate(self):
        
        self.bwrite(b"\x08\x00\x00\x10\x08\x3A\x04\x00")

        self.bwrite(b"\x08\x00\x00\x04\x02\x3B\x04\x00")

        self.bwrite(b"\x08\x00\x00\x00\x00\x0F\x04\x00")

        self.bwrite(b"\x08\x00\x00\x04\x02\x31\x04\x00")
        
        self.bwrite(b"\x08\x00\x00\x00\x00\x2A\x04\x00")
        
        if (self.buf_len == 16384):
            
            bln = 1
            
        elif (self.buf_len == 8192):
            
            bln = 2
            
        elif (self.buf_len == 4096):
            
            bln = 4

        if (self.samplerate == 125):

            self.bwrite(b"\x0F\x00\x3F\x42\x0F\x00")
            
            send_list = [0x10, 0x00, 0x1C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x1e84800 // bln + 390625
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x1e84800 // bln + 31250
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 250):

            self.bwrite(b"\x0F\x00\x1F\xA1\x07\x00")
            
            send_list = [0x10, 0x00, 0x9C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0xf42400 // bln + 195312
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0xf42400 // bln + 15625
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 500):

            self.bwrite(b"\x0F\x00\x8F\xD0\x03\x00")
            
            send_list = [0x10, 0x00, 0x5C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x7a1200 // bln + 97656
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x7a1200 // bln + 7812
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 1_250):

            self.bwrite(b"\x0F\x00\x9F\x86\x00\x00")
            
            send_list = [0x10, 0x00, 0x9C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x30d400 // bln + 39062
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x30d400 // bln + 3125
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 2_500):

            self.bwrite(b"\x0F\x00\x4F\xC3\x00\x00")
            
            send_list = [0x10, 0x00, 0x5C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x61a800 // bln + 19531
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x61a800 // bln + 1562
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 5_000):

            self.bwrite(b"\x0F\x00\xA7\x61\x00\x00")
            
            send_list = [0x10, 0x00, 0xBC, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0xC3500 // bln + 9765
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0xC35000 // bln + 781
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 12_500):

            self.bwrite(b"\x0F\x00\x0F\x27\x00\x00")
            
            send_list = [0x10, 0x00, 0x5C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x4E200 // bln + 3906
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x4E200 // bln + 312
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 25_000):

            self.bwrite(b"\x0F\x00\x87\x13\x00\x00")
            
            send_list = [0x10, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x27100 // bln + 1953
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x27100 // bln + 156
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)
            
        if (self.samplerate == 50_000):

            self.bwrite(b"\x0F\x00\xC3\x09\x00\x00") 

            send_list = [0x10, 0x00, 0xAC, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x13880 // bln + 976
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x13880 // bln + 78
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 125_000):

            self.bwrite(b"\x0F\x00\xE7\x03\x00\x00")
            
            send_list = [0x10, 0x00, 0xBC, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x7D00 // bln + 390
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x7D00 // bln + 31
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)
   
        if (self.samplerate == 250_000):

            self.bwrite(b"\x0F\x00\xF3\x01\x00\x00") 
   
            send_list = [0x10, 0x00, 0x6C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x3E80 // bln + 195
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x3E80 // bln + 15
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 500_000):

            self.bwrite(b"\x0F\x00\xF9\x00\x00\x00") 

            send_list = [0x10, 0x00, 0xC4, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0xD0, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x1F40 // bln + 97
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x1F40 // bln + 7
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        if (self.samplerate == 1_250_000):

            self.bwrite(b"\x0F\x00\x63\x00\x00\x00")

            send_list = [0x10, 0x00, 0x2C, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x0C80 // bln + 39
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x0C80 // bln + 3
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        elif (self.samplerate == 2_500_000):

            self.bwrite(b"\x0F\x00\x31\x00\x00\x00")

            send_list = [0x10, 0x00, 0xA4, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x640 // bln + 19
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x640 // bln + 1
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        elif (self.samplerate == 5_000_000):

            self.bwrite(b"\x0F\x00\x18\x00\x00\x00")

            send_list = [0x10, 0x00, 0xE0, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0xC8, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x320 // bln + 9
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x320 // bln + 0
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        elif (self.samplerate == 12_500_000):
        
            self.bwrite(b"\x0F\x00\x09\x00\x00\x00")

            send_list = [0x10, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x50, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x140 // bln + 4
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x140 // bln + 0
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        elif (self.samplerate == 25_000_000):
        
            self.bwrite(b"\x0F\x00\x04\x00\x00\x00")
            
            send_list = [0x10, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x28, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0xA0 // bln + 2
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0xA0 // bln + 0
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        elif (self.samplerate == 50_000_000):

            self.bwrite(b"\x0F\x00\x01\x00\x00\x00")

            send_list = [0x10, 0x00, 0x16, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x14, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x50 // bln + 1
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x50 // bln + 0
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        elif (self.samplerate == 125_000_000):

            self.bwrite(b"\x0F\x00\x00\x00\x00\x00")

            send_list = [0x10, 0x00, 0x80, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x20 // bln + 0
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x20 // bln + 0
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

        elif (self.samplerate == 250_000_000):

            self.bwrite(b"\x0F\x00\x00\x00\x00\x00")

            send_list = [0x10, 0x00, 0x4E, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            code1 = 0x10 // bln + 0
            send_list[3] = code1 & 0x0000FF
            send_list[4] = (code1 & 0x00FF00) >> 8
            send_list[5] = (code1 & 0xFF0000) >> 16
            
            code2 = 0x10 // bln + 0
            send_list[9] = code2 & 0x0000FF
            send_list[10] = (code2 & 0x00FF00) >> 8
            send_list[11] = (code2 & 0xFF0000) >> 16

            self.bwrite(send_list)

    def SetCHAndTrigger(self):
        
        send_list = [0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00]

        sCh = ['', '', '', '']
        
        for i in range(4):
            
            if ((self.ChVDiv[i] == 0.002) or (self.ChVDiv[i] == 0.005) or
                (self.ChVDiv[i] == 0.01) or (self.ChVDiv[i] == 0.02) or
                (self.ChVDiv[i] == 0.05) or (self.ChVDiv[i] == 0.1)):
            
                send_list[i + 2] = 0x2E
                
                if (self.ChVDiv[i] == 0.002):
                    
                    sCh[i] = 'D'

                elif (self.ChVDiv[i] == 0.005):
                    
                    sCh[i] = 'A'

                elif (self.ChVDiv[i] == 0.01):
                    
                    sCh[i] = '7'

                elif (self.ChVDiv[i] == 0.02):
                    
                    sCh[i] = '5'

                elif (self.ChVDiv[i] == 0.05):
                    
                    sCh[i] = '2'

                elif (self.ChVDiv[i] == 0.1):
                    
                    sCh[i] = '0'
            
            elif ((self.ChVDiv[i] == 0.2) or (self.ChVDiv[i] == 0.5) or
                  (self.ChVDiv[i] == 1)):
                
                send_list[i + 2] = 0x36

                if (self.ChVDiv[i] == 0.2):
                    
                    sCh[i] = '5'

                elif (self.ChVDiv[i] == 0.5):
                    
                    sCh[i] = '2'

                elif (self.ChVDiv[i] == 1):
                    
                    sCh[i] = '0'

            elif ((self.ChVDiv[i] == 2) or (self.ChVDiv[i] == 5) or
                  (self.ChVDiv[i] == 10)):
                
                send_list[i + 2] = 0x56
                
                if (self.ChVDiv[i] == 2):
                    
                    sCh[i] = '5'

                elif (self.ChVDiv[i] == 5):
                    
                    sCh[i] = '2'

                elif (self.ChVDiv[i] == 10):
                    
                    sCh[i] = '0'

        self.bwrite(send_list)
        
        self.bwrite(b"\x08\x00\x06\x06\x06\x06\x01\x01")

        self.bwrite(b"\x08\x00\x00\x10\x08\x3A\x04\x00")
        
        self.bwrite(b"\x08\x00\x00\x04\x02\x3B\x04\x00")
        
        self.bwrite(b"\x08\x00\x00\x00\x00\x0F\x04\x00")
        
        self.bwrite(b"\x08\x00\x00\x04\x02\x31\x04\x00")

        send_list2 = [0x08, 0x00, 0x00, int('0x' + sCh[1] + sCh[0], 16),
                      int('0x' + sCh[3] + sCh[2], 16), 0x2A, 0x04, 0x00]
        
        self.bwrite(send_list2)
        
    def SetRamAndTrigerControl(self):
        
        send_list = [0x12, 0x00, 0x00, 0x00, 0x00, self.trig_source]
        
        if (self.samplerate < 250_000_000):
            
            # self.bwrite(b"\x12\x00\x3D\x00\x00\x00") # last 00 - Ch1, 01 - Ch2, ...
            send_list[2] = 0x3D
        
        elif (self.samplerate == 250_000_000):
            
            # self.bwrite(b"\x12\x00\x3C\x00\x01\x00")
            send_list[2] = 0x3C
            
        self.bwrite(send_list)
        
    def SetCHsPos(self):
        
        self.bwrite(b"\x00\x00\xC2\x71") # 127 - 4a71, 129 - 3b72
        
        self.bwrite(b"\x01\x00\x2C\x71") # 127 - b570, 129 - a471
        
        self.bwrite(b"\x02\x00\xAD\x72") # 127 - 3672, 129 - 2573
        
        self.bwrite(b"\x04\x00\x39\x72") # 127 - c171, 129 - b172

    def SetVTriggerLevel(self):
        
        trig_low = 28
        trig_high = 228
        
        if (self.v_trig_level < trig_low):
            
            self.v_trig_level = int(trig_low)

        elif (self.v_trig_level > trig_high):
            
            self.v_trig_level = int(trig_high)
        
        HH = self.v_trig_level + 5
        LL = self.v_trig_level - 5
        MM = self.v_trig_level
        
        send_list = [0x07, 0x00, HH, HH, LL, LL, HH, HH, LL, LL,
                                 HH, HH, LL, LL, HH, HH, LL, LL,
                                 MM, MM, MM, MM, MM, MM, MM, MM]
        
        # self.bwrite(b"\x07\x00\x84\x84\x7C\x7C\x84\x84\x7C\x7C\x84\x84\x7C\x7C\x84\x84\x7C\x7C\x80\x80\x80\x80\x80\x80\x80\x80")
        self.bwrite(send_list)

    def SetTrigerMode(self):
        
        send_list = [0x11, 0x00, 0x00, self.trig_slope, 0x00, 0x00]

        self.bwrite(send_list)

        # self.bwrite(b"\x11\x00\x00\x00\x00\x00") # RISE
        # self.bwrite(b"\x11\x00\x00\x01\x00\x00") # FALL

    def StartCollectData(self):
        
        if (self.trig_sweep_mode == 'NORMAL'):
            
            self.bwrite(b"\x03\x00\x00\x00")
            
        elif (self.trig_sweep_mode == 'AUTO'): 
            
            self.bwrite(b"\x03\x00\x01\x00")
            
        elif (self.trig_sweep_mode == 'SINGLE'): 
            
            self.bwrite(b"\x03\x00\x04\x00")
        
    def GetState(self):
        
        self.bwrite(b"\x06\x00")
            
        read0 = np.array(self.bread(512), dtype = int)
        
        time.sleep(self.buf_len / self.samplerate * 1.5 + 0.005)
        
        self.bwrite(b"\x06\x00")
        
        read1 = np.array(self.bread(512), dtype = int)
        
        return 0

    def Compute_tg(self, trig23, trig1):
        
        j6 = 0
        
        j6 = 4
        
        j3 = trig23 - 0
        
        if (j3 < 0):
            
            j3 = j3 + 65536
        
        j5 = j3 & 0x80000007
        
        if (j5 < 0):
            
            j5 = (j5 - 1 | 0xfffffff8) + 1
        
        if (j5 != 0):
            
            if (j5 < 5):
                
                j3 = j3 - (j5 & 0xffff)
            
            else:
                
                j3 = j3 + (8 - (j5 & 0xffff))

        j5 = -trig1 - 1
        
        j = j5 & 7
        
        # 4 chs
        j = (j5 & 1) - 6
        
        j6 = j3 + (j - (0 & 0xffff)) * 4
        
        if (j6 < 0):
            
            j6 = j6 + 65536;
    
        return j6
    
    def GetData(self):
        
        self.StartCollectData()
        
        gs_data = np.array(self.GetState(), dtype = float)
        
        # Get trigger data
        self.bwrite(b"\x0D\x00")
        
        tg_data = self.bread(512)
        
        trig23 = tg_data[2] + tg_data[3] * 256
        trig1 = tg_data[1]
        
        j6 = self.Compute_tg(trig23, trig1) + 29
        
        send_list = [0x0E, 0x00, j6 & 0xFF, (j6 >> 8) & 0xFF]
        
        self.bwrite(send_list)
        
        packets = 4 * self.buf_len // 512
        
        # Get data
        self.bwrite([0x05, 0x00, 0x00, packets])

        Chs = np.array(self.bread(512 * packets), dtype = float).reshape((512 * packets // 4, 4)).T
        
        Ch1 = (Chs[0] - 128.) / 255. * 10. * self.ChVDiv[0]
        Ch2 = (Chs[1] - 128.) / 255. * 10. * self.ChVDiv[1]
        Ch3 = (Chs[2] - 129.) / 255. * 10. * self.ChVDiv[2]
        Ch4 = (Chs[3] - 128.) / 255. * 10. * self.ChVDiv[3]
        
        return [ Ch1, Ch2, Ch3, Ch4]

    def GetRawData(self):
        
        self.StartCollectData()
        
        gs_data = np.array(self.GetState(), dtype = float)
        
        # Get trigger data
        self.bwrite(b"\x0D\x00")
        
        tg_data = self.bread(512)
        
        # TODO: trigger code ???
        trig23 = tg_data[2] + tg_data[3] * 256
        trig1 = tg_data[1]
        
        # j6 = self.Compute_tg(trig23, trig1)
        j6 = self.Compute_tg(trig23, trig1) + 29
        
        send_list = [0x0E, 0x00, j6 & 0xFF, (j6 >> 8) & 0xFF]
        
        # print('j6 =', hex(j6), send_list)
        
        self.bwrite(send_list)
        
        # self.bwrite(b"\x0E\x00\x00\x00")

        packets = 4 * self.buf_len // 512
        # packets = 128
        
        # Get data
        self.bwrite([0x05, 0x00, 0x00, packets])

        Chs = np.array(self.bread(512 * packets), dtype = float).reshape((512 * packets // 4, 4)).T
        
        Ch1 = Chs[0]; Ch2 = Chs[1]; Ch3 = Chs[2]; Ch4 = Chs[3]
        
        return [ Ch1, Ch2, Ch3, Ch4, gs_data, tg_data ]

    def set_buf_len(self, bl):
        
        if (bl in self.buf_lens):
        
            self.buf_len = bl
            
            print('Buffer length of each channel is set to:', self.buf_len)
            
        else:
            
            print('Available buffer lengths:', self.buf_lens)
            
    def set_samplerate(self, rate):

        if (rate in self.dictN_SR.keys()):

            self.samplerate = rate
            self.TBase = self.dictN_SR[rate]
            self.time = np.linspace(0., self.buf_len - 1, self.buf_len) / self.samplerate
            
            print('Samplerate is set to:', 
                  pprint.pformat(self.samplerate, underscore_numbers = True))
            
        else:
            
            print('Available sample rates:',
                  pprint.pformat(self.get_rates(), underscore_numbers = True))
            
            print('Current samplerate:',
                  pprint.pformat(self.samplerate, underscore_numbers = True))

    def set_trig_sweep_mode(self, tsm):

        if (tsm in self.trig_sweep_modes):

            self.trig_sweep_mode = tsm
            
            print('Trigger sweep mode is set to: ' + self.trig_sweep_mode)
            
        else:
            
            print('Available trigger sweep modes:', self.trig_sweep_modes)
            
            print('Current sweep mode: ' + self.trig_sweep_mode)

    def set_chvdiv(self, chvdiv):
        
        for i in range(len(chvdiv)):
        
            if (chvdiv[i] in self.dictN_VDiv.keys()):        
        
                self.ChVDiv[i] = chvdiv[i]
        
            else:
            
                print('Wrong value of V / DIV for Ch%d' % (i + 1))
                
                print('Available V / DIV:', list(self.dictN_VDiv.keys()))
                
                print('Current V / DIV:')
                
                break
            
        print('Channel 1:', self.ChVDiv[0], ' V / DIV')
        print('Channel 2:', self.ChVDiv[1], ' V / DIV')
        print('Channel 3:', self.ChVDiv[2], ' V / DIV')
        print('Channel 4:', self.ChVDiv[3], ' V / DIV')
        
    def set_v_trig_source(self, vts):
        
        self.trig_source = vts
        
        print('Trigger source is channel: Ch%d' % (self.trig_source + 1))
        
    def set_v_trig_level(self, vtl):
        
        self.v_trig_level = int(vtl * 255. / 10. / self.ChVDiv[self.trig_source] + 128.)
        
        if (self.v_trig_level > 228):
            
            self.v_trig_level = 228
            
        elif (self.v_trig_level < 28):
            
            self.v_trig_level = 28
        
        v_trig = (self.v_trig_level - 128.) / 255. * 10. * self.ChVDiv[self.trig_source]
        
        print('Trigger level is set to: %1.2e V' % (v_trig))

    def get_rate(self):

        return self.samplerate

    def get_time(self):
        
        return self.time

    def get_rates(self):
        
        values = [ 25000, 50000, 125000, 250000, 500000, 1250000, 2500000,
                   5000000, 12500000, 25000000, 50000000, 125000000, 250000000]
        
        return values

    def close(self):
        
        try:

            self.dev.reset()

        except usb.core.USBError as e:
    
            print(e)
        
        usb.util.dispose_resources(self.dev)
        
        print("Connection is closed")

#%% Main

if __name__ == "__main__":

    pass

#%% End