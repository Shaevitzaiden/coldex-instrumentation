from __future__ import annotations

"""Dashboard tile summarizing hardware connectivity and telemetry health.

This tile is deliberately a *consumer only*.  It never opens a serial port,
polls a communicator, or owns a worker thread.  DeviceManager remains the sole
owner of device lifecycle and serial I/O; this widget simply observes the
DeviceStatus and SensorFrame objects already delivered to the GUI by DataHub.
"""

import collections
import time

from PyQt5 import QtCore, QtGui, QtWidgets

from ...data.data_hub import DataHub
from ...data.models import DeviceDefinition, DeviceStatus, SensorFrame
from .tile_base import TileWidget


class DeviceConnectivityTile(TileWidget):
    """Show live connection and communication-health information per device.

    Parameters
    ----------
    device_ids:
        Optional subset of configured device IDs.  ``None`` means every device
        from devices.yaml.  This is primarily an advanced YAML option; the
        normal Add Dashboard Panel flow displays all devices.
    rate_window_s:
        Rolling time window used to estimate GUI-observed frame frequency.
        The value is based on normalized SensorFrames reaching DataHub.  Devices
        that are command-only may therefore legitimately show ``No data``.
    """

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        data_hub: DataHub,
        device_definitions: dict[str, DeviceDefinition],
        device_ids: list[str] | None = None,
        rate_window_s: float = 5.0,
        removable: bool = True,
    ) -> None:
        self.data_hub = data_hub
        self.rate_window_s = max(1.0, float(rate_window_s))

        if device_ids:
            requested = {str(device_id) for device_id in device_ids}
            self.device_definitions = {
                device_id: definition
                for device_id, definition in device_definitions.items()
                if device_id in requested
            }
        else:
            self.device_definitions = dict(device_definitions)

        # Runtime communication statistics are intentionally local to the GUI
        # widget.  They are diagnostics, not authoritative acquisition data.
        self._last_frame_monotonic: dict[str, float] = {}
        self._recent_frame_times: dict[str, collections.deque[float]] = {
            device_id: collections.deque() for device_id in self.device_definitions
        }
        self._last_sequence: dict[str, int] = {}
        self._sequence_gaps: dict[str, int] = collections.defaultdict(int)

        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(6, 6, 6, 6)

        self.table = QtWidgets.QTableWidget(len(self.device_definitions), 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Device",
                "Role",
                "Status",
                "Port",
                "Baud",
                "Last data",
                "Frame rate",
                "Seq gaps",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col in range(1, 8):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeToContents
            )
        layout.addWidget(self.table)

        self._row_by_device: dict[str, int] = {}
        for row, (device_id, definition) in enumerate(self.device_definitions.items()):
            self._row_by_device[device_id] = row

            device_item = self._set_text(row, 0, device_id)
            if definition.description:
                device_item.setToolTip(definition.description)

            role = "Control + data" if definition.command_target else "Data / peripheral"
            self._set_text(row, 1, role)

            status_text = "Starting" if definition.enabled else "Disabled"
            status_item = self._set_text(row, 2, status_text)
            if not definition.enabled:
                status_item.setForeground(QtGui.QBrush(QtGui.QColor("#777777")))

            self._set_text(row, 3, str(definition.connection.get("port", "—")))
            self._set_text(row, 4, str(definition.connection.get("baudrate", "—")))
            self._set_text(row, 5, "No data")
            self._set_text(row, 6, "—")
            self._set_text(row, 7, "0")

        super().__init__(tile_id=tile_id, title=title, child=content, removable=removable)

        # Both signals originate from QtDataBridge -> DataHub, so all table
        # updates below execute safely on the main GUI thread.
        self.data_hub.device_status_changed.connect(self._on_device_status)
        self.data_hub.frame_received.connect(self._on_frame)

        # A tile may be created after one or more devices have already emitted
        # their initial status.  Seed the table from DataHub's latest cache so
        # it does not misleadingly remain at "Starting" until a later change.
        for status in self.data_hub.device_statuses.values():
            self._on_device_status(status)

        # Seed last-data age from the per-device DataHub cache.  Rate still
        # needs multiple new frames, but a newly added tile immediately knows
        # whether each device has produced telemetry recently.
        monotonic_now = time.monotonic()
        for device_id, frame in self.data_hub.latest_frames.items():
            if device_id not in self._row_by_device:
                continue
            if frame.host_received_monotonic_ns:
                last = frame.host_received_monotonic_ns / 1_000_000_000.0
                self._last_frame_monotonic[device_id] = min(monotonic_now, last)
            else:
                self._last_frame_monotonic[device_id] = monotonic_now
            if frame.sequence is not None:
                self._last_sequence[device_id] = int(frame.sequence)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh_ages_and_rates)
        self._timer.start(500)

    def _set_text(self, row: int, column: int, text: str) -> QtWidgets.QTableWidgetItem:
        item = self.table.item(row, column)
        if item is None:
            item = QtWidgets.QTableWidgetItem()
            self.table.setItem(row, column, item)
        item.setText(text)
        return item

    @QtCore.pyqtSlot(object)
    def _on_device_status(self, status: DeviceStatus) -> None:
        row = self._row_by_device.get(status.device_id)
        if row is None:
            return

        definition = self.device_definitions[status.device_id]
        if not definition.enabled:
            # Disabled devices have no DeviceWorker and therefore normally never
            # emit status, but keep the table semantically correct if one does.
            text = "Disabled"
            color = "#777777"
        elif status.connected:
            text = "Connected"
            color = "#177245"
        else:
            text = "Disconnected"
            color = "#a61b1b"

        item = self._set_text(row, 2, text)
        item.setToolTip(status.message)
        item.setForeground(QtGui.QBrush(QtGui.QColor(color)))

    @QtCore.pyqtSlot(object)
    def _on_frame(self, frame: SensorFrame) -> None:
        device_id = frame.source_id
        if device_id not in self._row_by_device:
            return

        now = time.monotonic()
        self._last_frame_monotonic[device_id] = now

        times = self._recent_frame_times.setdefault(device_id, collections.deque())
        times.append(now)
        self._trim_rate_window(times, now)

        # A positive jump indicates missing sequence numbers.  Equal/decreasing
        # sequence values are treated as a device restart/wrap rather than as a
        # giant false gap; the new sequence simply becomes the next baseline.
        if frame.sequence is not None:
            previous = self._last_sequence.get(device_id)
            sequence = int(frame.sequence)
            if previous is not None and sequence > previous + 1:
                self._sequence_gaps[device_id] += sequence - previous - 1
            self._last_sequence[device_id] = sequence

    def _trim_rate_window(self, times: collections.deque[float], now: float) -> None:
        while times and now - times[0] > self.rate_window_s:
            times.popleft()

    def _refresh_ages_and_rates(self) -> None:
        now = time.monotonic()
        for device_id, row in self._row_by_device.items():
            definition = self.device_definitions[device_id]
            if not definition.enabled:
                self._set_text(row, 5, "—")
                self._set_text(row, 6, "—")
                self._set_text(row, 7, "0")
                continue

            last = self._last_frame_monotonic.get(device_id)
            if last is None:
                self._set_text(row, 5, "No data")
                self._set_text(row, 6, "—")
            else:
                age = max(0.0, now - last)
                self._set_text(row, 5, f"{age:.1f} s")

                times = self._recent_frame_times.get(device_id)
                if times is not None:
                    self._trim_rate_window(times, now)

                if times is not None and len(times) >= 2:
                    span = times[-1] - times[0]
                    rate = (len(times) - 1) / span if span > 0 else 0.0
                    self._set_text(row, 6, f"{rate:.1f} Hz")
                else:
                    self._set_text(row, 6, "—")

            self._set_text(row, 7, str(self._sequence_gaps.get(device_id, 0)))
