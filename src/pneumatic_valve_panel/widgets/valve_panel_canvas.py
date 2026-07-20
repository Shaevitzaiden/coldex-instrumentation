from __future__ import annotations

import copy
import math
from typing import Literal

from PyQt5 import QtCore, QtGui, QtWidgets

from ..controllers.pneumatic_controller import PneumaticController
from ..models import ActuatedElementConfig, PanelConfig, PipeConfig, ValveTypeSpec

SelectionKind = Literal["element", "pipe"]
SelectionItem = tuple[SelectionKind, str]


class ValvePanelCanvas(QtWidgets.QWidget):
    """Scalable pneumatic panel with runtime-control and edit-canvas modes."""

    message = QtCore.pyqtSignal(str)
    layout_changed = QtCore.pyqtSignal()
    state_changed = QtCore.pyqtSignal()
    selection_changed = QtCore.pyqtSignal(str, str)  # primary kind, primary id
    selection_items_changed = QtCore.pyqtSignal(object)  # list[SelectionItem]
    pipe_mode_changed = QtCore.pyqtSignal(bool)
    edit_requested = QtCore.pyqtSignal(str, str)  # kind, id
    history_changed = QtCore.pyqtSignal(bool, bool)  # can_undo, can_redo

    def __init__(
        self,
        *,
        panel_config: PanelConfig,
        controller: PneumaticController | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel_config = panel_config
        self.controller = controller

        self._edit_mode = False
        self._selected_items: set[SelectionItem] = set()
        self._primary_selection: SelectionItem | None = None

        self._dragging_selection = False
        self._drag_history_recorded = False
        self._last_drag_design_pos = QtCore.QPointF()

        self._rubber_selecting = False
        self._rubber_start = QtCore.QPointF()
        self._rubber_current = QtCore.QPointF()

        self._panning = False
        self._last_pan_widget_pos = QtCore.QPointF()
        self._space_pressed = False

        self._pipe_creation_mode = False
        self._pending_pipe_start: tuple[float, float] | None = None

        self.show_grid = True
        self.snap_to_grid = True
        self.grid_spacing = 25.0
        self._zoom = 1.0
        self._pan = QtCore.QPointF(0.0, 0.0)

        self._undo_stack: list[tuple[str, dict]] = []
        self._redo_stack: list[tuple[str, dict]] = []
        self._max_history = 100
        self._restoring_history = False

        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMinimumSize(500, 300)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setAutoFillBackground(False)

    # ------------------------------------------------------------------
    # Basic properties and public API
    # ------------------------------------------------------------------
    def sizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt API name
        return QtCore.QSize(int(self.panel_config.design_width), int(self.panel_config.design_height))

    @property
    def selected_kind(self) -> SelectionKind | None:
        return self._primary_selection[0] if self._primary_selection else None

    @property
    def selected_id(self) -> str | None:
        return self._primary_selection[1] if self._primary_selection else None

    def selected_items(self) -> list[SelectionItem]:
        return sorted(self._selected_items, key=lambda item: (item[0], item[1]))

    def set_controller(self, controller: PneumaticController | None) -> None:
        self.controller = controller

    def set_panel_config(self, panel_config: PanelConfig) -> None:
        self.panel_config = panel_config
        self.clear_selection()
        self.clear_history()
        self.end_pipe_creation()
        self.fit_to_window()
        self.updateGeometry()
        self.update()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        if not self._edit_mode:
            self.end_pipe_creation()
            self.clear_selection()
            self.fit_to_window()
        self.message.emit("Edit mode ON" if self._edit_mode else "Runtime mode ON")
        self.update()

    def is_edit_mode(self) -> bool:
        return self._edit_mode

    def set_show_grid(self, enabled: bool) -> None:
        self.show_grid = bool(enabled)
        self.update()

    def set_snap_to_grid(self, enabled: bool) -> None:
        self.snap_to_grid = bool(enabled)
        self.message.emit("Snap to grid ON" if self.snap_to_grid else "Snap to grid OFF")
        self.update()

    def set_grid_spacing(self, spacing: float) -> None:
        self.grid_spacing = max(2.0, float(spacing))
        self.update()

    def begin_pipe_creation(self) -> None:
        if not self._edit_mode:
            self.set_edit_mode(True)
        self._pipe_creation_mode = True
        self._pending_pipe_start = None
        self.pipe_mode_changed.emit(True)
        self.message.emit("Pipe mode: click a first endpoint, then click a second endpoint. Endpoints snap to elements/grid.")
        self.setFocus()
        self.update()

    def end_pipe_creation(self) -> None:
        was_active = self._pipe_creation_mode
        self._pipe_creation_mode = False
        self._pending_pipe_start = None
        if was_active:
            self.pipe_mode_changed.emit(False)
        self.update()

    def center_of_visible_scene(self) -> tuple[float, float]:
        widget_center = QtCore.QPointF(self.width() / 2.0, self.height() / 2.0)
        design = self.widget_to_design(widget_center)
        return design.x(), design.y()

    # ------------------------------------------------------------------
    # Undo/redo history
    # ------------------------------------------------------------------
    def _snapshot(self) -> dict:
        return copy.deepcopy(self.panel_config.to_dict())

    def record_history(self, description: str) -> None:
        if self._restoring_history:
            return
        self._undo_stack.append((description, self._snapshot()))
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self.history_changed.emit(self.can_undo(), self.can_redo())

    def clear_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.history_changed.emit(False, False)

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> None:
        if not self._undo_stack:
            self.message.emit("Nothing to undo")
            return
        description, snapshot = self._undo_stack.pop()
        self._redo_stack.append((description, self._snapshot()))
        self._restore_snapshot(snapshot)
        self.message.emit(f"Undid: {description}")
        self.history_changed.emit(self.can_undo(), self.can_redo())

    def redo(self) -> None:
        if not self._redo_stack:
            self.message.emit("Nothing to redo")
            return
        description, snapshot = self._redo_stack.pop()
        self._undo_stack.append((description, self._snapshot()))
        self._restore_snapshot(snapshot)
        self.message.emit(f"Redid: {description}")
        self.history_changed.emit(self.can_undo(), self.can_redo())

    def _restore_snapshot(self, snapshot: dict) -> None:
        self._restoring_history = True
        try:
            restored = PanelConfig.from_dict(copy.deepcopy(snapshot))
            self.panel_config.__dict__.update(restored.__dict__)
            self._drop_invalid_selection()
            self.layout_changed.emit()
            self.updateGeometry()
            self.update()
        finally:
            self._restoring_history = False

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def clear_selection(self) -> None:
        self._selected_items.clear()
        self._primary_selection = None
        self._emit_selection_changed()
        self.update()

    def select_element(self, element_id: str, *, additive: bool = False) -> None:
        self._select_item(("element", element_id), additive=additive)

    def select_pipe(self, pipe_id: str, *, additive: bool = False) -> None:
        self._select_item(("pipe", pipe_id), additive=additive)

    def select_items(self, items: list[SelectionItem]) -> None:
        self._selected_items = set(items)
        self._primary_selection = items[-1] if items else None
        self._emit_selection_changed()
        self.update()

    def _select_item(self, item: SelectionItem, *, additive: bool = False) -> None:
        if additive:
            if item in self._selected_items:
                self._selected_items.remove(item)
                if self._primary_selection == item:
                    self._primary_selection = next(iter(self._selected_items), None)
            else:
                self._selected_items.add(item)
                self._primary_selection = item
        else:
            self._selected_items = {item}
            self._primary_selection = item
        self._emit_selection_changed()
        self.message.emit(f"Selected {item[0]}: {item[1]}" if item in self._selected_items else "Selection updated")
        self.update()

    def _emit_selection_changed(self) -> None:
        if self._primary_selection is None:
            self.selection_changed.emit("", "")
        else:
            self.selection_changed.emit(self._primary_selection[0], self._primary_selection[1])
        self.selection_items_changed.emit(self.selected_items())

    def _drop_invalid_selection(self) -> None:
        valid_elements = {element.id for element in self.panel_config.elements}
        valid_pipes = {pipe.id for pipe in self.panel_config.pipes}
        self._selected_items = {
            item for item in self._selected_items
            if (item[0] == "element" and item[1] in valid_elements)
            or (item[0] == "pipe" and item[1] in valid_pipes)
        }
        if self._primary_selection not in self._selected_items:
            self._primary_selection = next(iter(self._selected_items), None)
        self._emit_selection_changed()

    def selected_element(self) -> ActuatedElementConfig | None:
        if self._primary_selection is None or self._primary_selection[0] != "element":
            return None
        try:
            return self.panel_config.element_by_id(self._primary_selection[1])
        except KeyError:
            self._drop_invalid_selection()
            return None

    def selected_pipe(self) -> PipeConfig | None:
        if self._primary_selection is None or self._primary_selection[0] != "pipe":
            return None
        try:
            return self.panel_config.pipe_by_id(self._primary_selection[1])
        except KeyError:
            self._drop_invalid_selection()
            return None

    # ------------------------------------------------------------------
    # Layout mutations
    # ------------------------------------------------------------------
    def add_element(self, element: ActuatedElementConfig) -> None:
        self.record_history(f"add element {element.id}")
        element.center = self._snap_point_to_grid(element.center)
        self.panel_config.elements.append(element)
        self.select_element(element.id)
        self._layout_mutated(f"Added element {element.id}")

    def update_element(self, original_id: str, replacement: ActuatedElementConfig) -> None:
        self.record_history(f"edit element {original_id}")
        for index, element in enumerate(self.panel_config.elements):
            if element.id == original_id:
                self.panel_config.elements[index] = replacement
                self.select_element(replacement.id)
                self._layout_mutated(f"Updated element {replacement.id}")
                return
        raise KeyError(f"Unknown element: {original_id}")

    def update_pipe(self, original_id: str, replacement: PipeConfig) -> None:
        self.record_history(f"edit pipe {original_id}")
        for index, pipe in enumerate(self.panel_config.pipes):
            if pipe.id == original_id:
                self.panel_config.pipes[index] = replacement
                self.select_pipe(replacement.id)
                self._layout_mutated(f"Updated pipe {replacement.id}")
                return
        raise KeyError(f"Unknown pipe: {original_id}")

    def add_pipe(self, pipe: PipeConfig) -> None:
        self.record_history(f"add pipe {pipe.id}")
        self.panel_config.pipes.append(pipe)
        self.select_pipe(pipe.id)
        self._layout_mutated(f"Added pipe {pipe.id}")

    def delete_selected(self) -> None:
        if not self._selected_items:
            self.message.emit("Nothing selected")
            return
        self.record_history("delete selected")
        removed = list(self._selected_items)
        remove_elements = {item_id for kind, item_id in removed if kind == "element"}
        remove_pipes = {item_id for kind, item_id in removed if kind == "pipe"}
        self.panel_config.elements = [element for element in self.panel_config.elements if element.id not in remove_elements]
        self.panel_config.pipes = [pipe for pipe in self.panel_config.pipes if pipe.id not in remove_pipes]
        count = len(removed)
        self.clear_selection()
        self._layout_mutated(f"Deleted {count} item(s)")

    def rotate_selected(self, degrees: float = 90.0) -> None:
        if not self._selected_items:
            self.message.emit("Nothing selected")
            return
        self.record_history(f"rotate selected {degrees:g}°")
        for kind, item_id in list(self._selected_items):
            if kind == "element":
                element = self.panel_config.element_by_id(item_id)
                element.rotation = (element.rotation + degrees) % 360.0
            elif kind == "pipe":
                pipe = self.panel_config.pipe_by_id(item_id)
                pipe.start, pipe.end = _rotate_segment(pipe.start, pipe.end, degrees)
                if self.snap_to_grid:
                    pipe.start = self._snap_point_to_grid(pipe.start)
                    pipe.end = self._snap_point_to_grid(pipe.end)
        self._layout_mutated(f"Rotated selected item(s) by {degrees:g}°")

    def nudge_selected(self, dx: float, dy: float) -> None:
        if not self._selected_items:
            return
        self.record_history("nudge selected")
        self._move_selected(dx, dy)
        self._layout_mutated(f"Nudged selected by ({dx:g}, {dy:g})")

    def align_selected(self, mode: str) -> None:
        elements = [self.panel_config.element_by_id(item_id) for kind, item_id in self._selected_items if kind == "element"]
        if len(elements) < 2:
            self.message.emit("Select at least two elements to align")
            return
        self.record_history(f"align {mode}")
        if mode == "left":
            target = min(e.center[0] - e.size[0] / 2 for e in elements)
            for e in elements:
                e.center = (target + e.size[0] / 2, e.center[1])
        elif mode == "right":
            target = max(e.center[0] + e.size[0] / 2 for e in elements)
            for e in elements:
                e.center = (target - e.size[0] / 2, e.center[1])
        elif mode == "top":
            target = min(e.center[1] - e.size[1] / 2 for e in elements)
            for e in elements:
                e.center = (e.center[0], target + e.size[1] / 2)
        elif mode == "bottom":
            target = max(e.center[1] + e.size[1] / 2 for e in elements)
            for e in elements:
                e.center = (e.center[0], target - e.size[1] / 2)
        elif mode == "center_x":
            target = sum(e.center[0] for e in elements) / len(elements)
            for e in elements:
                e.center = (target, e.center[1])
        elif mode == "center_y":
            target = sum(e.center[1] for e in elements) / len(elements)
            for e in elements:
                e.center = (e.center[0], target)
        else:
            self.message.emit(f"Unknown align mode: {mode}")
            return
        self._layout_mutated(f"Aligned {len(elements)} elements")

    def distribute_selected(self, axis: str) -> None:
        elements = [self.panel_config.element_by_id(item_id) for kind, item_id in self._selected_items if kind == "element"]
        if len(elements) < 3:
            self.message.emit("Select at least three elements to distribute")
            return
        self.record_history(f"distribute {axis}")
        if axis == "horizontal":
            elements.sort(key=lambda e: e.center[0])
            start = elements[0].center[0]
            end = elements[-1].center[0]
            step = (end - start) / (len(elements) - 1)
            for i, element in enumerate(elements):
                element.center = (start + step * i, element.center[1])
        elif axis == "vertical":
            elements.sort(key=lambda e: e.center[1])
            start = elements[0].center[1]
            end = elements[-1].center[1]
            step = (end - start) / (len(elements) - 1)
            for i, element in enumerate(elements):
                element.center = (element.center[0], start + step * i)
        else:
            self.message.emit(f"Unknown distribute axis: {axis}")
            return
        self._layout_mutated(f"Distributed {len(elements)} elements")

    def _layout_mutated(self, message: str) -> None:
        self.layout_changed.emit()
        self.message.emit(message)
        self.update()

    # ------------------------------------------------------------------
    # Runtime state commands
    # ------------------------------------------------------------------
    def set_all_elements_state(self, active: bool, *, send: bool = True) -> None:
        if self._edit_mode:
            self.message.emit("Runtime commands are disabled while editing the layout")
            return
        for element in self.panel_config.elements:
            if not element.enabled:
                continue
            if send and self.controller is not None:
                self.controller.set_element_state(element.id, active)
            element.initially_active = active
        self.state_changed.emit()
        self.update()

    def _toggle_element(self, element_id: str) -> None:
        if self._edit_mode:
            return
        element = self.panel_config.element_by_id(element_id)
        if not element.enabled:
            self.message.emit(f"{element.id} is disabled")
            return
        new_state = not element.initially_active
        if self.controller is not None:
            self.controller.set_element_state(element.id, new_state)
        element.initially_active = new_state
        self.state_changed.emit()
        self.message.emit(f"{element.id} -> {'ACTIVE/OPEN' if new_state else 'INACTIVE/CLOSED'}")
        self.update()

    # ------------------------------------------------------------------
    # Pan / zoom / coordinate transforms
    # ------------------------------------------------------------------
    def fit_to_window(self) -> None:
        self._zoom = 1.0
        self._pan = QtCore.QPointF(0.0, 0.0)
        self.update()

    def zoom_by(self, factor: float, *, anchor_widget_pos: QtCore.QPointF | None = None) -> None:
        if not self._edit_mode:
            return
        anchor_widget_pos = anchor_widget_pos or QtCore.QPointF(self.width() / 2.0, self.height() / 2.0)
        anchor_design = self.widget_to_design(anchor_widget_pos)
        self._zoom = max(0.15, min(8.0, self._zoom * factor))
        base_offset, scale = self._scene_transform_parts(ignore_pan=True)
        self._pan = QtCore.QPointF(
            anchor_widget_pos.x() - anchor_design.x() * scale - base_offset.x(),
            anchor_widget_pos.y() - anchor_design.y() * scale - base_offset.y(),
        )
        self.update()

    def widget_to_design(self, point: QtCore.QPointF) -> QtCore.QPointF:
        offset, scale = self._scene_transform_parts()
        if scale <= 0:
            return QtCore.QPointF(point)
        return QtCore.QPointF((point.x() - offset.x()) / scale, (point.y() - offset.y()) / scale)

    def design_to_widget(self, point: QtCore.QPointF) -> QtCore.QPointF:
        offset, scale = self._scene_transform_parts()
        return QtCore.QPointF(point.x() * scale + offset.x(), point.y() * scale + offset.y())

    def _scene_transform_parts(self, *, ignore_pan: bool = False) -> tuple[QtCore.QPointF, float]:
        design_w = max(float(self.panel_config.design_width), 1.0)
        design_h = max(float(self.panel_config.design_height), 1.0)
        fit_scale = min(self.width() / design_w, self.height() / design_h)
        if fit_scale <= 0:
            fit_scale = 1.0
        scale = fit_scale * (self._zoom if self._edit_mode else 1.0)
        base_offset = QtCore.QPointF(
            (self.width() - design_w * fit_scale) / 2.0,
            (self.height() - design_h * fit_scale) / 2.0,
        )
        pan = QtCore.QPointF(0.0, 0.0) if ignore_pan or not self._edit_mode else self._pan
        return base_offset + pan, scale

    # ------------------------------------------------------------------
    # Qt events
    # ------------------------------------------------------------------
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802 - Qt API name
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(235, 235, 235))

        offset, scale = self._scene_transform_parts()
        painter.translate(offset)
        painter.scale(scale, scale)

        scene_rect = QtCore.QRectF(0, 0, self.panel_config.design_width, self.panel_config.design_height)
        painter.fillRect(scene_rect, QtGui.QColor(self.panel_config.background_color))
        painter.setPen(QtGui.QPen(QtGui.QColor(190, 190, 190), 1.0 / max(scale, 0.0001)))
        painter.drawRect(scene_rect)

        self._draw_grid(painter, scale)

        for pipe in self.panel_config.pipes:
            self._draw_pipe(painter, pipe, selected=self._is_selected("pipe", pipe.id))

        if self._pipe_creation_mode and self._pending_pipe_start is not None:
            self._draw_pending_pipe_hint(painter)

        for element in self.panel_config.elements:
            spec = self.panel_config.type_spec_for(element.element_type)
            self._draw_element(painter, element, spec, selected=self._is_selected("element", element.id))

        if self._rubber_selecting:
            self._draw_rubber_band(painter)

        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API name
        if event.button() not in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton, QtCore.Qt.MiddleButton):
            return super().mousePressEvent(event)

        self.setFocus()
        widget_pos = QtCore.QPointF(event.pos())
        design_pos = self.widget_to_design(widget_pos)
        point = (design_pos.x(), design_pos.y())
        hit_kind, hit_id = self._hit_test(point)

        if event.button() == QtCore.Qt.MiddleButton or (
            event.button() == QtCore.Qt.LeftButton and self._edit_mode and self._space_pressed
        ):
            self._panning = True
            self._last_pan_widget_pos = widget_pos
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == QtCore.Qt.RightButton:
            if hit_kind == "element" and hit_id is not None:
                self.select_element(hit_id)
                self.edit_requested.emit("element", hit_id)
                event.accept()
                return
            if hit_kind == "pipe" and hit_id is not None:
                self.select_pipe(hit_id)
                self.edit_requested.emit("pipe", hit_id)
                event.accept()
                return
            if self._edit_mode:
                self.clear_selection()
                event.accept()
                return
            return super().mousePressEvent(event)

        if self._pipe_creation_mode:
            self._handle_pipe_creation_click(point)
            event.accept()
            return

        if not self._edit_mode:
            if hit_kind == "element" and hit_id is not None:
                self._toggle_element(hit_id)
                event.accept()
                return
            return super().mousePressEvent(event)

        additive = bool(event.modifiers() & QtCore.Qt.ControlModifier)
        if hit_kind == "element" and hit_id is not None:
            item: SelectionItem = ("element", hit_id)
            if additive:
                self._select_item(item, additive=True)
            elif item not in self._selected_items:
                self.select_element(hit_id)
            else:
                self._primary_selection = item
                self._emit_selection_changed()
            self._dragging_selection = True
            self._drag_history_recorded = False
            self._last_drag_design_pos = design_pos
            event.accept()
            return
        if hit_kind == "pipe" and hit_id is not None:
            item = ("pipe", hit_id)
            if additive:
                self._select_item(item, additive=True)
            elif item not in self._selected_items:
                self.select_pipe(hit_id)
            else:
                self._primary_selection = item
                self._emit_selection_changed()
            self._dragging_selection = True
            self._drag_history_recorded = False
            self._last_drag_design_pos = design_pos
            event.accept()
            return

        self._rubber_selecting = True
        self._rubber_start = design_pos
        self._rubber_current = design_pos
        if not additive:
            self.clear_selection()
        event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API name
        widget_pos = QtCore.QPointF(event.pos())
        if self._panning:
            delta = widget_pos - self._last_pan_widget_pos
            self._last_pan_widget_pos = widget_pos
            self._pan += delta
            self.update()
            event.accept()
            return

        if not self._edit_mode:
            return super().mouseMoveEvent(event)

        design_pos = self.widget_to_design(widget_pos)
        if self._rubber_selecting:
            self._rubber_current = design_pos
            self.update()
            event.accept()
            return

        if self._dragging_selection:
            dx = design_pos.x() - self._last_drag_design_pos.x()
            dy = design_pos.y() - self._last_drag_design_pos.y()
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                if abs(dx) >= abs(dy):
                    dy = 0.0
                else:
                    dx = 0.0
            self._last_drag_design_pos = design_pos
            if not self._drag_history_recorded and (abs(dx) > 0.001 or abs(dy) > 0.001):
                self.record_history("move selected")
                self._drag_history_recorded = True
            self._move_selected(dx, dy)
            event.accept()
            return
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API name
        if self._panning and event.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.LeftButton):
            self._panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return

        if event.button() == QtCore.Qt.LeftButton and self._rubber_selecting:
            additive = bool(event.modifiers() & QtCore.Qt.ControlModifier)
            items = self._items_in_rubber_band()
            if additive:
                self.select_items(list(self._selected_items.union(items)))
            else:
                self.select_items(items)
            self._rubber_selecting = False
            self.update()
            event.accept()
            return

        if event.button() == QtCore.Qt.LeftButton and self._dragging_selection:
            self._dragging_selection = False
            if self._drag_history_recorded:
                if self.snap_to_grid and not (event.modifiers() & QtCore.Qt.AltModifier):
                    self._snap_selected_items_to_grid()
                self.layout_changed.emit()
            self._drag_history_recorded = False
            self.update()
            event.accept()
            return
        return super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API name
        design_pos = self.widget_to_design(QtCore.QPointF(event.pos()))
        hit_kind, hit_id = self._hit_test((design_pos.x(), design_pos.y()))
        if hit_kind == "element" and hit_id is not None:
            self.select_element(hit_id)
            if self._edit_mode:
                self.edit_requested.emit("element", hit_id)
        elif hit_kind == "pipe" and hit_id is not None:
            self.select_pipe(hit_id)
            if self._edit_mode:
                self.edit_requested.emit("pipe", hit_id)
        event.accept()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802 - Qt API name
        if not self._edit_mode:
            return super().wheelEvent(event)
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self.zoom_by(factor, anchor_widget_pos=QtCore.QPointF(event.pos()))
        event.accept()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802 - Qt API name
        key = event.key()
        if key == QtCore.Qt.Key_Space:
            self._space_pressed = True
            if self._edit_mode:
                self.setCursor(QtCore.Qt.OpenHandCursor)
            event.accept()
            return
        if key == QtCore.Qt.Key_Escape:
            if self._pipe_creation_mode:
                self.end_pipe_creation()
                self.message.emit("Pipe creation canceled")
            elif self._rubber_selecting:
                self._rubber_selecting = False
            elif self._edit_mode:
                self.clear_selection()
            else:
                return super().keyPressEvent(event)
            event.accept()
            return
        if not self._edit_mode:
            return super().keyPressEvent(event)

        if event.modifiers() & QtCore.Qt.ControlModifier and key == QtCore.Qt.Key_Z:
            self.undo()
            event.accept()
            return
        if event.modifiers() & QtCore.Qt.ControlModifier and key == QtCore.Qt.Key_Y:
            self.redo()
            event.accept()
            return
        if key in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        if key == QtCore.Qt.Key_R:
            degrees = -90.0 if event.modifiers() & QtCore.Qt.ShiftModifier else 90.0
            self.rotate_selected(degrees)
            event.accept()
            return
        if key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            step = self.grid_spacing if event.modifiers() & QtCore.Qt.ShiftModifier else 5.0
            dx = -step if key == QtCore.Qt.Key_Left else step if key == QtCore.Qt.Key_Right else 0.0
            dy = -step if key == QtCore.Qt.Key_Up else step if key == QtCore.Qt.Key_Down else 0.0
            self.nudge_selected(dx, dy)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802 - Qt API name
        if event.key() == QtCore.Qt.Key_Space:
            self._space_pressed = False
            if not self._panning:
                self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return
        return super().keyReleaseEvent(event)

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def _draw_grid(self, painter: QtGui.QPainter, scale: float) -> None:
        if not self._edit_mode or not self.show_grid:
            return
        spacing = max(2.0, self.grid_spacing)
        minor_pen = QtGui.QPen(QtGui.QColor(224, 224, 224), 1.0 / max(scale, 0.0001))
        major_pen = QtGui.QPen(QtGui.QColor(205, 205, 205), 1.0 / max(scale, 0.0001))
        x = 0.0
        index = 0
        while x <= self.panel_config.design_width:
            painter.setPen(major_pen if index % 4 == 0 else minor_pen)
            painter.drawLine(QtCore.QPointF(x, 0), QtCore.QPointF(x, self.panel_config.design_height))
            x += spacing
            index += 1
        y = 0.0
        index = 0
        while y <= self.panel_config.design_height:
            painter.setPen(major_pen if index % 4 == 0 else minor_pen)
            painter.drawLine(QtCore.QPointF(0, y), QtCore.QPointF(self.panel_config.design_width, y))
            y += spacing
            index += 1

    def _draw_pipe(self, painter: QtGui.QPainter, pipe: PipeConfig, *, selected: bool) -> None:
        pen = QtGui.QPen(QtGui.QColor(72, 72, 72), pipe.thickness)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QtCore.QPointF(*pipe.start), QtCore.QPointF(*pipe.end))

        highlight_pen = QtGui.QPen(
            QtGui.QColor(40, 120, 220) if selected else QtGui.QColor(115, 115, 115),
            max(1.5, pipe.thickness * 0.12),
        )
        highlight_pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(highlight_pen)
        painter.drawLine(QtCore.QPointF(*pipe.start), QtCore.QPointF(*pipe.end))

        if selected:
            self._draw_pipe_selection_handles(painter, pipe)
        if pipe.label:
            center = QtCore.QPointF((pipe.start[0] + pipe.end[0]) / 2.0, (pipe.start[1] + pipe.end[1]) / 2.0)
            painter.setPen(QtGui.QColor(20, 20, 20))
            painter.drawText(center + QtCore.QPointF(6, -6), pipe.label)

    def _draw_pending_pipe_hint(self, painter: QtGui.QPainter) -> None:
        if self._pending_pipe_start is None:
            return
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 120, 220), 2.0, QtCore.Qt.DashLine))
        start = QtCore.QPointF(*self._pending_pipe_start)
        painter.drawEllipse(start, 6.0, 6.0)

    def _draw_pipe_selection_handles(self, painter: QtGui.QPainter, pipe: PipeConfig) -> None:
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 120, 220), 2.0))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        for point in (pipe.start, pipe.end):
            painter.drawEllipse(QtCore.QPointF(*point), 6.0, 6.0)

    def _draw_element(self, painter: QtGui.QPainter, element: ActuatedElementConfig, spec: ValveTypeSpec, *, selected: bool) -> None:
        painter.save()
        painter.translate(QtCore.QPointF(*element.center))
        painter.rotate(element.rotation)

        width, height = element.size
        rect = QtCore.QRectF(-width / 2.0, -height / 2.0, width, height)
        path = self._shape_path(spec.shape, rect)
        base_color = self._element_color(element)

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(base_color))
        painter.drawPath(path)
        border_color = QtGui.QColor(35, 35, 35) if element.enabled else QtGui.QColor(130, 130, 130)
        painter.setPen(QtGui.QPen(border_color, 2.0))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawPath(path)

        if selected:
            select_pen = QtGui.QPen(QtGui.QColor(40, 120, 220), 3.0, QtCore.Qt.DashLine)
            painter.setPen(select_pen)
            painter.drawRect(rect.adjusted(-5, -5, 5, 5))

        marker_color = QtGui.QColor(20, 20, 20)
        marker_start = QtCore.QPointF(width / 2.0 + 3.0, 0.0)
        marker_end = QtCore.QPointF(width / 2.0 + 17.0, 0.0)
        painter.setPen(QtGui.QPen(marker_color, 2.0))
        painter.drawLine(marker_start, marker_end)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(marker_color))
        arrow_size = 4.5
        painter.drawPolygon(
            QtGui.QPolygonF([
                marker_end,
                QtCore.QPointF(marker_end.x() - arrow_size * 1.4, marker_end.y() - arrow_size),
                QtCore.QPointF(marker_end.x() - arrow_size * 1.4, marker_end.y() + arrow_size),
            ])
        )
        painter.restore()

        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        label_rect = QtCore.QRectF(element.center[0] - element.size[0] / 2.0, element.center[1] - element.size[1] / 2.0, element.size[0], element.size[1])
        painter.drawText(label_rect, QtCore.Qt.AlignCenter, element.label)

        if self._edit_mode:
            relay_text = f"R{element.relay_number}" if element.relay_number is not None else "R?"
            painter.setPen(QtGui.QColor(80, 80, 80))
            painter.drawText(QtCore.QPointF(element.center[0] - element.size[0] / 2.0, element.center[1] + element.size[1] / 2.0 + 14), relay_text)

    def _draw_rubber_band(self, painter: QtGui.QPainter) -> None:
        rect = QtCore.QRectF(self._rubber_start, self._rubber_current).normalized()
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 120, 220), 1.5, QtCore.Qt.DashLine))
        painter.setBrush(QtGui.QColor(40, 120, 220, 35))
        painter.drawRect(rect)

    def _shape_path(self, shape: str, rect: QtCore.QRectF) -> QtGui.QPainterPath:
        shape = shape.lower()
        path = QtGui.QPainterPath()
        if shape in {"circle", "ellipse", "oval"}:
            path.addEllipse(rect)
            return path
        if shape in {"rounded_rect", "rounded_rectangle", "actuator"}:
            path.addRoundedRect(rect, min(rect.width(), rect.height()) * 0.20, min(rect.width(), rect.height()) * 0.20)
            return path
        if shape in {"capsule", "pill"}:
            path.addRoundedRect(rect, min(rect.width(), rect.height()) / 2.0, min(rect.width(), rect.height()) / 2.0)
            return path
        if shape in {"diamond", "rhombus"}:
            poly = QtGui.QPolygonF([QtCore.QPointF(rect.center().x(), rect.top()), QtCore.QPointF(rect.right(), rect.center().y()), QtCore.QPointF(rect.center().x(), rect.bottom()), QtCore.QPointF(rect.left(), rect.center().y())])
            path.addPolygon(poly)
            path.closeSubpath()
            return path
        if shape == "triangle":
            poly = QtGui.QPolygonF([QtCore.QPointF(rect.right(), rect.center().y()), QtCore.QPointF(rect.left(), rect.top()), QtCore.QPointF(rect.left(), rect.bottom())])
            path.addPolygon(poly)
            path.closeSubpath()
            return path
        if shape == "hexagon":
            cx, cy = rect.center().x(), rect.center().y()
            rx, ry = rect.width() / 2.0, rect.height() / 2.0
            poly = QtGui.QPolygonF([QtCore.QPointF(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in (0, 60, 120, 180, 240, 300)])
            path.addPolygon(poly)
            path.closeSubpath()
            return path
        path.addRect(rect)
        return path

    def _element_color(self, element: ActuatedElementConfig) -> QtGui.QColor:
        if not element.enabled:
            return QtGui.QColor(180, 180, 180)
        if element.initially_active:
            return QtGui.QColor(241, 108, 107)
        return QtGui.QColor(255, 193, 7)

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------
    def _handle_pipe_creation_click(self, point: tuple[float, float]) -> None:
        snapped = self._snap_point(point)
        if self._pending_pipe_start is None:
            self._pending_pipe_start = snapped
            self.message.emit("Pipe mode: first endpoint set. Click the second endpoint.")
            self.update()
            return
        start = self._pending_pipe_start
        end = snapped
        if _distance(start, end) < 1.0:
            self.message.emit("Pipe endpoint is too close to the start; choose a different endpoint.")
            return
        self.add_pipe(PipeConfig(id=self.panel_config.next_pipe_id(), start=start, end=end, thickness=18.0))
        self._pending_pipe_start = None
        self.message.emit("Pipe added. Click another first endpoint, or press Esc to leave pipe mode.")

    def _snap_point(self, point: tuple[float, float]) -> tuple[float, float]:
        element_snapped = self._snap_point_to_element(point)
        if element_snapped != point:
            return element_snapped
        if self.snap_to_grid:
            return self._snap_point_to_grid(point)
        return point

    def _snap_point_to_element(self, point: tuple[float, float]) -> tuple[float, float]:
        snap_radius = max(25.0, self.grid_spacing * 1.5)
        best: tuple[float, ActuatedElementConfig] | None = None
        for element in self.panel_config.elements:
            distance = _distance(point, element.center)
            if distance <= snap_radius and (best is None or distance < best[0]):
                best = (distance, element)
        if best is not None:
            return best[1].center
        return point

    def _snap_point_to_grid(self, point: tuple[float, float]) -> tuple[float, float]:
        if not self.snap_to_grid:
            return point
        spacing = max(1.0, self.grid_spacing)
        return (round(point[0] / spacing) * spacing, round(point[1] / spacing) * spacing)

    def _snap_selected_items_to_grid(self) -> None:
        for kind, item_id in list(self._selected_items):
            if kind == "element":
                element = self.panel_config.element_by_id(item_id)
                element.center = self._snap_point_to_grid(element.center)
            elif kind == "pipe":
                pipe = self.panel_config.pipe_by_id(item_id)
                pipe.start = self._snap_point_to_grid(pipe.start)
                pipe.end = self._snap_point_to_grid(pipe.end)

    def _move_selected(self, dx: float, dy: float) -> None:
        for kind, item_id in list(self._selected_items):
            if kind == "element":
                element = self.panel_config.element_by_id(item_id)
                element.center = (element.center[0] + dx, element.center[1] + dy)
            elif kind == "pipe":
                pipe = self.panel_config.pipe_by_id(item_id)
                pipe.start = (pipe.start[0] + dx, pipe.start[1] + dy)
                pipe.end = (pipe.end[0] + dx, pipe.end[1] + dy)
        self.update()

    def _items_in_rubber_band(self) -> list[SelectionItem]:
        rect = QtCore.QRectF(self._rubber_start, self._rubber_current).normalized()
        items: list[SelectionItem] = []
        for element in self.panel_config.elements:
            if rect.contains(QtCore.QPointF(*element.center)):
                items.append(("element", element.id))
        for pipe in self.panel_config.pipes:
            start = QtCore.QPointF(*pipe.start)
            end = QtCore.QPointF(*pipe.end)
            mid = QtCore.QPointF((pipe.start[0] + pipe.end[0]) / 2.0, (pipe.start[1] + pipe.end[1]) / 2.0)
            if rect.contains(start) or rect.contains(end) or rect.contains(mid):
                items.append(("pipe", pipe.id))
        return items

    def _hit_test(self, point: tuple[float, float]) -> tuple[SelectionKind | None, str | None]:
        for element in reversed(self.panel_config.elements):
            spec = self.panel_config.type_spec_for(element.element_type)
            if self._point_hits_element(point, element, spec):
                return "element", element.id
        for pipe in reversed(self.panel_config.pipes):
            if _distance_to_segment(point, pipe.start, pipe.end) <= max(8.0, pipe.thickness / 2.0 + 4.0):
                return "pipe", pipe.id
        return None, None

    def _point_hits_element(self, point: tuple[float, float], element: ActuatedElementConfig, spec: ValveTypeSpec) -> bool:
        local = _to_local_rotated(point, element.center, -element.rotation)
        width, height = element.size
        rect = QtCore.QRectF(-width / 2.0, -height / 2.0, width, height)
        path = self._shape_path(spec.shape, rect)
        return path.contains(QtCore.QPointF(*local))

    def _is_selected(self, kind: SelectionKind, item_id: str) -> bool:
        return (kind, item_id) in self._selected_items


def _to_local_rotated(point: tuple[float, float], center: tuple[float, float], degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    cos_t = math.cos(radians)
    sin_t = math.sin(radians)
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    return dx * cos_t - dy * sin_t, dx * sin_t + dy * cos_t


def _rotate_point(point: tuple[float, float], center: tuple[float, float], degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    cos_t = math.cos(radians)
    sin_t = math.sin(radians)
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    return center[0] + dx * cos_t - dy * sin_t, center[1] + dx * sin_t + dy * cos_t


def _rotate_segment(start: tuple[float, float], end: tuple[float, float], degrees: float) -> tuple[tuple[float, float], tuple[float, float]]:
    center = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    return _rotate_point(start, center, degrees), _rotate_point(end, center, degrees)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _distance_to_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return _distance(point, start)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    closest = (x1 + t * dx, y1 + t * dy)
    return _distance(point, closest)
