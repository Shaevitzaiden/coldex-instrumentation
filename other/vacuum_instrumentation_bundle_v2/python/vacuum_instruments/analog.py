from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class AnalogPressure:
    source:str; voltage:float; pressure:float|None; unit:str; valid:bool; status:str

def gp475_voltage_to_pressure(v:float, unit:str='Torr', mode:str='0-7V')->AnalogPressure:
    if v >= 9.5:
        return AnalogPressure('gp475',v,None,unit,False,'gauge_unplugged_or_fault')
    if mode=='0-7V': exponent={'Torr':-4,'mbar':-4,'Pa':-2}[unit]
    elif mode=='1-8V': exponent={'Torr':-5,'mbar':-5,'Pa':-3}[unit]
    else: raise ValueError('Only logarithmic 0-7V and 1-8V modes are implemented')
    return AnalogPressure('gp475',v,10.0**(v+exponent),unit,True,'ok')

def pdr_d1_voltage_to_pressure(v:float, full_scale:float, unit:str='Torr')->AnalogPressure:
    valid=-0.1 <= v <= 10.5
    p=(v/10.0)*full_scale if valid else None
    return AnalogPressure('pdr_d1',v,p,unit,valid,'ok' if valid else 'voltage_out_of_range')
