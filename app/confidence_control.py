"""Compact, synchronized confidence slider and percentage entry."""
from __future__ import annotations

import math

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QSlider, QSpinBox, QWidget


class ConfidenceControl(QWidget):
    """Edit a normalized confidence threshold in whole percentage points.

    Values are restricted to 5–99%, matching the model settings. Both child
    controls report through one signal, including programmatic changes.
    """

    valueChanged = Signal(float)

    def __init__(self, value: float = .25, parent: QWidget | None = None):
        percent = self._to_percent(value)
        super().__init__(parent)
        self._percent = percent
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(5, 99)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(5)
        self.slider.setMinimumWidth(90)
        self.slider.setAccessibleName("Confidence slider")
        self.slider.setValue(percent)

        self.spin = QSpinBox(self)
        self.spin.setRange(5, 99)
        self.spin.setSuffix(" %")
        self.spin.setSingleStep(1)
        self.spin.setFixedWidth(78)
        self.spin.setAccessibleName("Confidence percentage")
        self.spin.setValue(percent)

        tooltip = "Minimum model confidence. Higher values require a stronger match."
        self.slider.setToolTip(tooltip)
        self.spin.setToolTip(tooltip)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)

        self.slider.valueChanged.connect(self._set_percent)
        self.spin.valueChanged.connect(self._set_percent)

    @staticmethod
    def _to_percent(value: float) -> int:
        try:
            normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Confidence must be a finite number between 0.05 and 0.99.") from exc
        if not math.isfinite(normalized) or not .05 <= normalized <= .99:
            raise ValueError("Confidence must be a finite number between 0.05 and 0.99.")
        return round(normalized * 100)

    def value(self) -> float:
        return self._percent / 100.0

    def setValue(self, value: float) -> None:
        self._set_percent(self._to_percent(value))

    def _set_percent(self, percent: int) -> None:
        if percent == self._percent:
            return
        self._percent = percent
        # Block child signals while synchronizing so each user change is
        # delivered to the application once, regardless of the source control.
        with QSignalBlocker(self.slider), QSignalBlocker(self.spin):
            self.slider.setValue(percent)
            self.spin.setValue(percent)
        self.valueChanged.emit(self.value())
