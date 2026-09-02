from __future__ import annotations

"""Central actuator registry.

This object is deliberately the *only* authoritative owner of physical relay
bindings.  GUI elements store actuator IDs, command producers resolve those IDs
at command time, and editor widgets update bindings here instead of duplicating
relay numbers in several YAML files.
"""

from collections import defaultdict
from typing import Iterable

from PyQt5 import QtCore

from .models import ActuatorDefinition


class ActuatorRegistry(QtCore.QObject):
    """Mutable application-wide collection of :class:`ActuatorDefinition`.

    The registry emits ``changed`` whenever definitions/bindings change so the
    valve canvas, validation browser, and any future actuator-management UI can
    refresh without polling.
    """

    changed = QtCore.pyqtSignal()
    binding_changed = QtCore.pyqtSignal(str)  # actuator_id

    def __init__(
        self,
        definitions: Iterable[ActuatorDefinition] = (),
        *,
        relay_count: int = 24,
        known_device_ids: Iterable[str] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.relay_count = int(relay_count)
        # A registry may be constructed without device knowledge in small unit
        # tests, but the application passes every configured device ID here.
        # Existing YAML with an unknown device is still loadable so validation
        # can explain it; *new* edits are rejected by update/upsert operations.
        self.known_device_ids = (
            {str(device_id) for device_id in known_device_ids}
            if known_device_ids is not None
            else None
        )
        self._definitions: dict[str, ActuatorDefinition] = {
            definition.actuator_id: definition for definition in definitions
        }

    @property
    def definitions(self) -> dict[str, ActuatorDefinition]:
        """Return a shallow copy so callers cannot replace registry entries."""

        return dict(self._definitions)

    def all(self) -> list[ActuatorDefinition]:
        return list(self._definitions.values())

    def replace_all(self, definitions: Iterable[ActuatorDefinition]) -> None:
        """Replace the complete registry contents and notify all observers.

        This is intentionally a registry-level operation rather than callers
        reaching into ``_definitions``.  It is used when a user explicitly
        discards unsaved actuator edits and reloads ``actuators.yaml``.

        The replacement is validated for duplicate actuator IDs before any
        state is changed.  Physical relay conflicts are *not* rejected here:
        old configuration files may contain a conflict, and preserving that
        state allows :meth:`validate` and the GUI validation panel to explain
        the problem instead of silently dropping a binding.
        """

        replacement: dict[str, ActuatorDefinition] = {}
        for definition in definitions:
            actuator_id = str(definition.actuator_id)
            if actuator_id in replacement:
                raise ValueError(f"Duplicate actuator id: {actuator_id!r}")
            replacement[actuator_id] = definition

        old_bindings = {
            actuator_id: (definition.device_id, definition.relay_number)
            for actuator_id, definition in self._definitions.items()
        }
        new_bindings = {
            actuator_id: (definition.device_id, definition.relay_number)
            for actuator_id, definition in replacement.items()
        }

        self._definitions = replacement

        # A binding-specific signal is useful for widgets that only need to
        # refresh one logical actuator.  Emit it for IDs whose binding appeared,
        # disappeared, or changed, followed by one coarse registry notification.
        for actuator_id in sorted(set(old_bindings) | set(new_bindings)):
            if old_bindings.get(actuator_id) != new_bindings.get(actuator_id):
                self.binding_changed.emit(actuator_id)
        self.changed.emit()

    def get(self, actuator_id: str) -> ActuatorDefinition:
        try:
            return self._definitions[str(actuator_id)]
        except KeyError as exc:
            raise KeyError(f"Unknown actuator id: {actuator_id!r}") from exc

    def maybe_get(self, actuator_id: str | None) -> ActuatorDefinition | None:
        if not actuator_id:
            return None
        return self._definitions.get(str(actuator_id))

    def ensure(
        self,
        actuator_id: str,
        *,
        label: str | None = None,
        kind: str = "relay",
        device_id: str = "controller",
        relay_number: int | None = None,
        enabled: bool = True,
        default_active: bool = False,
        metadata: dict | None = None,
        emit: bool = True,
    ) -> ActuatorDefinition:
        """Return an existing definition or create one.

        This is primarily used by backwards-compatibility migration when old
        panel/dashboard files still carry a relay number directly.
        """

        actuator_id = str(actuator_id)
        existing = self._definitions.get(actuator_id)
        if existing is not None:
            return existing
        definition = ActuatorDefinition(
            actuator_id=actuator_id,
            label=str(label or actuator_id),
            kind=str(kind),
            device_id=str(device_id),
            relay_number=relay_number,
            enabled=bool(enabled),
            default_active=bool(default_active),
            metadata=dict(metadata or {}),
        )
        self._definitions[actuator_id] = definition
        if emit:
            self.changed.emit()
        return definition

    def _validate_edit_binding(
        self,
        *,
        device_id: str,
        relay_number: int | None,
        allow_unknown_device: bool = False,
    ) -> tuple[str, int | None]:
        """Normalize and validate a binding supplied by an editor/command API."""

        normalized_device = str(device_id)
        relay = None if relay_number in (None, 0) else int(relay_number)
        if relay is not None and not 1 <= relay <= self.relay_count:
            raise ValueError(
                f"Relay {relay} is outside valid range 1-{self.relay_count}"
            )
        if (
            not allow_unknown_device
            and self.known_device_ids is not None
            and normalized_device not in self.known_device_ids
        ):
            raise ValueError(
                f"Unknown device {normalized_device!r}; define it in devices.yaml before binding actuators to it"
            )
        return normalized_device, relay

    def upsert_many(
        self,
        definitions: Iterable[ActuatorDefinition],
        *,
        allow_conflict: bool = False,
        allow_unknown_device: bool = False,
    ) -> None:
        """Atomically create/update several actuator definitions.

        This is the preferred editor operation.  All proposed device/relay
        bindings are validated against the *final* registry state before any
        mutation occurs.  Therefore a failed edit cannot leave a half-created
        actuator behind, and several actuators may swap relays in one action.
        """

        proposed_by_id: dict[str, ActuatorDefinition] = {}
        for raw in definitions:
            actuator_id = str(raw.actuator_id)
            if actuator_id in proposed_by_id:
                raise ValueError(f"Duplicate actuator id in edit: {actuator_id!r}")
            device_id, relay = self._validate_edit_binding(
                device_id=raw.device_id,
                relay_number=raw.relay_number,
                allow_unknown_device=allow_unknown_device,
            )
            proposed_by_id[actuator_id] = ActuatorDefinition(
                actuator_id=actuator_id,
                label=str(raw.label),
                kind=str(raw.kind),
                device_id=device_id,
                relay_number=relay,
                enabled=bool(raw.enabled),
                default_active=bool(raw.default_active),
                metadata=dict(raw.metadata),
            )

        if not proposed_by_id:
            return

        prospective = dict(self._definitions)
        prospective.update(proposed_by_id)

        if not allow_conflict:
            usage: dict[tuple[str, int], list[str]] = defaultdict(list)
            for definition in prospective.values():
                if definition.relay_number is not None:
                    usage[(definition.device_id, int(definition.relay_number))].append(
                        definition.actuator_id
                    )
            duplicates = [
                (binding, owners)
                for binding, owners in usage.items()
                if len(owners) > 1
            ]
            if duplicates:
                (device_id, relay), owners = duplicates[0]
                raise ValueError(
                    f"{device_id} relay {relay} is already assigned to "
                    + ", ".join(owners)
                )

        old_bindings = {
            actuator_id: (
                self._definitions[actuator_id].device_id,
                self._definitions[actuator_id].relay_number,
            )
            if actuator_id in self._definitions
            else None
            for actuator_id in proposed_by_id
        }

        self._definitions.update(proposed_by_id)

        for actuator_id, definition in proposed_by_id.items():
            if old_bindings[actuator_id] != (definition.device_id, definition.relay_number):
                self.binding_changed.emit(actuator_id)
        self.changed.emit()

    def upsert(
        self,
        definition: ActuatorDefinition,
        *,
        allow_conflict: bool = False,
        allow_unknown_device: bool = False,
    ) -> ActuatorDefinition:
        """Atomically create or replace one logical actuator definition."""

        self.upsert_many(
            [definition],
            allow_conflict=allow_conflict,
            allow_unknown_device=allow_unknown_device,
        )
        return self.get(definition.actuator_id)

    def update_definition(
        self,
        actuator_id: str,
        *,
        label: str | None = None,
        kind: str | None = None,
        enabled: bool | None = None,
        default_active: bool | None = None,
        metadata: dict | None = None,
    ) -> ActuatorDefinition:
        definition = self.get(actuator_id)
        if label is not None:
            definition.label = str(label)
        if kind is not None:
            definition.kind = str(kind)
        if enabled is not None:
            definition.enabled = bool(enabled)
        if default_active is not None:
            definition.default_active = bool(default_active)
        if metadata is not None:
            definition.metadata = dict(metadata)
        self.changed.emit()
        return definition

    def update_bindings(
        self,
        bindings: dict[str, tuple[str, int | None]],
        *,
        allow_conflict: bool = False,
        allow_unknown_device: bool = False,
    ) -> None:
        """Atomically apply several device/relay assignments.

        Validation is performed against the *final* proposed registry state,
        which means two actuators may swap relays in one operation without an
        artificial intermediate collision.
        """

        normalized: dict[str, tuple[str, int | None]] = {}
        for actuator_id, (device_id, relay_number) in bindings.items():
            self.get(actuator_id)  # validate ID
            normalized[str(actuator_id)] = self._validate_edit_binding(
                device_id=str(device_id),
                relay_number=relay_number,
                allow_unknown_device=allow_unknown_device,
            )

        if not allow_conflict:
            prospective: dict[tuple[str, int], list[str]] = defaultdict(list)
            for definition in self._definitions.values():
                device_id, relay = normalized.get(
                    definition.actuator_id,
                    (definition.device_id, definition.relay_number),
                )
                if relay is not None:
                    prospective[(device_id, int(relay))].append(definition.actuator_id)
            duplicates = [
                (binding, owners)
                for binding, owners in prospective.items()
                if len(owners) > 1
            ]
            if duplicates:
                (device_id, relay), owners = duplicates[0]
                raise ValueError(
                    f"{device_id} relay {relay} is already assigned to "
                    + ", ".join(owners)
                )

        changed_ids: list[str] = []
        for actuator_id, (device_id, relay) in normalized.items():
            definition = self.get(actuator_id)
            if definition.device_id != device_id or definition.relay_number != relay:
                definition.device_id = device_id
                definition.relay_number = relay
                changed_ids.append(actuator_id)
        for actuator_id in changed_ids:
            self.binding_changed.emit(actuator_id)
        if changed_ids:
            self.changed.emit()

    def update_binding(
        self,
        actuator_id: str,
        *,
        device_id: str,
        relay_number: int | None,
        allow_conflict: bool = False,
        allow_unknown_device: bool = False,
    ) -> ActuatorDefinition:
        """Change one physical binding after validating global ownership."""

        self.update_bindings(
            {str(actuator_id): (str(device_id), relay_number)},
            allow_conflict=allow_conflict,
            allow_unknown_device=allow_unknown_device,
        )
        return self.get(actuator_id)

    def owners_for_binding(
        self,
        device_id: str,
        relay_number: int,
        *,
        exclude_actuator_id: str | None = None,
    ) -> list[ActuatorDefinition]:
        return [
            definition
            for definition in self._definitions.values()
            if definition.actuator_id != exclude_actuator_id
            and definition.device_id == str(device_id)
            and definition.relay_number == int(relay_number)
        ]

    def relay_usage(self, device_id: str | None = None) -> dict[tuple[str, int], list[ActuatorDefinition]]:
        usage: dict[tuple[str, int], list[ActuatorDefinition]] = defaultdict(list)
        for definition in self._definitions.values():
            if definition.relay_number is None:
                continue
            if device_id is not None and definition.device_id != device_id:
                continue
            usage[(definition.device_id, int(definition.relay_number))].append(definition)
        return dict(usage)

    def available_relays(
        self,
        device_id: str,
        *,
        exclude_actuator_id: str | None = None,
    ) -> list[int]:
        used = {
            relay
            for (owner_device, relay), owners in self.relay_usage(device_id).items()
            if owner_device == device_id
            and any(owner.actuator_id != exclude_actuator_id for owner in owners)
        }
        return [relay for relay in range(1, self.relay_count + 1) if relay not in used]

    def validate(self) -> list[str]:
        messages: list[str] = []
        for definition in self._definitions.values():
            # Disabled entries may be intentional placeholders for hardware that
            # has not been commissioned yet; they do not require a relay.
            if not definition.enabled:
                continue
            if (
                self.known_device_ids is not None
                and definition.device_id not in self.known_device_ids
            ):
                messages.append(
                    f"{definition.actuator_id}: unknown device {definition.device_id!r}"
                )
            if definition.relay_number is None:
                messages.append(f"{definition.actuator_id}: no relay binding")
            elif not 1 <= int(definition.relay_number) <= self.relay_count:
                messages.append(
                    f"{definition.actuator_id}: relay {definition.relay_number} outside "
                    f"valid range 1-{self.relay_count}"
                )
        for (device_id, relay), owners in sorted(self.relay_usage().items()):
            if len(owners) > 1:
                names = ", ".join(owner.actuator_id for owner in owners)
                messages.append(
                    f"{device_id} relay {relay} is assigned to multiple actuators: {names}"
                )
        return messages
