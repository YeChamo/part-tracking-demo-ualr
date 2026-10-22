"""A larger presentation of an existing camera view and its overlays.

The supplied widget reads the same frame/state as the main window. This window
only requests repaints; camera acquisition, inference and conveyor control stay
with their existing owners.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class FullscreenCameraWindow(QWidget):
    closed = Signal()

    def __init__(self, view: QWidget, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Window)
        self.view = view
        self._closed_emitted = False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("Part Tracking Demo UALR — Camera")
        if parent is not None and parent.styleSheet():
            self.setStyleSheet(parent.styleSheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        header = QHBoxLayout()
        header.addWidget(QLabel("Camera view"))
        header.addStretch(1)
        self.exit_button = QPushButton("Exit full screen (Esc)")
        self.exit_button.clicked.connect(self.close)
        header.addWidget(self.exit_button)
        layout.addLayout(header)
        layout.addWidget(view, 1)

        self._refresh = QTimer(self)
        self._refresh.setInterval(30)
        self._refresh.timeout.connect(view.update)
        self._exit_shortcuts = []
        for key in ("Esc", "F11"):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self.close)
            self._exit_shortcuts.append(shortcut)

    def open_fullscreen(self) -> None:
        self._closed_emitted = False
        self.showFullScreen()
        self._refresh.start()
        self.view.update()
        self.activateWindow()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F11):
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        super().closeEvent(event)
        if event.isAccepted():
            self._refresh.stop()
            if not self._closed_emitted:
                self._closed_emitted = True
                self.closed.emit()
