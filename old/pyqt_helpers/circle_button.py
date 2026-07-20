from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import numpy as np

try:
    from lines import VLine, HLine
except ModuleNotFoundError:
    from pyqt_helpers.lines import VLine, HLine

class CircleButton(QPushButton):
    def __init__(self, radius:int=None, parent:QObject=None, start_pos:tuple=(0,0), locked=True, ducklings=[]):
        super().__init__(parent)
        
        ### ----- general ----- ###
        self.set_radius(radius)
        # Flag to keep track of the button "state" - pneumatic valve open or closed
        self.button_open = False
        self.ducklings = ducklings
        self.init_button_position(start_pos)
        
        ### ----- colors ----- ###
        closed_light = QColor(247, 217, 126, 255)
        closed_mid = QColor(255, 193, 7, 255)
        closed_dark = QColor(214, 165, 18, 255)

        open_light = QColor(249, 149, 148)
        open_mid = QColor(241, 108, 107, 255)
        open_dark = QColor(216, 27, 96, 255)

        self.closed_color_gradients = self.create_color_gradients(closed_light, closed_mid, closed_dark)
        self.open_color_gradients = self.create_color_gradients(open_light, open_mid, open_dark)
        self.disabled_color_gradients = self.create_color_gradients(self.palette().color(self.palette().Light),
                                                                    self.palette().color(self.palette().Midlight),
                                                                    self.palette().color(self.palette().Dark))

        ### ----- movement ----- ###
        self._mouse_press_pos = self.geometry().center() # Position of mouse click, initialized to reasonable QPoint
        self._mouse_move_pos = self.geometry().center() # Position of mouse movement, initialized to reasonable QPoint
        self.button_locked = locked  # Are we allowing the button to move
        self.move_threshold = 3 #px

    def init_button_position(self, start_pos):
        start_pos = QPoint(int(start_pos[0]-self.radius/2), int(start_pos[1]-self.radius/2))
        super().move(start_pos)
    
    def create_color_gradients(self, light:QColor, mid:QColor, dark:QColor):
        """A method to create nice gradients between the selected colors to make the button look like
        a 3D object. Graphic deign go brr!

        It's not as scary as it looks, but it's still pretty magical. I don't fully know how it works, sourced from 
        https://www.riverbankcomputing.com/pipermail/pyqt/2020-March/042586.html

        Args:
            light (QColor): _description_
            mid (QColor): _description_
            dark (QColor): _description_

        Returns:
            _type_: _description_
        """
        # a radial gradient for the "shadow effect" when button is unpressed
        backgroundUp = QConicalGradient(.5, .5, 135)

        backgroundUp.setCoordinateMode(backgroundUp.ObjectBoundingMode)
        backgroundUp.setStops([
            (0.0, light),
            (0.3, dark),
            (0.6, dark),
            (1.0, light),
        ])

        # the same as above, but inverted for pressed state
        backgroundDown = QConicalGradient(.5, .5, 315)

        backgroundDown.setCoordinateMode(backgroundDown.ObjectBoundingMode)
        backgroundDown.setStops(backgroundUp.stops())

        # a "mask" for the conical gradient
        ringShapeDown = QRadialGradient(.5, .5, .5)

        ringShapeDown.setCoordinateMode(ringShapeDown.ObjectBoundingMode)
        ringShapeDown.setStops([
            (0.7536231884057971, mid),
            (0.7960662525879917, QtCore.Qt.transparent),
        ])

        ringShapeUp = QRadialGradient(.5, .5, .5)

        ringShapeUp.setCoordinateMode(ringShapeUp.ObjectBoundingMode)
        ringShapeUp.setStops([
            (0.7536231884057971, mid),
            (0.7960662525879917, QtCore.Qt.transparent),
            (0.9627329192546584, QtCore.Qt.transparent),
        ])

        return backgroundUp, backgroundDown, ringShapeUp, ringShapeDown
    
    def change_button_state(self):
        """Mostly does what it says on the tin. Flips our internal flag that keeps track of the 'state' of the 
        button - since these correspond to pneumatic valves, the state is either 'open' or 'closed'"""
        if self.button_open == False:
            self.button_open = True
        else:
            self.button_open = False

    def get_state(self) -> str:
        if self.button_open:
            return "OPEN"
        else:
            return "CLOSED"
        
    def is_open(self):
        if self.button_open:
            return True
        else:
            return False

    def lock_button_movement(self):
        self.button_locked = True

    def unlock_button_movement(self):
        self.button_locked = False

    def get_center(self):
        return self.geometry().center().x(), self.geometry().center().y()

    def set_radius(self, radius=None):
        """Method to set the button radius. If left blank, sets the radius as twice the button font size

        Args:
            radius (int): Desired radius in px of the button
        """
        # If not provided, set the radius as twice the font size
        if radius is None:
            radius = self.font().pointSize() * 2
        # Update the internal variable
        self.radius = radius
        # Notify the layout manager that the size hint has changed
        self.updateGeometry()
    
    def get_button_rect(self) -> QRect:
        """Creates a QRect object based on the internal button size

        Returns:
            rect: QRect
        """
        # just a helper function to avoid repetitions
        size = min(self.width(), self.height()) - 1
        rect = QtCore.QRect(0, 0, size, size)
        rect.moveCenter(self.rect().center())
        return rect

    def mousePressEvent(self, event):
        """Overwrites the QPushButton mouesPressEvent method with modifications for our circular, movable button"""
        # Ensure that the click happens within the circle 
        path = QPainterPath()
        path.addEllipse(QtCore.QRectF(self.get_button_rect()))
        # If it does, continue
        if path.contains(event.pos()):
            # Record the position where we clicked (for movement)
            self._mouse_press_pos = event.globalPos()
            self._mouse_move_pos = event.globalPos()
            # Call the parent class method
            super().mousePressEvent(event)
            # Change colors
            # self.change_button_state()

    def sizeHint(self):
        """Overwrites the QPushButton sizeHint method to hold the recommended size for the widget"""
        return QtCore.QSize(self.radius, self.radius)
    
    def hasHeightForWidth(self):
        """Overwrites the QPushButton hasHeightForWidth method. That method normally 
        returns true if the widget's preferred height depends on its width and otherwise returns false. In our case, only return True

        Returns:
            True
        """
        return True

    def heightForWidth(self, width):
        """Overwrites the QPushButton heightForWidth method. Returns the preferred height for this widget, given the width w.

        Args:
            width (int): width in px

        Returns:
            width
        """
        return width

    
    def paint_text(self, qp:QPainter):
        rect = self.get_button_rect()

        fm = QFontMetrics(self.font())
        width = fm.horizontalAdvance(self.text())
        height = fm.height()
        pos = QPoint(rect.center().x() - int(width/2), rect.center().y() + int(height/2.75))
        
        qp.setPen(QColor(0, 0, 0, 255))
        qp.drawText(pos, self.text())

    def paintEvent(self, event):
        """Overwrites the paintEvent method. Renders the circular button"""
        qp = QPainter(self)
        qp.setRenderHints(qp.Antialiasing)
        qp.translate(.5, .5)
        qp.setPen(QtCore.Qt.NoPen)
        rect = self.get_button_rect()
        if self.isEnabled():
            # Render if the button is pressed (based on "backgroundDown" and "ringShapeDown" color gradients)
            if self.isDown() or self.isChecked():
                # Render yellow if we're in the open state
                if self.button_open:
                    qp.setBrush(self.open_color_gradients[1])
                    qp.drawEllipse(rect)
                    qp.setBrush(self.open_color_gradients[3])
                    qp.drawEllipse(rect)
                # Otherwise render red if we're in the closed state
                else:
                    qp.setBrush(self.closed_color_gradients[1])
                    qp.drawEllipse(rect)
                    qp.setBrush(self.closed_color_gradients[3])
                    qp.drawEllipse(rect)
            # Render if the button is not pressed (based on "backgroundUp" and "ringShapeUp" color gradients)
            else:
                # Render yellow if we're in the open state
                if self.button_open:
                    qp.setBrush(self.open_color_gradients[0])
                    qp.drawEllipse(rect)
                    qp.setBrush(self.open_color_gradients[2])
                    qp.drawEllipse(rect)
                # Otherwise render red if we're in the closed state
                else:
                    qp.setBrush(self.closed_color_gradients[0])
                    qp.drawEllipse(rect)
                    qp.setBrush(self.closed_color_gradients[2])
                    qp.drawEllipse(rect)
            
        else:
            qp.setBrush(self.disabled_color_gradients[0])
            qp.drawEllipse(rect)
            qp.setBrush(self.disabled_color_gradients[2])
            qp.drawEllipse(rect)
        
        self.paint_text(qp)


    def mouseMoveEvent(self, event:QMouseEvent):
        """Overwrites the QPushButton mouseMoveEvent method. Records the position of the mouse movement, finds the difference
        between that position and the button, and moves the button
        """
        # If we're allowing the button to move...
        if self.button_locked == False:
            # Adjust offset from clicked point to origin of widget
            currPos = self.mapToGlobal(self.pos())
            globalPos = event.globalPos()
            diff = globalPos - self._mouse_move_pos
            newPos = self.mapFromGlobal(currPos + diff)
            
            super().move(newPos)

            self._mouse_move_pos = globalPos

        # Trigger the original mouseReleaseEvent callback
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event:QMouseEvent):
        """Overwrites the QPushButton mouseReleaseEvent method. Ignores the button click if we've
        moved the button more than a threshold value"""
        
        moved = event.globalPos() - self._mouse_press_pos 
        # If we've moved, we shouldn't click the button
        if moved.manhattanLength() > self.move_threshold:
            event.ignore()
        # If we haven't moved, we should click the button
        else:
            self.change_button_state()
            super().mouseReleaseEvent(event)
    
    def set_vert_geometry(self, child:VLine):
        # Create a new geometry for the child object
        new_geo = QRect()
        # Set the left and right of the vertical rectangle - 
            # The same as the button, offset by its thickness
        child_thickness = child.geometry().width()
        new_geo.setLeft(self.geometry().center().x() - int(child_thickness/2))
        new_geo.setRight(self.geometry().center().x() + int(child_thickness/2))
        # Set the top and bottom, depending on which side of the "baseline"
            # the button is currently on
        if child.geometry().bottom() > (self.geometry().center().y() + 10):
            new_geo.setTop(self.geometry().center().y())
            new_geo.setBottom(child.baseline())
            child.setGeometry(new_geo)
        elif child.geometry().bottom() < (self.geometry().center().y() + 10):
            new_geo.setBottom(self.geometry().center().y())
            new_geo.setTop(child.baseline())
        # Assign the child that new geometry
            child.setGeometry(new_geo)

    def set_hrz_geometry(self, child:HLine):
        # Create a blank new geometry object
        new_geo = QRect()
        # Set the top and bottom of the horizontal rectangle - 
            # The same as the button, offset by its thickness
        child_thickness = child.geometry().height()
        new_geo.setTop(self.geometry().center().y() - int(child_thickness/2))
        new_geo.setBottom(self.geometry().center().y() + int(child_thickness/2))
        # Set the left and right, depending on which side of the "baseline"
            # the button is currently on
        if child.geometry().right() > (self.geometry().center().x() + 10):
            new_geo.setLeft(self.geometry().center().x())
            new_geo.setRight(child.baseline())
        elif child.geometry().right() < (self.geometry().center().x() + 10):
            new_geo.setRight(self.geometry().center().x())
            new_geo.setLeft(child.baseline())

        # Assign the child that new geometry
        child.setGeometry(new_geo)
    
    def set_geometry_child(self, child:QFrame):
        if child.frameShape() == QFrame.VLine:
            self.set_vert_geometry(child)
        elif child.frameShape() == QFrame.HLine:
            self.set_hrz_geometry(child)
        else:
            print(f"Unknown child geometry")


    def moveEvent(self, event:QMoveEvent):
        # Make sure the button is never moved outside of the parent object
        a0 = event.pos()
        if self.parentWidget() is not None:
            # Cap each cardinal extreme of the circular button to make sure they stay within the parent dimensions
            if self.geometry().right() >= self.parentWidget().size().width():
                a0.setX(self.parentWidget().size().width() - self.radius)
            if self.geometry().left() < 0:
                a0.setX(0)
            if self.geometry().top() < 0:
                a0.setY(0)
            if self.geometry().bottom() >= self.parentWidget().size().height():
                a0.setY(self.parentWidget().size().height() - self.radius)

        
        
        # move each child object
        if self.ducklings is not None:
            for child in self.ducklings:
                self.set_geometry_child(child)

        super().move(a0)
                    
        super().moveEvent(event)


if __name__ == "__main__":
    import sys

    def clicked():
        print("clicked!")

    qapp = QApplication(sys.argv)
    w = QWidget()
    w.setMinimumSize(100, 100)
    w.setMaximumSize(500, 500)

    myButton = CircleButton(100, w, locked=False, start_pos=(50, 110))
    myButton.clicked.connect(clicked)
    myButton.setText("hi!")
    myButton.setFont(QFont("Helvetica", 12))

    w.show()
    qapp.exec_()