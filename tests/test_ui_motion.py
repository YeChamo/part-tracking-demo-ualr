"""Headless motion lifecycle tests; every controller call is an in-memory stub."""
from __future__ import annotations

import csv
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

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
        self.runs = 0

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
        self.runs += 1
        run_id = "new-run" if self.runs == 1 else f"new-run-{self.runs}"
        self.current = {"ok": True, "run_id": run_id, "status": "running", "running": True, "repeat_mode": "once"}
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
        (self.root / 'data' / 'settings.json').write_text('{"visual_only":false,"yolox_mode":"two_models","rule":"color"}',encoding='utf-8')
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
        # Synthetic instantaneous movements keep dispatch immediate. Real
        # bottle length and clearance remain enabled in the event's plan.
        self.window.settings["move_ms"] = 0
        self.window.started_at = time.monotonic()
        self.window.last_packet = {"captured": time.monotonic(), "inspection_ready": True}
        self.window.armed = armed
        if armed:
            self.window.send_gate.set()

    def schedule(self, bottle_id=1, *, bad=True, captured=None):
        captured = time.monotonic() if captured is None else captured
        self.window.decision(Decision(bottle_id, bad, ["Blue differs from pass color"] if bad else [], captured, (10, 20, 70, 180)))
        event = self.window.events[-1]
        if ("_plan" in event and self.window.settings["distance_mm"] == 0
                and all(self.window.settings[key] == 0 for key in ("delay_ms", "lead_ms", "move_ms"))):
            # The instantaneous synthetic fixture has no real transit/move
            # budget. Give its in-memory request callback time to execute.
            event["_send_deadline"] = captured + .25
        return event, captured

    def accept(self):
        self.live()
        event, captured = self.schedule()
        self.window.dispatch_due(captured)
        self.jobs.run_next()
        return event

    def poll(self):
        self.window.poll_motion()
        self.jobs.run_next()

    def feed_classifier_packets(self, reasons_for_frame):
        """Exercise production packet -> tracker -> UI -> scheduler, no camera."""
        camera = StubCamera()
        self.window.worker = camera
        self.window.started_at = 100.0
        self.window.settings.update(distance_mm=100, belt_speed=200, lead_ms=200, move_ms=150)
        for index, x in enumerate(range(180, 841, 30)):
            captured = 100.0 + index * .1
            flags = reasons_for_frame(index, x)
            camera.packet = {"frame": np.zeros((400, 1000, 3), np.uint8),
                             "boxes": [(x - 30, 100, x + 30, 300)], "reasons": [flags],
                             "colors": ["blue"], "color_confidences": [.88],
                             "model_labels": ["blue"], "captured": captured,
                             "inspection_ready": True, "visual_only": False,
                             "confidence_revision": 0, "barcodes": [],
                             "vision_pipeline": "YOLOX bottles; color NN"}
            with patch("app.ui.time.monotonic", return_value=captured):
                self.window.tick()
            if x + 30 < 800:
                self.assertEqual(self.window.events, [], "Upstream color evidence must wait for line crossing")

    def test_classifier_color_packet_rejects_once_at_line_and_sends_selected_program(self):
        self.live()
        self.feed_classifier_packets(lambda _index, _x: ["Color NN blue (divert)"])
        self.assertEqual(len(self.window.events), 1)
        event = self.window.events[0]
        self.assertEqual(event["bottle_id"], 1)
        self.assertEqual(event["color"], "blue")
        self.assertEqual(event["decision"], 1)
        self.assertIn("Color NN blue (divert)", event["detail"])
        self.assertEqual(len(self.window.pending), 1)
        self.assertEqual(self.controller.calls, [])
        due = event["_plan"]["due_at"]
        with patch("app.ui.time.monotonic", return_value=due):
            self.window.dispatch_due(due)
            self.jobs.run_next()
        triggers = [call for call in self.controller.calls if call[0] == "trigger"]
        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0][1], "reject-once")
        self.assertEqual(event["output"], "ACCEPTED")
        self.assertEqual(self.window.complete_count, 0, "Acceptance is not physical completion")

    def test_classifier_pass_packet_stays_disarmed_without_scheduling_motion(self):
        self.live(armed=False)
        self.feed_classifier_packets(lambda _index, _x: [])
        self.assertEqual(len(self.window.events), 1)
        event = self.window.events[0]
        self.assertEqual((event["color"], event["decision"], event["output"]), ("blue", 0, "DISARMED"))
        self.assertFalse(self.window.pending)
        self.assertFalse(self.jobs.pending)
        self.assertFalse(self.controller.calls)
        self.assertFalse(self.window.send_gate.is_set())

    def test_late_classifier_mismatch_at_crossing_is_not_allowed_to_pass_unconfirmed(self):
        self.live()
        self.feed_classifier_packets(lambda _index, x: ["Color NN blue (divert)"] if x >= 780 else [])
        self.assertEqual(len(self.window.events), 1)
        event = self.window.events[0]
        self.assertEqual(event["decision"], 1)
        self.assertIn("Unconfirmed color: Color NN blue (divert)", event["detail"])
        self.assertEqual(event["output"], "SCHEDULED")
        self.assertFalse(self.controller.calls)

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
        self.assertEqual(self.window.complete_count, 0)
        self.assertTrue(self.window.owns_motion)
        self.window.resume_sequence(event["_plan"]["clearance_at"] + .01)
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
        self.window.resume_sequence(event["_plan"]["clearance_at"] + .01)
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

    def test_pass_program_is_selected_for_a_good_bottle(self):
        self.live()
        self.window.settings["pass_program_id"] = "pass-once"
        event, captured = self.schedule(bad=False)
        self.assertEqual(event["decision"], 0)
        self.assertEqual(event["program_id"], "pass-once")
        self.window.dispatch_due(captured)
        self.jobs.run_next()
        triggers = [call for call in self.controller.calls if call[0] == "trigger"]
        self.assertEqual([call[1] for call in triggers], ["pass-once"])
        self.assertEqual(self.window.active_program, "pass-once")
        self.assertEqual(self.window.pass_count, 1)
        self.assertEqual(self.window.divert_count, 0)

    def test_no_action_pass_reserves_clearance_and_blocks_reject(self):
        self.live()
        event, captured = self.schedule(bad=False)
        self.window.dispatch_due(captured)
        self.assertEqual(event["output"], "PASS")
        self.assertFalse(self.jobs.pending)
        self.assertFalse(self.controller.calls)
        self.assertEqual(self.window.pass_clearance_until, event["_plan"]["clearance_at"])
        reject, reject_at = self.schedule(2, captured=captured + .05)
        with self.assertLogs(level="ERROR"):
            self.window.dispatch_due(reject_at)
        self.assertEqual(reject["output"], "SPACING CONFLICT")
        self.assertFalse(self.window.armed)
        self.assertFalse(self.window.running)
        self.assertFalse(self.jobs.pending)
        self.assertFalse(any(call[0] == "trigger" for call in self.controller.calls))

    def test_pass_arriving_during_reject_sequence_stops_output(self):
        self.accept()
        passed, captured = self.schedule(2, bad=False)
        with self.assertLogs(level="ERROR"):
            self.window.dispatch_due(captured)
        self.assertEqual(passed["output"], "REJECTOR BUSY")
        self.assertFalse(self.window.armed)
        self.assertFalse(self.window.running)
        self.jobs.run_next()  # The only new command is Stop for the active cycle.
        self.assertEqual(sum(call[0] == "trigger" for call in self.controller.calls), 1)
        self.assertEqual(sum(call[0] == "stop" for call in self.controller.calls), 1)

    def test_return_waits_for_both_primary_hold_and_bottle_clearance(self):
        # One case is limited by clearance; the other is limited by the hold.
        for index, hold_ms in enumerate((100, 1000), start=1):
            with self.subTest(hold_ms=hold_ms):
                self.live()
                self.window.settings["return_program_id"] = "return-once"
                self.window.settings["hold_ms"] = hold_ms
                event, captured = self.schedule(index)
                self.window.dispatch_due(captured)
                self.jobs.run_next()
                finished_at = captured + .05
                self.controller.current.update(status="completed", running=False)
                with patch("app.ui.time.monotonic", return_value=finished_at):
                    self.poll()
                expected_wait = max(finished_at + hold_ms / 1000, event["_plan"]["clearance_at"])
                self.assertEqual(self.window.sequence_wait_until, expected_wait)
                self.assertEqual(self.window.complete_count, index - 1)
                self.assertTrue(self.window.owns_motion)
                self.assertFalse(self.jobs.pending)
                self.window.resume_sequence(expected_wait - .001)
                self.assertFalse(self.jobs.pending)
                self.window.resume_sequence(expected_wait)
                self.assertEqual(self.window.active_program, "return-once")
                self.assertEqual(self.window.sequence_stage, "return")
                self.jobs.run_next()
                self.assertEqual(self.controller.calls[-1][0:2], ("trigger", "return-once"))
                self.assertEqual(self.window.complete_count, index - 1)
                self.controller.current.update(status="completed", running=False)
                with patch("app.ui.time.monotonic", return_value=expected_wait + .05):
                    self.poll()
                self.assertEqual(event["output"], "COMPLETED")
                self.assertEqual(self.window.complete_count, index)
                self.assertFalse(self.window.owns_motion)

    def test_repeat_waits_for_new_completed_run_and_counts_one_bottle(self):
        self.window.settings["reject_cycles"] = 2
        self.window.settings["hold_ms"] = 200
        event = self.accept()
        captured = event["_plan"]["arrival_at"]
        self.poll()  # First run is still running; no repeat is requested.
        self.window.resume_sequence(captured + 10)
        self.assertFalse(self.jobs.pending)
        self.assertEqual(sum(call[0] == "trigger" for call in self.controller.calls), 1)
        self.controller.current.update(status="completed", running=False)
        with patch("app.ui.time.monotonic", return_value=captured + .05):
            self.poll()
        self.assertEqual(event["cycles_completed"], 1)
        self.assertEqual(self.window.complete_count, 0)
        wait_until = self.window.sequence_wait_until
        self.window.resume_sequence(wait_until - .001)
        self.assertFalse(self.jobs.pending)
        self.window.resume_sequence(wait_until)
        self.jobs.run_next()
        triggers = [call for call in self.controller.calls if call[0] == "trigger"]
        self.assertEqual(len(triggers), 2)
        self.assertEqual([call[1] for call in triggers], ["reject-once", "reject-once"])
        self.assertNotEqual(triggers[0][2], triggers[1][2])
        self.assertEqual(self.window.sequence_cycle, 2)
        self.assertEqual(self.window.complete_count, 0)
        second_run = self.controller.current["run_id"]
        self.controller.current.update(run_id="new-run", status="completed", running=False)
        self.poll()  # The first cycle's old completed status cannot finish cycle two.
        self.assertEqual(self.window.complete_count, 0)
        self.assertTrue(self.window.owns_motion)
        self.controller.current.update(run_id=second_run, status="completed", running=False)
        with patch("app.ui.time.monotonic", return_value=wait_until + .05):
            self.poll()
        self.assertEqual(event["cycles_completed"], 2)
        self.assertEqual(event["output"], "COMPLETED")
        self.assertEqual(self.window.complete_count, 1)
        self.assertFalse(self.window.owns_motion)

    def test_stop_during_hold_prevents_return_and_repeat(self):
        self.window.settings.update(return_program_id="return-once", reject_cycles=2, hold_ms=1000)
        event = self.accept()
        self.controller.current.update(status="completed", running=False)
        self.poll()
        hold_until = self.window.sequence_wait_until
        self.assertIsNotNone(hold_until)
        self.window.stop()
        self.window.resume_sequence(hold_until + 10)
        self.assertEqual(len(self.jobs.pending), 1)  # Stop only, no return/repeat.
        self.jobs.run_next()
        self.controller.current.update(status="stopped", running=False)
        self.poll()
        self.window.resume_sequence(hold_until + 20)
        self.assertFalse(self.jobs.pending)
        triggers = [call for call in self.controller.calls if call[0] == "trigger"]
        self.assertEqual([call[1] for call in triggers], ["reject-once"])
        self.assertEqual(self.window.complete_count, 0)
        self.assertEqual(event["cycles_completed"], 0)
        self.assertFalse(self.window.owns_motion)

    def test_delayed_primary_poll_does_not_change_return_stage(self):
        self.window.settings.update(return_program_id="return-once", hold_ms=0)
        event = self.accept()
        self.window.poll_motion()
        _old_function, old_callback = self.jobs.pending.pop(0)
        self.controller.current.update(status="completed", running=False)
        self.poll()
        self.window.resume_sequence(self.window.sequence_wait_until)
        self.jobs.run_next()
        self.assertEqual(self.window.active_program, "return-once")
        phase = self.window.phase_generation
        self.window.poll_motion()  # The current return-stage status is pending.
        self.assertTrue(self.window.network_poll)
        old_callback(None, EtherMotionError("Delayed primary status failure"))
        self.assertTrue(self.window.network_poll)
        self.assertEqual(self.window.phase_generation, phase)
        self.assertEqual(self.window.active_program, "return-once")
        self.assertIsNone(self.window.active_run)
        self.assertEqual(event["output"], "ACCEPTED")
        self.assertTrue(self.window.armed)
        self.assertEqual(self.window.complete_count, 0)
        self.jobs.run_next()

    def test_stop_targets_the_active_return_program_snapshot(self):
        self.window.settings.update(return_program_id="return-once", hold_ms=0)
        self.accept()
        self.controller.current.update(status="completed", running=False)
        self.poll()
        self.window.resume_sequence(self.window.sequence_wait_until)
        self.jobs.run_next()
        self.window.settings["program_id"] = "unrelated-program"
        self.window.settings["return_program_id"] = "different-return"
        self.window.stop()
        self.jobs.run_next()
        stops = [call for call in self.controller.calls if call[0] == "stop"]
        self.assertEqual([call[1] for call in stops], ["return-once"])

    def test_arming_checks_pass_reject_and_return_programs(self):
        self.live(armed=False)
        self.window.pass_program.addItem("Pass once", "pass-once")
        self.window.pass_program.setCurrentIndex(self.window.pass_program.findData("pass-once"))
        self.window.return_program.addItem("Return once", "return-once")
        self.window.return_program.setCurrentIndex(self.window.return_program.findData("return-once"))
        self.window.toggle_arm(True)
        self.jobs.run_next()
        programs = {call[1] for call in self.controller.calls if call[0] == "ready"}
        self.assertEqual(programs, {"pass-once", "reject-once", "return-once"})
        self.assertTrue(self.window.armed)

    def test_readiness_latency_cannot_consume_the_diverter_move_budget(self):
        self.live()
        self.window.settings.update(distance_mm=60, lead_ms=200, move_ms=150)
        event, captured = self.schedule()
        self.assertAlmostEqual(event["_plan"]["due_at"] - captured, .1)
        self.assertAlmostEqual(event["_send_deadline"] - captured, .15)
        self.window.dispatch_due(event["_plan"]["due_at"])
        # Readiness/status work finishes too late to leave enough time for
        # the gate to move, although generic 250 ms dispatch tolerance remains.
        with patch("app.ui.time.monotonic", return_value=event["_send_deadline"] + .001):
            with self.assertLogs(level="ERROR"):
                self.jobs.run_next()
        self.assertEqual(event["output"], "REFUSED")
        self.assertIn("deadline", event["detail"].lower())
        self.assertFalse(self.window.running)
        self.assertFalse(any(call[0] == "trigger" for call in self.controller.calls))

    def test_dispatch_rejects_a_missed_move_deadline_before_queueing(self):
        self.live()
        self.window.settings.update(distance_mm=60, lead_ms=200, move_ms=150)
        event, _captured = self.schedule()
        with self.assertLogs(level="ERROR"):
            self.window.dispatch_due(event["_send_deadline"] + .001)
        self.assertEqual(event["output"], "MISSED TIMING")
        self.assertFalse(self.jobs.pending)
        self.assertFalse(self.controller.calls)
        self.assertFalse(self.window.armed)


if __name__ == "__main__":
    unittest.main()
