# -*- coding: utf-8 -*-
"""
Created on %(date)s

@author: %(username)s
"""

import numpy as np, pylab as pl, sys, os
import pyhantek6254BC

#%%% Hantek setup

h0 = pyhantek6254BC.Hantek()

#%% Settings

# SR = 25_000
# SR = 250_000
# SR = 500_000
# SR = 1_250_000
SR = 2_500_000
# SR = 5_000_000
# SR = 12_500_000
# SR = 25_000_000
# SR = 50_000_000
# SR = 250_000_000

ChVDIV = [1, 1, 0.005, 0.002]

#%% Apply settings

h0.set_buf_len(16384 // 1)

h0.set_samplerate(SR)

h0.set_chvdiv(ChVDIV)

h0.set_v_trig_source(0)

h0.set_v_trig_level(0.)

h0.set_trig_sweep_mode('NORMAL')

h0.Configure()

#%%% Calculations

t = 1000. * h0.get_time() # ms

Ch1, Ch2, Ch3, Ch4 = h0.GetData()

#%%

h0.close()

#%%% Graphics

pl.figure()

# Ch1

pl.subplot(221)

pl.plot(t, Ch1, 'r', label = 'Ch1')

pl.ylim([-5. * ChVDIV[0], 5. * ChVDIV[0]])

pl.legend()

pl.grid(True)

pl.xlabel('Time, ms')
pl.ylabel('U, Volts')

# Ch2

pl.subplot(222)

pl.plot(t, Ch2, 'g', label = 'Ch2')

pl.ylim([-5. * ChVDIV[1], 5. * ChVDIV[1]])

pl.legend()

pl.grid(True)

pl.xlabel('Time, ms')
pl.ylabel('U, Volts')

# Ch3

pl.subplot(223)

pl.plot(t, Ch3, 'b', label = 'Ch3')

pl.ylim([-5. * ChVDIV[2], 5. * ChVDIV[2]])

pl.legend()

pl.grid(True)

pl.xlabel('Time, ms')
pl.ylabel('U, Volts')

# Ch4

pl.subplot(224)

pl.plot(t, Ch4, 'c', label = 'Ch4')

pl.ylim([-5. * ChVDIV[3], 5. * ChVDIV[3]])

pl.legend()

pl.grid(True)

pl.xlabel('Time, ms')
pl.ylabel('U, Volts')

pl.show()

#%%%

if __name__ == "__main__":
    
    pass

#%%% End