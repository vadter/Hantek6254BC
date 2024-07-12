# -*- coding: utf-8 -*-
"""
Created on %(date)s

@author: %(username)s
"""

import numpy as np, pylab as pl, sys, os
import pyhantek6254BC
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
import pyqtgraph as pg
import multiprocessing as mp
import time

#%% Funcs

def updateGraph(qu1, chvd):
    
    pg_layout = pg.GraphicsLayoutWidget()
    
    pg_layout.show()
    
    p1 = pg_layout.addPlot(x = [], y = [], row = 0, col = 0, title = "Ch 1")
    p1.setYRange(-chvd[0] * 5, chvd[0] * 5, padding = 0)
    curve1 = p1.plot([], [], pen = pg.mkPen('r', width = 1))
    
    p2 = pg_layout.addPlot(x = [], y = [], row = 0, col = 1, title = "Ch 2")
    p2.setYRange(-chvd[1] * 5, chvd[1] * 5, padding = 0)
    curve2 = p2.plot([], [], pen = pg.mkPen('g', width = 1))

    p3 = pg_layout.addPlot(x = [], y = [], row = 1, col = 0, title = "Ch 3")
    p3.setYRange(-chvd[2] * 5, chvd[2] * 5, padding = 0)
    curve3 = p3.plot([], [], pen = pg.mkPen('b', width = 1))
    
    p4 = pg_layout.addPlot(x = [], y = [], row = 1, col = 1, title = "Ch 4")
    p4.setYRange(-chvd[3] * 5, chvd[3] * 5, padding = 0)
    curve4 = p4.plot([], [], pen = pg.mkPen('c', width = 1))
    
    while True:
        
        Dat = qu1.get()
        
        curve1.setData(Dat[0], Dat[1])
        curve2.setData(Dat[0], Dat[2])
        curve3.setData(Dat[0], Dat[3])
        curve4.setData(Dat[0], Dat[4])
        
        QtWidgets.QApplication.processEvents()
        
        time.sleep(0.01)

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

ChVDIV = [1, 1, 0.5, 0.2] # volts

#%% Apply settings

h0 = pyhantek6254BC.Hantek()

h0.set_buf_len(16384 // 1) # buffer len 16k, 8k, 4k

h0.set_samplerate(SR) # samples / sec

h0.set_chvdiv(ChVDIV) #

h0.set_v_trig_source(0) # 0 - ch1, 1 - ch2, ...

h0.set_v_trig_level(0.) # volts

h0.set_trig_sweep_mode('NORMAL') # 'AUTO', 'SINGLE'

h0.Configure()

# t = h0.get_time() * SR
t = h0.get_time()

#%% Graph process

que1 = mp.Queue()

graph_process = mp.Process(target = updateGraph, args = (que1, ChVDIV))

graph_process.start()

#%%% Calculations

while True:
    
    Ch1, Ch2, Ch3, Ch4 = h0.GetData()

    que1.put((t, Ch1, Ch2, Ch3, Ch4))
    
    # Ch1, Ch2, Ch3, Ch4, a, b = h0.GetRawData()
    
    # que1.put((t, (Ch1 - 128.) / 255. * 10. * ChVDIV[0],
    #              (Ch2 - 128.) / 255. * 10. * ChVDIV[1],
    #              (Ch3 - 128.) / 255. * 10. * ChVDIV[2],
    #              (Ch4 - 128.) / 255. * 10. * ChVDIV[3]))
    
    time.sleep(0.1)

graph_process.join()

h0.close()

#%%%

if __name__ == "__main__":
    
    pass

#%%% End