"""Live confidence changes never publish an in-flight stale inference."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from app.vision import VideoWorker


class LiveConfidenceTests(unittest.TestCase):
    def make_worker(self):
        return VideoWorker({"source": "usb", "rule": "color", "confidence": .25,
                            "color_confidence": .4}, Path("."))

    def run_frames(self, worker, pipeline, count):
        frame = np.full((40, 50, 3), 120, dtype=np.uint8)
        packets = []
        reads = 0
        faults = []
        worker.fault.connect(faults.append)

        def read(_source):
            nonlocal reads
            packets.append(worker.take_latest())
            reads += 1
            if reads > count:
                worker.stop()
                return None, float(reads)
            return frame.copy(), float(reads)

        with patch("app.vision.YoloXPipeline", return_value=pipeline) as constructor, patch.object(
                worker, "_open_source", return_value=(("usb", object(), None), "Fake camera")) as opened, patch.object(
                worker, "_read_source", side_effect=read), patch.object(
                worker, "_close_source") as closed, patch(
                "app.vision.barcode_status", return_value=(False, "Test decoder disabled")), patch(
                "app.vision._decode_frame_and_crops") as decoder:
            worker.run()
        constructor.assert_called_once()
        opened.assert_called_once()
        closed.assert_called_once()
        decoder.assert_not_called()
        self.assertEqual(faults, [])
        self.assertEqual(pipeline.open_calls, 1)
        self.assertEqual(pipeline.close_calls, 1)
        return packets

    def test_change_during_inference_discards_old_result_and_uses_new_threshold_next_frame(self):
        worker = self.make_worker()
        pipeline = _Pipeline()

        def change_during_first_inference():
            self.assertEqual(worker.update_confidence(.7, .8), 1)

        pipeline.on_first_infer = change_during_first_inference
        packets = self.run_frames(worker, pipeline, count=2)
        self.assertEqual(len(packets), 3)
        self.assertIsNone(packets[0])  # Before the first frame.
        self.assertIsNone(packets[1])  # First inference used superseded settings.
        self.assertIsNotNone(packets[2])
        self.assertEqual(packets[2]["captured"], 2.0)
        self.assertEqual(packets[2]["confidence_revision"], 1)
        self.assertEqual(pipeline.infer_thresholds, [(.25, .4), (.7, .8)])
        self.assertEqual(pipeline.threshold_updates, [(.7, .8)])

    def test_update_discards_mailbox_before_next_frame(self):
        worker = self.make_worker()
        worker._latest = {"confidence_revision": 0, "captured": 12.0}
        revision = worker.update_confidence(.65, .75)
        self.assertEqual(revision, 1)
        self.assertIsNone(worker.take_latest())
        pipeline = _Pipeline()
        packets = self.run_frames(worker, pipeline, count=1)
        self.assertEqual(pipeline.infer_thresholds, [(.65, .75)])
        self.assertEqual(packets[-1]["confidence_revision"], revision)

    def test_rapid_updates_apply_latest_pair_without_reopening_models(self):
        worker = self.make_worker()
        self.assertEqual(worker.update_confidence(.4, .5), 1)
        self.assertEqual(worker.update_confidence(.6, .8), 2)
        pipeline = _Pipeline()
        packets = self.run_frames(worker, pipeline, count=2)
        self.assertEqual(pipeline.threshold_updates, [(.6, .8)])
        self.assertEqual(pipeline.infer_thresholds, [(.6, .8), (.6, .8)])
        self.assertTrue(all(packet["confidence_revision"] == 2 for packet in packets if packet))

    def test_nan_and_invalid_ranges_leave_revision_pending_pair_and_mailbox_unchanged(self):
        worker = self.make_worker()
        worker.update_confidence(.5, .6)
        pending = worker._requested_confidence
        mailbox = {"confidence_revision": 1}
        worker._latest = mailbox
        invalid_pairs = ((float("nan"), .6), (.5, float("nan")),
                         (float("inf"), .6), (.5, -float("inf")),
                         (0, .6), (.5, 0), (-.1, .6), (.5, 1.01))
        for bottle, color in invalid_pairs:
            with self.subTest(bottle=bottle, color=color), self.assertRaises(ValueError):
                worker.update_confidence(bottle, color)
            self.assertEqual(worker._confidence_revision, 1)
            self.assertEqual(worker._requested_confidence, pending)
            self.assertIs(worker._latest, mailbox)


class _Pipeline:
    def __init__(self):
        self.thresholds = (.25, .4)
        self.threshold_updates = []
        self.infer_thresholds = []
        self.open_calls = 0
        self.close_calls = 0
        self.on_first_infer = None

    def open(self):
        self.open_calls += 1

    def close(self):
        self.close_calls += 1

    def describe(self):
        return "Fake YOLOX bottle and color models"

    def set_confidence(self, bottle, color):
        self.thresholds = (bottle, color)
        self.threshold_updates.append(self.thresholds)

    def infer(self, frame):
        self.infer_thresholds.append(self.thresholds)
        if len(self.infer_thresholds) == 1 and self.on_first_infer is not None:
            self.on_first_infer()
        return {"boxes": [], "reasons": [], "colors": [], "color_confidences": [],
                "model_labels": [], "inference_ms": 1.0}


if __name__ == "__main__":
    unittest.main()
