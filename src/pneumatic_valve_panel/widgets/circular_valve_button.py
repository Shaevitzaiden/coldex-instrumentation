from __future__ import annotations

from PyQt5 import QtCore, QtGui, QtWidgets


class CircularValveButton(QtWidgets.QPushButton):
    """Round, checkable valve button with optional drag-to-position edit mode."""

    moved = QtCore.pyqtSignal(QtCore.QPoint)

    def __init__(
        self,
        *,
        label: str,
        radius: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(label, parent)
        self.radius = int(radius)
        self._edit_mode = False
        self._drag_start_global = QtCore.QPoint()
        self._drag_start_widget = QtCore.QPoint()
        self._drag_moved = False
        self._drag_threshold_px = 3

        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMinimumSize(self.radius, self.radius)
        self.setMaximumSize(self.radius, self.radius)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        self.setCursor(QtCore.Qt.SizeAllCursor if enabled else QtCore.Qt.PointingHandCursor)

    def set_center(self, center: QtCore.QPoint) -> None:
        self.move(center.x() - self.radius // 2, center.y() - self.radius // 2)

    def center(self) -> QtCore.QPoint:
        return QtCore.QPoint(self.x() + self.width() // 2, self.y() + self.height() // 2)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.radius, self.radius)

    def hitButton(self, pos: QtCore.QPoint) -> bool:  # noqa: N802 - Qt API name
        center = QtCore.QPoint(self.width() // 2, self.height() // 2)
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        return (dx * dx + dy * dy) <= (self.width() // 2) ** 2

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._edit_mode and event.button() == QtCore.Qt.LeftButton:
            self._drag_start_global = event.globalPos()
            self._drag_start_widget = self.pos()
            self._drag_moved = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._edit_mode and event.buttons() & QtCore.Qt.LeftButton:
            delta = event.globalPos() - self._drag_start_global
            if delta.manhattanLength() > self._drag_threshold_px:
                self._drag_moved = True
            self.move(self._drag_start_widget + delta)
            self.moved.emit(self.center())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._edit_mode and event.button() == QtCore.Qt.LeftButton:
            self.moved.emit(self.center())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)

        rect = QtCore.QRectF(1, 1, self.width() - 2, self.height() - 2)
        base_color = self._base_color()

        gradient = QtGui.QRadialGradient(rect.center(), rect.width() * 0.65)
        gradient.setColorAt(0.0, base_color.lighter(135))
        gradient.setColorAt(0.65, base_color)
        gradient.setColorAt(1.0, base_color.darker(150))
        painter.setBrush(QtGui.QBrush(gradient))
        painter.drawEllipse(rect)

        border_pen = QtGui.QPen(base_color.darker(180), 2)
        painter.setPen(border_pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))

        if self._edit_mode:
            painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40), 1, QtCore.Qt.DashLine))
            painter.drawEllipse(rect.adjusted(5, 5, -5, -5))

        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), QtCore.Qt.AlignCenter, self.text())

    def _base_color(self) -> QtGui.QColor:
        if not self.isEnabled():
            return QtGui.QColor(180, 180, 180)
        if self.isChecked():
            return QtGui.QColor(241, 108, 107)  # open
        return QtGui.QColor(255, 193, 7)  # closed
