from __future__ import annotations

from PyQt5 import QtWidgets

from ..models import PanelConfig, PipeConfig


class PipeDialog(QtWidgets.QDialog):
    """Simple dialog for editing a selected pipe segment."""

    def __init__(
        self,
        *,
        panel_config: PanelConfig,
        existing: PipeConfig,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel_config = panel_config
        self.existing = existing
        self.setWindowTitle("Edit Pipe")
        self.setModal(True)
        self._build_ui()
        self._populate()

    def result_pipe(self) -> PipeConfig:
        return PipeConfig(
            id=self.existing.id,
            start=(float(self.x1_spin.value()), float(self.y1_spin.value())),
            end=(float(self.x2_spin.value()), float(self.y2_spin.value())),
            thickness=float(self.thickness_spin.value()),
            label=self.label_edit.text().strip(),
            metadata=dict(self.existing.metadata),
        )

    def _build_ui(self) -> None:
        form = QtWidgets.QFormLayout()
        self.label_edit = QtWidgets.QLineEdit()
        self.x1_spin = QtWidgets.QDoubleSpinBox()
        self.y1_spin = QtWidgets.QDoubleSpinBox()
        self.x2_spin = QtWidgets.QDoubleSpinBox()
        self.y2_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self.x1_spin, self.y1_spin, self.x2_spin, self.y2_spin):
            spin.setRange(-10000.0, 10000.0)
            spin.setDecimals(1)
            spin.setSingleStep(5.0)
        self.thickness_spin = QtWidgets.QDoubleSpinBox()
        self.thickness_spin.setRange(2.0, 100.0)
        self.thickness_spin.setDecimals(1)
        self.thickness_spin.setSingleStep(1.0)

        form.addRow("Label", self.label_edit)
        form.addRow("Start X", self.x1_spin)
        form.addRow("Start Y", self.y1_spin)
        form.addRow("End X", self.x2_spin)
        form.addRow("End Y", self.y2_spin)
        form.addRow("Thickness", self.thickness_spin)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _populate(self) -> None:
        self.label_edit.setText(self.existing.label)
        self.x1_spin.setValue(self.existing.start[0])
        self.y1_spin.setValue(self.existing.start[1])
        self.x2_spin.setValue(self.existing.end[0])
        self.y2_spin.setValue(self.existing.end[1])
        self.thickness_spin.setValue(self.existing.thickness)
