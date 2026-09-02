from __future__ import annotations

"""Dashboard tile for controlling four relay-driven pneumatic crushers.

The crushers share the same relay controller used by the pneumatic valve panel,
but they are intentionally *not* represented as valve-panel elements.  This
keeps the two GUI concepts independent while still routing every hardware
command through :class:`DeviceManager` and the controller's single worker
thread.

Physical convention used by this tile
-------------------------------------
The hardware described for this application is spring/air extended by default
and retracts when its solenoid is powered.  Consequently:

    relay active / powered   -> crusher RAISED / RETRACTED
    relay inactive / off     -> crusher LOWERED / EXTENDED

The Up arrow therefore sends ``is_active=True`` and the Down arrow sends
``is_active=False``.
"""

from dataclasses import dataclass
from typing import Any

from PyQt5 import QtCore, QtWidgets

from ...actuators import ActuatorRegistry
from ...data.data_hub import DataHub
from ...data.models import CommandResult
from ...hardware.device_manager import DeviceManager
from .tile_base import TileWidget


@dataclass(frozen=True)
class CrusherDefinition:
    """Configuration for one physical crusher channel."""

    crusher_id: str
    label: str
    actuator_id: str

    @classmethod
    def from_mapping(cls, data: dict[str, Any], index: int) -> "CrusherDefinition":
        crusher_id = str(data.get("id", f"crusher_{index}"))
        return cls(
            crusher_id=crusher_id,
            label=str(data.get("label", f"Crusher {index}")),
            actuator_id=str(data.get("actuator_id", crusher_id)),
        )


@dataclass
class _CrusherUi:
    """Qt widgets and runtime state belonging to one crusher column."""

    definition: CrusherDefinition
    up_button: QtWidgets.QToolButton
    down_button: QtWidgets.QToolButton
    binding_label: QtWidgets.QLabel
    status_label: QtWidgets.QLabel
    current_powered: bool | None = None
    pending_target: bool | None = None


