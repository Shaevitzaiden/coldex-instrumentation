from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

class HLine(QFrame):
    """A horizontal line"""
    def __init__(self, parent, start_x=0, start_y=0, init_length=50, thickness=20):
        super().__init__(parent)
        self.setMinimumHeight(thickness)
        self.setMidLineWidth(thickness)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)

        parent_width = self.parentWidget().geometry().width()
        parent_height = self.parentWidget().geometry().height()

        # make sure the line shows up at the beginning by seeding it with a geometry
        # if init_length < 0:
        #     self.setGeometry(0,0,0,0)
        # else:
        #     self.setGeometry(parent_width, parent_height, 0, 0)
        self.setGeometry(start_x, start_y, init_length, 0)

        baseline = start_x + init_length
        self.setBaseline(baseline)

        self.thickness = thickness
        self.length = init_length

        # Movement params
        self.line_locked = True
        self._mouse_press_pos = None
        self._mouse_move_pos = None

    def baseline(self):
        return self.baseline_position
    
    def setBaseline(self, baseline):
        self.baseline_position = baseline

    def unlock_line_movement(self):
        self.line_locked = False

    def lock_line_movement(self):
        self.line_locked = True

    def mousePressEvent(self, event:QMouseEvent):
        """Overwrites the default mouse click callback. Every time we click the mouse, record the position"""
        self._mouse_press_pos = event.globalPos()
        self._mouse_move_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event:QMouseEvent):
        """Overwrites the QPushButton mouseMoveEvent method. Records the position of the mouse movement, finds the difference
        between that position and the button, and moves the button
        """
        # If we're allowing the line to move...
        if self.line_locked == False:
            # Adjust offset from clicked point to origin of widget
            currPos = self.mapToGlobal(self.pos())
            globalPos = event.globalPos()
            diff = globalPos - self._mouse_move_pos
            newPos = self.mapFromGlobal(currPos + diff)
            # Move and record
            super().move(newPos)
            self._mouse_move_pos = globalPos
    
class VLine(QFrame):
    """A vertical line"""
    def __init__(self, parent, start_x=0, start_y=0, init_length=50, thickness=20):
        super().__init__(parent)
        self.setMinimumWidth(thickness)
        self.setMidLineWidth(thickness)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)

        
        parent_height = self.parentWidget().geometry().height()
        parent_width = self.parentWidget().geometry().width()

        baseline = start_y + init_length
        self.setBaseline(baseline)

        self.thickness = thickness
        self.length = init_length

        # make sure the line shows up at the beginning by seeding it with a geometry
        # if init_length < 0:
        #     self.setGeometry(0,0,0,0)
        # else:
        #     self.setGeometry(parent_width, parent_height, 0, 0)

        self.setGeometry(start_x, start_y, 0, init_length)

        # Movement params
        self.line_locked = True
        self._mouse_press_pos = None
        self._mouse_move_pos = None
    
    def baseline(self):
        return self.baseline_position
    
    def setBaseline(self, baseline):
        self.baseline_position = baseline

    def unlock_line_movement(self):
        self.line_locked = False

    def lock_line_movement(self):
        self.line_locked = True

    def mousePressEvent(self, event:QMouseEvent):
        """Overwrites the default mouse click callback. Every time we click the mouse, record the position"""
        self._mouse_press_pos = event.globalPos()
        self._mouse_move_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event:QMouseEvent):
        """Overwrites the QPushButton mouseMoveEvent method. Records the position of the mouse movement, finds the difference
        between that position and the button, and moves the button
        """
        # If we're allowing the line to move...
        if self.line_locked == False:
            # Adjust offset from clicked point to origin of widget
            currPos = self.mapToGlobal(self.pos())
            globalPos = event.globalPos()
            diff = globalPos - self._mouse_move_pos
            newPos = self.mapFromGlobal(currPos + diff)
            # Move and record
            super().move(newPos)
            self._mouse_move_pos = globalPos
    
        
if __name__ == "__main__":
    import sys
    from circle_button import CircleButton
    import yaml

    with open("config/button_locs.yaml", "r") as stream:
        button_locs = yaml.safe_load(stream)

    app = QApplication(sys.argv)
    widget = QWidget()
    widget.setGeometry(0, 0, 500, 500)

    mybutton = "button 3"

    # hrz_lines = button_locs["Buttons"][mybutton]["hlines"]
    vrt_lines = button_locs["Buttons"][mybutton]["vlines"]

    ducklings = []
    for length, thickness in zip(vrt_lines["lengths"], vrt_lines["thicknesses"]):
        line = VLine(widget, button_locs["Buttons"][mybutton]["x"], button_locs["Buttons"][mybutton]["y"], length, thickness)
        ducklings.append(line)

    # for length, thickness in zip(hrz_lines["lengths"], hrz_lines["thicknesses"]):
    #     line = HLine(widget, button_locs["Buttons"][mybutton]["x"], length, thickness)
    #     ducklings.append(line)

    print(widget.geometry().size()) 

    button = CircleButton(50, 
                          widget, 
                          start_pos=(button_locs["Buttons"][mybutton]["x"], button_locs["Buttons"][mybutton]["y"]),
                          ducklings=ducklings, 
                          locked=False)
    
    print(button.geometry().center())

    widget.show()
    app.exec()

    button_loc_dic = {}
    button_loc_dic.update({"button 1": {"x":button.geometry().center().x(), "y":button.geometry().center().y()}})
    print(button_loc_dic)