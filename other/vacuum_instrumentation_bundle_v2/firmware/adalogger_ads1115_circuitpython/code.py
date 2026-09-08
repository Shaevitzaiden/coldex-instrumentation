# Simple streaming-only CircuitPython example for Feather RP2040 Adalogger + ADS1115.
# Copy adafruit_ads1x15 from the matching CircuitPython library bundle into CIRCUITPY/lib.
import time, board
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

i2c=board.STEMMA_I2C(); ads=ADS.ADS1115(i2c); ads.gain=2
GAIN=5.99
channels=[AnalogIn(ads,x) for x in (ADS.P0,ADS.P1,ADS.P2,ADS.P3)]
while True:
    vals=[c.voltage*GAIN for c in channels]
    print('{"type":"sample","t_s":%.6f,"volts":[%.6f,%.6f,%.6f,%.6f]}' % ((time.monotonic(),)+tuple(vals)))
    time.sleep(0.1)
