import time
from vacuum_instruments import GraphixController, AdaloggerDAQ, gp475_voltage_to_pressure, pdr_d1_voltage_to_pressure

GRAPHIX_PORT='COM7'; DAQ_PORT='COM8'; PDR_FULL_SCALE_TORR=100.0

with GraphixController(GRAPHIX_PORT) as g:
    daq=AdaloggerDAQ(DAQ_PORT)
    try:
        while True:
            gx=g.read_pressure(1)
            s=daq.read_once()
            # Firmware reports original instrument-side voltage after divider correction.
            gp=gp475_voltage_to_pressure(s['volts'][0], 'Torr', '0-7V')
            pdr=pdr_d1_voltage_to_pressure(s['volts'][1], PDR_FULL_SCALE_TORR)
            print(f'GRAPHIX={gx.value:g} {gx.unit} | GP475={gp.pressure:g} Torr | PDR-D-1={pdr.pressure:g} Torr')
            time.sleep(0.25)
    finally:
        daq.close()
