To get it work you need to install python 3, the pyusb, matplotlib and pyqtgraph libraries for scripts with the appropriate names (I use it under conda environment conda-forge).

Ubuntu: copy 60-hantek-6254BC.rules to /lib/udev/rules.d/ and reboot

Implemented functions based on the Qt example program for windows of the official software:

1. A variant of the 4-channel operation mode has been implemented (mode 1 and 2 channels are not implemented).
2. The length of the data buffer is set for each channel 4k, 8k, 16k.
3. Sample rate is set from 250 Msamples / s to 125 samples / s.
4. Channels are placed in the middle of the range (128 / 255 bit).
5. Sweep modes for the trigger are 'AUTO', 'NORMAL', 'SINGLE'.

Script of pyhantek6254BC.py are based on https://github.com/danielkucera/pyhantek
