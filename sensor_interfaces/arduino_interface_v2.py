#!/usr/bin/env python3

# Serial communication libraries
import serial
from serial.serialutil import SerialException

# Logging setup - finish later
import logging
from logdecorator import log_on_start, log_on_end

# Shutdown behavior
import atexit


class SerialObject():
    """My attempt at a semi generalized serial communications object"""
    def __init__(self, close_port_on_exit=True):
        self.port = None
        self.baud_rate = None
        self.ser = None 
        
        self.outbound_structure = {
            "msg_size": 2, # bytes
            "start_character": None,
            "delimiter": None,
            "end_character": None
            }
        
        self.inbound_structure = {
            "msg_size": 1, # bytes
            "start_character": None,
            "delimiter": None,
            "end_character": None
        }

        # Program exit behavior to close port
        if close_port_on_exit:
            atexit.register(self.disconnect)

    
    def connect(self, port, baud_rate, timeout=1):
        """Open the serial connection with the specified port and baudrate"""
        self.port = port
        self.baud_rate = baud_rate
        
        try:
            self.ser = serial.Serial(port, baud_rate, timeout=timeout)
            print("Successfully connected")
        except SerialException:    
            raise Warning(f"Could not connect to serial port {port} with baud rate {baud_rate}")
            
    def disconnect(self):
        """Close the serial connection if it's open"""
        if self.ser is not None:
            self.ser.close()
            self.ser = None

    def send_command(self, cmd):
        """Build message based on outbound message structure"""
        pass

    def configure_msg_structure(self, msg_dir, **kwargs):
        config_dict = self.inbound_structure if (msg_dir == 'inbound') else self.outbound_structure
        # Loop through kwaargs, if any match dict entries, update values
        for key, value in kwargs.items():
            if key in config_dict:
                config_dict[key] = value
            else:
                raise Warning("Config structure key provided in invalid")


    def load_msg_structure(self, msg_dir):
        """Load message structure from config yaml file"""
        pass


if __name__ == "__main__":
    s = SerialObject(port="COM3", baud_rate=250000)
    print(s.inbound_structure)
    s.configure_msg_structure('inbound', msg_size=3)
    print(s.inbound_structure)


    


