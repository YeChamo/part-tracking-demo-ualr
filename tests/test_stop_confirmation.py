"""A terminal program result must not hide an unconfirmed physical Stop."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui import MainWindow


class _Jobs:
    def __init__(self):
        self.pool = Mock()
        self.pending = []

    def submit(self, function, callback):
        self.pending.append((function, callback))

    def run_next(self):
        function, callback = self.pending.pop(0)
        try:
            result, error = function(), None
        except Exception as exc:
            result, error = None, exc
        callback(result, error)


class StopConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="ualr-stop-confirmation-")
        self.root = Path(self.folder.name)
        (self.root / "data").mkdir()
        (self.root / 'data' / 'settings.json').write_text('{"visual_only":false,"yolox_mode":"two_models","rule":"color"}',encoding='utf-8')
        with patch("app.ui.QTimer.singleShot"):
            self.window = MainWindow(self.root, smoke_test=True)
        self.window.timer.stop()
        self.window.jobs.pool.shutdown(wait=True, cancel_futures=True)
        self.jobs = self.window.jobs = _Jobs()
        self.client = self.window.client = Mock()
        self.client.stop.return_value = {"ok": True, "operation": "stop"}
        self.window.settings["source"] = "usb"
        self.window.running = self.window.armed = True
        self.window.owns_motion = self.window.output_busy = True
        self.window.active_program = "return-once"
        self.window.active_event = {"event_id": "test-stop", "output": "HOLD / CLEARANCE", "detail": ""}
        self.window.sequence_wait_until = time.monotonic() + 60
        self.window.sequence_next = "repeat"
        self.window.send_gate.set()

    def tearDown(self):
        self.window.owns_motion = self.window.output_busy = False
        self.window.worker = None
        self.window.close()
        self.window.deleteLater()
        self.folder.cleanup()

    def acknowledge_stop(self):
        self.window.stop()
        self.jobs.run_next()
        self.assertTrue(self.window.stop_acknowledged)
        self.assertTrue(self.window.owns_motion)

    def poll(self, **status):
        self.client.program_status.return_value = {"ok": True, "running": False, **status}
        self.window.poll_motion()
        self.jobs.run_next()

    def assert_ownership_retained(self):
        self.assertTrue(self.window.owns_motion)
        self.assertTrue(self.window.stopping_motion)
        self.assertFalse(self.window.output_busy)
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.send_gate.is_set())
        self.assertIn("could not confirm", self.window.motion_label.text())

    def test_accepted_stop_then_failed_terminal_status_requires_explicit_healthy_retry(self):
        self.acknowledge_stop()
        self.poll(status="failed", error="Stop was not confirmed: drive did not acknowledge",
                  stop_errors=["drive did not acknowledge"])
        self.assert_ownership_retained()
        self.window.resume_sequence(time.monotonic() + 120)
        self.assertEqual(self.jobs.pending, [])

        self.window.request_motion_stop()
        self.assertEqual(len(self.jobs.pending), 1)
        self.jobs.run_next()
        self.assertTrue(self.window.stop_acknowledged)
        self.assertTrue(self.window.owns_motion)
        self.poll(status="stopped", error="", stop_errors=[])
        self.assertFalse(self.window.owns_motion)
        self.assertFalse(self.window.stopping_motion)
        self.assertFalse(self.window.output_busy)
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertIsNone(self.window.sequence_wait_until)
        self.assertIsNone(self.window.sequence_next)
        self.assertEqual(self.client.stop.call_count, 2)
        calls = self.client.stop.call_args_list
        self.assertEqual([call.args[0] for call in calls], ["return-once", "return-once"])
        self.assertNotEqual(calls[0].args[1], calls[1].args[1])

    def test_stopped_status_with_stop_errors_still_retains_ownership(self):
        self.acknowledge_stop()
        self.poll(status="stopped", error="", stop_errors=["drive Stop unconfirmed"])
        self.assert_ownership_retained()

    def test_unknown_nonrunning_status_is_not_confirmation(self):
        self.acknowledge_stop()
        self.poll(status="unknown", error="", stop_errors=[])
        self.assert_ownership_retained()


if __name__ == "__main__":
    unittest.main()
