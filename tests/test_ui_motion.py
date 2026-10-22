"""Headless motion lifecycle tests; every controller call is an in-memory stub."""
from __future__ import annotations

import csv
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ethermotion import EtherMotionError
from app.tracking import Decision
from app.ui import MainWindow


class _Pool:
    def shutdown(self, **kwargs):
        pass


class QueuedJobs:
    """Run network functions and their GUI callbacks in a chosen test order."""
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


class StubController:
    def __init__(self):
        self.calls = []
        self.current = {"ok": True, "run_id": "old-run", "status": "completed", "running": False, "repeat_mode": "once"}
        self.stop_error = None

    def check_ready(self, program):
        self.calls.append(("ready", program))
        return {"ok": True, "program_id": program}

    def program_status(self, program):
        self.calls.append(("status", program))
        return self.current.copy()

    def trigger(self, program, request_id, *, allow_send=None, deadline=None):
        if allow_send is not None and not allow_send():
            raise EtherMotionError("Cancelled before transmission.")
        if deadline is not None and time.monotonic() > deadline:
            raise EtherMotionError("Motion deadline expired.")
        self.calls.append(("trigger", program, request_id))
        self.current = {"ok": True, "run_id": "new-run", "status": "running", "running": True, "repeat_mode": "once"}
        return {"ok": True, "operation": "run", "request_id": request_id, "duplicate": False}

    def stop(self, program, request_id):
        self.calls.append(("stop", program, request_id))
        if self.stop_error:
            raise self.stop_error
        self.current.update(status="stopping", running=True)
        return {"ok": True, "operation": "stop", "request_id": request_id}


class StubCamera:
    def __init__(self, packet=None):
        self.packet = packet
        self.stopped = False

    def take_latest(self):
        packet, self.packet = self.packet, None
        return packet

    def stop(self):
        self.stopped = True

    def isRunning(self):
        return False


class UiMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="ualr-ui-motion-")
        self.root = Path(self.folder.name)
        (self.root / "data").mkdir()
        # Disable the normal 200 ms simulation autostart.  Tests never process
        # GUI events or create a camera/network thread.
        with patch("app.ui.QTimer.singleShot"):
            self.window = MainWindow(self.root, smoke_test=True)
        self.window.timer.stop()
        self.window.jobs.pool.shutdown(wait=True, cancel_futures=True)
        self.jobs = QueuedJobs()
        self.window.jobs = self.jobs
        self.controller = StubController()
        self.window.client = self.controller
        self.window.program.clear()
        self.window.program.addItem("Reject once", "reject-once")
        self.window.settings["program_id"] = "reject-once"

    def tearDown(self):
        # Close without queueing an additional fake Stop or waiting for a source.
        self.window.owns_motion = self.window.output_busy = False
        self.window.worker = None
        self.window.close()
        self.window.deleteLater()
        self.folder.cleanup()

    def live(self, armed=True):
        self.window.running = True
        self.window.settings["source"] = "usb"
        self.window.settings["distance_mm"] = 0
        self.window.settings["delay_ms"] = self.window.settings["lead_ms"] = 0
        self.window.started_at = time.monotonic()
        self.window.last_packet = {"captured": time.monotonic(), "inspection_ready": True}
        self.window.armed = armed
        if armed:
            self.window.send_gate.set()

    def schedule(self, bottle_id=1):
        captured = time.monotonic()
        self.window.decision(Decision(bottle_id, True, ["Blue differs from pass color"], captured, (10, 20, 70, 180)))
        return self.window.events[-1], captured

    def accept(self):
        self.live()
        event, captured = self.schedule()
        self.window.dispatch_due(captured)
        self.jobs.run_next()
        return event

    def poll(self):
        self.window.poll_motion()
        self.jobs.run_next()

    def test_stop_cancels_scheduled_output_and_persists_csv_state(self):
        self.live()
        self.window.settings["distance_mm"] = 1000
        event, _ = self.schedule()
        self.assertEqual(event["output"], "SCHEDULED")
        self.window.stop()
        self.assertEqual(event["output"], "CANCELLED")
        self.assertFalse(self.window.pending)
        self.assertFalse(self.window.send_gate.is_set())
        self.assertFalse(self.jobs.pending)
        self.assertEqual(self.window.table.item(0, 4).text(), "CANCELLED")
        with (self.root / "data" / f"session-{self.window.session}.csv").open(encoding="utf-8-sig", newline="") as file:
            self.assertEqual(list(csv.DictReader(file))[0]["output"], "CANCELLED")

    def test_stale_arm_callback_cannot_enable_newer_arm_attempt(self):
        self.live(armed=False)
        original_gate = self.window.send_gate
        self.window.toggle_arm(True)
        self.window.toggle_arm(False)
        self.window.toggle_arm(True)
        self.assertEqual(len(self.jobs.pending), 2)
        self.jobs.run_next()  # Ready result from the cancelled first attempt.
        self.assertFalse(self.window.armed)
        self.assertTrue(self.window.arming)
        self.assertFalse(original_gate.is_set())
        self.jobs.run_next()
        self.assertTrue(self.window.armed)
        self.assertFalse(self.window.arming)
        self.assertTrue(self.window.send_gate.is_set())
        self.assertIsNot(self.window.send_gate, original_gate)
        self.assertFalse(original_gate.is_set())

    def test_acceptance_is_not_counted_until_new_run_completes(self):
        self.live()
        event, captured = self.schedule()
        self.window.dispatch_due(captured)
        self.assertTrue(self.window.request_pending)
        self.window.poll_motion()
        self.assertEqual(len(self.jobs.pending), 1)  # No status polling before ACK.
        self.jobs.run_next()
        self.assertEqual(event["output"], "ACCEPTED")
        self.assertEqual(self.window.complete_count, 0)
        self.assertTrue(self.window.owns_motion)
        self.poll()
        self.assertEqual(self.window.active_run, "new-run")
        self.assertEqual(event["run_id"], "new-run")
        self.assertEqual(self.window.complete_count, 0)
        self.controller.current.update(status="completed", running=False)
        self.poll()
        self.assertEqual(self.window.complete_count, 1)
        self.assertEqual(event["output"], "COMPLETED")
        self.assertFalse(self.window.owns_motion)

    def test_old_completed_run_is_not_credited_to_new_bottle(self):
        event = self.accept()
        self.controller.current.update(run_id="old-run", status="completed", running=False)
        self.poll()
        self.assertEqual(self.window.complete_count, 0)
        self.assertIsNone(self.window.active_run)
        self.assertTrue(self.window.owns_motion)
        self.assertEqual(event["output"], "ACCEPTED")
        self.controller.current.update(run_id="new-run", status="completed", running=False)
        self.poll()
        self.assertEqual(self.window.complete_count, 1)

    def test_stop_before_queued_send_prevents_trigger(self):
        self.live()
        _, captured = self.schedule()
        self.window.dispatch_due(captured)
        self.window.stop()
        self.assertEqual(len(self.jobs.pending), 2)  # Send already queued, then Stop.
        with self.assertLogs(level="ERROR"):
            self.jobs.run_next()
        self.jobs.run_next()
        self.assertFalse(any(call[0] == "trigger" for call in self.controller.calls))
        self.assertFalse(any(call[0] == "status" for call in self.controller.calls))
        self.assertEqual(sum(call[0] == "stop" for call in self.controller.calls), 1)

    def test_stop_acknowledgement_keeps_ownership_until_stopped_status(self):
        event = self.accept()
        self.window.stop()
        self.window.poll_motion()
        self.assertEqual(len(self.jobs.pending), 1)  # Wait for Stop ACK first.
        self.jobs.run_next()
        self.assertTrue(self.window.stop_acknowledged)
        self.assertTrue(self.window.owns_motion)
        self.assertEqual(event["output"], "STOP REQUESTED")
        self.poll()
        self.assertTrue(self.window.owns_motion)  # Service still reports stopping.
        self.controller.current.update(status="stopped", running=False)
        self.poll()
        self.assertFalse(self.window.owns_motion)
        self.assertFalse(self.window.stopping_motion)
        self.assertEqual(self.window.complete_count, 0)

    def test_status_queued_before_stop_cannot_release_ownership_before_stop_ack(self):
        self.accept()
        self.window.poll_motion()  # This older status request precedes Stop.
        self.window.stop()
        self.controller.current.update(status="completed", running=False)
        self.jobs.run_next()
        self.assertFalse(self.window.stop_acknowledged)
        self.assertTrue(self.window.owns_motion)
        self.assertTrue(self.window.stopping_motion)
        self.jobs.run_next()
        self.assertTrue(self.window.owns_motion)
        self.assertTrue(self.window.stop_acknowledged)
        self.controller.current.update(status="stopped", running=False)
        self.poll()
        self.assertFalse(self.window.owns_motion)
        self.assertFalse(self.window.output_busy)

    def test_uncertain_stop_blocks_restart_and_allows_explicit_retry(self):
        self.accept()
        self.controller.stop_error = EtherMotionError("Stop response lost", uncertain=True)
        self.window.stop()
        self.jobs.run_next()
        self.assertTrue(self.window.owns_motion)
        self.assertFalse(self.window.output_busy)
        self.assertFalse(self.window.start_button.isEnabled())
        self.controller.stop_error = None
        self.window.request_motion_stop()
        self.jobs.run_next()
        self.assertTrue(self.window.stop_acknowledged)
        self.assertEqual(sum(call[0] == "stop" for call in self.controller.calls), 2)

    def test_unavailable_inspection_cancels_pending_output_before_dispatch(self):
        self.live()
        event, _ = self.schedule()
        self.window.worker = StubCamera({"captured": time.monotonic(), "inspection_ready": False,
                                         "inspection_error": "Color inspection unavailable"})
        with self.assertLogs(level="ERROR"):
            self.window.tick()
        self.assertFalse(self.window.running)
        self.assertEqual(event["output"], "CANCELLED")
        self.assertTrue(self.window.worker.stopped)
        self.assertFalse(self.jobs.pending)
        self.assertFalse(self.controller.calls)

    def test_source_without_first_frame_fails_after_timeout(self):
        self.live(armed=False)
        self.window.last_packet = None
        self.window.started_at = time.monotonic() - 16
        self.window.worker = StubCamera()
        with self.assertLogs(level="ERROR"):
            self.window.tick()
        self.assertFalse(self.window.running)
        self.assertIn("15 seconds", self.window.status.text())
        self.assertFalse(self.controller.calls)

    def test_stop_start_uses_new_motion_event_id_for_restarted_track_one(self):
        self.window.start()  # Simulation only, so no VideoWorker/camera opens.
        self.live()
        first, _ = self.schedule(bottle_id=1)
        self.window.stop()
        self.window.start()
        self.live()
        second, _ = self.schedule(bottle_id=1)
        self.assertEqual(first["session"], second["session"])
        self.assertNotEqual(first["event_id"], second["event_id"])
        self.assertNotEqual(first["request_id"], second["request_id"])


if __name__ == "__main__":
    unittest.main()
