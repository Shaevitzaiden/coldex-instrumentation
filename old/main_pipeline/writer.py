# -------------
# The display class
# -------------

import time
import yaml
import csv
import pandas as pd

# from gui import GUI
try:
    from main_pipeline.bus import Bus
except ImportError:
    from bus import Bus

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

class Writer():
    """Class that reads the interpreted data and saves it to the disk"""
    @log_on_end(logging.INFO, "Display class initiated", logger=logger)
    def __init__(self) -> None:
        pass

if __name__ == "__main__":
    mywriter = Writer()