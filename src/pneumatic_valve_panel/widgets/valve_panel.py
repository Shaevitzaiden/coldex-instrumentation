from __future__ import annotations

from functools import partial
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from ..controllers.valve_controller import ValveController
from ..models import AttachedLine, PanelConfig, PanelLine, ValveButtonConfig
from .circular_valve_button import CircularValveButton


class ValvePanel(QtWidgets.QWidget):
    """Config-driven pneumatic valve panel.

    This widget owns only GUI concerns: button creation, line drawing, edit-mode
    layout changes, and user interaction events. It delegates hardware actions
    to ``ValveController``.
    """

    message = QtCore.pyqtSignal(str)
    valve_state_changed = QtCore.pyqtSignal(str, bool)
    layout_changed = QtCore.pyqtSignal()

    def __init__(
        self,
        *,
        panel_config: PanelConfig,
        controller: Optional[ValveController] = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel_config = panel_config
        self.controller = controller
        self._edit_mode = False
        self._buttons: dict[str, CircularValveButton] = {}

        self.setMinimumSize(self.panel_config.width, self.panel_config.height)
        self.setAutoFillBackground(True)
        self._set_background_color(QtGui.QColor(248, 248, 248))
        self.rebuild()

    def set_controller(self, controller: ValveController | None) -> None:
        self.controller = controller

    def set_panel_config(self, panel_config: PanelConfig) -> None:
        self.panel_config = panel_config
        self.setMinimumSize(self.panel_config.width, self.panel_config.height)
        self.rebuild()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        for button in self._buttons.values():
            button.set_edit_mode(enabled)
        self.message.emit("Layout edit mode ON" if enabled else "Layout edit mode OFF")
        self.update()

    def rebuild(self) -> None:
        for button in self._buttons.values():
            button.setParent(None)
            button.deleteLater()
        self._buttons.clear()

        for button_config in self.panel_config.buttons:
            self._create_button(button_config)
        self.update()

    def sync_button_positions_to_config(self) -> None:
        for button_config in self.panel_config.buttons:
            button = self._buttons.get(button_config.id)
            if button is not None:
                center = button.center()
                button_config.center = (center.x(), center.y())

    def set_all_buttons_checked(self, checked: bool, *, send: bool = True) -> None:
        for valve_id, button in self._buttons.items():
            if not button.isEnabled():
                continue
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)
            if send and self.controller is not None:
                self.controller.set_valve_state(valve_id, checked)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        for line in self.panel_config.lines:
            self._draw_panel_line(painter, line)

        for button_config in self.panel_config.buttons:
            for line in button_config.attached_lines:
                self._draw_attached_line(painter, button_config.center, line)

    def _create_button(self, button_config: ValveButtonConfig) -> None:
        radius = int(button_config.radius or self.panel_config.button_radius)
        button = CircularValveButton(label=button_config.label, radius=radius, parent=self)
        button.setObjectName(button_config.id)
        button.setEnabled(button_config.enabled)
        button.setChecked(button_config.initially_open)
        button.set_center(QtCore.QPoint(*button_config.center))
        button.setToolTip(self._make_tooltip(button_config))
        button.set_edit_mode(self._edit_mode)
        button.toggled.connect(partial(self._on_button_toggled, button_config.id))
        button.moved.connect(partial(self._on_button_moved, button_config.id))
        button.show()
        self._buttons[button_config.id] = button

    def _on_button_toggled(self, valve_id: str, is_open: bool) -> None:
        if self._edit_mode:
            return
        try:
            if self.controller is not None:
                self.controller.set_valve_state(valve_id, is_open)
        except Exception as exc:  # keep GUI state synchronized if hardware command fails
            button = self._buttons[valve_id]
            button.blockSignals(True)
            button.setChecked(not is_open)
            button.blockSignals(False)
            self.message.emit(f"Valve command failed for {valve_id}: {exc}")
            raise

        state = "OPEN" if is_open else "CLOSED"
        self.message.emit(f"{valve_id} -> {state}")
        self.valve_state_changed.emit(valve_id, is_open)
        self.update()

    def _on_button_moved(self, valve_id: str, center: QtCore.QPoint) -> None:
        if not self._edit_mode:
            return
        for button_config in self.panel_config.buttons:
            if button_config.id == valve_id:
                button_config.center = (center.x(), center.y())
                break
        self.layout_changed.emit()
        self.update()

    def _draw_panel_line(self, painter: QtGui.QPainter, line: PanelLine) -> None:
        start = QtCore.QPoint(*line.start)
        if line.orientation == "h":
            end = QtCore.QPoint(start.x() + line.length, start.y())
        else:
            end = QtCore.QPoint(start.x(), start.y() + line.length)
        self._draw_line(painter, start, end, line.thickness)

    def _draw_attached_line(
        self,
        painter: QtGui.QPainter,
        center_xy: tuple[int, int],
        line: AttachedLine,
    ) -> None:
        start = QtCore.QPoint(*center_xy)
        if line.orientation == "h":
            end = QtCore.QPoint(start.x() + line.length, start.y())
        else:
            end = QtCore.QPoint(start.x(), start.y() + line.length)
        self._draw_line(painter, start, end, line.thickness)

    def _draw_line(
        self,
        painter: QtGui.QPainter,
        start: QtCore.QPoint,
        end: QtCore.QPoint,
        thickness: int,
    ) -> None:
        pen = QtGui.QPen(QtGui.QColor(60, 60, 60), int(thickness))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(start, end)

    def _make_tooltip(self, button_config: ValveButtonConfig) -> str:
        return (
            f"Valve: {button_config.id}\n"
            f"Label: {button_config.label}\n"
            f"Command ID: {button_config.command_id}\n"
            f"Metadata: {button_config.metadata}"
        )

    def _set_background_color(self, color: QtGui.QColor) -> None:
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, color)
        self.setPalette(palette)
