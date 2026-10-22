"""Main-window model, confidence, and full-screen integration without hardware."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from app.confidence_control import ConfidenceControl
from app.ui import MainWindow


class _Pool:
    def shutdown(self, **kwargs):
        pass


class _QueuedJobs:
    def __init__(self):
        self.pool = _Pool()
        self.pending = []

    def submit(self, function, callback):
        self.pending.append((function, callback))


class UiControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="ualr-ui-controls-")
        self.root = Path(self.folder.name)
        (self.root / "data").mkdir()
        # No event loop: prevent normal simulation startup and never let a
        # timer create camera/network work while these controls are exercised.
        with patch("app.ui.QTimer.singleShot"):
            self.window = MainWindow(self.root, smoke_test=True)
        self.window.timer.stop()
        self.window.jobs.pool.shutdown(wait=True, cancel_futures=True)
        self.window.jobs = _QueuedJobs()

    def tearDown(self):
        self.window.confidence_timer.stop()
        self.window.owns_motion = self.window.output_busy = False
        self.window.worker = None
        self.window.close()
        self.window.deleteLater()
        self.folder.cleanup()

    def live(self):
        self.window.running = True
        self.window.settings["source"] = "usb"
        self.window.last_packet = {"captured": time.monotonic(), "inspection_ready": True,
                                   "confidence_revision": 0}
        self.window.client = Mock()
        self.window.program.clear()
        self.window.program.addItem("Demo divert", "demo-divert")
        self.window.update_enabled()

    def test_models_tab_contains_model_pickers_and_confidence_controls(self):
        matches = [index for index in range(self.window.tabs.count())
                   if self.window.tabs.tabText(index) == "Models"]
        self.assertEqual(len(matches), 1)
        self.window.tabs.setCurrentIndex(matches[0])
        models = self.window.tabs.currentWidget()
        for key in ("model_path", "color_model_path", "confidence", "color_confidence"):
            self.assertTrue(models.isAncestorOf(self.window.fields[key]), key)
        for key in ("confidence", "color_confidence"):
            self.assertIsInstance(self.window.fields[key], ConfidenceControl)

        chosen = [str(self.root / "bottles.onnx"), str(self.root / "colors.onnx")]
        with patch("app.ui.QFileDialog.getOpenFileName", side_effect=[(path, "") for path in chosen]) as picker:
            self.window.path_buttons["model_path"].click()
            self.window.path_buttons["color_model_path"].click()
        self.assertEqual(picker.call_count, 2)
        self.assertTrue(all("*.onnx" in call.args[-1] for call in picker.call_args_list))
        self.window.collect_settings()
        saved = json.loads((self.root / "data" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["model_path"], chosen[0])
        self.assertEqual(saved["color_model_path"], chosen[1])
        with patch("app.ui.QFileDialog.getOpenFileName", return_value=("", "")):
            self.window.path_buttons["model_path"].click()
        self.assertEqual(self.window.fields["model_path"].text(), chosen[0])

    def test_combined_model_disables_separate_color_picker_and_live_locks_model_paths(self):
        mode = self.window.fields["yolox_mode"]
        mode.setCurrentIndex(mode.findData("combined"))
        self.assertTrue(self.window.fields["model_path"].isEnabled())
        self.assertFalse(self.window.fields["color_model_path"].isEnabled())
        self.assertFalse(self.window.path_buttons["color_model_path"].isEnabled())
        mode.setCurrentIndex(mode.findData("two_models"))
        self.assertTrue(self.window.fields["color_model_path"].isEnabled())
        self.assertTrue(self.window.path_buttons["color_model_path"].isEnabled())
        self.live()
        for key in ("model_path", "color_model_path"):
            self.assertFalse(self.window.fields[key].isEnabled())
            self.assertFalse(self.window.path_buttons[key].isEnabled())

    def test_confidence_adjustment_stays_enabled_live_disarmed_and_locks_during_output(self):
        self.live()
        for key in ("confidence", "color_confidence"):
            self.assertTrue(self.window.fields[key].isEnabled())
            self.assertTrue(self.window.fields[key].slider.isEnabled())
            self.assertTrue(self.window.fields[key].spin.isEnabled())
        for blocked_state in ("armed", "arming", "owns_motion"):
            with self.subTest(blocked_state=blocked_state):
                self.window.armed = self.window.arming = self.window.owns_motion = False
                setattr(self.window, blocked_state, True)
                self.window.update_enabled()
                for key in ("confidence", "color_confidence"):
                    self.assertFalse(self.window.fields[key].isEnabled())
                    self.assertFalse(self.window.fields[key].slider.isEnabled())
                    self.assertFalse(self.window.fields[key].spin.isEnabled())
        self.window.armed = self.window.arming = self.window.owns_motion = False
        self.window.update_enabled()
        self.assertTrue(self.window.fields["confidence"].isEnabled())

    def test_debounce_sends_both_final_values_once_and_discards_old_tracks(self):
        self.live()
        worker = Mock()
        worker.update_confidence.return_value = 3
        self.window.worker = worker
        self.window.tracker.update([(10, 10, 40, 100)], [[]], time.monotonic(), 640, 480)
        self.assertTrue(self.window.tracker.tracks)
        self.window.track_meta[1] = {"color": "blue", "barcode": "old-track"}

        self.window.fields["confidence"].slider.setValue(62)
        self.window.fields["color_confidence"].spin.setValue(75)
        self.assertTrue(self.window.confidence_timer.isActive())
        self.assertEqual(self.window.confidence_timer.interval(), 150)
        worker.update_confidence.assert_not_called()
        self.assertFalse(self.window.arm.isEnabled())

        # Emit the timeout synchronously so the test opens no event loop.
        self.window.confidence_timer.timeout.emit()
        worker.update_confidence.assert_called_once_with(.62, .75)
        self.assertFalse(self.window.confidence_timer.isActive())
        self.assertEqual(self.window.expected_confidence_revision, 3)
        self.assertEqual(self.window.tracker.tracks, [])
        self.assertEqual(self.window.track_meta, {})
        self.assertFalse(self.window.arm.isEnabled())
        saved = json.loads((self.root / "data" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual((saved["confidence"], saved["color_confidence"]), (.62, .75))

    def test_arming_waits_for_a_packet_matching_new_confidence_revision(self):
        self.live()
        self.window.expected_confidence_revision = 2
        self.window.last_packet["confidence_revision"] = 1
        self.window.update_enabled()
        self.assertFalse(self.window.arm.isEnabled())
        self.window.toggle_arm(True)
        self.assertFalse(self.window.armed)
        self.assertFalse(self.window.arming)
        self.assertEqual(self.window.jobs.pending, [])
        self.assertIn("confidence", self.window.output_note.text())

        self.window.last_packet["confidence_revision"] = 2
        self.window.last_packet["captured"] = time.monotonic()
        self.window.update_enabled()
        self.assertTrue(self.window.arm.isEnabled())
        self.window.toggle_arm(True)
        self.assertTrue(self.window.arming)
        self.assertEqual(len(self.window.jobs.pending), 1)

    def test_pending_slider_debounce_blocks_arming_even_before_revision_is_queued(self):
        self.live()
        self.window.fields["confidence"].setValue(.7)
        self.assertTrue(self.window.confidence_timer.isActive())
        self.assertFalse(self.window.arm.isEnabled())
        self.window.toggle_arm(True)
        self.assertFalse(self.window.armed)
        self.assertFalse(self.window.arming)
        self.assertEqual(self.window.jobs.pending, [])

    def test_fullscreen_renders_shared_latest_frame_without_creating_camera_or_worker(self):
        self.live()
        worker = Mock()
        self.window.worker = worker
        self.window.armed = True
        original_tracker = self.window.tracker
        with patch("app.ui.VideoWorker") as constructor, patch("app.ui.cv2.VideoCapture") as capture:
            self.window.toggle_fullscreen()
            fullscreen = self.window.fullscreen
            self.assertIsNotNone(fullscreen)
            self.assertIs(fullscreen.view.main, self.window)
            self.assertIsNot(fullscreen.view, self.window.view)
            frame = np.full((100, 180, 3), 90, dtype=np.uint8)
            self.window.last_packet = {"frame": frame}
            with patch("app.ui.cv2.cvtColor", wraps=cv2.cvtColor) as convert:
                fullscreen.view.grab()
            self.assertGreater(convert.call_count, 0)
            self.assertIs(convert.call_args.args[0], frame)
            self.assertIs(self.window.worker, worker)
            self.assertIs(self.window.tracker, original_tracker)
            self.assertTrue(self.window.running)
            self.assertTrue(self.window.armed)
            self.window.toggle_fullscreen()
            self.assertIsNone(self.window.fullscreen)
            self.assertTrue(self.window.running)
            self.assertTrue(self.window.armed)
            constructor.assert_not_called()
            capture.assert_not_called()
            worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
