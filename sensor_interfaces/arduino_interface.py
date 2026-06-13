# Communicates with Arduino

import numpy as np
import serial
import yaml
from serial import SerialException

import logging
from logdecorator import log_on_start , log_on_end , log_on_error
# Set up a logger for this module
logger = logging.getLogger(__name__)
# Set the lowest-severity log message the logger will handle (debug = lowest, critical = highest)
logger.setLevel(logging.DEBUG)
# Create a handler that saves logs to the log folder named as the current date
# fh = logging.FileHandler(f"logs\\{time.strftime('%Y-%m-%d', time.localtime())}.log")
fh = logging.StreamHandler()
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)
# Create a formatter to specify our log format
formatter = logging.Formatter("%(levelname)s: %(asctime)s - %(name)s:  %(message)s", datefmt="%H:%M:%S")
fh.setFormatter(formatter)

class ArduinoInterface():

    def __init__(self, serial_port, baud_rate, custom_logger=None):
        
        if custom_logger is not None:
            self.logger = custom_logger
        else:
            self.logger = logger
        
        self.initialize_pyserial(serial_port, baud_rate)

        # Different serial command characters
        self.start_character = "<"
        self.end_character = ">"
        # self.one_thing = "1"
        # self.another_thing = "2"

    def initialize_pyserial(self, port, baud):
        """
        Method to open the serial port at the specified baud. Also specifies a timeout to prevent infinite blocking.
        These values (except for timeout) MUST match the instrument. Typing "mode" in the Windows Command Prompt 
        gives information about serial ports, but sometimes the baud is wrong, so beware. Check sensor documentation.
        Inputs - port (str, serial port), baud (int, baud rate)
        """
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            logger.info(f"Connected to serial port {port} with baud {baud}")
            self.ser.flush()
            self.ser.reset_input_buffer()
            self.ser.readline()
            self.ser.readline()
        except SerialException:
            logger.warning(f"Could not connect to serial port {port}")

    @log_on_start(logging.INFO, "Initializing Arduino", logger=logger)
    def initialize_arduino(self, timeout=10):
        """
        Queries the Arduino sensors until we get a valid output. If we can't get a valid reading after a set of attempts,
        report that initialization failed.
        
        The initialization methods return one of three values: 
        1 (real hardware, succeeded), 2 (simulated hardware), 3 (failed to initialize / error)
        """
        try:
            for i in range(timeout):
                logger.info(f"Initialization attempt {i+1}/{timeout}")
                timestamp, data_out = self.query()
            
                # Validity check
                if data_out:
                    logger.info("Arduino initialized")
                    return 1

        except Exception as e:
            logger.info(f"Exception in Arduino initialization: {e}")

        logger.info(f"Arduino initialization failed after {timeout} attempts")
        return 3
    
    @log_on_end(logging.INFO, "Arduino shut down", logger=logger)
    def shutdown_arduino(self):
        # Do whatever we need to do to turn off the sensors properly
        self.ser.close()
        return 0
    
    @log_on_start(logging.INFO, "Querying arduino", logger=logger)
    def query(self):
        get_data = self.ser.readline()
        data_string = get_data.decode('utf-8')
        # data_string = get_data

        self.logger.info(f"Result from querying arduino: {data_string}")

        return data_string
    
    def validate_command(self, command):
        """unimplemented"""
        return True

    def send_command(self, command):
        command_valid = self.validate_command(command)
        if command_valid:
            msg_str = self.start_character+command+self.end_character
            logger.debug(f"Sending command to Arduino: {msg_str}")
            self.ser.write(str(msg_str).encode())
            self.query()
            
        else:
            logger.debug(f"Invalid Arduino command: {command}")

    def validate_and_format_pin(self, pin):
        try:
            pin_int = int(pin)
        except ValueError as e:
            logger.error(f"Invalid arduino pin: {pin} ({e})")
            return False
        else:
            if pin_int > 1 and pin_int <= 69:
                pass
            else:
                logger.error(f"Invalid arduino pin: {pin} not between 1-69")
                return False

        pin_str = str(pin)
        if len(pin_str) == 1:
            pin_str = "0"+pin_str
        
        return pin_str

    def set_pin_high(self, pin):
        pin = self.validate_and_format_pin(pin)
        if pin:
            # logger.info(f"Setting pin {pin} high")
            msg_str = "01;"+pin
            self.send_command(msg_str)

    def set_pin_low(self, pin):
        pin = self.validate_and_format_pin(pin)
        if pin:
            # logger.info(f"Setting pin {pin} low")
            msg_str = "00;"+pin
            self.send_command(msg_str)


if __name__ == "__main__":
    myarduino = ArduinoInterface("COM4", 19200)