# -------------
# This is the Graphical User Interface (GUI) - true to its name, many graphs and user interfaces going on here!
# I've tried to make it as modular as possible, so adding additional sensors in the future won't be as much of a pain.
# 
# Most of the GUI features - like what sensors we display, what notetaking capabilities we need out of a logging panel, etc
# are managed through external YAML files
# -------------

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT  as NavigationToolbar
# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

import matplotlib.pyplot as plt
import numpy as np
import yaml
import sys
import time
import multiprocessing
import os
import psutil
from collections import deque
from functools import partial
import concurrent.futures
import traceback
import pandas as pd
import logging
from logdecorator import log_on_start , log_on_end , log_on_error
from pathlib import Path

from pyqt_helpers.live_plots import MyFigureCanvas
from pyqt_helpers.circle_button import CircleButton
from pyqt_helpers.custom_logging import GUIHandler
from pyqt_helpers.lines import VLine, HLine
from pyqt_helpers.helpers import *

from main_pipeline.sensor import Sensor
from main_pipeline.interpreter import Interpreter
from main_pipeline.writer import Writer
from main_pipeline.bus import Bus

import automation_routines

# Set up a logger for this module
logger = logging.getLogger("GUI")
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

class ApplicationWindow(QWidget):
    """
    This is the Graphical User Interface, or GUI! It sets up the user interface for the main pipeline.

    Args:
        This class inherits from the general QWidget class in order to make the main window. There are lots of different 
        ways to this inheriting, which make some of the syntax slightly different in between applications. Ah well.
        
    """
    def __init__(self):
        """Constructor, called when the class is instantiated"""
        # Initialize the inherited class (QWidget)
        super().__init__()

        # Window settings
        self.setGeometry(50, 50, 2000, 1000) # window size (x-coord, y-coord, width, height)
        self.setWindowTitle("")

        # Set some fonts
        self.bold16 = QFont("Helvetica", 16)
        self.bold16.setBold(True)
        self.norm16 = QFont("Helvetica", 16)
        self.bold12 = QFont("Helvetica", 12)
        self.bold12.setBold(True)
        self.norm12 = QFont("Helvetica", 12)
        self.norm10 = QFont("Helvetica", 10)

        self.logger = logger

        status_layout = self.build_status_layout()

        # Initialize the main sense-interpret-save data pipeline
        self.init_data_pipeline()

        self.data_dict = {
            "all data": {},
            "metadata": {},
        }

        # Set data buffer parameters
        self.max_buffer_length = 5000 # How long we let the buffers get, helps with memory
        self.default_plot_length = 60 # Length of time (in sec) we plot before you have to scroll back to see it
        self.init_data_buffer()

        # Start some metadata parameters
        with open("config/project_metadata.yaml", "r") as stream:
            self.metadata_dict = yaml.safe_load(stream)
        self.flask_n = 1

        # Read in the Arduino pin configuration set up in our yaml config
        with open("config/sensor_comms.yaml", "r") as stream:
            self.sensor_comms = yaml.safe_load(stream)

        # Get today's date
        current_time = time.time()
        date = epoch_to_pacific_time(current_time).date
        self.date_str = str(date[0])
        
        # Pneumatic grid variables
        with open("config/button_locs.yaml", "r") as stream:
            pneumatic_grid_layout = yaml.safe_load(stream)
        self.button_locs = pneumatic_grid_layout["Buttons"]
        self.grid_lines = pneumatic_grid_layout["Lines"]

        self.buttons_locked = True
        self.num_buttons = len(self.button_locs)
        self.pneumatic_grid_buttons = []
        self.pneumatic_autonomous_controls = {}
        
        # Create the main GUI panels
        # We can arrange things in a QGridLayout by specifying (row, column, rowspan, columnspan)
        main_layout = QGridLayout()
        main_layout.addLayout(status_layout, 2, 0)
        main_layout.addLayout(self.build_control_layout(), 0, 0)
        main_layout.addLayout(self.build_pneum_ctrl_layout(), 1, 0)
        main_layout.addLayout(self.build_plotting_layout(), 0, 1, 1, 2)
        main_layout.addLayout(self.build_pneumatic_layout(), 1, 1, 2, 2)

        main_layout.setColumnStretch(0, 0)
        main_layout.setColumnStretch(1, 1)
        main_layout.setRowStretch(0, 1)
        main_layout.setRowStretch(1, 1)
        main_layout.setRowStretch(2, 1)

        self.setLayout(main_layout)
        
        # Create a threadpool for this class, so we can do threading later
        self.threadpool = QThreadPool()
            
        # Initiate two timers that both trigger every X ms:
        timer_update = 1000
        # One for updating the plots...
        self.plot_figs_timer = QTimer()
        self.plot_figs_timer.timeout.connect(self.update_plots)
        self.plot_figs_timer.start(timer_update)
        # ...and one for collecting, processing, and saving data
        self.execution_timer = QTimer()
        self.execution_timer.timeout.connect(self.run_data_collection)
        self.execution_timer.start(timer_update)
        
        # Show the window
        self.show()

    def __del__(self):
        """Destructor, called when the class is destroyed
        """
        self.sensor.shutdown_sensors()
    
    def closeEvent(self, event):
        """This method overwrites the default QWidget closeEvent that triggers when the window "X" is clicked.
        It ensures we can shutdown sensors cleanly by opening a QMessageBox to prompt the user to quit/cancel
        """

        try:
            if self.multiprocess.is_alive():
                self.p.kill()
                self.multiprocess.terminate()
                self.multiprocess.join()
        except AttributeError:
            pass
        
        # self.check_close_event()
        # # If we actually want to shut down, shutdown the sensors and then accept the closeEvent
        # if self.accept_quit:
        #     self.sensor.shutdown_sensors()
        #     try:
        #         self.executor.shutdown()
        #     except:
        #         pass
        #     event.accept()
        # # Otherwise, ignore it
        # else:
        #     event.ignore()

    def check_close_event(self):
        """Method to check if the user actually wants to quit or not. Opens a QMessageBox and stores
        the result as a boolean in self.accept_quit."""
        # Flags to handle clean shutdown by storing the "are you sure you want to quit" result
        self.accept_quit = None
        # Set up a messagebox to prompt the user
        msgbox = QMessageBox()
        msgbox.setIcon(QMessageBox.Question)
        msgbox.setText("Are you sure you want to close the app? This shuts down sensors and stops data collection.")
        msgbox.setWindowTitle("MGR App")
        msgbox.setStandardButtons(QMessageBox.Close | QMessageBox.Cancel)
        # Get the user click and parse it appropriately
        msg_return = msgbox.exec()
        if msg_return == QMessageBox.Close:
            self.accept_quit = True
        elif msg_return == QMessageBox.Cancel:
            self.accept_quit = False

    ## --------------------- HELPERS --------------------- ## 
    def default_label(self, text:str="Label", font:QFont=QFont("Helvetica", 12)):
        label = QLabel(self)
        label.setText(text)
        label.setFont(font)
        label.setMaximumHeight(50)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        return label
    
    def default_button(self, text:str="", font=QFont("Helvetica", 12), callback=None, enabled=True, requires_self=False):
        button = QPushButton(text, self)
        button.setFont(font) 
        button.setEnabled(enabled)
        if not requires_self:
            button.clicked.connect(callback)
        else:
            button.clicked.connect(partial(callback, button))
        return button
    
    def dividing_line(self, orientation=QFrame.HLine):
        dividing_line = QFrame(self)
        dividing_line.setFrameShape(orientation)
        return dividing_line
        
    ## --------------------- SENSOR STATUS & CONTROL --------------------- ## 
       
    def build_control_layout(self):
        """Method to build the layout for sensor status & control"""
        control_layout = QGridLayout()
        control_layout.setContentsMargins(0, 20, 10, 0)
        # Initialize variables to store sensor control parameters, like temperature and pressure setpoint
        self.init_sensor_control_params()
        # Grab button information for both the main title array and the individual sensors
        title_button_info, sensor_button_info, control_button_info = self.define_sensor_button_callbacks()
        # Make the title row - has general buttons for initializing sensors and starting data collection
        start_next_row, title_colspan = self.make_title_control_panel(control_layout, title_button_info)
        # Make the individual button rows
        self.make_sensor_control_panel(control_layout, sensor_button_info, control_button_info, starting_row=start_next_row, colspan=title_colspan)
        # Position the panel at the top of the window and make it stretchy
        control_layout.setAlignment(QtCore.Qt.AlignTop)

        return control_layout
    
    def init_sensor_control_params(self):
        """Method to initialize dictionaries to hold sensor control information, namely their status and setpoint control values
        """
        # Every instrument has a status value, so initialize a dictionary with a status entry for every sensor
        self.instrument_status_dict = {}
        for name in self.instrument_names:
            self.instrument_status_dict.update({name:0}) # "0" means offline

        # The instruments that have setpoint control values have that set in the sensor_data configuration file, which 
        # lives in self.big_data dict. If there's a key corresponding to "Control", add the sensor and the name of the
        # control parameter to our control dictionary
        self.sensor_control_inputs = {}
        for sensor in self.sensor_names:
            try:
                self.big_data_dict[sensor]["Control"]
            except KeyError:
                pass
            else:
                for control_param in self.big_data_dict[sensor]["Control"]:
                    self.sensor_control_inputs.update({sensor: {control_param: None}}) # Initialize it to None to be safe

    def make_title_control_panel(self, parent:QGridLayout, title_button_info:dict, colspan=2):
        """Builds the panel for general sensor control - has buttons to initialize/shutdown sensors and start/stop data collection

        Args:
            parent (QGridLayout): Parent layout
            title_button_info (dict): Dictionary containing key-value pairs of 
                "button name":{"callback:button_callback_function, "enabled":True/False}
            colspan (int, optional): How many columns of buttons. Defaults to 2.

        Returns:
            start_next_row (int): What row of a QGridLayout any further widgets should start on

            **colspan**: *int*: How many columns we've used so far
        """
        # Set the title
        label = QLabel(self)
        label.setText("Sensor Status & Control")
        label.setMinimumWidth(int(self.width()/3))
        label.setFont(self.bold16)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        parent.addWidget(label, 0, 0, 1, colspan) # args: widget, row, column, rowspan, columnspan

        # Determine the dimensions of our button grid
        num_rows, num_cols = find_grid_dims(num_elements=len(title_button_info), num_cols=colspan)

        # For all the buttons we want to generate (stored in the title_button_info dict),
        # create, position, and assign a callback for each
        i = 0
        title_button_text = list(title_button_info.keys())
        self.title_buttons = {} # Holding onto the buttons for later
        for row in range(1, num_rows+1): # Adjusting for the QLabel title that we put on row 1
            for col in range(num_cols):
                try:
                    button_text = title_button_text[i]
                    button = QPushButton(self)
                    button.setText(button_text)
                    button.setFont(self.norm12)
                    button.pressed.connect(title_button_info[button_text]["callback"]) # set the button callback
                    button.setEnabled(title_button_info[button_text]["enabled"]) # set the button initial state (enabled/disabled)
                    parent.addWidget(button, row, col)
                    self.title_buttons.update({button_text:button})
                    i+=1
                except IndexError:
                    pass

        # Add a separation line to the layout after all the buttons
        line = QFrame(self)
        line.setFrameShape(QFrame.HLine)
        parent.addWidget(line, row+1, 0, 1, colspan)

        # We should add any further widgets after that^ line widget, so 2 rows after the last button
        start_next_row = num_rows+2

        return start_next_row, colspan
        
    def make_sensor_control_panel(self, parent:QGridLayout, sensor_buttons:dict, input_buttons:dict, starting_row, colspan):
        """Builds the panel for specific sensor control - has buttons that depend upon sensor functionality

        Args:
            parent (QGridLayout): Parent layout
            sensor_buttons (dict): Dictionary containing key-value pairs of "sensor_name":{button_1_name:button_1_callback, ...}
                for the buttons that do whatever they say in their names
            input_buttons (dict): Dictionary containing key-value pairs of "sensor_name":{button_1_name:button_1_callback, ...}
                for the buttons that send setpoint commands
            starting_row (int): What row of the parent layout we should start building from
            colspan (int): How many columns are already being used in the parent layout

        Returns:
            start_next_row (int): What row of a QGridLayout any further widgets should start on
        """
        # For all the sensors, create control buttons (if applicable) and a status indicator
        self.instrument_status_display = {} # Holding onto the status displays for later
        row = starting_row
        for sensor in self.instrument_names:
            # First widget we want to place - the sensor title
            title = QLabel(self)
            title.setFont(self.bold12)
            title.setText(sensor)
            title.setAlignment(Qt.AlignHCenter)
            title.setStyleSheet("padding-top:10px")
            parent.addWidget(title, row, 0, 1, colspan)
            row +=1
            # Second widget - the status indicator (QLabel that changes color & text upon initialization and shutdown)
            status = QLabel(self)
            status.setText("OFFLINE")
            status.setFont(self.norm12)
            status.setStyleSheet("background-color:#AF5189; margin:10px")
            status.setAlignment(Qt.AlignHCenter)
            parent.addWidget(status, row, 0, 1, colspan, alignment=Qt.AlignTop)
            row +=1
            self.instrument_status_display.update({sensor:status}) # Hold onto the status display for later
            # Third widget - sensor buttons (initialize, shutdown, start, etc)
            # If this sensor has buttons to add...
            try:
                # ...extract their names from the dictionary...
                buttons = sensor_buttons[sensor]
                c = 0 # Column counter
                n = 0 # Button counter
                for button in buttons:
                    # ...make a button...
                    b = QPushButton(self)
                    b.setText(button)
                    b.setFont(self.norm12)
                    # ...and connect its callback to the function that lives at this key in the dictionary.
                    b.pressed.connect(sensor_buttons[sensor][button])
                    parent.addWidget(b, row, c)
                    c += 1
                    n += 1
                    # Every two buttons, add another row and reset the column counter
                    if n%2 == 0:
                        row += 1
                        c = 0
                row +=1
            # Otherwise, catch the error and move on
            except KeyError:
                logger.debug(f"No command buttons for the {sensor}")
            # Fourth widget - control input. This is a button that sends the input (the callback function lives in 
                # input_buttons) and a line entry that lets the user set the input
                # Validation for the inputs happens in the lowest level sensor interface, so it's safe to chuck any
                # values at them from here
            try:
                control_inputs = self.sensor_control_inputs[sensor]
                buttons = input_buttons[sensor]
                # Iterate through both lists, making buttons and text inputs as we go
                for button, ctrl_input in zip(buttons, control_inputs):
                    # Add a button
                    b = QPushButton(self)
                    b.setText(button)
                    b.setFont(self.norm12)
                    # Connect its callback to the function that lives at this key of the dictionary
                    b.pressed.connect(input_buttons[sensor][button])
                    parent.addWidget(b, row, 0)
                    # Add a text input
                    line = QLineEdit(self)
                    line.setFont(self.norm12)
                    # Display the current value of the control input as placeholder text
                    line.setPlaceholderText(f"{ctrl_input}: {self.sensor_control_inputs[sensor][ctrl_input]}")
                    # When the input is set, add it to the dictionary of control inputs
                    line.editingFinished.connect(partial(self._save_control_input, line, sensor, ctrl_input))
                    parent.addWidget(line, row, 1)
                    row +=1
            except KeyError:
                logger.debug(f"No control inputs for the {sensor}")
            # Fifth widget - dividing line
            line = QFrame(self)
            line.setFrameShape(QFrame.HLine)
            parent.addWidget(line, row, 0, 1, colspan)
            row +=1

        # We should add any further widgets after the last dividing line
        start_next_row = row + 1
        return start_next_row
    
    def define_sensor_button_callbacks(self):
        """Method that sets the button callbacks for the sensor status & control panel. **If you're adding a new sensor, you'll
        likely need to add to this method.**

        Returns:
            title_buttons (dict): Dictionary with title button information 
                {"button_name":{"callback":button_callback, "enabled":True/False}}
            
            sensor_buttons (dict): Dictionary with sensor button information {"sensor_name":{"button_name":button_callback}}
        """

        # Initialize a dictionary of general title buttons - these functions control all the sensors or general large GUI functions
        title_buttons = {}
        title_button_names = ["Initialize All Sensors", "Shutdown All Sensors", "New Project", "Update Project", "Stop"]
        title_button_callbacks = [self._on_sensor_init, self._on_sensor_shutdown, self._on_new_project, self._on_update_project, self._on_stop_data]
        title_button_enabled = [True, True, True, False, True]
        for name, callback, enabled in zip(title_button_names, title_button_callbacks, title_button_enabled):
            title_buttons.update({name: {"callback":callback, "enabled":enabled}})

        # Initialize a dictionary of buttons for each sensor. These buttons do whatever they say on the tin (e.g "Start X"
            # runs the initialization sequence for X.)
            # I want the "status" bar of each sensor to update when some of these buttons are pressed, so I do something a little cheeky
            # with their callbacks - using "partial()" creates a temporary function where the first argument is the function 
            # to execute and the following arguments are its inputs. I use this to pass each sensor button function into a general
            # "_on_sensor_button" method that updates the sensor status as well as executing the desired callback whenever the button
            # is pressed
        sensor_buttons = {}
        sensor_buttons.update({"Arduino": {"Start Arduino": partial(self._on_sensor_button, "Arduino", self.sensor.arduino.initialize_arduino),
                                           "Stop Arduino": partial(self._on_sensor_button, "Arduino", self.sensor.arduino.shutdown_arduino)}})

        # sensor_buttons.update({"Picarro Gas": {"Start Picarro":
        #                                        partial(self._on_sensor_button, "Picarro Gas", self.sensor.gas_picarro.initialize_picarro)}})
        
        # Initialize another dictionary of buttons for each sensor. These are a special set that sends user-specified control inputs,
            # instead of running the same function/protocol each time. I use the same "partial()" strategy here to specify which
            # sensor and which input parameter we're sending, which gets read from a dictionary in _send_control_input and saved to 
            # that dictionary in _save_control_input
        input_buttons = {}
        input_buttons.update({"Arduino": {"Arduino Input": partial(self._send_control_input, "Arduino", "Arduino control 1", self.sensor.arduino.send_command)}})      

        return title_buttons, sensor_buttons, input_buttons
        
    def _on_sensor_button(self, sensor:str, initialization_function):
        """Method that calls the function passed into initialization_function, gets the initialization result,
        and uses it to update the appropriate sensor status.

        Args:
            sensor (str): Name of the sensor. Must match a key in self.big_data_dict
            initialization_function (method): Whatever you want the sensor button to do
        """
        init_result = initialization_function()
        self.instrument_status_dict.update({sensor: init_result})
        self.update_instrument_status()

    def _on_sensor_init(self):
        """Callback function for the 'Initialize All Sensors' button
        """
        # Start our sensor initialization in a thread so any blocking doesn't cause the GUI to freeze
        worker = Worker(self.sensor.initialize_sensors)
        # When it's done, trigger the _finished_sensor_init function
        worker.signals.result.connect(self._finished_sensor_init)
        self.threadpool.start(worker)

    def _finished_sensor_init(self, instrument_status:dict):
        """Method that gets triggered when that thread^ in _on_sensor_init finishes.

        Args:
            instrument_status (dict): dictionary returned from self.sensor.initialize_sensors
        """
        # Update the sensor status dictionary and the GUI
        self.instrument_status_dict = instrument_status
        self.update_instrument_status()
        # Enable the data collection buttons
        self.title_buttons["New Project"].setEnabled(True)
        
    def _on_sensor_shutdown(self):
        """Callback function for the 'Shutdown All Sensors' button
        """
        self.data_collection = False
        # Start our sensor shutdown in a thread so any blocking doesn't cause the GUI to freeze
        worker = Worker(self.sensor.shutdown_sensors)
        # When it's done, trigger the _finished_sensor_shutdown function
        worker.signals.result.connect(self._finished_sensor_shutdown)
        self.threadpool.start(worker)

    def _finished_sensor_shutdown(self, instrument_status:dict):
        """Method that gets triggered when that thread^ in _on_sensor_shutdown finishes.

        Args:
            instrument_status (dict): dictionary returned from self.sensor.shutdown_sensors
        """
        # Update the sensor status dictionary and the GUI
        self.instrument_status_dict = instrument_status
        self.update_instrument_status()
    
    def _on_stop_data(self):
        """Callback function for the "Stop Data Collection" button. Sets the data_collection flag to false
        """
        self.data_collection = False
        # self.title_buttons["Update Project"].setEnabled(False)

    def _send_control_input(self, sensor:str, input_name:str, control_function):
        """Method to grab the control input out of the self.sensor_control_inputs dictionary
        and send it to the provided control function

        Args:
            sensor (str): The sensor name, must correspond to a key in self.big_data_dict
            input_name (str): The name of the input parameter we're sending, must correspond to a key in self.sensor_control_inputs
            control_function (method): The function in question
        """
        control_input = self.sensor_control_inputs[sensor][input_name]
        control_function(control_input)

    def _save_control_input(self, line:QLineEdit, sensor:str, input_name:str):
        """Callback function for the QLineEdit entries, called whenever the user finishes editing them.

        Args:
            line (QLineEdit): The line entry in question
            sensor (str): The sensor name, must correspond to a key in self.big_data_dict
            input_name (str): The name of the input parameter we're sending, must correspond to a key in self.sensor_control_inputs
        """
        # Grab the current text of the line entry
        current_input = line.text()
        # Save the text to the correct key of the dictionary
        self.sensor_control_inputs[sensor][input_name] = current_input
        # Set the line text to reflect the new input, and clear the line
        line.setPlaceholderText(f"{input_name}: {current_input}")
        line.clear()

    def update_instrument_status(self):
        """Method to update the sensor status upon initialization or shutdown. Uses the values stored in
        self.instrument_status_dict to set the color and text of each sensor status widget."""
        # Loop through the sensors and grab their status from the sensor status dictionary
        for name in self.instrument_names:
            status = self.instrument_status_dict[name]
            # If we're offline
            if status == 0:
                # color = "#D80F0F"
                color = "#AF5189"
                text = "OFFLINE"
            # If we're online / successfully initialized
            elif status == 1:
                color = "#619CD2"
                text = "ONLINE"
            # If we're disconnected / using shadow hardware
            elif status == 2:
                color = "#FFC107"
                text = "SHADOW HARDWARE"
            # IF we failed initialization / there's some other error going on
            elif status == 3:
                color = "#D55E00"
                text = "ERROR"
            # If we recieved an erroneous reading, make it obvious
            else:
                color = "purple"
                text = "?????"

            # Update the sensor status accordingly
            status = self.instrument_status_display[name] # This is a dictionary of QLabels
            status.setText(text)
            status.setStyleSheet(f"background-color:{color}; margin:10px")

    ## --------------------- NEW/UPDATE PROJECT UI --------------------- ## 
    def _on_new_project(self):
        """Callback function for the "New Project" button. Pulls up a new window with a table to get
        metadata about the current project. Sets the data paths and files accordingly if the user
        says "go", does nothing if the user says "cancel. See _on_start_project for more.
        """
        start_button = self.default_button("Start", self.bold12, self._on_start_project)
        self._sample_data_UI(
                            window_title="New Sample Data", 
                            title="All fields are required", 
                            enter_button=start_button,
                            use_case="new")

        #### reset status logs ?
    
    def _on_update_project(self):
        """Callback function for the "Update Project" button. Pulls up the same window & table as 
        for "New Project" but with already-existing metadata, lets the user edit as they wish. 
        See on_update_metadata for more.
        """
        update_button = self.default_button("Update", self.bold12, self._on_update_metadata)
        self._sample_data_UI(
                            title="Update Sample Data", 
                            window_title="Watch out! Anything you enter overwrites existing metadata.", 
                            enter_button=update_button,
                            use_case="update")

    def _sample_data_UI(self, window_title:str, title:str, enter_button:QPushButton, use_case:str):
        """Long but fairly straightforward! Method that builds the layout for the "New Project" and "Update Project" buttons. 
        Creates a user-entry grid based on the entries set in project_metadata.yaml.

        Args:
            window_title (str): Window title
            title (str): Top-of-page label
            enter_button (QPushButton): The "enter" button (complete with callback) - since I use this method for both new and update, 
                I want "enter" to do different things
        """
        # Create and name a new window
        self.new_project_window = QWidget()
        self.new_project_window.setWindowTitle(window_title)
        layout = QVBoxLayout()
        
        layout.addWidget(self.default_label(title, self.bold12), alignment=Qt.AlignCenter)
        layout.addWidget(self.dividing_line())

        # First thing on the entry form: sample metadata (date, researcher, etc)
        metadata_layout = QHBoxLayout()
        metadata_layout.addWidget(self.dividing_line(QFrame.VLine))
        # For each piece of data to collect, add a text entry
        user_metadata = self.metadata_dict["New project"]["User metadata"]
        metadata = self.data_dict["metadata"]
        self.new_project_entries = {}
        for data in user_metadata:
            # First widget - label
            label = self.default_label(data, font=self.norm10)
            metadata_layout.addWidget(label)
            # Second widget - text entry box
            entry = QLineEdit(self)
            # if len(metadata) > 0:# is not None:
            if use_case == "update" and len(metadata) > 0:
                entry.setText(metadata[data])
            metadata_layout.addWidget(entry)
            # Hang onto the text entry box widget for later
            self.new_project_entries.update({data: entry})
            # Third widget - dividing line
            metadata_layout.addWidget(self.dividing_line(QFrame.VLine))

        # Add the sample metadata and some dividing lines
        layout.addLayout(metadata_layout)
        layout.addWidget(self.dividing_line())
        layout.addWidget(self.dividing_line())

        # Second thing on the entry form: sample data (measurements, coreID, etc)
        sample_layout = QGridLayout()
        sample_layout.addWidget(self.dividing_line(QFrame.VLine), 0, 0, 2, 1)
        # More data entry - slightly more complicated because we're using multiple columns here
        widgets_per_col = 2
        sample_data = self.metadata_dict["New project"]["Sample data"]
        sample_rows, sample_cols = find_grid_dims(len(sample_data), len(sample_data)*widgets_per_col)
        metadata = self.data_dict["metadata"]
        i = 0
        for row in range(0, sample_rows):
            for col in range(1, sample_cols+1, widgets_per_col):
                data = sample_data[i]
                # First widget - label
                label = self.default_label(data, font=self.norm10)
                sample_layout.addWidget(label, row, col)
                # Second widget - text entry box
                entry = QLineEdit(self)
                if label.text() == "Flask":
                    entry.setText(str(self.flask_n))
                if use_case == "update " and len(metadata) > 0: # is not None:
                    entry.setText(metadata[data])
                sample_layout.addWidget(entry, row+1, col)
                # Again, hang onto the data entry
                self.new_project_entries.update({data: entry})
                # Third widget - dividing line
                sample_layout.addWidget(self.dividing_line(QFrame.VLine), row, col+1, 2, 1)
                i+=1

        # Add the sample data and another dividing line        
        layout.addLayout(sample_layout)
        layout.addWidget(self.dividing_line())
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # Add buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(enter_button,
                                alignment = Qt.AlignRight)
        button_layout.addWidget(self.default_button("Cancel", self.bold12, self.new_project_window.close), 
                                alignment=Qt.AlignLeft)
        button_layout.setAlignment(Qt.AlignVCenter | Qt.AlignBottom)
        # layout.addLayout(button_layout, stretch=1)

        # Add the widgets to the new window and show the window
        self.new_project_window.setLayout(layout)
        self.new_project_window.show()

    def _on_start_project(self):
        """
        Callback function for the "Start" new project button. It grabs the new project metadata entries,
        creates a new directory and files based on the entries, and makes sure we don't overwrite
        anything without express user permission.
        """
        # Get project metadata, adding our own internal timestamp
        metadata = {key:self.new_project_entries[key].text() for key in self.new_project_entries}
        metadata.update({"Unix timestamp": time.time()})

        # Check if data/YYMMDD/flaskN directory exists. I've split up the folders by flask, should check
        # and see if that's what they want to do
        flask_n = self.new_project_entries["Flask"].text()
        current_data_dir = f"data/{self.date_str}/flask{flask_n}"
        # If it does, fabulous
        if Path(current_data_dir).is_dir():
            pass
        # If it doesn't, make it
        else:
            logger.info(f"Making directory {current_data_dir}")
            Path(current_data_dir).mkdir(parents=True)

        # Now that we've established the correct directory, create our data filepaths
        self.current_data_paths = {
            "all data": f"{current_data_dir}/dataFull.csv",             ############################################# hardcode alert ##
            "metadata": f"{current_data_dir}/metadata.csv"
        }
        # For each file we want to make...
        files_exist_flag = False
        for data in self.current_data_paths:
            path = self.current_data_paths[data]
            # Try to make it. If the filename exists, 'x' will raise a FileExistsError
            try:
                write_new_csv_dict(path, self.data_dict[data])
            # If we find a file that exists already, note that and break out of the loop
            except FileExistsError:
                files_exist_flag = True
                break
        # If we've found a file that exists already, prompt the user with a messagebox.
        if files_exist_flag:
            ask = QMessageBox()
            ask.setIcon(QMessageBox.Question)
            ask.setText(f"Files with this flask number (Flask {flask_n}) exist already. Overwrite metadata?")
            ask.setWindowTitle("Files exist already!")
            ask.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            # Get the user click.
            msg_return = ask.exec()
            # If they accept the overwrite, 
            if msg_return == QMessageBox.Yes:
                # overwrite the metadata.
                overwrite_csv_dict(filepath=self.current_data_paths["metadata"], 
                                    data=self.data_dict["metadata"]
                                    )
            # Otherwise, exit the method without starting data collection or closing the new window.
            elif msg_return == QMessageBox.No:
                return

        # Finally, now that the user is done editing, do some internal cleaning up - 
        # Update our internal metadata
        self.data_dict["metadata"] = metadata
        # Activate data collection (eventually)
        print("Data collection currently deactivated")
        # self.data_collection = True
        # Update our internal Flask counter (or, try to - a safety measure in case we were given 
            # something other than a number)
        try:
            self.flask_n = int(self.new_project_entries["Flask"].text()) + 1
        except ValueError:
            pass
        # Activate the "update project" button - only needs to happen once, but doesn't hurt
        self.title_buttons["Update Project"].setEnabled(True)
        # Finally finally, close the window
        self.new_project_window.close()
                       
    def _on_update_metadata(self):
        """Updates the metadata with the provided entries"""
        # Get the existing metadata from our big internal dictionary
        metadata = self.data_dict["metadata"]
        # If the user has entered anything (i.e not an empty string), grab it
        for key in self.new_project_entries:
            entry = self.new_project_entries[key].text()
            if entry != "":
                metadata.update({key: entry})
        
        # Update our internal timestamp
        metadata.update({"Unix timestamp": time.time()})
        # Export and update our metadata
        overwrite_csv_dict(filepath=self.current_data_paths["metadata"], data=metadata)
        self.data_dict["metadata"] = metadata
        # Close the window
        self.new_project_window.close()

    ## --------------------- PNEUMATIC GRID --------------------- ##

    # Grid buttons
    def build_pneumatic_layout(self):  

        pneumatic_layout = QGridLayout()

        label = self.default_label("Pneumatic Grid", self.bold16)
        pneumatic_layout.addWidget(label, 0, 1)

        line = self.dividing_line(QFrame.VLine)
        pneumatic_layout.addWidget(line, 0, 0, 4, 1)
                             
        pneum_widget = self.make_pneumatic_button_grid()
        pneumatic_layout.addWidget(pneum_widget, 1, 1)

        button = self.default_button("Edit Button Layout", self.norm12, self._on_edit_pneumatic_buttons)
        pneumatic_layout.addWidget(button, 3, 1, alignment=Qt.AlignBottom|Qt.AlignRight)

        line = self.dividing_line(QFrame.VLine)
        pneumatic_layout.addWidget(line, 0, 2, 4, 1)

        return pneumatic_layout

    def make_pneumatic_button_grid(self):
        parent_widget = QWidget()
        parent_widget.setMinimumHeight(int(self.height()/2.25))
        parent_widget.setMinimumWidth(int(self.width()*0.6))
        self.draw_pneumatic_grid_lines(parent_widget)

        # For each button, create our custom button object and add the specified 
        #   horizontal and vertical lines from config/button_locs.yaml. Since we 
        #   want these lines to follow along if the button is moved, I've called 
        #   them "ducklings"
        for i in range(1, self.num_buttons+1):
            # First, see if we've specified either horizontal or vertical lines, catching the 
            #   error that would pop up if we haven't entered either of these dict keys
            # Then, if they exist, add each horizontal/vertical to the "ducklings" list
            ducklings = []
            try:
                hrz_lines = self.button_locs[f"button {i}"]["hlines"] 
            except KeyError as e:
                hrz_lines = {}
            else:
                # Compile the horizontal lines and add to "ducklings"
                try:
                    for length, thickness in zip(hrz_lines["lengths"], hrz_lines["thicknesses"]):
                        line = HLine(parent_widget, 
                                     self.button_locs[f"button {i}"]["x"], 
                                     self.button_locs[f"button {i}"]["y"],
                                     length, 
                                     thickness)
                        line.lower()
                        ducklings.append(line)
                except (TypeError, KeyError):
                    pass
            try:
                vrt_lines = self.button_locs[f"button {i}"]["vlines"]
            except KeyError:
                vrt_lines = {}
            # Compile the vertical lines and add to "ducklings"
            else:
                try:
                    for length, thickness in zip(vrt_lines["lengths"], vrt_lines["thicknesses"]):
                        line = VLine(parent_widget, 
                                     self.button_locs[f"button {i}"]["x"], 
                                     self.button_locs[f"button {i}"]["y"], 
                                     length, 
                                     thickness)
                        line.lower()
                        ducklings.append(line)
                except (TypeError, KeyError):
                    pass
            
            # Finally, create the button at the specified position and assign it ducklings 
            #   and a callback function
            start_pos = (self.button_locs[f"button {i}"]["x"], self.button_locs[f"button {i}"]["y"])
            button = CircleButton(radius=65, parent=parent_widget, start_pos=start_pos, ducklings=ducklings)
            button.setText(str(i))
            button.setFont(self.norm12)
            self.pneumatic_grid_buttons.append(button)
            button.clicked.connect(partial(self._on_push_pneumatic_button, button))

        return parent_widget
    
    def draw_pneumatic_grid_lines(self, parent_widget:QWidget):
        vlines = self.grid_lines["vlines"]
        hlines = self.grid_lines["hlines"]
        self.pneumatic_grid_lines = {"vlines": [], "hlines": []}
        for x, y, length, thickness in zip(vlines["starts"]["x"], vlines["starts"]["y"], vlines["lengths"], vlines["thicknesses"]):
            line = VLine(parent_widget, x, y, length, thickness)
            line.lower()
            self.pneumatic_grid_lines["vlines"].append(line)
        for x, y, length, thickness in zip(hlines["starts"]["x"], hlines["starts"]["y"], hlines["lengths"], hlines["thicknesses"]):
            line = HLine(parent_widget, x, y, length, thickness)
            line.lower()
            self.pneumatic_grid_lines["hlines"].append(line)

    
    def _on_edit_pneumatic_buttons(self):

        # Needs to be a class variable otherwise it goes out of scope        
        self.button_edit_window = AnotherWindow("Edit Valve Buttons")
        
        button_text = "Unlock Button Positions" if self.buttons_locked else "Lock Button Positions"
        button = self.default_button(button_text, self.norm12, self._control_pneumatic_button_movement, requires_self=True)
        button.setMinimumWidth(int(self.width()*0.15)) # Set our width to be 15% of the main window. Just to look nice
        self.button_edit_window.set_widget(button)

        button = self.default_button("Save Button Positions", self.norm12, self._save_pneumatic_button_positions)
        self.button_edit_window.set_widget(button)

        self.button_edit_window.show()

    def _on_push_pneumatic_button(self, button:CircleButton):          
        # Find the arduino pin that corresponds to our button number
        button_num = button.text()   
        try:
            pin = self.sensor_comms["Pneumatic valves"][f"Button {button_num}"]["digital pin"]
        except KeyError as e:
            logger.error(f"Could not find Button {button_num} in sensor_comms.yaml (Key error {e})")
            return
        # Send the arduino signal accordingly
        logger.info(f"Valve {button_num} set to {button.get_state()}")
        if button.is_open():
            self.sensor.arduino.set_pin_high(pin)
        else:
            self.sensor.arduino.set_pin_low(pin)

    def _control_pneumatic_button_movement(self, control_button:QPushButton):
        if self.pneumatic_grid_buttons[0].button_locked:
            for pneumatic_button in self.pneumatic_grid_buttons:
                pneumatic_button.unlock_button_movement() # Unlock the buttons
                control_button.setText("Lock Button Positions") # Change the button text to reflect the button status
                self.buttons_locked = False # Keep track of our own internal flag
            for line in self.pneumatic_grid_lines["vlines"]:
                line.unlock_line_movement()
            for line in self.pneumatic_grid_lines["hlines"]:
                line.unlock_line_movement()
        else:
            for pneumatic_button in self.pneumatic_grid_buttons:
                pneumatic_button.lock_button_movement()
                control_button.setText("Unlock Button Positions")
                self.buttons_locked = True
            for line in self.pneumatic_grid_lines["vlines"]:
                line.lock_line_movement()
            for line in self.pneumatic_grid_lines["hlines"]:
                line.lock_line_movement()

    def _save_pneumatic_button_positions(self):
        # button_loc_dic = {}
        for i, pneumatic_button in enumerate(self.pneumatic_grid_buttons, start=1):
            self.button_locs[f"button {i}"]["x"] = pneumatic_button.get_center()[0]
            self.button_locs[f"button {i}"]["y"] = pneumatic_button.get_center()[1]

        for line_type in ["vlines", "hlines"]:
            line_x = []
            line_y = []
            line_len = []
            line_thickness = []
            for line in self.pneumatic_grid_lines[line_type]:
                line_x.append(line.geometry().x())
                line_y.append(line.geometry().y())
                line_len.append(line.length)
                line_thickness.append(line.thickness)
            
            self.grid_lines[line_type]["starts"]["x"] = line_x
            self.grid_lines[line_type]["starts"]["y"] = line_y
            self.grid_lines[line_type]["lengths"] = line_len
            self.grid_lines[line_type]["thicknesses"] = line_thickness

        final_dict = {"Buttons": self.button_locs, "Lines": self.grid_lines}
        
        with open("config/button_locs.yaml", "w") as yaml_file:
            yaml.dump(final_dict, yaml_file, sort_keys=False)

    # Autonomous / manual control
    def build_pneum_ctrl_layout(self):
        pneum_control_layout = QVBoxLayout()
        # Layout title
        label = self.default_label("Pneumatic Valve Control", self.bold12)
        pneum_control_layout.addWidget(label)
        # Button to toggle manual/autonomous pneumatic valve mode control
        button = self.default_button(
                                    text="Enable Autonomous Valve Control", 
                                    callback=self._on_manual_valve_control, 
                                    requires_self=True)
        button.setCheckable(True) # Make the button toggle instead of push
        button.setStyleSheet("QPushButton"
                             "{"
                             "background-color : #D89F3F;"
                             "}"
                             "QPushButton::checked"
                             "{"
                             "background-color : #477FD4;"
                             "}"
                             ) 
        button.setMinimumWidth(int(label.width() * 3))
        pneum_control_layout.addWidget(button, alignment=Qt.AlignHCenter|Qt.AlignTop)
        # Automation routine section
        label = self.default_label("Automation Routine", self.norm12)
        pneum_control_layout.addWidget(label, alignment=Qt.AlignHCenter|Qt.AlignBottom)
        # Get the available routines
        self.auto_routine_dict = automation_routines.get_automation_routines()
        # Make a combobox to let the user choose the automation routine
        dropdown = QComboBox()
        dropdown.addItems(self.auto_routine_dict.keys())
        dropdown.setDisabled(True)
        dropdown.setFont(self.norm10)
        self.pneumatic_autonomous_controls.update({"dropdown":dropdown})
        pneum_control_layout.addWidget(dropdown, alignment=Qt.AlignTop)
        # Make buttons to play, pause, and stop the automation routine
        buttons_layout = QHBoxLayout()
        # Play
        button = self.default_button(callback=partial(self._on_start_autonomous, dropdown), enabled=False)
        button.setIcon(QIcon("doc/imgs/play.png"))
        self.pneumatic_autonomous_controls.update({"start":button})
        buttons_layout.addWidget(button, alignment=Qt.AlignTop) 
        # Pause
        button = self.default_button(callback=partial(self._on_pause_autonomous, dropdown), enabled=False)
        button.setIcon(QIcon("doc/imgs/pause.png"))
        self.pneumatic_autonomous_controls.update({"pause":button})
        buttons_layout.addWidget(button, alignment=Qt.AlignTop)
        # Stop
        button = self.default_button(callback=partial(self._on_stop_autonomous, dropdown), enabled=False)
        button.setIcon(QIcon("doc/imgs/stop.png"))
        self.pneumatic_autonomous_controls.update({"stop":button})
        buttons_layout.addWidget(button, alignment=Qt.AlignTop)
        pneum_control_layout.addLayout(buttons_layout)
        # Add two dividing lines, for panache
        for _ in range(2):
            line = self.dividing_line()
            pneum_control_layout.addWidget(line) 

        return pneum_control_layout

    def _on_manual_valve_control(self, button:QPushButton):
        # If button is checked, lock out manual controls
        if button.isChecked():
            button.setText("Enable Manual Valve Control")
            for pneumatic_button in self.pneumatic_grid_buttons:
                pneumatic_button.setDisabled(True)
            for _, control in self.pneumatic_autonomous_controls.items():
                control.setEnabled(True)
            self.sensor.close_arduino_serial()
        # If button is unchecked, lock out autonomous controls
        else:
            button.setText("Enable Autonomous Valve Control")
            for pneumatic_button in self.pneumatic_grid_buttons:
                pneumatic_button.setEnabled(True)
            for _, control in self.pneumatic_autonomous_controls.items():
                control.setDisabled(True)
            self.sensor.open_arduino_serial()

    def _on_start_autonomous(self, routine_select:QComboBox):
        routine_name = routine_select.currentText()
        logger.info(f"Starting autonomous routine: {routine_name}")
        
        # try to get our process status
        try:
            status = self.p.status()
        # we have not yet started - self.p doesn't exist
        except:
            pid = os.getpid()
            arduino = self.sensor.arduino
            self.multiprocess = multiprocessing.Process(target=self.auto_routine_dict[routine_name].run,
                                            # kwargs={"logger": logger, "arduino": arduino}
                                            kwargs={"logger": logger}
                                            )
            self.multiprocess.start()
            self.p = psutil.Process(self.multiprocess.pid)
        # we have started - self.p does exist
        else:
            if status == "stopped": # we're suspended
                self.p.resume()
            elif status == "sleeping" or status == "running": # we're running
                pass 
            else: # something has gone Wrong
                logger.warning(f"Unknown process status: {status}")

        self.pneumatic_autonomous_controls["start"].setDisabled(True)
        self.pneumatic_autonomous_controls["pause"].setEnabled(True)
        self.pneumatic_autonomous_controls["stop"].setEnabled(True)

    def _on_pause_autonomous(self, routine_select:QComboBox):
        routine_name = routine_select.currentText()
        logger.info(f"Pausing autonomous routine: {routine_name}")

        # Try to get our process status
        try:
            self.p.status()
        # If we can't, the process doesn't exist. We're have nothing to pause, so don't do anything
        except:
            pass
        # If we can, pause the process
        else:
            self.p.suspend()

        self.pneumatic_autonomous_controls["start"].setEnabled(True)

    def _on_stop_autonomous(self, routine_select:QComboBox):
        routine_name = routine_select.currentText()
        logger.info(f"Stopping autonomous routine: {routine_name}")

        # If our process is alive, kill it
        if self.multiprocess.is_alive():
            self.p.kill()
            self.multiprocess.terminate()
            self.multiprocess.join()

        self.pneumatic_autonomous_controls["start"].setEnabled(True)
        self.pneumatic_autonomous_controls["pause"].setDisabled(True)
        self.pneumatic_autonomous_controls["stop"].setDisabled(True)
            
    ## --------------------- STATUS PANEL --------------------- ##

    def build_status_layout(self):
        status_panel = QVBoxLayout()

        label = self.default_label("Status & Logs", self.bold16)
        status_panel.addWidget(label)

        list_widget = QTextEdit(self)
        # list_widget.setMaximumHeight(int(pneum_widget.height()*0.75))

        handler = GUIHandler(list_widget, level=logging.DEBUG)
        self.logger.addHandler(handler)
        formatter = logging.Formatter("%(levelname)s: %(asctime)s - %(name)s:  %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(formatter)
        self.GUI_log_handler = handler

        self.logger.info("Getting logger {0} - {1}".format(id(logger), logger.handlers))
        self.logger.debug("This is normal text")
        self.logger.warning("Watch out")
        self.logger.error("Something has gone wrong")
        self.logger.critical("Oh god everything is broken")

        status_panel.addWidget(list_widget, alignment=Qt.AlignTop)

        return status_panel

    ## --------------------- DATA STREAMING / LIVE PLOTTING --------------------- ##

    def build_plotting_layout(self):
        """
        A method to build the central plotting panel. Uses a QTabWidget to give us a conveinent way to display 
        the live sensor plots. For each sensor (stored in self.sensor_names), we add a tab to hold the 
        matplotlib figure and toolbar that will display sensor data.
        """
        plotting_layout = QVBoxLayout()
        # plotting_layout.setContentsMargins(10, 20, 10, 0)
        # Make a title
        label = QLabel(self)
        label.setText("Live Sensor Data")
        label.setFont(self.bold16)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        plotting_layout.addWidget(label)

        # Initialize the plotting flag
        self.data_collection = False

        # Create some object variables to hold plotting information - the QTabWidget that displays the figs, and a dictionary
        # to hold onto the figure objects themselves for later updating
        self.plot_tab = QTabWidget(self)
        self.plot_tab.setMinimumHeight(int(self.height()/2.25))
        self.plot_figs = {}
        # Loop through the sensors, create a figure & toolbar for each, and add them to the QTabWidget
        for sensor in self.sensor_names:
            # Create a new tab and give it a vertical layout
            tab = QWidget(self)
            tab.setObjectName(sensor)
            tab_vbox = QVBoxLayout(tab)
            # For each figure, we want a subplot corresponding to each piece of data returned by the sensor. Grab that number
            num_subplots = len(self.big_data_dict[sensor]["Data"])
            # Create the figure and toolbar
            fig = MyFigureCanvas(x_init=[[np.nan]]*num_subplots,   # List of lists, one for each subplot, to initialize the figure x-data
                                 y_init=[[np.nan]]*num_subplots, # List of lists, one for each subplot, to initialize the figure y-data
                                 xlabels=["Time"]*num_subplots,
                                 ylabels=list(self.big_data_dict[sensor]["Data"].keys()),
                                 num_subplots=num_subplots,
                                 x_range=self.default_plot_length, # Set xlimit range of each axis
                                 )
            toolbar = NavigationToolbar(canvas=fig, parent=self, coordinates=False)
            # Create a button to plot the entire day of data in a separate window
            button = QPushButton("Plot Entire Day")
            button.setFont(self.norm12)
            button.setEnabled(False)
            button.pressed.connect(partial(self.plot_entire_day, sensor))
            button.setMaximumHeight(50)
            # Add the figure, toolbar, and button to this tab's layout
            tab_vbox.addWidget(toolbar, alignment=Qt.AlignHCenter)
            tab_vbox.addWidget(fig)
            tab_vbox.addWidget(button)
            # Add this tab to the QTabWidget
            self.plot_tab.addTab(tab, sensor)
            # Hold onto the figure object for later
            self.plot_figs.update({sensor: fig})
        # Once we've done all that, add the QTabWidget to the main layout
        plotting_layout.addWidget(self.plot_tab)

        return plotting_layout

    def _thread_plots(self):
        """Method to update the live plots with the buffers stored in self.big_data_dict
        """
        # Grab the name of the current QTabWidget tab we're on (which sensor data we're displaying)
        plot_name = self.plot_tab.currentWidget().objectName()
        fig = self.plot_figs[plot_name]
        # Make sure the figure is the correct object - not strictly necessary, but a good safety check
        if type(fig) == MyFigureCanvas:
            # Grab the updated x and y values from the big data buffer
            x_data_list, y_data_list = self.get_xy_data_from_buffer(plot_name)
            # Pass the updated data into the figure object and redraw the axes
            fig.update_data(x_new=x_data_list, y_new=y_data_list)
            fig.update_canvas()
    
    def update_plots(self):
        """Method to start a thread that will update the live plots with the buffers stored in self.big_data_dict
        """
        # If the data collection flag is active...
        if self.data_collection:
            worker = Worker(self._thread_plots)
            self.threadpool.start(worker)

    def get_xy_data_from_buffer(self, plot_name:str):
        """Method to parse the big data buffer and pull out the sensor channels we're interested in plotting.

        Args:
            plot_name (str): The name of the QWidget we're plotting on, should match a sensor in self.sensor names or be "All" for the
                main page plots

        Returns:
            x_data_list (list): List of deques from self.big_data_dict - timestamp for each sensor channel

            **y_data_list** (list): List of deques from self.big_data_dict - data for each sensor channel
        """
        # Try to extract "plot_name" from the big buffer - if it's a sensor, we'll be able to pull the data directly
        try:
            # Extract data from the buffer
            num_subplots = len(self.big_data_dict[plot_name]["Data"].keys())
            t = self.big_data_dict[plot_name]["Time (epoch)"]
            y = list(self.big_data_dict[plot_name]["Data"].values())
            # Convert from UTC epoch time to pacific time, passing in the y_data too to ensure the arrays
            # stay the same shape
            t_pacific_time, y_data_list = epoch_to_pacific_time(t, y)
            # All sensor channels have the same timestamp, so make n_subplots copies of the time
            x_data_list = [t_pacific_time]*num_subplots 
            
        # If we can't find it in the buffer (and we should never get here since all dict keys are passed in externally), 
        # something went wrong. The plots safely don't update if we pass in None, so do that
        except KeyError as e:
            logger.error(f"Error in reading the data buffer when updating plots: {e}")
            x_data_list = None
            y_data_list = None

        return x_data_list, y_data_list

    def _get_entire_day_data(self, sensor):
        """Method that reads the big data saving csv, pulls out the channels of the sensor we want,
        and returns them.

        Args:
            sensor (str): The name of the sensor, must match a key in self.big_data_dict

        Returns:
            result (tuple): tuple of (sensor: *str*, data: *dict*)
        """
        # Grab the filepath of the data csv from the writer object
        filepath = self.writer.get_data_directory()
        # Grab the data channels we have for this sensor - we'll use these to get data from the csv
        channels = list(self.big_data_dict[sensor]["Data"].keys())
        # Add time so we can get that too
        channels.append("time (epoch)")
        # The data is saved to the csv in the form "Sensor Name": "Channel Name", so format it here
        cols = [f"{sensor}: {channel}" for channel in channels]
        try:
            data = pd.read_csv(filepath, delimiter=',', header=0, usecols=cols)
        except FileNotFoundError as e:
            logger.warning(f"Error in accessing csv data: {e}")
            data = {}

        return sensor, data
    
    def _update_entire_day_plot(self, result):
        """Method that triggers when the threaded self._get_entire_day_data finishes, 
        giving us the dictionary of sensor data pulled from the csv file. 

        Args:
            result (tuple): tuple of (sensor: *str*, data: *dict*)
        """
        # The thread retuns the name of the sensor and the dictionary of data
        sensor, data = result
        # Grab some metadata from the big_data_dict - the channels of data we have for this sensor, and the 
        # number of subplots we need to display them all
        channels = list(self.big_data_dict[sensor]["Data"].keys())
        num_subplots = len(channels)
        # Pull the time from the data input and convert it from UTC epoch time to Pacific time
        t = (data[f"{sensor}: time (epoch)"]).values
        y = [data[f"{sensor}: {channel}"] for channel in channels]
        t_pacific_time, y_data = epoch_to_pacific_time(t, y)
        # Create a figure and toolbar with the data for each sensor channel
        fig = MyFigureCanvas(x_init=[t_pacific_time]*num_subplots,
                             y_init=y_data,
                             num_subplots=num_subplots,
                             xlabels=["Datetime"]*num_subplots,
                             ylabels=channels,
                             x_range=len(t),
                             )
        toolbar = NavigationToolbar(fig, self)
        # Create another window, add the widgets, and show the window
        self.plot_window = AnotherWindow(title=sensor)
        self.plot_window.set_widget(toolbar)
        self.plot_window.set_widget(fig)
        self.plot_window.show()

    def plot_entire_day(self, sensor:str):
        """Method to spin up a thread that plots the entire day's worth of data and displays it on another window.

        Args:
            sensor (str): The name of the sensor, must match a key in self.big_data_dict
        """
        # Set up the thread to grab sensor data from the csv
        worker = Worker(self._get_entire_day_data, sensor)
        # When the thread finishes, display the result
        worker.signals.result.connect(self._update_entire_day_plot)
        # Start the thread
        self.threadpool.start(worker)
        

    ## --------------------- DATA COLLECTION PIPELINE --------------------- ##

    def init_data_pipeline(self):
        """Creates objects of the Sensor(), Interpreter(), and Display() classes, and sets busses and delay times 
        for each sense/interpret/save process (see run_data_collection for how these are all used)
        """
        # Create each main object of the pipeline
        self.sensor = Sensor(custom_logger=logger, debug=False)
        self.interpreter = Interpreter()
        self.writer = Writer()

        # Initialize a bus for each thread we plan to spin up later
        self.abakus_bus = Bus()
        self.flowmeter_sli2000_bus = Bus()
        self.flowmeter_sls1500_bus = Bus()
        self.laser_bus = Bus()
        self.picarro_gas_bus = Bus()
        self.bronkhorst_bus = Bus()
        self.main_interp_bus = Bus()

    def init_data_buffer(self):
        """Method to read in and save the sensor_data configuration yaml file

        Updates:
            **self.big_data_dict**: *dict* - Holds buffer of data with key-value pairs 'Sensor Name':deque[data buffer]

            **self.sensor_names**: *list* - Sensor names that correspond to the buffer dict keys

        """
        # Read in the sensor data config file to initialize the data buffer. 
        # Creates a properly formatted, empty dictionary to store timestamps and data readings to each sensor
        try:
            with open("config/sensor_data.yaml", 'r') as stream:
                self.big_data_dict = yaml.safe_load(stream)
        except FileNotFoundError as e:
            logger.error(f"Error in loading the sensor data config file: {e}")
            self.big_data_dict = {}

        # Comb through the keys, set the timestamp to the current time and the data to zero
        sensor_names = self.big_data_dict.keys()
        self.instrument_names = list(sensor_names)
        self.sensor_names = list(sensor_names)
        for name in sensor_names:
            try:
                channels = self.big_data_dict[name]["Data"].keys()
                self.big_data_dict[name]["Time (epoch)"] = deque([np.nan], maxlen=self.max_buffer_length)
                for channel in channels:
                    self.big_data_dict[name]["Data"][channel] = deque([np.nan], maxlen=self.max_buffer_length)
            except KeyError as e:
                print(f"Trouble reading {name} sensor data: {e}")
                self.sensor_names.remove(name)

        # Grab the names of the sensors from the dictionary

    def _thread_data_collection(self):
        """Method to spin up threads for each sensor, plus the interpreter and the writer. 
        Allows us to take, process, and save data (mostly) simultaneously

        Returns:
            data (dict): Big dictionary of processed sensor data, has the same structure as self.big_data_dict
        """
        # Create a ThreadPoolExecutor to accomplish a bunch of tasks at once. These threads pass data between themselves with busses (which handle
        # proper locking, so we're not trying to read and write at the same time) and return a big dictionary of the most recent processed sensor data
        try:
            with concurrent.futures.ThreadPoolExecutor() as self.executor:
                self.executor.submit(self.sensor.abakus_producer, self.abakus_bus)
                self.executor.submit(self.sensor.flowmeter_sli2000_producer, self.flowmeter_sli2000_bus)
                self.executor.submit(self.sensor.flowmeter_sls1500_producer, self.flowmeter_sls1500_bus)
                self.executor.submit(self.sensor.laser_producer, self.laser_bus)
                self.executor.submit(self.sensor.picarro_gas_producer, self.picarro_gas_bus)
                self.executor.submit(self.sensor.bronkhorst_producer, self.bronkhorst_bus)
                self.executor.submit(self.interpreter.main_consumer_producer, self.abakus_bus, self.flowmeter_sli2000_bus,
                                            self.flowmeter_sls1500_bus, self.laser_bus, self.picarro_gas_bus, self.bronkhorst_bus, 
                                            self.main_interp_bus)

                eWriter = self.executor.submit(self.writer.write_consumer, self.main_interp_bus)
        except RuntimeError as e:
            logger.warning(f"Encountered Error in data threading: {e}")

        # Get the processed data from the final class (also blocks until everything has completed its task)
        data = eWriter.result()
        return data
    
    def _update_buffer(self, new_data:dict):
        """Method to update the self.big_data_dict buffer with new data from the sensor pipeline.
        
        Args:
            new_data (dict): Most recent data update. Should have the same key/value structure as big_data_dict
            use_noise (bool): Adds some random noise if true. For testing only
        """
        # For each sensor, grab the timestamp and the data from each sensor channel
        for name in self.sensor_names:
            # Grab and append the timestamp
            try:    # Check if the dictionary key exists... 
                new_time = new_data[name]["Time (epoch)"]  
                self.big_data_dict[name]["Time (epoch)"].append(new_time)
            except KeyError as e:   # ... otherwise log an exception
                logger.warning(f"Error updating the {name} buffer timestamp: {e}")
            except TypeError as e:  # Sometimes due to threading shenanigans it comes through as "NoneType", check for that too
                logger.warning(f"Error updating the {name} buffer timestamp: {e}")
                pass
            
            # Grab and append the data from each channel
            channels = list(self.big_data_dict[name]["Data"].keys())
            for channel in channels:
                try:    # Check if the dictionary key exists... 
                    ch_data = new_data[name]["Data"][channel]
                    self.big_data_dict[name]["Data"][channel].append(ch_data)
                except KeyError:    # ... otherwise log an exception
                    logger.warning(f"Error updating the {name} buffer data: {e}")
                    pass
                except TypeError as e: 
                    logger.warning(f"Error updating the {name} buffer data: {e}")
                    pass
    
    def run_data_collection(self):
        """Method to complete the entire sense/interpret/save data pipeline once. This is called by a timer way back in __init__, so gets triggered every time that
        timer fires. It spins up a bunch of threads to gather data from each sensor, pass raw data into the interpretor class, and save the processed data
        """
        # If data collection is active...
        if self.data_collection:
            # Set up a thread to go query all the instruments once and process their results
            worker = Worker(self._thread_data_collection)
            # Once that's finished, trigger the method to save the results to our internal data buffer
            worker.signals.result.connect(self._update_buffer)
            # Spin up the thread
            self.threadpool.start(worker)

###################################### HELPER CLASSES ######################################

## --------------------- SEPARATE WINDOW --------------------- ##
class AnotherWindow(QWidget):
    """This class is a skeleton window with the capability of adding external widgets. If we need another window 
    (e.g to plot all that day's data on a new screen) we can call this class and add widgets. It's bare-bones and
    really only good for simple windows; if you need more functionality, you'd probably want to make a custom class.

    Args:
        QWidget (QWidget): Inherits from the general QWidget class
    """
    def __init__(self, title="New Window"):
        super().__init__()
        self.setWindowTitle(title)
        # Give the window a single layout
        self.my_layout = QVBoxLayout()
        self.setLayout(self.my_layout)

    def set_widget(self, widget:QWidget):
        """Simple method to add a widget to the layout.

        Args:
            widget (QWidget): The widget to be added
        """
        self.my_layout.addWidget(widget)


## --------------------- PYQT THREADING --------------------- ##
class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.

    Supported signals are:
        - finished: None
        - error: tuple (exctype, value, traceback.format_exc() )
        - result: anything (object data returned from processing)
        - progress: int indicating % progress
    """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

class Worker(QRunnable):
    """
    Worker thread

    Inherits from QRunnable to handle worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function
    """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except: # If there's an error, report it
            exctype, value = sys.exc_info()[:2]
            logger.error(traceback.print_exc((exctype, value, traceback.format_exc())))
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit() # Done


# If we're running from this script, spin up QApplication and start the GUI
if __name__ == "__main__":
    qapp = QtWidgets.QApplication(sys.argv)
    app = ApplicationWindow()

    qapp.exec_()