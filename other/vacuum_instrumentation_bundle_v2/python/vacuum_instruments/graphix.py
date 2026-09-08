from __future__ import annotations
from dataclasses import dataclass
import re
import serial

class GraphixError(RuntimeError): pass
class GraphixNack(GraphixError): pass

@dataclass(frozen=True)
class GraphixPressure:
    channel:int; value:float; unit:str; raw:str

class GraphixController:
    SI=0x0F; SO=0x0E; ACK=0x06; NACK=0x15; EOT=0x04
    def __init__(self, port:str, baudrate:int=38400, timeout:float=0.5):
        self.ser=serial.Serial(port, baudrate=baudrate, bytesize=8, parity='N', stopbits=1,
                               timeout=timeout, write_timeout=timeout, xonxoff=False, rtscts=False, dsrdtr=False)
        self.ser.reset_input_buffer(); self.ser.reset_output_buffer()
    def close(self):
        if self.ser and self.ser.is_open: self.ser.close()
    def __enter__(self): return self
    def __exit__(self,*_): self.close()
    @staticmethod
    def checksum(data:bytes)->int:
        c=255-(sum(data)%256)
        return c+32 if c<32 else c
    @classmethod
    def make_read_frame(cls, group:int, parameter:int)->bytes:
        body=bytes([cls.SI])+f"{group};{parameter}".encode('ascii')
        return body+bytes([cls.checksum(body), cls.EOT])
    def _read_frame(self)->bytes:
        data=self.ser.read_until(bytes([self.EOT]))
        if not data: raise TimeoutError('GRAPHIX did not respond')
        if data[-1] != self.EOT: raise GraphixError(f'Incomplete response: {data!r}')
        if len(data)<3: raise GraphixError(f'Response too short: {data!r}')
        expected=self.checksum(data[:-2]); got=data[-2]
        if expected!=got: raise GraphixError(f'CRC mismatch expected={expected} got={got}: {data!r}')
        return data
    def read_parameter(self, group:int, parameter:int)->str:
        self.ser.reset_input_buffer(); self.ser.write(self.make_read_frame(group,parameter)); self.ser.flush()
        r=self._read_frame(); kind=r[0]; text=r[1:-2].decode('ascii','replace').strip()
        if kind==self.NACK: raise GraphixNack(text)
        if kind!=self.ACK: raise GraphixError(f'Unexpected response byte 0x{kind:02X}: {r!r}')
        return text
    def identify(self)->str: return self.read_parameter(5,1)
    def read_pressure(self, channel:int=1)->GraphixPressure:
        if channel not in (1,2,3): raise ValueError('channel must be 1, 2, or 3')
        raw=self.read_parameter(channel,29)
        m=re.match(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)\s*(.*)$', raw)
        if not m: raise GraphixError(f'Cannot parse pressure response {raw!r}')
        return GraphixPressure(channel,float(m.group(1)),m.group(2).strip(),raw)
