# -------------
# The sensor class
# 
# Currently can't be run from here, since it's importing things from the sensor_interfaces package. Need to figure that out.
# -------------

# General imports
import serial
from serial import SerialException
import time
import yaml
import numpy as np
import pandas as pd
import datetime

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

# Custom imports
from main_pipeline.bus import Bus
from sensor_interfaces import sim_instruments

####### -------------------------------- Try to connect to all the sensors -------------------------------- #######
# If we can connect, use the real sensor at the specified serial port and baud. if not, use simulated hardware. 
# This allows us to have the entire process running even if we only want a few sensors online

# Load the sensor comms configuration file - dictionary with sensor serial ports and baud rates
try:
    with open("config/sensor_comms.yaml", 'r') as stream:
        comms_config = yaml.safe_load(stream)
except FileNotFoundError as e:
    logger.error(f"Error in loading the sensor_comms configuration file: {e} Check your file storage and directories")

# Arduino
try:
    serial.Serial(port=comms_config["Arduino"]["serial port"], baudrate=comms_config["Arduino"]["baud rate"])
    from sensor_interfaces.arduino_interface import ArduinoInterface
    logger.info(f"Successfully connected to port {comms_config['Arduino']['serial port']}, using real Arduino hardware")
except SerialException:
    from sensor_interfaces.sim_instruments import ArduinoInterface
    logger.info(f"Couldn't find Arduino at port {comms_config['Arduino']['serial port']}, shadowing sensor calls with substitute functions")
except KeyError as e:
    logger.warning(f"Key error in reading sensor_comms configuration file: {e}. Check that your dictionary keys match")


class Sensor():
    """Class that reads from the different sensors and publishes that data over busses"""
    @log_on_end(logging.INFO, "Sensor class initiated", logger=logger)
    def __init__(self, custom_logger:logging.Logger=None, debug=False) -> None:
        
        # Read in the sensor config file to grab a list of all the sensors we're working with
        try:
            with open("config/sensor_data.yaml", 'r') as stream:
                self.big_data_dict = yaml.safe_load(stream)
        except FileNotFoundError as e:
            logger.error(f"Error in loading the sensor data config file: {e}")
            self.big_data_dict = {}
        
        self.sensor_names = list(self.big_data_dict.keys())

        # Create a dictionary to store the status of each sensor -- 0 (offline), 1 (real hardware, online), 2 (simulated hardware), 3 (failed to initialize / error)
        self.sensor_status_dict = {}
        for name in self.sensor_names:
            self.sensor_status_dict.update({name:0})

        # If we've passed in a custom logger, use that. Otherwise, set up one of our own
        if logger is not None:
            self.logger = custom_logger
        else:
            self.logger = logger

        self.arduino = ArduinoInterface(serial_port=comms_config["Arduino"]["serial port"], 
                                        baud_rate=comms_config["Arduino"]["baud rate"],
                                        custom_logger=custom_logger)

    def __del__(self):
        self.shutdown_sensors()

    @log_on_start(logging.INFO, "Initializing sensors", logger=logger)
    @log_on_end(logging.INFO, "Finished initializing sensors", logger=logger)
    def initialize_sensors(self):
        """
        Method to take each sensor through a sequence to check that it's on and getting valid readings.
        **If you're adding a new sensor, you probably need to modify this method**

        Returns - status of each sensor 
        """

        # Fill in the dictionary with the results of calling the sensor init functions
        self.sensor_status_dict.update({"Dummy sensor": 0})

        return self.sensor_status_dict

    @log_on_start(logging.INFO, "Shutting down sensors", logger=logger)
    @log_on_end(logging.INFO, "Finished shutting down sensors", logger=logger)
    def shutdown_sensors(self):
        """
        Method to stop measurements/exit data collection/turn off the sensors that need it; the rest don't have a shutdown feature.
        **If you're adding a new sensor, you probably need to modify this method.**
        
        Shuts down - Arduino
        Returns - status of each sensor
        """
        # Updates the status dictionary with the results of shutting down the sensors
        self.sensor_status_dict.update({"Dummy sensor": 0})

        return self.sensor_status_dict

    def close_arduino_serial(self):
        self.arduino.ser.close()

    def open_arduino_serial(self):
        self.arduino.initialize_pyserial(port=comms_config["Arduino"]["serial port"], 
                                        baud=comms_config["Arduino"]["baud rate"])