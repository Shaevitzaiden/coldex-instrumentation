# Communicates with Arduino

import numpy as np
import time

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
        self.initialize_pyserial(serial_port, baud_rate)

        # Different serial command characters
        self.start_character = "<"
        self.end_character = ">"
        self.one_thing = "1"
        self.another_thing = "2"

        if custom_logger is not None:
            self.logger = custom_logger
        else:
            self.logger = logger

        self.logger.info("test 3")

    def initialize_pyserial(self, port, baud):
        pass

    @log_on_start(logging.INFO, "Initializing Arduino", logger=logger)
    def initialize_arduino(self, timeout=10):
        """
        The initialization methods return one of three values: 
        1 (real hardware, initialization succeeded), 2 (simulated hardware), 3 (initialization failed / error)
            
            Returns - 2
        """
        logger.info("Arduino initialized")
        return 2
    
    @log_on_end(logging.INFO, "Arduino shut down", logger=logger)
    def shutdown_arduino(self):
        return 0
    
    @log_on_start(logging.INFO, "Querying arduino", logger=logger)
    def query(self):
        output = np.nan
        timestamp = time.time()

        return timestamp, output
    
    def validate_command(self, command):
        return True

    # @log_on_end(logging.INFO, "Sent command to arduino", logger=logger)
    def send_command(self, command):
        command_valid = self.validate_command(command)
        if command_valid:
            logger.debug(f"Sent command to simulated Arduino: {command}")
        else:
            logger.debug(f"Invalid Arduino command: {command}")

    def validate_and_format_pin(self, pin):
        try:
            pin_int = int(pin)
        except ValueError as e:
            self.logger.error(f"Invalid arduino pin: {pin} ({e})")
            return False
        else:
            if pin_int > 1 and pin_int <= 69:
                pass
            else:
                self.logger.error(f"Invalid arduino pin: {pin} not between 1-69")
                return False

        pin_str = str(pin)
        if len(pin_str) == 1:
            pin_str = "0"+pin_str
        
        return pin_str
    
    def set_pin_high(self, pin):
        pin = self.validate_and_format_pin(pin)
        self.logger.info("--------------")
        if pin:
            self.logger.info(f"Setting pin {pin} high")
            msg_str = "01;"+pin
            self.send_command(msg_str)

    def set_pin_low(self, pin):
        pin = self.validate_and_format_pin(pin)
        if pin:
            self.logger.info(f"Setting pin {pin} low")
            msg_str = "00;"+pin
            self.send_command(msg_str)

