# -------------
# This class is a barebones example to show how the sensor>interpreter>display pipeline of the main script functions
# -------------

import numpy as np
import time
import concurrent.futures
from readerwriterlock import rwlock
import sys, os


class Bus():
    """Class that sets up a bus to pass information around with read/write locking"""
    def __init__(self):
        self.message = [0,0]
        self.lock = rwlock.RWLockWriteD() # sets up a lock to prevent simultanous reading and writing

    def write(self, message):
        with self.lock.gen_wlock():
            self.message = message

    def read(self):
        with self.lock.gen_rlock():
            message = self.message
        return message
    
class DummySensor():
    """Class that mimics a sensor by generating random integers. This would be the place to read from the different 
    sensors and publish that data over busses"""
    def __init__(self) -> None:
        self.data = 0.0

    def sensor_producer(self, sensor_bus:Bus, delay):
        self.read_sensor()
        sensor_bus.write(self.data)
        time.sleep(delay)

    def read_sensor(self):
        self.data = [np.random.randint(-5, 6), np.random.randint(-5, 6)]

class DummyInterpreter():
    """Class that reads data from the sensor bus, does some processing, and republishes on an interpreter bus.
    Currently just takes in the random integer from DummySensor and doubles it"""
    def __init__(self) -> None:
        self.doubled = 0.0

    def doubler_consumer_producer(self, sensor_bus:Bus, doubler_bus:Bus, delay):
        data = sensor_bus.read()
        self.doubler(data)
        doubler_bus.write(self.doubled)
        time.sleep(delay)

    def doubler(self, data):
        try: 
            self.doubled = data
        except TypeError:
            pass

class DummyDisplay():
    """Class that reads the interpreted data and prints it"""
    def __init__(self) -> None:
        pass

    def display_consumer(self, interpreter_bus:Bus, delay):
        interp_data = interpreter_bus.read()
        print(interp_data)
        
class DummyExecutor():
    """Class that handles passing the data around on all the busses. Still needs a clean shutdown."""
    def __init__(self) -> None:
        # Initialize the classes
        self.sensor = DummySensor()
        self.interpreter = DummyInterpreter()
        self.display = DummyDisplay()

        # Initialize the busses
        self.sensor_bus = Bus()
        self.interpreter_bus = Bus()

        # Set the delay times (sec) - the delays are needed to chill out the threads since we'll be running in a While True loop later
        self.sensor_delay = 0.1
        self.interp_delay = 0.1
        self.display_delay = 0.1
        
    def execute(self):
        """Method to execute the sensor, interpreter, and display classes with threading. Calls the appropriate methods within
        those classes and passes them the correct busses and delay times."""

        while True:
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    eSensor = executor.submit(self.sensor.sensor_producer, self.sensor_bus, self.sensor_delay)
                    eInterpreter = executor.submit(self.interpreter.doubler_consumer_producer, self.sensor_bus, 
                                                    self.interpreter_bus, self.interp_delay)
                    eDisplay = executor.submit(self.display.display_consumer, self.interpreter_bus, self.display_delay)

                eSensor.result()
                eInterpreter.result()
                eDisplay.result()

            except KeyboardInterrupt:
                try:
                    sys.exit(130)
                except SystemExit:
                    os._exit(130)

if __name__ == "__main__":
    my_executor = DummyExecutor()
    my_executor.execute()