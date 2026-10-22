import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from app.vision import (VideoWorker, barcode_status, classify, classify_color, decode_barcodes,
                        inspection_error, teach_color, teach_reference)


def good_bottle():
    image = np.full((300, 160, 3), 35, dtype=np.uint8)
    box = (20, 20, 140, 280)
    image[20:280, 20:140] = (30, 120, 220)
    image[20:78, 20:140] = (230, 70, 20)
    image[110:224, 20:140] = (25, 220, 40)
    for y in range(115, 218, 8):
        image[y:y+3, 32:128] = (220, 230, 240)
    return image, box


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.frame, self.box = good_bottle()
        self.reference = teach_reference(self.frame, self.box)
        self.settings = {"rule": "cap_label"}

    def test_reference_roundtrips_and_good_matches(self):
        reference = json.loads(json.dumps(self.reference))
        self.assertEqual(classify(self.frame, self.box, self.settings, reference), [])

    def test_missing_cap_is_rejected(self):
        frame = self.frame.copy()
        frame[20:78, 20:140] = (35, 35, 35)
        self.assertTrue(any("Cap" in why for why in classify(frame, self.box, self.settings, self.reference)))

    def test_missing_label_is_rejected(self):
        frame = self.frame.copy()
        frame[110:224, 20:140] = (30, 120, 220)
        reasons = classify(frame, self.box, self.settings, self.reference)
        self.assertTrue(any("Label" in why for why in reasons))
        self.assertFalse(any("Cap" in why for why in reasons))

    def test_untrained_and_corrupt_reference_never_pass(self):
        self.assertTrue(classify(self.frame, self.box, self.settings, None))
        self.reference["cap"]["hist"][0] = float("nan")
        self.assertTrue(inspection_error(self.settings, self.reference))

    def test_cap_only_and_demo_rules(self):
        changed = self.frame.copy()
        changed[110:224, 20:140] = 0
        self.assertEqual(classify(changed, self.box, {"rule": "cap"}, self.reference), [])
        self.assertTrue(classify(changed, self.box, {"rule": "all"}, None))
        self.assertEqual(classify(changed, self.box, {"rule": "none"}, None), [])

    def test_tiny_box_rejected(self):
        with self.assertRaises(ValueError):
            teach_reference(self.frame, (1, 1, 2, 2))


class ColorTests(unittest.TestCase):
    @staticmethod
    def image(hue, saturation=220, value=220):
        hsv = np.full((300, 160, 3), (hue, saturation, value), dtype=np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), (0, 0, 160, 300)

    def test_predefined_colors_and_routing(self):
        for name, hue in (("red", 0), ("orange", 15), ("yellow", 29),
                          ("green", 65), ("blue", 110), ("purple", 150)):
            with self.subTest(name=name):
                image, box = self.image(hue)
                measured, confidence = classify_color(image, box)
                self.assertEqual(measured, name)
                self.assertGreater(confidence, 0.9)
                self.assertEqual(classify(image, box, {"pass_color": name}, None), [])
                other = "blue" if name != "blue" else "orange"
                self.assertTrue(classify(image, box, {"pass_color": other}, None))

    def test_red_wrap_clear_and_dark_unknown(self):
        image, box = self.image(179)
        self.assertEqual(classify_color(image, box)[0], "red")
        image, box = self.image(0, saturation=0)
        self.assertEqual(classify_color(image, box)[0], "clear")
        self.assertEqual(classify(image, box, {"pass_color": "clear"}, None), [])
        image, box = self.image(15, value=10)
        self.assertEqual(classify_color(image, box)[0], "unknown")
        self.assertEqual(classify(image, box, {}, None), ["Unknown color"])

    def test_mixed_color_is_unknown(self):
        orange, box = self.image(15)
        blue, _ = self.image(110)
        orange[:, 80:] = blue[:, 80:]
        self.assertEqual(classify_color(orange, box)[0], "unknown")

    def test_sample_zone_avoids_label_and_is_configurable(self):
        orange, box = self.image(15)
        blue, _ = self.image(110)
        orange[230:, :] = blue[230:, :]
        self.assertEqual(classify_color(orange, box)[0], "blue")
        self.assertEqual(classify_color(orange, box, {"color_y1": .20, "color_y2": .40})[0], "orange")

    def test_cap_label_and_belt_colors_do_not_define_body_color(self):
        orange, box = self.image(15)
        blue, _ = self.image(110)
        # A strongly colored cap/label covers most of the bottle. The exposed
        # liquid at the bottom remains orange; edge strips are the blue belt.
        orange[:225] = blue[:225]
        orange[:, :18] = blue[:, :18]
        orange[:, 142:] = blue[:, 142:]
        self.assertEqual(classify_color(orange, box)[0], "orange")

    def test_taught_color_requires_reference_and_compares_circular_hue(self):
        image, box = self.image(179)
        reference = teach_color(image, box)
        self.assertTrue(inspection_error({"pass_color": "taught"}, None))
        self.assertFalse(inspection_error({"pass_color": "taught"}, reference))
        red, _ = self.image(2)
        self.assertEqual(classify(red, box, {"pass_color": "taught"}, reference), [])
        blue, _ = self.image(110)
        self.assertTrue(classify(blue, box, {"pass_color": "taught"}, reference))


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


class MailboxTests(unittest.TestCase):
    def test_barcode_coordinates_are_never_replayed_on_another_frame(self):
        class FakeDetector:
            def infer(self, frame):
                return SimpleNamespace(detections=[], inference_ms=1.0)
            def close(self): pass
        frame = np.full((100, 100, 3), 100, dtype=np.uint8)
        source = ("usb", object(), None)
        packets = []
        timestamps = iter((10.0, 10.05, 10.20))
        with tempfile.TemporaryDirectory() as folder:
            worker = VideoWorker({"source": "usb", "rule": "none"}, Path(folder))
            def read(_source):
                packet = worker.take_latest()
                if packet is not None:
                    packets.append(packet)
                try:
                    return frame.copy(), next(timestamps)
                except StopIteration:
                    raise EOFError("Test source ended")
            symbol = {"text": "5901234123457", "format": "EAN-13", "bbox": (5, 5, 20, 25)}
            with patch.object(worker, "_make_detector", return_value=FakeDetector()), patch.object(
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
        class FakeDetector:
            def close(self): pass
        capture = EmptyVideo()
        with tempfile.TemporaryDirectory() as folder:
            worker = VideoWorker({"source": "video", "rule": "none"}, Path(folder))
            faults = []
            worker.fault.connect(faults.append)
            worker._latest = {"frame": "stale"}
            with patch.object(worker, "_make_detector", return_value=FakeDetector()), patch.object(
                    worker, "_open_source", return_value=(("video", capture, None), "sample.avi")):
                worker.run()  # Fake source only: no actual camera or hardware is opened.
            self.assertTrue(capture.released)
            self.assertIsNone(worker.take_latest())
            self.assertEqual(len(faults), 1)
            self.assertIn("Video ended", faults[0])


if __name__ == "__main__":
    unittest.main()
