###
# Example setup for an automation routine. I suggest setting them all up this way - 
# a class to manage the routine itself with a single entry point (run_routine). These script
# MUST have a function called run() in order for the GUI to understand them. 
# 
# Another thing to note is that I've set up run() to take an arbitrary input: run(**kwargs)
# It looks like magic, but it just means "keyworded argument". Whatever we give the function gets
# turned into a dictionary with the key-value pairs we specified. This lets us stay a little more
# flexible and backwards compatible - if I add a new script with an input we haven't used for
# old scripts, the old scripts can just ignore the new input. Doesn't work in reverse - we can't stop
# using established inputs willy nilly - but such is life.
###

import time
import logging
import yaml

from sensor_interfaces.arduino_interface import ArduinoInterface

class TestRoutine:
    def __init__(self, **kwargs):

        # # Uncomment this to see how **kwargs works
        # print("kwargs: ")
        # for key, value in kwargs.items():
        #     print(f"key: {key}, value: {value}")
        # print("-----")
        
        # Set up logging. If we've passed in a logger, use that. Otherwise, make our own
        try:
            self.logger = kwargs["logger"]
        except KeyError:
            self.logger = logging.getLogger(__name__)
            fh = logging.StreamHandler()
            fh.setLevel(logging.DEBUG)
            self.logger.addHandler(fh)

        # Set up our instance of the arduino.
        try:
            with open("config/sensor_comms.yaml", 'r') as stream:
                comms_config = yaml.safe_load(stream)
        except FileNotFoundError as e:
            self.logger.error(f"Error in loading the sensor_comms configuration file: {e} Check your file storage and directories")
        
        self.arduino = ArduinoInterface(serial_port=comms_config["Arduino"]["serial port"], 
                                        baud_rate=comms_config["Arduino"]["baud rate"])
        

        # Read in the Arduino pin configuration set up in our yaml
        with open("config/sensor_comms.yaml", "r") as stream:
            sensor_comms = yaml.safe_load(stream)
        try:
            self.pin_config_dict = sensor_comms["Pneumatic valves"]
        except KeyError:
            self.pin_config_dict = {}

    def run_routine(self):
        for button in self.pin_config_dict:
            try:
                pin = self.pin_config_dict[button]["digital pin"]
            except KeyError as e:
                self.logger.error(f"Could not find corresponding arduino pin for button {button} ({e})")
            
            self.arduino.set_pin_high(pin)
            time.sleep(0.5)
            self.arduino.set_pin_low(pin)
            time.sleep(0.5)

def run(**kwargs):
    myRoutine = TestRoutine(**kwargs)
    myRoutine.run_routine()