import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from app.vision import VideoWorker, barcode_status, decode_barcodes


class BarcodeTests(unittest.TestCase):
    def test_blank_image_has_no_invented_barcode(self):
        self.assertEqual(decode_barcodes(np.full((200, 400, 3), 255, dtype=np.uint8)), [])

    @unittest.skipUnless(hasattr(cv2, "QRCodeEncoder_create"), "QR encoder unavailable")
    def test_actual_generated_qr_is_decoded(self):
        qr = cv2.QRCodeEncoder_create().encode("UALR-TEST-123")
        qr = cv2.copyMakeBorder(qr, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
        qr = cv2.resize(qr, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        image = cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)
        symbols = decode_barcodes(image)
        self.assertTrue(any(item["text"] == "UALR-TEST-123" for item in symbols))
        self.assertTrue(all(len(item["bbox"]) == 4 for item in symbols))

    def test_actual_ean13_bottle_barcode_is_decoded(self):
        if barcode_status()[1] != "ZXing-C++":
            self.skipTest("Retail EAN-13 validation requires the packaged ZXing-C++ decoder")
        # EAN-13 known test symbol, rendered directly from its binary bars.
        # This tests a retail bottle barcode, independently of any decoder's writer.
        digits = "5901234123457"
        left = ("0001101", "0011001", "0010011", "0111101", "0100011",
                "0110001", "0101111", "0111011", "0110111", "0001011")
        parity = "LGGLLG"  # Leading digit 5.
        invert = lambda bits: "".join("0" if bit == "1" else "1" for bit in bits)
        bits = "101"
        for digit, pattern in zip(digits[1:7], parity):
            code = left[int(digit)]
            bits += code if pattern == "L" else invert(code[::-1])
        bits += "01010"
        bits += "".join(invert(left[int(digit)]) for digit in digits[7:]) + "101"
        image = np.full((200, (len(bits) + 24) * 4, 3), 255, dtype=np.uint8)
        for index, bit in enumerate(bits):
            if bit == "1":
                image[20:180, (index+12)*4:(index+13)*4] = 0
        symbols = decode_barcodes(image)
        self.assertTrue(any(item["text"] == digits for item in symbols))


class FakePipeline:
    def __init__(self, result=None):
        self.result = result or {"boxes": [], "reasons": [], "colors": [],
                                 "color_confidences": [], "model_labels": [],
                                 "inference_ms": 1.0}
        self.opened = False
        self.closed = False
        self.frames = []

    def open(self):
        self.opened = True

    def describe(self):
        return "YOLOX test bottle/color models"

    def infer(self, frame):
        self.frames.append(frame)
        return self.result

    def close(self):
        self.closed = True


class MailboxTests(unittest.TestCase):
    def test_barcode_coordinates_are_never_replayed_on_another_frame(self):
        pipeline = FakePipeline()
        frame = np.full((100, 100, 3), 100, dtype=np.uint8)
        source = ("usb", object(), None)
        packets = []
        timestamps = iter((10.0, 10.05, 10.20))
        with tempfile.TemporaryDirectory() as folder:
            worker = VideoWorker({"source": "usb", "rule": "color"}, Path(folder))
            def read(_source):
                packet = worker.take_latest()
                if packet is not None:
                    packets.append(packet)
                try:
                    return frame.copy(), next(timestamps)
                except StopIteration:
                    raise EOFError("Test source ended")
            symbol = {"text": "5901234123457", "format": "EAN-13", "bbox": (5, 5, 20, 25)}
            with patch("app.vision.YoloXPipeline", return_value=pipeline), patch.object(
                    worker, "_open_source", return_value=(source, "fake USB")), patch.object(
                    worker, "_read_source", side_effect=read), patch.object(
                    worker, "_close_source"), patch("app.vision.barcode_status", return_value=(True, "Test decoder")), patch(
                    "app.vision._decode_frame_and_crops", return_value=[symbol]) as decoder:
                worker.run()
            self.assertEqual(decoder.call_count, 2)
            self.assertEqual(len(packets), 3)
            self.assertEqual(packets[0]["barcodes"], [symbol])
            self.assertEqual(packets[0]["barcode_captured"], packets[0]["captured"])
            self.assertEqual(packets[1]["captured"], 10.05)
            self.assertEqual(packets[1]["barcodes"], [])
            self.assertIsNone(packets[1]["barcode_captured"])
            self.assertTrue(packets[1]["barcode_available"])
            self.assertEqual(packets[2]["barcodes"], [symbol])
            self.assertEqual(packets[2]["barcode_captured"], packets[2]["captured"])
            self.assertTrue(pipeline.opened)
            self.assertTrue(pipeline.closed)

    def test_take_latest_consumes_and_stop_discards(self):
        worker = VideoWorker({}, Path("."))
        worker._latest = {"frame": 1}
        self.assertEqual(worker.take_latest(), {"frame": 1})
        self.assertIsNone(worker.take_latest())
        worker._latest = {"frame": 2}
        worker.stop()
        self.assertIsNone(worker.take_latest())

    def test_eof_fault_and_close_clear_stale_frame(self):
        class EmptyVideo:
            released = False
            def read(self): return False, None
            def get(self, _): return 30.0
            def release(self): self.released = True
        capture = EmptyVideo()
        pipeline = FakePipeline()
        with tempfile.TemporaryDirectory() as folder:
            worker = VideoWorker({"source": "video", "rule": "color"}, Path(folder))
            faults = []
            worker.fault.connect(faults.append)
            worker._latest = {"frame": "stale"}
            with patch("app.vision.YoloXPipeline", return_value=pipeline), patch.object(
                    worker, "_open_source", return_value=(("video", capture, None), "sample.avi")):
                worker.run()  # Fake source only: no actual camera or hardware is opened.
            self.assertTrue(capture.released)
            self.assertTrue(pipeline.closed)
            self.assertIsNone(worker.take_latest())
            self.assertEqual(len(faults), 1)
            self.assertIn("Video ended", faults[0])


class YoloXWorkerTests(unittest.TestCase):
    def test_visual_tracking_forwards_detector_confidence_without_color_requirements(self):
        frame = np.full((100, 100, 3), 127, np.uint8)
        pipeline = FakePipeline({"boxes": [(20, 10, 80, 90)], "colors": ["unknown"],
                                 "color_confidences": [0.0], "confidences": [.77],
                                 "model_labels": ["bottle"], "visual_only": True,
                                 "reasons": [[]], "inference_ms": 3.0})
        with tempfile.TemporaryDirectory() as folder:
            worker = VideoWorker({"source": "usb", "visual_only": True, "rule": "tracking"}, Path(folder))
            packets = []
            reads = 0
            def read(_source):
                nonlocal reads
                reads += 1
                if reads == 1:
                    return frame, 10.0
                packets.append(worker.take_latest())
                raise EOFError("Test source ended")
            with patch("app.vision.YoloXPipeline", return_value=pipeline), patch.object(
                    worker, "_open_source", return_value=(("usb", object(), None), "Fake camera")), patch.object(
                    worker, "_read_source", side_effect=read), patch.object(worker, "_close_source"), patch(
                    "app.vision.barcode_status", return_value=(False, "Unavailable")):
                worker.run()
            self.assertEqual(len(packets), 1)
            self.assertTrue(packets[0]["visual_only"])
            self.assertTrue(packets[0]["inspection_ready"])
            self.assertEqual(packets[0]["confidences"], [.77])
            self.assertEqual(packets[0]["model_labels"], ["bottle"])
            self.assertEqual(packets[0]["reasons"], [[]])

    def test_worker_uses_model_predictions_instead_of_pixel_color(self):
        # The visible pixels are orange. The model reports blue, and its class
        # prediction and routing decision must arrive at the UI unchanged.
        frame = np.full((100, 100, 3), (0, 128, 255), dtype=np.uint8)
        expected = {"boxes": [(10.0, 10.0, 90.0, 90.0)],
                    "colors": ["blue"], "color_confidences": [0.92],
                    "reasons": [["YOLOX color blue (divert)"]],
                    "model_labels": ["blue_bottle"], "inference_ms": 4.75}
        pipeline = FakePipeline(expected)
        packets = []
        timestamps = iter((10.0,))
        with tempfile.TemporaryDirectory() as folder:
            worker = VideoWorker({"source": "usb", "rule": "color", "pass_color": "orange"}, Path(folder))
            def read(_source):
                packet = worker.take_latest()
                if packet is not None:
                    packets.append(packet)
                try:
                    return frame.copy(), next(timestamps)
                except StopIteration:
                    raise EOFError("Test source ended")
            with patch("app.vision.YoloXPipeline", return_value=pipeline), patch.object(
                    worker, "_open_source", return_value=(("usb", object(), None), "fake USB")), patch.object(
                    worker, "_read_source", side_effect=read), patch.object(
                    worker, "_close_source"), patch("app.vision.barcode_status", return_value=(False, "Unavailable")):
                worker.run()
            self.assertEqual(len(packets), 1)
            packet = packets[0]
            for key, value in expected.items():
                self.assertEqual(packet[key], value, key)
            self.assertEqual(packet["defects"], expected["boxes"])
            self.assertTrue(packet["inspection_ready"])
            self.assertEqual(packet["vision_pipeline"], pipeline.describe())
            self.assertEqual(len(pipeline.frames), 1)
            np.testing.assert_array_equal(pipeline.frames[0], frame)
            self.assertTrue(pipeline.closed)

    def test_missing_trained_color_model_does_not_open_camera(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = VideoWorker({"source": "usb", "rule": "color", "yolox_mode": "two_models",
                                  "color_model_path": str(Path(folder) / "missing_color_model.onnx")}, Path(folder))
            faults = []
            worker.fault.connect(faults.append)
            with patch.object(worker, "_open_source") as open_source:
                worker.run()
            open_source.assert_not_called()
            self.assertIsNone(worker.take_latest())
            self.assertEqual(len(faults), 1)
            self.assertIn("YOLOX model was not found", faults[0])


if __name__ == "__main__":
    unittest.main()
