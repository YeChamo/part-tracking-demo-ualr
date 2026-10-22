"""Validate synthetic imagery and decode it with ZXing when installed."""
import importlib.util
import unittest

import numpy as np

from app.barcode_fixture import (
    DEFAULT_EAN13, demo_barcode, ean13_bgr, ean13_modules, make_ean13, normalize_ean13,
)


class BarcodeFixtureTests(unittest.TestCase):
    def test_checksum_known_examples_and_per_bottle_assignment(self):
        self.assertEqual(make_ean13("012345678901"), "0123456789012")
        self.assertEqual(make_ean13("400638133393"), "4006381333931")
        codes = [demo_barcode(sequence) for sequence in range(20)]
        self.assertEqual(len(set(codes)), 20)
        self.assertTrue(all(code.startswith("200") and len(code) == 13 for code in codes))
        self.assertEqual(DEFAULT_EAN13, "2000000000015")

    def test_invalid_data_or_checksum_is_refused(self):
        for value in ("0123456789013", "123", "١٢٣٤٥٦٧٨٩٠١٢", 123456789012, " abcdefghijk"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_ean13(value)
        for sequence in (-1, True, 1.5, 1_000_000_000):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                demo_barcode(sequence)

    def test_modules_include_full_left_middle_and_right_guards(self):
        modules = ean13_modules("0123456789012")
        self.assertEqual(len(modules), 95)
        self.assertEqual(modules[:3], "101")
        self.assertEqual(modules[45:50], "01010")
        self.assertEqual(modules[-3:], "101")
        self.assertEqual(modules[3:10], "0011001")  # L-encoded digit 1
        self.assertEqual(modules[50:57], "1000100")  # R-encoded digit 7

    def test_render_is_bgr_with_clean_quiet_zones(self):
        image = ean13_bgr()
        self.assertEqual(image.shape, (140, 476, 3))
        self.assertEqual(image.dtype, np.uint8)
        self.assertTrue(np.all(image[:, :48] == 255))
        self.assertTrue(np.all(image[:, -48:] == 255))
        self.assertTrue(np.array_equal(image[:, :, 0], image[:, :, 2]))
        self.assertEqual(set(np.unique(image)), {0, 255})

    @unittest.skipUnless(importlib.util.find_spec("zxingcpp") is not None, "zxingcpp decoder is not installed in this interpreter")
    def test_real_decoder_reads_every_first_digit_parity(self):
        import zxingcpp

        for first in range(10):
            code = make_ean13(str(first) + "12345678901")
            with self.subTest(code=code):
                results = zxingcpp.read_barcodes(ean13_bgr(code, module_width=5, height=180))
                # An EAN-13 beginning with 0 can be identified as equivalent
                # UPC-A, which omits that initial zero in the decoder text.
                decoded = [result.text for result in results]
                self.assertTrue(code in decoded or (code.startswith("0") and code[1:] in decoded), decoded)


if __name__ == "__main__":
    unittest.main()