class CrusherControlTile(TileWidget):
    """Four-channel relay control panel for pneumatic ice crushers.

    The tile owns no serial port and no hardware thread.  It submits generic
    ``set_element_state`` commands to ``DeviceManager`` exactly like the valve
    system does.  ``DeviceManager`` routes those commands to the configured
    controller worker, ensuring the serial communicator still has only one
    owner even when several GUI widgets issue commands.

    Parameters
    ----------
    crushers:
        Four mappings containing ``id``, ``label`` and ``actuator_id``.
        Physical device/relay routing comes from the central actuator registry.
    initialize_retracted:
        If true, queue a powered/retracted command for every valid crusher when
        the tile is created.  This matches the requested safe/default position.
    """

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        device_manager: DeviceManager,
        actuator_registry: ActuatorRegistry,
        data_hub: DataHub,
        crushers: list[dict[str, Any]] | None = None,
        initialize_retracted: bool = True,
        removable: bool = True,
    ) -> None:
        self.device_manager = device_manager
        self.actuator_registry = actuator_registry
        self.data_hub = data_hub
        self.initialize_retracted = bool(initialize_retracted)

        raw_crushers = list(crushers or [])
        # The requested hardware has exactly four crushers.  Missing entries are
        # filled with unassigned defaults so the tile can still render safely.
        while len(raw_crushers) < 4:
            index = len(raw_crushers) + 1
            raw_crushers.append(
                {
                    "id": f"crusher_{index}",
                    "label": f"Crusher {index}",
                    "actuator_id": f"crusher_{index}",
                }
            )
        raw_crushers = raw_crushers[:4]
        self.crushers = [
            CrusherDefinition.from_mapping(data, index)
            for index, data in enumerate(raw_crushers, start=1)
        ]

        self._ui_by_id: dict[str, _CrusherUi] = {}
        self._warning_label = QtWidgets.QLabel()
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet(
            "QLabel { color: #8a4b00; background: #fff3cd; "
            "border: 1px solid #e1b96a; padding: 5px; }"
        )

        content = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(content)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        root.addWidget(self._warning_label)

        columns = QtWidgets.QHBoxLayout()
        columns.setSpacing(10)
        root.addLayout(columns, 1)

        for definition in self.crushers:
            crusher_widget, crusher_ui = self._build_crusher_column(definition)
            self._ui_by_id[definition.crusher_id] = crusher_ui
            columns.addWidget(crusher_widget, 1)

        super().__init__(
            tile_id=tile_id,
            title=title,
            child=content,
            removable=removable,
        )

        # CommandResult arrives through QtDataBridge -> DataHub, so this slot is
        # guaranteed to run in the GUI thread and may safely modify buttons.
        self.data_hub.relay_result_received.connect(self._on_command_result)

        # Device connection changes are reflected immediately in button enable
        # state.  This prevents obviously invalid requests while disconnected.
        self.data_hub.device_connection_changed.connect(self._on_device_connection_changed)

        # Relay/device bindings can be edited from the pneumatic element editor
        # or another dashboard configuration dialog while this tile is alive.
        # Commands already resolve the registry at click time; this signal keeps
        # the human-readable binding labels and enabled state equally current.
        self.actuator_registry.changed.connect(self._on_actuator_registry_changed)

        self._refresh_validation_and_enabled_state()

        # The requested default physical state is powered/retracted.  Commands
        # are queued here; DeviceManager's worker will execute them after the
        # controller service connects, even if the tile was constructed before
        # the QThread starts.
        if self.initialize_retracted:
            QtCore.QTimer.singleShot(0, self.retract_all)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_crusher_column(
        self,
        definition: CrusherDefinition,
    ) -> tuple[QtWidgets.QWidget, _CrusherUi]:
        panel = QtWidgets.QFrame()
        panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        name = QtWidgets.QLabel(definition.label)
        name_font = name.font()
        name_font.setBold(True)
        name.setFont(name_font)
        name.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(name)

        actuator = self.actuator_registry.maybe_get(definition.actuator_id)
        relay_text = (
            f"{definition.actuator_id} · {actuator.device_id} R{actuator.relay_number}"
            if actuator is not None and actuator.relay_number is not None
            else f"{definition.actuator_id} · unassigned"
        )
        relay_label = QtWidgets.QLabel(relay_text)
        relay_label.setAlignment(QtCore.Qt.AlignCenter)
        relay_label.setStyleSheet("color: palette(mid);")
        layout.addWidget(relay_label)

        up_button = QtWidgets.QToolButton()
        up_button.setText("▲")
        up_button.setToolTip("Raise / retract crusher (power solenoid)")
        up_button.setMinimumSize(62, 54)
        up_font = up_button.font()
        up_font.setPointSize(max(18, up_font.pointSize() + 8))
        up_font.setBold(True)
        up_button.setFont(up_font)

        down_button = QtWidgets.QToolButton()
        down_button.setText("▼")
        down_button.setToolTip("Lower / extend crusher (remove solenoid power)")
        down_button.setMinimumSize(62, 54)
        down_button.setFont(up_font)

        status_label = QtWidgets.QLabel("State unknown")
        status_label.setAlignment(QtCore.Qt.AlignCenter)
        status_label.setWordWrap(True)

        up_button.clicked.connect(
            lambda _checked=False, crusher_id=definition.crusher_id: self._request_state(
                crusher_id, True
            )
        )
        down_button.clicked.connect(
            lambda _checked=False, crusher_id=definition.crusher_id: self._request_state(
                crusher_id, False
            )
        )

        layout.addStretch(1)
        layout.addWidget(up_button)
        layout.addWidget(status_label)
        layout.addWidget(down_button)
        layout.addStretch(1)

        ui = _CrusherUi(
            definition=definition,
            up_button=up_button,
            down_button=down_button,
            binding_label=relay_label,
            status_label=status_label,
            current_powered=None,
        )
        self._apply_visual_state(ui)
        return panel, ui

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def retract_all(self) -> None:
        """Queue powered/retracted commands for every valid crusher."""

        self._refresh_validation_and_enabled_state()
        for crusher_id, ui in self._ui_by_id.items():
            if self._crusher_can_command(ui):
                self._request_state(crusher_id, True)

    def _request_state(self, crusher_id: str, powered: bool) -> None:
        """Queue one crusher state without touching the serial port directly."""

        ui = self._ui_by_id[crusher_id]
        self._refresh_validation_and_enabled_state()
        if not self._crusher_can_command(ui):
            return
        if ui.pending_target is not None:
            return

        definition = ui.definition
        actuator = self.actuator_registry.get(definition.actuator_id)

        ui.pending_target = bool(powered)
        self._apply_visual_state(ui)
        self._refresh_validation_and_enabled_state()

        # Namespace element IDs by tile ID.  This lets several crusher-control
        # tiles coexist without their asynchronous command results colliding.
        command_element_id = f"{self.tile_id}.{definition.crusher_id}"

        try:
            self.device_manager.set_actuator_state(
                actuator_id=definition.actuator_id,
                element_id=command_element_id,
                element_type="crusher_solenoid",
                is_active=bool(powered),
                metadata={
                    "origin": "user.crusher_control",
                    "crusher_id": definition.crusher_id,
                    "crusher_label": definition.label,
                    "physical_state": "retracted" if powered else "extended",
                    "requested_state_label": (
                        "RAISED/RETRACTED" if powered else "LOWERED/EXTENDED"
                    ),
                },
            )
        except Exception as exc:
            # Routing/configuration errors can occur before a DeviceWorker sees
            # the command (for example an unknown device_id).  Treat them like
            # failed asynchronous commands and keep the prior confirmed state.
            ui.pending_target = None
            self._apply_visual_state(ui, error=str(exc))
            self.data_hub.log(
                f"Crusher command could not be queued: {definition.label}: {exc}",
                level="ERROR",
                source="user.crusher_control",
                details={
                    "crusher_id": definition.crusher_id,
                    "actuator_id": definition.actuator_id,
                    "device_id": actuator.device_id,
                },
            )
            self._refresh_validation_and_enabled_state()

    @QtCore.pyqtSlot(object)
    def _on_command_result(self, result: CommandResult | dict[str, Any]) -> None:
        """Apply only results that belong to this tile's crusher commands."""

        if isinstance(result, dict):
            device_id = str(result.get("device_id", ""))
            command_type = str(result.get("command_type", ""))
            success = bool(result.get("success", False))
            message = str(result.get("message", ""))
            payload = dict(result.get("payload", {}) or {})
        else:
            device_id = result.device_id
            command_type = result.command_type
            success = result.success
            message = result.message
            payload = dict(result.payload)

        if command_type != "set_element_state":
            return

        element_id = str(payload.get("element_id", ""))
        prefix = f"{self.tile_id}."
        if not element_id.startswith(prefix):
            return

        crusher_id = element_id[len(prefix):]
        ui = self._ui_by_id.get(crusher_id)
        if ui is None:
            return

        requested_powered = bool(payload.get("is_active", ui.pending_target))
        ui.pending_target = None

        if success:
            ui.current_powered = requested_powered
            self._apply_visual_state(ui)
        else:
            self._apply_visual_state(ui, error=message or "Command failed")

        self._refresh_validation_and_enabled_state()

    # ------------------------------------------------------------------
    # Validation / state presentation
    # ------------------------------------------------------------------
    def _crusher_can_command(self, ui: _CrusherUi) -> bool:
        actuator = self.actuator_registry.maybe_get(ui.definition.actuator_id)
        if actuator is None or not actuator.enabled or actuator.relay_number is None:
            return False
        if ui.pending_target is not None:
            return False
        if actuator.device_id in self.data_hub.device_connections:
            if not self.data_hub.device_connections[actuator.device_id]:
                return False
        return True

    def _refresh_validation_and_enabled_state(self) -> None:
        warnings: list[str] = []
        for ui in self._ui_by_id.values():
            actuator = self.actuator_registry.maybe_get(ui.definition.actuator_id)
            if actuator is None:
                ui.binding_label.setText(f"{ui.definition.actuator_id} · missing")
                warnings.append(f"{ui.definition.label}: actuator {ui.definition.actuator_id!r} is missing")
            elif actuator.relay_number is None:
                ui.binding_label.setText(
                    f"{ui.definition.actuator_id} · {actuator.device_id} · unassigned"
                )
                warnings.append(f"{ui.definition.label}: actuator {ui.definition.actuator_id} is unassigned")
            else:
                ui.binding_label.setText(
                    f"{ui.definition.actuator_id} · {actuator.device_id} R{actuator.relay_number}"
                )
                if not actuator.enabled:
                    warnings.append(f"{ui.definition.label}: actuator {ui.definition.actuator_id} is disabled")
            enabled = self._crusher_can_command(ui)
            ui.up_button.setEnabled(enabled)
            ui.down_button.setEnabled(enabled)
        self._warning_label.setText("\n".join(dict.fromkeys(warnings)))
        self._warning_label.setVisible(bool(warnings))

    def _apply_visual_state(self, ui: _CrusherUi, error: str | None = None) -> None:
        """Render confirmed/pending/error state without changing hardware."""

        if error:
            ui.status_label.setText(f"ERROR\n{error}")
            ui.status_label.setStyleSheet("color: #b00020; font-weight: bold;")
            return

        if ui.pending_target is not None:
            target = "Raise / Retract" if ui.pending_target else "Lower / Extend"
            ui.status_label.setText(f"Pending…\n{target}")
            ui.status_label.setStyleSheet("color: #8a5a00; font-weight: bold;")
            return

        if ui.current_powered is None:
            ui.status_label.setText("State unknown")
            ui.status_label.setStyleSheet("color: palette(mid); font-weight: bold;")
            ui.up_button.setStyleSheet("")
            ui.down_button.setStyleSheet("")
        elif ui.current_powered:
            ui.status_label.setText("Raised / Retracted")
            ui.status_label.setStyleSheet("font-weight: bold;")
            ui.up_button.setStyleSheet("font-weight: bold; border: 2px solid palette(highlight);")
            ui.down_button.setStyleSheet("")
        else:
            ui.status_label.setText("Lowered / Extended")
            ui.status_label.setStyleSheet("font-weight: bold;")
            ui.up_button.setStyleSheet("")
            ui.down_button.setStyleSheet("font-weight: bold; border: 2px solid palette(highlight);")

    @QtCore.pyqtSlot()
    def _on_actuator_registry_changed(self) -> None:
        self._refresh_validation_and_enabled_state()

    @QtCore.pyqtSlot(str, bool)
    def _on_device_connection_changed(self, device_id: str, connected: bool) -> None:
        if any(
            (actuator := self.actuator_registry.maybe_get(ui.definition.actuator_id)) is not None
            and actuator.device_id == device_id
            for ui in self._ui_by_id.values()
        ):
            self._refresh_validation_and_enabled_state()
