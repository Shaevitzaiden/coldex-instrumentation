from __future__ import annotations
import json, serial, time

class AdaloggerDAQ:
    """Host driver for the newline-delimited JSON protocol in the included Arduino firmware."""
    def __init__(self, port:str, baudrate:int=115200, timeout:float=1.0):
        self.ser=serial.Serial(port,baudrate=baudrate,timeout=timeout,write_timeout=timeout)
        time.sleep(0.5); self.ser.reset_input_buffer()
    def close(self):
        if self.ser.is_open:self.ser.close()
    def command(self, text:str):
        self.ser.write((text.strip()+'\n').encode()); self.ser.flush()
        deadline=time.monotonic()+self.ser.timeout
        while time.monotonic()<deadline:
            line=self.ser.readline()
            if not line: continue
            obj=json.loads(line)
            if obj.get('type') in ('ack','info','sample','error'): return obj
        raise TimeoutError(text)
    def read_once(self): return self.command('READ')
    def set_rate(self,hz:float): return self.command(f'RATE {hz}')
    def start(self): return self.command('START')
    def stop(self): return self.command('STOP')
    def iter_samples(self):
        while True:
            line=self.ser.readline()
            if not line: continue
            obj=json.loads(line)
            if obj.get('type')=='sample': yield obj
