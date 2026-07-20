import sys
import logging
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import *


class GUIHandler(logging.Handler, QtCore.QObject):
    appendText = QtCore.pyqtSignal(str)
    setBackgroundColor = QtCore.pyqtSignal(QColor)
    setTextColor = QtCore.pyqtSignal(QColor)

    def __init__(self, parent:QtWidgets.QTextEdit, level):
        super().__init__(level)
        QtCore.QObject.__init__(self)
        
        # self.widget = parent QtWidgets.QTextEdit(parent)
        self.widget = parent

        self.widget.setReadOnly(True)
        self.appendText.connect(self.widget.append)
        self.setBackgroundColor.connect(self.widget.setTextBackgroundColor)
        self.setTextColor.connect(self.widget.setTextColor)

        self.backgroundColors = {
                            "DEBUG": QColor(25, 162, 135, 255),
                            "INFO": QColor(151, 195, 214, 255),
                            "WARNING": QColor(255, 149, 0, 255),
                            "ERROR": QColor(189, 74, 28, 255),
                            "CRITICAL": QColor(111, 0, 0, 255),
        }

        self.textColors = {
                            "DEBUG": QColor(0, 0, 0, 255),
                            "INFO": QColor(0, 0, 0, 255),
                            "WARNING": QColor(0, 0, 0, 255),
                            "ERROR": QColor(0, 0, 0, 255),
                            "CRITICAL": QColor(255, 255, 255, 255),
        }

    def emit(self, record):
        bg_color = self.backgroundColors[record.levelname]
        self.setBackgroundColor.emit(bg_color)

        txt_color = self.textColors[record.levelname]
        self.setTextColor.emit(txt_color)

        out = self.format(record)
        self.appendText.emit(out)


if __name__ == "__main__":
    log = logging.getLogger("Foo")
    log.setLevel(logging.DEBUG)

    app = QtWidgets.QApplication(sys.argv)

    widget = QtWidgets.QTextEdit()
    handler = GUIHandler(widget, level=logging.DEBUG)
    log.addHandler(handler)

    formatter = logging.Formatter("%(levelname)s: %(asctime)s - %(name)s:  %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)

    log.info("Getting logger {0} - {1}".format(id(log), log.handlers))
    log.debug("This is normal text")
    log.warning("Watch out")
    log.error("Something has gone wrong")
    log.critical("Oh god everything is broken")

    widget.show()
    sys.exit(app.exec_())