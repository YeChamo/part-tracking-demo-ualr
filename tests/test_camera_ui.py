"""Headless camera picker integration tests; no capture streams or Qt event loop."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
from PySide6.QtWidgets import QApplication

from app.cameras import CameraChoice, resolve_usb_camera
from app.ui import MainWindow
from app.vision import VideoWorker


class _Pool:
    def shutdown(self, **kwargs):
        pass


class QueuedJobs:
    def __init__(self):
        self.pending = []
        self.pool = _Pool()

    def submit(self, function, callback):
        self.pending.append((function, callback))

    def run_next(self):
        function, callback = self.pending.pop(0)
        try:
            result, error = function(), None
        except Exception as exc:
            result, error = None, exc
        callback(result, error)


class CameraPickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="ualr-camera-picker-")
        self.root = Path(self.folder.name)
        (self.root / "data").mkdir()
        self.laptop = CameraChoice("usb", "usb:laptop", "Laptop built-in", 0)
        self.external = CameraChoice("usb", "usb:conveyor", "Conveyor USB camera", 1)
        self.basler = CameraChoice("basler", "basler:12345", "Basler ace (12345)", serial="12345")
        self.inventory = [self.laptop, self.external, self.basler]
        self.discovery = patch("app.ui.discover_cameras", side_effect=lambda: list(self.inventory))
        self.discovery.start()
        self.addCleanup(self.discovery.stop)
        # Never process GUI events: no simulation autostart, SDK scan, capture,
        # network request, or queued timer callback is allowed to run.
        with patch("app.ui.QTimer.singleShot"):
            self.window = MainWindow(self.root, smoke_test=True)
        self.window.timer.stop()
        self.window.jobs.pool.shutdown(wait=True, cancel_futures=True)
        self.jobs = QueuedJobs()
        self.window.jobs = self.jobs

    def tearDown(self):
        self.window.owns_motion = self.window.output_busy = False
        self.window.worker = None
        self.window.close()
        self.window.deleteLater()
        self.folder.cleanup()

    def source(self, kind):
        self.window.source.setCurrentIndex(self.window.source.findData(kind))
        self.assertTrue(self.window.camera_scanning)
        self.jobs.run_next()
        self.assertFalse(self.window.camera_scanning)

    def select(self, camera_id):
        for index in range(self.window.camera_picker.count()):
            value = self.window.camera_picker.itemData(index)
            if isinstance(value, CameraChoice) and value.id == camera_id:
                self.window.camera_picker.setCurrentIndex(index)
                return
        self.fail(f"Picker did not contain {camera_id}")

    def refresh(self):
        self.window.refresh_cameras()
        self.jobs.run_next()

    def test_usb_scan_and_refresh_leave_placeholder_until_operator_selects(self):
        self.source("usb")
        self.assertIsNone(self.window.camera_picker.currentData())
        self.assertFalse(self.window.fields["camera_index"].isEnabled())
        self.assertIn(self.external.name, self.window.camera_picker.itemText(2))
        self.assertNotIn(self.basler.name, " ".join(self.window.camera_picker.itemText(i)
                                                     for i in range(self.window.camera_picker.count())))
        self.refresh()
        self.assertIsNone(self.window.camera_picker.currentData())
        with self.assertRaisesRegex(ValueError, "Choose your camera by name"):
            self.window.collect_settings()

    def test_named_external_selection_saves_id_name_and_current_index(self):
        self.source("usb")
        self.select(self.external.id)
        self.window.collect_settings()
        saved = json.loads((self.root / "data" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["camera_id"], self.external.id)
        self.assertEqual(saved["camera_name"], self.external.name)
        self.assertEqual(saved["camera_index"], 1)
        self.assertFalse(saved["camera_manual"])
        self.assertFalse(self.window.fields["camera_index"].isEnabled())

    def test_saved_external_selection_follows_identity_after_index_reorder(self):
        self.source("usb")
        self.select(self.external.id)
        self.window.collect_settings()
        moved = CameraChoice("usb", self.external.id, self.external.name, 5)
        self.inventory = [self.laptop, moved]
        self.refresh()
        self.assertEqual(self.window.camera_picker.currentData(), moved)
        self.window.collect_settings()
        with patch("app.cameras.discover_cameras", return_value=self.inventory):
            choice = resolve_usb_camera(self.window.settings)
        self.assertEqual(choice.id, self.external.id)
        self.assertEqual(choice.index, 5)

    def test_unplugged_selected_external_leaves_placeholder_and_blocks_start(self):
        self.source("usb")
        self.select(self.external.id)
        self.window.collect_settings()
        self.inventory = [self.laptop]
        self.refresh()
        self.assertIsNone(self.window.camera_picker.currentData())
        self.assertIn("unavailable", self.window.status.text())
        with self.assertRaisesRegex(ValueError, "Choose your camera by name"):
            self.window.collect_settings()
        with patch("app.ui.VideoWorker") as worker:
            self.window.start()
        worker.assert_not_called()
        self.assertFalse(self.window.running)
        self.assertIn("Choose your camera", self.window.status.text())
        self.assertEqual(self.window.settings["camera_id"], self.external.id)

    def test_numeric_camera_requires_explicit_manual_option(self):
        self.inventory = []
        self.source("usb")
        self.window.fields["camera_index"].setValue(3)
        with self.assertRaisesRegex(ValueError, "Choose your camera by name"):
            self.window.collect_settings()
        self.window.camera_picker.setCurrentIndex(self.window.camera_picker.findData("manual"))
        self.assertTrue(self.window.fields["camera_index"].isEnabled())
        self.window.collect_settings()
        self.assertTrue(self.window.settings["camera_manual"])
        self.assertEqual(self.window.settings["camera_id"], "")
        with patch("app.cameras.discover_cameras", side_effect=AssertionError("Manual mode needs no discovery")):
            self.assertEqual(resolve_usb_camera(self.window.settings).index, 3)

    def test_basler_picker_filters_devices_and_retains_selected_serial(self):
        self.source("basler")
        self.assertEqual(self.window.camera_picker.count(), 2)
        self.assertIsNone(self.window.camera_picker.currentData())
        self.select(self.basler.id)
        self.window.collect_settings()
        self.assertEqual(self.window.settings["basler_serial"], "12345")
        other = CameraChoice("basler", "basler:54321", "Basler ace (54321)", serial="54321")
        self.inventory = [other, self.basler, self.laptop]
        self.refresh()
        self.assertEqual(self.window.camera_picker.currentData(), self.basler)
        self.window.collect_settings()
        self.assertEqual(self.window.settings["basler_serial"], "12345")

    def test_video_source_disables_camera_picker_and_manual_index(self):
        self.source("usb")
        self.window.source.setCurrentIndex(self.window.source.findData("video"))
        self.assertFalse(self.window.camera_picker.isEnabled())
        self.assertFalse(self.window.refresh_cameras_button.isEnabled())
        self.assertFalse(self.window.fields["camera_index"].isEnabled())
        self.assertFalse(self.jobs.pending)

    def test_source_switch_during_usb_scan_automatically_scans_new_basler_source(self):
        self.window.source.setCurrentIndex(self.window.source.findData("usb"))
        self.assertTrue(self.window.camera_scanning)
        self.assertEqual(len(self.jobs.pending), 1)
        self.window.source.setCurrentIndex(self.window.source.findData("basler"))
        self.assertEqual(len(self.jobs.pending), 1)  # Finish the old scan first.
        self.jobs.run_next()
        self.assertTrue(self.window.camera_scanning)
        self.assertEqual(len(self.jobs.pending), 1)  # New source automatically queued.
        self.jobs.run_next()
        self.assertFalse(self.window.camera_scanning)
        self.assertFalse(self.jobs.pending)
        self.assertEqual(self.window.camera_picker.count(), 2)
        self.assertIsNone(self.window.camera_picker.currentData())
        self.assertEqual(self.window.camera_picker.itemData(1), self.basler)
        self.assertTrue(self.window.camera_picker.isEnabled())

    def test_start_and_picker_are_disabled_until_scan_finishes(self):
        self.window.source.setCurrentIndex(self.window.source.findData("usb"))
        self.assertTrue(self.window.camera_scanning)
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.camera_picker.isEnabled())
        self.assertFalse(self.window.refresh_cameras_button.isEnabled())
        self.jobs.run_next()
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertTrue(self.window.camera_picker.isEnabled())
        self.select(self.external.id)
        self.window.collect_settings()
        self.window.refresh_cameras()
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.camera_picker.isEnabled())
        self.jobs.run_next()
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertEqual(self.window.camera_picker.currentData(), self.external)


class CameraOpenSelectionTests(unittest.TestCase):
    def test_worker_opens_named_external_current_index_with_dshow(self):
        device = CameraChoice("usb", "usb:external", "External conveyor camera", 4)
        worker = VideoWorker({"source": "usb", "camera_id": device.id,
                              "camera_name": device.name, "camera_index": 0}, Path("."))
        capture = Mock()
        capture.isOpened.return_value = True
        with patch("app.cameras.discover_cameras", return_value=[device]), \
             patch("app.vision.cv2.VideoCapture", return_value=capture) as open_capture, \
             patch("sys.platform", "win32"):
            source, source_name = worker._open_source()
        open_capture.assert_called_once_with(4, cv2.CAP_DSHOW)
        self.assertEqual(source[0], "usb")
        self.assertIs(source[1], capture)
        self.assertIn(device.name, source_name)
        capture.set.assert_called_once_with(cv2.CAP_PROP_BUFFERSIZE, 1)
        worker._close_source(source)
        capture.release.assert_called_once_with()

    def test_worker_missing_selected_external_never_opens_laptop(self):
        laptop = CameraChoice("usb", "usb:laptop", "Laptop camera", 0)
        worker = VideoWorker({"source": "usb", "camera_id": "usb:external",
                              "camera_name": "Conveyor camera", "camera_index": 0}, Path("."))
        with patch("app.cameras.discover_cameras", return_value=[laptop]), \
             patch("app.vision.cv2.VideoCapture") as open_capture, \
             self.assertRaisesRegex(RuntimeError, "Conveyor camera is not available"):
            worker._open_source()
        open_capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
