from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from collections import deque
import time
import matplotlib.pyplot as plt

try:
    from pyqt_helpers.helpers import epoch_to_pacific_time
except ModuleNotFoundError:
    from helpers import epoch_to_pacific_time

## --------------------- PLOTTING --------------------- ##
class MyFigureCanvas(FigureCanvas):
    """This is the FigureCanvas in which a live plot is drawn."""
    def __init__(self, x_init:deque, y_init:deque, xlabels:list, ylabels:list, num_subplots=1, x_range=60, axis_titles=None) -> None:
        """
        :param x_init:          Initial x-data
        :param y_init:          Initial y-data
        :param x_range:         How much data we show on the x-axis, in x-axis units

        """
        super().__init__(plt.Figure())

        # Initialize constructor arguments
        self.x_data = x_init
        self.y_data = y_init
        self.x_range = x_range
        self.num_subplots = num_subplots

        # Generate the number of subplots requested
        self.figure.subplots(num_subplots, 1)
        self.axs = self.figure.get_axes()

        # Initialize each axis with the provided axes names and initial data
        for i, ax in enumerate(self.axs):
            ax.plot(x_init[i], y_init[i], '.--')
            ax.set_xlabel(xlabels[i])
            ax.set_ylabel(ylabels[i])
            if axis_titles is not None:
                ax.set_title(axis_titles[i])

        # Set a figure size
        self.figure.set_figheight(4*num_subplots)
        self.figure.tight_layout()
        
        self.draw()   

    def update_data(self, x_new=None, y_new=None):
        """Method to update the variables to plot. If nothing is given, doesn't update data - safety catch in case something has gone wrong with the GUI"""    
        if x_new is None:
            pass
        else:
            self.x_data = x_new

        if y_new is None:
            pass
        else:
            self.y_data = y_new

    def update_canvas(self) -> None:
        """Method to update the plots based on the buffers stored in self.x_data and self.y_data"""
        # Loop through the number of subplots in this figure
        for i, ax in enumerate(self.axs):
            # Clear the figure without resetting the axis bounds or ticks
            for artist in ax.lines:
                artist.remove()
            # Plot the updated data
            ax.plot(self.x_data[i], self.y_data[i], '.--')
            # Make sure we aren't either plotting offscreen or letting the x axis get too long
            # We can't do math directly with Timestamp objects, so do the math in epoch time and then convert
            current_time = time.time()
            desired_x_min = current_time - self.x_range
            current_time_datetime, _ = epoch_to_pacific_time(current_time)
            x_min_datetime, _ = epoch_to_pacific_time(desired_x_min)
            # Set the limits
            ax.set_xlim([x_min_datetime, current_time_datetime])
        # Finally, update the plot
        self.draw()

if __name__ == "__main__":
    import sys
    import numpy as np
    from collections import deque
    from PyQt5.QtWidgets import *

    app = QApplication(sys.argv)
    widget = QWidget()
    layout = QVBoxLayout()

    x = deque([0, 1, 2, 3, 4])
    y = deque(np.random.randint(-5, 5, size=len(x)))
    plot = MyFigureCanvas([x], [y], ["x axis"], ["y axis"], num_subplots=1)

    layout.addWidget(plot)

    widget.setLayout(layout)
    widget.show()
    app.exec()
