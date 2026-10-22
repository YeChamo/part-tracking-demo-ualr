"""Full-screen rendering controls; no camera, inference, or motion hardware."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from app.fullscreen_view import FullscreenCameraWindow


class CountingView(QWidget):
    def __init__(self, shared_state):
        super().__init__()
        self.shared_state = shared_state
        self.paint_count = 0
        self.last_frame = None

    def paintEvent(self, event):
        self.paint_count += 1
        self.last_frame = self.shared_state["frame"]


class FullscreenViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.main = QWidget()
        self.main.worker = object()
        self.main.shared_state = {"frame": object()}
        self.main.show()

    def tearDown(self):
        self.main.close()
        self.main.deleteLater()
        self.qt.processEvents()

    def make_window(self):
        view = CountingView(self.main.shared_state)
        window = FullscreenCameraWindow(view, self.main)
        window.open_fullscreen()
        self.qt.processEvents()
        return window, view

    def test_fullscreen_repaints_the_supplied_shared_view(self):
        original_worker = self.main.worker
        window, view = self.make_window()
        self.assertTrue(window.isWindow())
        self.assertTrue(window.isFullScreen())
        self.assertIs(window.view, view)
        self.assertIs(view.parentWidget(), window)
        first_paints = view.paint_count
        next_frame = object()
        self.main.shared_state["frame"] = next_frame
        QTest.qWait(100)
        self.assertGreater(view.paint_count, first_paints)
        self.assertIs(view.last_frame, next_frame)
        self.assertIs(self.main.worker, original_worker)
        window.close()

    def test_escape_and_f11_close_only_the_fullscreen_window(self):
        original_worker = self.main.worker
        for key in (Qt.Key.Key_Escape, Qt.Key.Key_F11):
            with self.subTest(key=key):
                window, view = self.make_window()
                closed = []
                window.closed.connect(lambda: closed.append(True))
                view.setFocus()
                QTest.keyClick(view, key)
                self.assertEqual(closed, [True])
                self.assertFalse(window.isVisible())
                self.assertFalse(window._refresh.isActive())
                self.assertTrue(self.main.isVisible())
                self.assertIs(self.main.worker, original_worker)
                self.qt.processEvents()

    def test_exit_button_emits_closed_once_and_stops_refresh(self):
        window, _view = self.make_window()
        closed = []
        window.closed.connect(lambda: closed.append(True))
        QTest.mouseClick(window.exit_button, Qt.MouseButton.LeftButton)
        self.assertEqual(closed, [True])
        self.assertFalse(window._refresh.isActive())
        self.assertFalse(window.isVisible())
        self.assertTrue(self.main.isVisible())


if __name__ == "__main__":
    unittest.main()
