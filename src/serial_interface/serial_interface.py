#!/usr/bin/env python3

# Serial communication libraries
import serial
from serial.serialutil import SerialException
from serial.tools import list_ports

# Logging setup - finish later
import logging
from logdecorator import log_on_start, log_on_end

# time
import time

# Shutdown behavior
import atexit


class SerialObject():
    """My attempt at a semi generalized serial communications interface"""
    def __init__(self, close_port_on_exit=True):
        self.port = None
        self.baud_rate = None
        self.ser = None 
        
        self.outbound_structure = {
            "msg_size": 2, # bytes
            "start_character": None,
            "delimiter": None,
            "end_character": None,
            "encoding": "UTF-8"
            }
        
        self.inbound_structure = {
            "msg_size": 1, # bytes
            "start_character": None,
            "delimiter": None,
            "end_character": None,
            "encoding": "UTF-8"
        }

        # Dictionary to store command mappings
        self.commands = {}

        # Program exit behavior to close port
        if close_port_on_exit:
            atexit.register(self.disconnect)
 
    def connect(self, port, baud_rate, timeout=1, sleep_time=0.01):
        """Open the serial connection with the specified port and baudrate"""
        self.port = port
        self.baud_rate = baud_rate
        
        try:
            self.ser = serial.Serial(port, baud_rate, timeout=timeout)
            print("Successfully connected")
            time.sleep(sleep_time)
        except SerialException:    
            print(f"Could not connect to serial port {port} at baud rate {baud_rate}")
            try_find_port = input("Would you like to see a list of available serial ports? (y/n): ")
            if try_find_port.lower() == 'y':
                selected_port = select_serial_port()
                if selected_port:
                    self.connect(selected_port, baud_rate, timeout=timeout, sleep_time=sleep_time)
            
    def disconnect(self):
        """Close the serial connection if it's open"""
        if self.ser is not None:
            self.ser.close()
            self.ser = None
            print("Disconnected")

    def write(self, cmd):
        """Build message based on outbound message structure"""
        msg_str = self.build_msg(cmd)
        num_bytes_written = self.ser.write(msg_str)
        return num_bytes_written

    def read(self, num_bytes="default", timeout=1):
        num_bytes = self.inbound_structure['msg_size'] if num_bytes == "default" else num_bytes
        start_time = time.time()
        while self.ser.in_waiting < num_bytes:
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout while waiting for data")

            time.sleep(0.01)
        # Read in message and decode using specified encoding for inbound msgs
        data = self.ser.readline(num_bytes)
        data = data.decode(self.inbound_structure['encoding']).strip("\r\n")

        # Parse message based on start and end characters and delimiters
        print(data)

    def build_msg(self, msg):
        """Use outbound message structure to package message"""
        packaged_msg = ""
        
        # Add start character if it is not None
        if self.outbound_structure["start_character"] is not None:
            packaged_msg +=  self.outbound_structure["start_character"]
        
        # Add main body of msg
        packaged_msg += str(msg)

        # Add end character if it is not None
        if self.outbound_structure["end_character"] is not None:
            packaged_msg += self.outbound_structure["end_character"]

        # Encode and return packaged message 
        return packaged_msg.encode(self.outbound_structure['encoding'])

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


def get_serial_port_details():
    """Return detailed metadata for all currently available serial ports."""
    ports = []
    for port in list_ports.comports():
        ports.append({
            "device": port.device,
            "name": port.name,
            "description": port.description,
            "hwid": port.hwid,
            "manufacturer": port.manufacturer,
            "product": port.product,
            "serial_number": port.serial_number,
            "location": port.location,
            "interface": port.interface,
            "vid": f"0x{port.vid:04X}" if port.vid is not None else None,
            "pid": f"0x{port.pid:04X}" if port.pid is not None else None,
        })
    return ports

def serial_ports():
    """Return a simple list of active serial port device names (for compatibility)."""
    return [port["device"] for port in get_serial_port_details()]

def select_serial_port():
    """Prompt the user to select a serial port from the available options."""
    ports = get_serial_port_details()
    if not ports:
        print("No active serial ports found.")
        return None

    print("Available serial ports:")
    for idx, port in enumerate(ports, start=1):
        print(f"[{idx}] {port['device']} - {port.get('description') or 'No description'}")

    while True:
        try:
            selection = int(input("Select a port by number (or 0 to cancel): "))
            if selection == 0:
                return None
            elif 1 <= selection <= len(ports):
                return ports[selection - 1]["device"]
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def display_serial_ports_data():
    port_details = get_serial_port_details()
    if not port_details:
        print("No active serial ports found.")
    else:
        for idx, port in enumerate(port_details, start=1):
            print(f"[{idx}] {port['device']} - {port.get('description') or 'No description'}")

            if port.get("manufacturer"):
                print(f"    Manufacturer: {port['manufacturer']}")
            if port.get("product"):
                print(f"    Product: {port['product']}")
            if port.get("serial_number"):
                print(f"    Serial Number: {port['serial_number']}")
            if port.get("vid") and port.get("pid"):
                print(f"    VID:PID: {port['vid']}:{port['pid']}")
            if port.get("location"):
                print(f"    Location: {port['location']}")
            if port.get("hwid"):
                print(f"    HWID: {port['hwid']}")


if __name__ == "__main__":
    s = SerialObject()
    s.configure_msg_structure('outbound', msg_size=3, start_character='<', end_character='>')
    
    # try to connect to an arduino
    test_msg = "1, 1"
    s.connect("COM3", 250000, sleep_time=0.5)


    # Send test message
    s.write("1,1")
    # time.sleep(0.5)

    # Try to read response
    s.read(timeout=2, num_bytes=3)



    


