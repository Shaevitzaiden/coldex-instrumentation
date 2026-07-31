from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from PyQt5 import QtCore, QtWidgets

from .app_context import AppContext
from .config_io import load_panel_config, save_panel_config
from .controllers.pneumatic_controller import PneumaticController
from .data import (
    DashboardConfig,
    DashboardTileConfig,
    DataHub,
    DataHubLoggingHandler,
    DeviceDefinition,
    QtDataBridge,
    SensorDefinition,
    StreamHub,
    load_dashboard_config,
    load_device_definitions,
    load_sensor_definitions,
    save_dashboard_config,
)
from .hardware import DeviceManager
from .models import PanelConfig
from .recording import SessionRecorder
from .widgets import (
    ElementDialog,
    PipeDialog,
    PropertiesPanel,
    RecordingPanel,
    TileConfigDialog,
    ValidationPanel,
    ValvePanelCanvas,
)
from .widgets.tiles import DashboardWidget, LivePlotTile, LogTile, SensorValuesTile, TileRegistry, TileWidget, ValvePanelTile


class MainWindow(QtWidgets.QMainWindow):
    """Dashboard shell containing the valve panel and data-view tiles."""

    def __init__(
        self,
        *,
        config_path: Path,
        communicator: Any = None,
        communicators: dict[str, Any] | None = None,
        dashboard_config_path: Path | None = None,
        sensor_config_path: Path | None = None,
        device_config_path: Path | None = None,
        data_root: Path | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path)
        self.dashboard_config_path = Path(dashboard_config_path or self.config_path.with_name("dashboard.yaml"))
        self.sensor_config_path = Path(sensor_config_path or self.config_path.with_name("sensors.yaml"))
        self.device_config_path = Path(device_config_path or self.config_path.with_name("devices.yaml"))
        self.data_root = Path(data_root or self.config_path.parent.parent / "recorded_sessions")

        self.panel_config: PanelConfig = load_panel_config(self.config_path)
        self.dashboard_config: DashboardConfig = load_dashboard_config(self.dashboard_config_path)
        self._default_dashboard_config = copy.deepcopy(self.dashboard_config)
        self.sensor_definitions: dict[str, SensorDefinition] = load_sensor_definitions(self.sensor_config_path)
        self.device_definitions: dict[str, DeviceDefinition] = load_device_definitions(self.device_config_path)
        self._dirty = False
        self._dashboard_dirty = False
        self._save_close_confirmed = False
        self._shutdown_complete = False

        # StreamHub is the application-wide, non-Qt data backbone.  Every
        # serial device, recorder, plot bridge, and future automation worker
        # observes the same normalized streams without competing for one queue.
        self.stream_hub = StreamHub()

        # QtDataBridge rate-limits high-rate streams before they reach widgets.
        # The recorder subscribes directly to StreamHub and therefore does not
        # lose full-rate data when the GUI redraw rate is lower.
        self.qt_data_bridge = QtDataBridge(stream_hub=self.stream_hub, parent=self)
        self.data_hub = DataHub(stream_hub=self.stream_hub, parent=self)
        self.qt_data_bridge.frame_received.connect(self.data_hub.publish_frame)
        self.qt_data_bridge.log_received.connect(self.data_hub.publish_log_event)
        self.qt_data_bridge.command_result_received.connect(self.data_hub.publish_relay_result)
        self.qt_data_bridge.device_status_received.connect(self.data_hub.publish_device_status)

        self.qt_log_handler = DataHubLoggingHandler(self.stream_hub)
        self.qt_log_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(self.qt_log_handler)

        self.session_recorder = SessionRecorder(
            stream_hub=self.stream_hub,
            sensor_definitions=self.sensor_definitions,
            base_directory=self.data_root,
            autosave_interval_s=30,
            parent=self,
        )

        # Backwards compatibility: callers may still inject one ``communicator``.
        # It is assigned to the configured command-target device.  New code
        # should pass a mapping such as {"controller": ..., "flow_meter": ...}.
        communicator_map = dict(communicators or {})
        if communicator is not None and "controller" not in communicator_map:
            command_targets = [
                definition.communicator_key or definition.device_id
                for definition in self.device_definitions.values()
                if definition.command_target
            ]
            communicator_map[command_targets[0] if command_targets else "controller"] = communicator

        self.device_manager = DeviceManager(
            device_definitions=self.device_definitions,
            sensor_definitions=self.sensor_definitions,
            communicators=communicator_map,
            stream_hub=self.stream_hub,
            parent=self,
        )
        # Alias retained because a few external integrations may still refer to
        # MainWindow.hardware_service.  It now represents the multi-device manager.
        self.hardware_service = self.device_manager

        self.controller = PneumaticController(
            panel_config=self.panel_config,
            communicator=self.device_manager,
            logger=self.logger,
        )

        self.setWindowTitle(self.panel_config.title)
        self.resize(1500, 900)

        self.canvas = ValvePanelCanvas(panel_config=self.panel_config, controller=self.controller)
        self.canvas.message.connect(self.statusBar().showMessage)
        self.canvas.pipe_mode_changed.connect(self._on_pipe_mode_changed)
        self.canvas.edit_requested.connect(self._on_canvas_edit_requested)
        self.canvas.layout_changed.connect(self._on_layout_changed)
        self.canvas.selection_items_changed.connect(self._on_selection_items_changed)
        self.canvas.history_changed.connect(self._on_history_changed)

        self.properties_panel = PropertiesPanel()
        self.properties_panel.set_panel_config(self.panel_config)
        self.properties_panel.element_changed.connect(self.canvas.update_element)
        self.properties_panel.pipe_changed.connect(self.canvas.update_pipe)
        self.properties_panel.delete_requested.connect(self.canvas.delete_selected)
        self.properties_panel.rotate_requested.connect(self.canvas.rotate_selected)

        self.validation_panel = ValidationPanel(relay_count=24)
        self.validation_panel.set_panel_config(self.panel_config)

        # Valve-layout support panels remain ordinary edit-only docks. They are
        # not part of the operational dashboard layout and are hidden outside
        # valve-layout edit mode.
        self.properties_dock = QtWidgets.QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setWidget(self.properties_panel)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.properties_dock)

        self.validation_dock = QtWidgets.QDockWidget("Validation / Relay Browser", self)
        self.validation_dock.setObjectName("ValidationDock")
        self.validation_dock.setWidget(self.validation_panel)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.validation_dock)
        self.tabifyDockWidget(self.properties_dock, self.validation_dock)

        self.recording_panel = RecordingPanel(
            sensor_definitions=self.sensor_definitions,
            base_directory=self.data_root,
            autosave_interval_s=self.session_recorder.autosave_interval_s,
        )
        self._connect_recording_panel()

        self.connection_label = QtWidgets.QLabel("Hardware: starting")
        self.recording_status_label = QtWidgets.QLabel("Sensor logging: inactive")
        self.statusBar().addPermanentWidget(self.connection_label)
        self.statusBar().addPermanentWidget(self.recording_status_label)
        self.data_hub.connection_changed.connect(self._on_connection_changed)
        self.data_hub.device_connection_changed.connect(self._on_device_connection_changed)
        self.session_recorder.recording_changed.connect(self._on_recording_changed)
        self.session_recorder.session_directory_changed.connect(self.recording_panel.set_session_directory)
        self.session_recorder.message.connect(self.recording_panel.show_message)
        self.session_recorder.message.connect(self.statusBar().showMessage)

        self._create_actions()

        self.app_context = AppContext(
            panel_config=self.panel_config,
            controller=self.controller,
            data_hub=self.data_hub,
            stream_hub=self.stream_hub,
            device_manager=self.device_manager,
            sensor_definitions=self.sensor_definitions,
            logger=self.logger,
        )
        self.tile_registry = TileRegistry()
        self._register_tile_types()

        self.dashboard = DashboardWidget(
            rows=self.dashboard_config.rows,
            columns=self.dashboard_config.columns,
            row_stretches=self.dashboard_config.row_stretches,
            column_stretches=self.dashboard_config.column_stretches,
        )
        self.dashboard.tile_removed.connect(self._on_tile_removed)
        self.dashboard.tile_configure_requested.connect(self._configure_dashboard_tile)
        self.dashboard.layout_changed.connect(self._on_dashboard_layout_changed)
        self.setCentralWidget(self.dashboard)
        self._build_dashboard_from_config()

        self._create_menus()
        self._create_toolbar()
        self._update_valve_mode_ui(edit_mode=False)
        self._update_dashboard_mode_ui(edit_mode=False)
        self._update_window_title()
        self.statusBar().showMessage(f"Loaded panel {self.config_path}")
        self.data_hub.log(
            "Application dashboard opened",
            source="application",
            details={
                "panel_config": str(self.config_path),
                "dashboard_config": str(self.dashboard_config_path),
                "sensor_config": str(self.sensor_config_path),
                "device_config": str(self.device_config_path),
            },
        )
        QtCore.QTimer.singleShot(0, self.device_manager.start)

    def set_communicator(self, communicator: Any | None, device_id: str | None = None) -> None:
        """Replace one live device communicator after startup.

        ``device_id`` defaults to the configured command-target device so the
        method remains compatible with the former single-device API.
        """

        self.device_manager.set_communicator(
            device_id or self.device_manager.default_command_device_id,
            communicator,
        )

    # ------------------------------------------------------------------
    # Dashboard construction
    # ------------------------------------------------------------------
    def _build_dashboard_from_config(self) -> None:
        valve_panel_added = False
        for tile_config in self.dashboard_config.tiles:
            if tile_config.tile_type == "valve_panel":
                if valve_panel_added:
                    continue
                valve_panel_added = True
            try:
                tile = self._create_tile(tile_config)
                self.dashboard.add_tile(tile, tile_config, emit_change=False)
            except Exception as exc:
                self.data_hub.log(
                    f"Could not create tile {tile_config.tile_id}: {exc}",
                    level="ERROR",
                    source="dashboard",
                )
                continue

    def _register_tile_types(self) -> None:
        self.tile_registry.register("valve_panel", lambda config, context: self._make_valve_panel_tile(config))
        self.tile_registry.register(
            "live_plot",
            lambda config, context: LivePlotTile(
                tile_id=config.tile_id,
                title=config.title,
                data_hub=context.data_hub,
                sensor_definitions=context.sensor_definitions,
                channels=list(config.config.get("channels", [])) or list(context.sensor_definitions),
                plot_groups=list(config.config.get("plot_groups", [])),
                group_by_unit=bool(config.config.get("group_by_unit", True)),
                history_seconds=float(config.config.get("history_seconds", 30.0)),
                removable=config.removable,
            ),
        )
        self.tile_registry.register(
            "sensor_values",
            lambda config, context: SensorValuesTile(
                tile_id=config.tile_id,
                title=config.title,
                data_hub=context.data_hub,
                sensor_definitions=context.sensor_definitions,
                channels=list(config.config.get("channels", [])) or list(context.sensor_definitions),
                removable=config.removable,
            ),
        )
        self.tile_registry.register(
            "log",
            lambda config, context: LogTile(
                tile_id=config.tile_id,
                title=config.title,
                data_hub=context.data_hub,
                removable=config.removable,
            ),
        )
        self.tile_registry.register(
            "recording",
            lambda config, context: self._make_recording_tile(config),
        )

    def _make_recording_tile(self, config: DashboardTileConfig) -> TileWidget:
        # The default bottom row is intentionally compact. A scroll area keeps
        # every recording control available without forcing the bottom row to
        # grow beyond its configured 25% share of the window.
        self.recording_panel.setMinimumSize(0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setWidget(self.recording_panel)
        return TileWidget(
            tile_id=config.tile_id,
            title=config.title,
            child=scroll,
            removable=config.removable,
        )

    def _make_valve_panel_tile(self, config: DashboardTileConfig) -> ValvePanelTile:
        self.valve_tile = ValvePanelTile(
            tile_id=config.tile_id,
            title=config.title,
            canvas=self.canvas,
            close_all_action=self.close_all_action,
            edit_layout_action=self.edit_layout_action,
            save_config_action=self.save_config_action,
            save_config_as_action=self.save_config_as_action,
            undo_action=self.undo_action,
            redo_action=self.redo_action,
            add_element_action=self.add_element_action,
            add_pipe_action=self.add_pipe_action,
            edit_selected_action=self.edit_selected_action,
            rotate_selected_action=self.rotate_selected_action,
            delete_selected_action=self.delete_selected_action,
            show_grid_action=self.show_grid_action,
            snap_to_grid_action=self.snap_to_grid_action,
            grid_spacing_action=self.grid_spacing_action,
            fit_to_window_action=self.fit_to_window_action,
            zoom_in_action=self.zoom_in_action,
            zoom_out_action=self.zoom_out_action,
            alignment_actions=(
                self.align_left_action,
                self.align_right_action,
                self.align_top_action,
                self.align_bottom_action,
                self.align_center_x_action,
                self.align_center_y_action,
                self.distribute_horizontal_action,
                self.distribute_vertical_action,
            ),
            removable=config.removable,
        )
        return self.valve_tile

    def _create_tile(self, config: DashboardTileConfig) -> TileWidget:
        return self.tile_registry.create(config, self.app_context)

    # ------------------------------------------------------------------
    # Actions / menus / toolbar
    # ------------------------------------------------------------------
    def _create_actions(self) -> None:
        self.load_config_action = QtWidgets.QAction("Load Panel Config…", self)
        self.load_config_action.triggered.connect(self._load_config_dialog)
        self.load_config_action.setShortcut("Ctrl+O")

        self.save_config_action = QtWidgets.QAction("Save Valve Layout", self)
        self.save_config_action.triggered.connect(self._save_layout)
        self.save_config_action.setShortcut("Ctrl+S")

        self.save_config_as_action = QtWidgets.QAction("Save Valve Layout As…", self)
        self.save_config_as_action.triggered.connect(self._save_layout_as)
        self.save_config_as_action.setShortcut("Ctrl+Shift+S")

        self.edit_layout_action = QtWidgets.QAction("Edit Valve Layout", self)
        self.edit_layout_action.setCheckable(True)
        self.edit_layout_action.toggled.connect(self._on_edit_layout_toggled)
        self.edit_layout_action.setShortcut("Ctrl+E")

        self.edit_dashboard_action = QtWidgets.QAction("Edit Dashboard Layout", self)
        self.edit_dashboard_action.setCheckable(True)
        self.edit_dashboard_action.toggled.connect(self._on_edit_dashboard_toggled)
        self.edit_dashboard_action.setShortcut("Ctrl+D")

        self.add_tile_action = QtWidgets.QAction("Add Dashboard Panel…", self)
        self.add_tile_action.triggered.connect(self._add_dashboard_tile)
        self.save_dashboard_action = QtWidgets.QAction("Save Dashboard Layout", self)
        self.save_dashboard_action.triggered.connect(self._save_dashboard_layout)
        self.reset_dashboard_layout_action = QtWidgets.QAction("Reset Dashboard Layout", self)
        self.reset_dashboard_layout_action.triggered.connect(self._reset_dashboard_layout)

        self.undo_action = QtWidgets.QAction("Undo", self)
        self.undo_action.triggered.connect(self.canvas.undo)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setEnabled(False)
        self.redo_action = QtWidgets.QAction("Redo", self)
        self.redo_action.triggered.connect(self.canvas.redo)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.setEnabled(False)

        self.add_element_action = QtWidgets.QAction("Add Element…", self)
        self.add_element_action.triggered.connect(self._add_element_dialog)
        self.add_element_action.setShortcut("Ctrl+N")
        self.edit_selected_action = QtWidgets.QAction("Edit Selected…", self)
        self.edit_selected_action.triggered.connect(self._edit_selected_dialog)
        self.edit_selected_action.setShortcut("Return")
        self.add_pipe_action = QtWidgets.QAction("Add Pipe", self)
        self.add_pipe_action.setCheckable(True)
        self.add_pipe_action.triggered.connect(self._toggle_pipe_creation)
        self.add_pipe_action.setShortcut("Ctrl+P")
        self.rotate_selected_action = QtWidgets.QAction("Rotate Selected 90°", self)
        self.rotate_selected_action.triggered.connect(lambda: self.canvas.rotate_selected(90.0))
        self.rotate_selected_action.setShortcut("R")
        self.delete_selected_action = QtWidgets.QAction("Delete Selected", self)
        self.delete_selected_action.triggered.connect(self.canvas.delete_selected)
        self.delete_selected_action.setShortcut("Delete")

        self.show_grid_action = QtWidgets.QAction("Show Grid", self)
        self.show_grid_action.setCheckable(True)
        self.show_grid_action.setChecked(True)
        self.show_grid_action.toggled.connect(self.canvas.set_show_grid)
        self.snap_to_grid_action = QtWidgets.QAction("Snap to Grid", self)
        self.snap_to_grid_action.setCheckable(True)
        self.snap_to_grid_action.setChecked(True)
        self.snap_to_grid_action.toggled.connect(self.canvas.set_snap_to_grid)
        self.grid_spacing_action = QtWidgets.QAction("Grid Spacing…", self)
        self.grid_spacing_action.triggered.connect(self._set_grid_spacing_dialog)
        self.fit_to_window_action = QtWidgets.QAction("Fit Valve Panel to Window", self)
        self.fit_to_window_action.triggered.connect(self.canvas.fit_to_window)
        self.fit_to_window_action.setShortcut("Ctrl+0")
        self.zoom_in_action = QtWidgets.QAction("Zoom In", self)
        self.zoom_in_action.triggered.connect(lambda: self.canvas.zoom_by(1.2))
        self.zoom_in_action.setShortcut("Ctrl++")
        self.zoom_out_action = QtWidgets.QAction("Zoom Out", self)
        self.zoom_out_action.triggered.connect(lambda: self.canvas.zoom_by(1.0 / 1.2))
        self.zoom_out_action.setShortcut("Ctrl+-")

        self.align_left_action = QtWidgets.QAction("Align Left", self)
        self.align_left_action.triggered.connect(lambda: self.canvas.align_selected("left"))
        self.align_right_action = QtWidgets.QAction("Align Right", self)
        self.align_right_action.triggered.connect(lambda: self.canvas.align_selected("right"))
        self.align_top_action = QtWidgets.QAction("Align Top", self)
        self.align_top_action.triggered.connect(lambda: self.canvas.align_selected("top"))
        self.align_bottom_action = QtWidgets.QAction("Align Bottom", self)
        self.align_bottom_action.triggered.connect(lambda: self.canvas.align_selected("bottom"))
        self.align_center_x_action = QtWidgets.QAction("Align Center X", self)
        self.align_center_x_action.triggered.connect(lambda: self.canvas.align_selected("center_x"))
        self.align_center_y_action = QtWidgets.QAction("Align Center Y", self)
        self.align_center_y_action.triggered.connect(lambda: self.canvas.align_selected("center_y"))
        self.distribute_horizontal_action = QtWidgets.QAction("Distribute Horizontally", self)
        self.distribute_horizontal_action.triggered.connect(lambda: self.canvas.distribute_selected("horizontal"))
        self.distribute_vertical_action = QtWidgets.QAction("Distribute Vertically", self)
        self.distribute_vertical_action.triggered.connect(lambda: self.canvas.distribute_selected("vertical"))

        self.close_all_action = QtWidgets.QAction("Close/Deactivate All", self)
        self.close_all_action.triggered.connect(self._close_all_elements)

        self.start_logging_action = QtWidgets.QAction("Start Sensor Logging", self)
        self.start_logging_action.triggered.connect(
            lambda: self._start_sensor_logging(self.recording_panel.selected_sensor_ids())
        )
        self.stop_logging_action = QtWidgets.QAction("Stop Sensor Logging + Save", self)
        self.stop_logging_action.triggered.connect(self._stop_sensor_logging)
        self.stop_logging_action.setEnabled(False)
        self.snapshot_action = QtWidgets.QAction("Save Data Snapshot", self)
        self.snapshot_action.triggered.connect(self._save_snapshot)
        self.save_session_action = QtWidgets.QAction("Save Session Now", self)
        self.save_session_action.triggered.connect(self._save_session_now)
        self.export_logs_action = QtWidgets.QAction("Export Logs…", self)
        self.export_logs_action.triggered.connect(self._export_logs)
        self.save_close_action = QtWidgets.QAction("Save and Close", self)
        self.save_close_action.triggered.connect(self._save_and_close)

        self.quit_action = QtWidgets.QAction("Quit", self)
        self.quit_action.triggered.connect(self.close)
        self.quit_action.setShortcut("Ctrl+Q")

        self._editing_actions = [
            self.save_config_action,
            self.save_config_as_action,
            self.undo_action,
            self.redo_action,
            self.add_element_action,
            self.add_pipe_action,
            self.edit_selected_action,
            self.rotate_selected_action,
            self.delete_selected_action,
            self.show_grid_action,
            self.snap_to_grid_action,
            self.grid_spacing_action,
            self.fit_to_window_action,
            self.zoom_in_action,
            self.zoom_out_action,
            self.align_left_action,
            self.align_right_action,
            self.align_top_action,
            self.align_bottom_action,
            self.align_center_x_action,
            self.align_center_y_action,
            self.distribute_horizontal_action,
            self.distribute_vertical_action,
        ]
        self._dashboard_editing_actions = [
            self.add_tile_action,
            self.save_dashboard_action,
            self.reset_dashboard_layout_action,
        ]

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.load_config_action)
        file_menu.addAction(self.save_dashboard_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_session_action)
        file_menu.addAction(self.snapshot_action)
        file_menu.addAction(self.export_logs_action)
        file_menu.addAction(self.save_close_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        dashboard_menu = self.menuBar().addMenu("Dashboard")
        dashboard_menu.addAction(self.edit_dashboard_action)
        dashboard_menu.addAction(self.add_tile_action)
        dashboard_menu.addAction(self.save_dashboard_action)
        dashboard_menu.addAction(self.reset_dashboard_layout_action)

        recording_menu = self.menuBar().addMenu("Recording")
        recording_menu.addAction(self.start_logging_action)
        recording_menu.addAction(self.stop_logging_action)
        recording_menu.addAction(self.snapshot_action)
        recording_menu.addAction(self.save_session_action)
        recording_menu.addAction(self.export_logs_action)

        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.properties_dock.toggleViewAction())
        view_menu.addAction(self.validation_dock.toggleViewAction())

        help_menu = self.menuBar().addMenu("Help")
        shortcuts_action = QtWidgets.QAction("Editing Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

    def _create_toolbar(self) -> None:
        self.toolbar = self.addToolBar("Operation")
        self.toolbar.setMovable(False)
        self.toolbar.addAction(self.edit_dashboard_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.start_logging_action)
        self.toolbar.addAction(self.stop_logging_action)
        self.toolbar.addAction(self.snapshot_action)

        self.dashboard_toolbar = self.addToolBar("Dashboard Editor")
        self.dashboard_toolbar.setMovable(False)
        self.dashboard_toolbar.addAction(self.add_tile_action)
        self.dashboard_toolbar.addAction(self.save_dashboard_action)
        self.dashboard_toolbar.addAction(self.reset_dashboard_layout_action)

    # ------------------------------------------------------------------
    # File/config actions
    # ------------------------------------------------------------------
    def _maybe_save_dirty(self) -> bool:
        if not self._dirty:
            return True
        response = QtWidgets.QMessageBox.question(
            self,
            "Save valve-layout changes?",
            "The valve layout has unsaved changes. Save before continuing?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
        )
        if response == QtWidgets.QMessageBox.Cancel:
            return False
        if response == QtWidgets.QMessageBox.Yes:
            self._save_layout()
        return True

    def _maybe_save_dashboard_dirty(self) -> bool:
        if not self._dashboard_dirty:
            return True
        response = QtWidgets.QMessageBox.question(
            self,
            "Save dashboard changes?",
            "The dashboard panel layout has unsaved changes. Save before continuing?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
        )
        if response == QtWidgets.QMessageBox.Cancel:
            return False
        if response == QtWidgets.QMessageBox.Yes:
            self._save_dashboard_layout()
        return True

    def _load_config_dialog(self) -> None:
        if not self._maybe_save_dirty():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load panel config",
            str(self.config_path.parent),
            "YAML files (*.yaml *.yml);;All files (*)",
        )
        if path:
            self._load_config(Path(path))

    def _load_config(self, path: Path) -> None:
        config = load_panel_config(path)
        self.config_path = path
        self.panel_config = config
        self.app_context.panel_config = config
        self.controller.set_panel_config(config)
        self.canvas.set_panel_config(config)
        self.properties_panel.set_panel_config(config)
        self.validation_panel.set_panel_config(config)
        self._dirty = False
        self._update_window_title()
        self.statusBar().showMessage(f"Loaded {path}")
        self.data_hub.log(f"User loaded valve layout {path}", source="user.layout")

    def _save_layout(self) -> None:
        save_panel_config(self.panel_config, self.config_path)
        self._dirty = False
        self._update_window_title()
        self.statusBar().showMessage(f"Saved {self.config_path}")
        self.data_hub.log(f"User saved valve layout {self.config_path}", source="user.layout")

    def _save_layout_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save panel config as",
            str(self.config_path),
            "YAML files (*.yaml *.yml);;All files (*)",
        )
        if not path:
            return
        self.config_path = Path(path)
        self._save_layout()

    def _save_dashboard_layout(self) -> None:
        self.dashboard_config = self.dashboard.current_config()
        save_dashboard_config(self.dashboard_config, self.dashboard_config_path)
        self._dashboard_dirty = False
        self._update_window_title()
        self.statusBar().showMessage(f"Saved dashboard layout {self.dashboard_config_path}")
        self.data_hub.log(
            f"User saved dashboard layout {self.dashboard_config_path}",
            source="user.dashboard",
        )

    # ------------------------------------------------------------------
    # Mode and editor actions
    # ------------------------------------------------------------------
    def _update_valve_mode_ui(self, *, edit_mode: bool) -> None:
        self.canvas.set_edit_mode(edit_mode)
        if hasattr(self, "valve_tile"):
            self.valve_tile.set_valve_edit_mode(edit_mode)
        self.properties_dock.setVisible(edit_mode)
        self.validation_dock.setVisible(edit_mode)
        self.close_all_action.setEnabled(not edit_mode and not self.edit_dashboard_action.isChecked())
        self.close_all_action.setVisible(not edit_mode)
        for action in self._editing_actions:
            action.setVisible(edit_mode)
            if action not in (self.undo_action, self.redo_action):
                action.setEnabled(edit_mode)
        self.undo_action.setEnabled(edit_mode and self.canvas.can_undo())
        self.redo_action.setEnabled(edit_mode and self.canvas.can_redo())
        if not edit_mode and self.add_pipe_action.isChecked():
            self.add_pipe_action.blockSignals(True)
            self.add_pipe_action.setChecked(False)
            self.add_pipe_action.blockSignals(False)

    def _update_dashboard_mode_ui(self, *, edit_mode: bool) -> None:
        self.dashboard.set_dashboard_edit_mode(edit_mode)
        self.dashboard_toolbar.setVisible(edit_mode)
        for action in self._dashboard_editing_actions:
            action.setVisible(edit_mode)
            action.setEnabled(edit_mode)
        self.canvas.set_runtime_interaction_enabled(not edit_mode and not self.edit_layout_action.isChecked())
        self.edit_layout_action.setEnabled(not edit_mode)
        self.close_all_action.setEnabled(not edit_mode and not self.edit_layout_action.isChecked())

    def _on_edit_layout_toggled(self, enabled: bool) -> None:
        if enabled and self.edit_dashboard_action.isChecked():
            self.edit_dashboard_action.setChecked(False)
        self._update_valve_mode_ui(edit_mode=enabled)
        self.canvas.set_runtime_interaction_enabled(not enabled and not self.edit_dashboard_action.isChecked())
        self.statusBar().showMessage(
            "Valve-layout edit mode enabled; hardware toggle commands are disabled"
            if enabled
            else "Runtime valve control enabled"
        )

    def _on_edit_dashboard_toggled(self, enabled: bool) -> None:
        if enabled and self.edit_layout_action.isChecked():
            self.edit_layout_action.setChecked(False)
        self._update_dashboard_mode_ui(edit_mode=enabled)
        self.statusBar().showMessage(
            "Dashboard edit mode enabled; use panel headers to configure/remove panels"
            if enabled
            else "Dashboard runtime mode enabled"
        )

    def _on_canvas_edit_requested(self, kind: str, item_id: str) -> None:
        if not self.edit_layout_action.isChecked():
            self.edit_layout_action.setChecked(True)
        self._edit_selected_dialog()

    def _on_pipe_mode_changed(self, enabled: bool) -> None:
        if self.add_pipe_action.isChecked() != enabled:
            self.add_pipe_action.blockSignals(True)
            self.add_pipe_action.setChecked(enabled)
            self.add_pipe_action.blockSignals(False)

    def _on_selection_items_changed(self, selected_items: object) -> None:
        self.properties_panel.set_selection(list(selected_items))

    def _on_history_changed(self, can_undo: bool, can_redo: bool) -> None:
        edit_mode = self.edit_layout_action.isChecked()
        self.undo_action.setEnabled(edit_mode and can_undo)
        self.redo_action.setEnabled(edit_mode and can_redo)

    def _on_layout_changed(self) -> None:
        self._dirty = True
        self._update_window_title()
        self.properties_panel.refresh()
        self.validation_panel.refresh()

    def _on_dashboard_layout_changed(self) -> None:
        self._dashboard_dirty = True
        self._update_window_title()

    def _update_window_title(self) -> None:
        markers = ("*" if self._dirty else "") + ("◆" if self._dashboard_dirty else "")
        self.setWindowTitle(f"{markers}{self.panel_config.title} — {self.config_path.name}")

    # ------------------------------------------------------------------
    # Valve-layout actions
    # ------------------------------------------------------------------
    def _add_element_dialog(self) -> None:
        if not self.edit_layout_action.isChecked():
            self.edit_layout_action.setChecked(True)
        dialog = ElementDialog(
            panel_config=self.panel_config,
            default_center=self.canvas.center_of_visible_scene(),
            parent=self,
        )
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.canvas.add_element(dialog.result_element())

    def _edit_selected_dialog(self) -> None:
        if len(self.canvas.selected_items()) > 1:
            self.statusBar().showMessage("Multiple items selected; use the Properties panel for bulk operations")
            return
        element = self.canvas.selected_element()
        if element is not None:
            dialog = ElementDialog(panel_config=self.panel_config, existing=element, parent=self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.canvas.update_element(element.id, dialog.result_element())
            return
        pipe = self.canvas.selected_pipe()
        if pipe is not None:
            dialog = PipeDialog(panel_config=self.panel_config, existing=pipe, parent=self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.canvas.update_pipe(pipe.id, dialog.result_pipe())
            return
        self.statusBar().showMessage("Select an element or pipe first")

    def _toggle_pipe_creation(self, checked: bool) -> None:
        if checked:
            if not self.edit_layout_action.isChecked():
                self.edit_layout_action.setChecked(True)
            self.canvas.begin_pipe_creation()
        else:
            self.canvas.end_pipe_creation()

    def _set_grid_spacing_dialog(self) -> None:
        spacing, accepted = QtWidgets.QInputDialog.getDouble(
            self,
            "Grid spacing",
            "Spacing in design units:",
            self.canvas.grid_spacing,
            2.0,
            500.0,
            1,
        )
        if accepted:
            self.canvas.set_grid_spacing(spacing)

    def _close_all_elements(self) -> None:
        self.data_hub.log(
            "User requested close/deactivate all unlocked elements",
            source="user.command",
        )
        try:
            self.canvas.set_all_elements_state(False, send=True)
        except Exception as exc:
            self.data_hub.log(f"Close-all request failed: {exc}", level="ERROR", source="user.command")
            QtWidgets.QMessageBox.critical(self, "Close all failed", str(exc))
            return
        self.statusBar().showMessage("Close/deactivate-all commands queued")

    # ------------------------------------------------------------------
    # Dashboard tile actions
    # ------------------------------------------------------------------
    def _add_dashboard_tile(self) -> None:
        prefix = "tile"
        dialog = TileConfigDialog(
            sensor_definitions=self.sensor_definitions,
            default_tile_id=self.dashboard.current_config().next_tile_id(prefix),
            parent=self,
        )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        config = dialog.result_config()
        if config.tile_id in self.dashboard.tiles:
            QtWidgets.QMessageBox.warning(self, "Duplicate tile ID", f"A tile named {config.tile_id!r} already exists.")
            return
        try:
            tile = self._create_tile(config)
            self.dashboard.add_tile(tile, config)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Could not place tile", str(exc))
            return
        self.data_hub.log(f"User added dashboard panel {config.tile_id}", source="user.dashboard")

    def _configure_dashboard_tile(self, tile_id: str) -> None:
        config = self.dashboard.tile_configs.get(tile_id)
        if config is None:
            return
        dialog = TileConfigDialog(
            sensor_definitions=self.sensor_definitions,
            existing=config,
            parent=self,
        )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        replacement = dialog.result_config()
        try:
            if config.tile_type in {"valve_panel", "recording", "log"}:
                self.dashboard.update_tile_config(tile_id, replacement)
            else:
                self._replace_dashboard_tile(tile_id, replacement)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Could not update tile", str(exc))
            return
        self.data_hub.log(f"User configured dashboard panel {tile_id}", source="user.dashboard")

    def _replace_dashboard_tile(self, tile_id: str, config: DashboardTileConfig) -> None:
        new_tile = self._create_tile(config)
        self.dashboard.replace_tile(tile_id, new_tile, config)

    def _reset_dashboard_layout(self) -> None:
        response = QtWidgets.QMessageBox.question(
            self,
            "Reset dashboard layout?",
            "Reset the dashboard to the fixed 60/40 by 75/25 four-panel layout?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if response != QtWidgets.QMessageBox.Yes:
            return
        self._rebuild_dashboard(copy.deepcopy(self._default_dashboard_config))
        self._dashboard_dirty = True
        self._update_window_title()
        self.data_hub.log(
            "User reset dashboard layout to the fixed four-panel default",
            source="user.dashboard",
        )

    def _rebuild_dashboard(self, config: DashboardConfig) -> None:
        # Preserve the two singleton operational widgets while deleting the old
        # dashboard and its replaceable plot/log tile instances.
        self.canvas.setParent(None)
        self.recording_panel.setParent(None)
        old_dashboard = self.takeCentralWidget()

        self.dashboard_config = config
        self.dashboard = DashboardWidget(
            rows=config.rows,
            columns=config.columns,
            row_stretches=config.row_stretches,
            column_stretches=config.column_stretches,
        )
        self.dashboard.tile_removed.connect(self._on_tile_removed)
        self.dashboard.tile_configure_requested.connect(self._configure_dashboard_tile)
        self.dashboard.layout_changed.connect(self._on_dashboard_layout_changed)
        self.setCentralWidget(self.dashboard)
        self._build_dashboard_from_config()
        self.dashboard.set_dashboard_edit_mode(self.edit_dashboard_action.isChecked())
        if old_dashboard is not None:
            old_dashboard.deleteLater()

    def _on_tile_removed(self, tile_id: str) -> None:
        self.data_hub.log(f"User removed dashboard panel {tile_id}", source="user.dashboard")


    # ------------------------------------------------------------------
    # Recording actions
    # ------------------------------------------------------------------
    def _connect_recording_panel(self) -> None:
        panel = self.recording_panel
        panel.start_requested.connect(self._start_sensor_logging)
        panel.stop_requested.connect(self._stop_sensor_logging)
        panel.snapshot_requested.connect(self._save_snapshot)
        panel.save_now_requested.connect(self._save_session_now)
        panel.export_logs_requested.connect(self._export_logs)
        panel.save_close_requested.connect(self._save_and_close)
        panel.base_directory_changed.connect(self._set_recording_base_directory)
        panel.autosave_interval_changed.connect(self.session_recorder.set_autosave_interval)

    @QtCore.pyqtSlot(object)
    def _start_sensor_logging(self, sensor_ids: object) -> None:
        try:
            if self.session_recorder.session_directory is None:
                self.session_recorder.set_base_directory(self.recording_panel.directory_edit.text())
            directory = self.session_recorder.start_sensor_logging(list(sensor_ids))
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Could not start logging", str(exc))
            return
        self.data_hub.log(
            "User started sensor logging",
            source="user.recording",
            details={"sensors": sorted(self.session_recorder.selected_sensor_ids), "directory": str(directory)},
        )

    def _stop_sensor_logging(self) -> None:
        try:
            directory = self.session_recorder.stop_sensor_logging()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.data_hub.log(
            "User stopped sensor logging and saved buffered data",
            source="user.recording",
            details={"directory": str(directory)},
        )
        self.session_recorder.save_now()

    def _save_snapshot(self) -> None:
        try:
            snapshot = self.session_recorder.save_snapshot()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Snapshot failed", str(exc))
            return
        self.data_hub.log(
            "User saved a non-terminating data snapshot",
            source="user.recording",
            details={"snapshot": str(snapshot)},
        )
        self.session_recorder.save_now()
        self.statusBar().showMessage(f"Snapshot saved to {snapshot}")

    def _save_session_now(self) -> None:
        try:
            directory = self.session_recorder.save_now()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.data_hub.log(
            "User manually saved the current session",
            source="user.recording",
            details={"directory": str(directory)},
        )
        self.session_recorder.save_now()
        self.statusBar().showMessage(f"Session saved to {directory}")

    def _export_logs(self) -> None:
        default = self.session_recorder.ensure_session_directory() / "system_log_export.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export logs",
            str(default),
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return
        try:
            self.session_recorder.export_logs(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Log export failed", str(exc))
            return
        self.data_hub.log(f"User exported logs to {path}", source="user.recording")
        self.session_recorder.save_now()

    def _set_recording_base_directory(self, path: str) -> None:
        try:
            self.session_recorder.set_base_directory(path)
        except RuntimeError as exc:
            QtWidgets.QMessageBox.information(self, "Session already created", str(exc))

    def _save_and_close(self) -> None:
        response = QtWidgets.QMessageBox.question(
            self,
            "Save and close?",
            "Save all buffered logs and sensor data, stop hardware communication, and close the application?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel,
        )
        if response != QtWidgets.QMessageBox.Yes:
            return
        self._save_close_confirmed = True
        self.close()

    @QtCore.pyqtSlot(bool)
    def _on_connection_changed(self, connected: bool) -> None:
        # Aggregate fallback used before individual device statuses arrive.
        if not self.data_hub.device_connections:
            self.connection_label.setText(
                "Hardware: connected" if connected else "Hardware: disconnected"
            )

    @QtCore.pyqtSlot(str, bool)
    def _on_device_connection_changed(self, device_id: str, connected: bool) -> None:
        enabled_count = sum(1 for definition in self.device_definitions.values() if definition.enabled)
        connected_count = sum(self.data_hub.device_connections.values())
        self.connection_label.setText(
            f"Hardware: {connected_count}/{enabled_count} devices connected"
        )

    @QtCore.pyqtSlot(bool)
    def _on_recording_changed(self, active: bool) -> None:
        self.recording_status_label.setText("Sensor logging: ACTIVE" if active else "Sensor logging: inactive")
        self.recording_panel.set_recording_active(active)
        self.start_logging_action.setEnabled(not active)
        self.stop_logging_action.setEnabled(active)

    # ------------------------------------------------------------------
    # Help / shutdown
    # ------------------------------------------------------------------
    def _show_shortcuts(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Editing shortcuts",
            "Runtime mode:\n"
            "  Click an enabled element to toggle it through the hardware service.\n"
            "  Right-click an element to toggle or lock/unlock it.\n\n"
            "Valve-layout edit mode:\n"
            "  Ctrl+E: toggle valve-layout editing\n"
            "  Ctrl+Z / Ctrl+Y: undo / redo\n"
            "  Ctrl+N: add a new element\n"
            "  Ctrl+P: add pipes by clicking endpoints\n"
            "  R / Shift+R: rotate selected ±90°\n"
            "  Delete/Backspace: delete selected\n\n"
            "Dashboard layout editing:\n"
            "  Ctrl+D: toggle dashboard editing\n"
            "  Runtime mode keeps all four operational panels fixed.\n"
            "  In dashboard edit mode, use each panel's gear button to change its row, column, or span.\n"
            "  Removable panels also show a remove button.\n\n"
            "Recording data:\n"
            "  Select sensors in the Session Recording panel, then start logging.\n"
            "  Save Snapshot flushes/copies current data without stopping acquisition.",
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self._shutdown_complete:
            event.accept()
            return
        if not self._maybe_save_dirty() or not self._maybe_save_dashboard_dirty():
            event.ignore()
            return
        if self.session_recorder.sensor_logging_active and not self._save_close_confirmed:
            response = QtWidgets.QMessageBox.question(
                self,
                "Sensor logging is active",
                "Save all buffered sensor data and logs, stop acquisition, and close?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Cancel,
            )
            if response != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
        try:
            self.data_hub.log("Application shutdown requested", source="application")
            self.device_manager.stop()
            QtWidgets.QApplication.processEvents()
            self.data_hub.log("All device services stopped", source="application")
            # Stop GUI bridge subscriptions after final device events have been
            # published; the recorder still has its independent subscriptions.
            self.qt_data_bridge.close()
            self.session_recorder.finalize()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Shutdown save error",
                f"The application encountered an error while saving session data:\n{exc}",
            )
            event.ignore()
            return
        logging.getLogger().removeHandler(self.qt_log_handler)
        self._shutdown_complete = True
        event.accept()
