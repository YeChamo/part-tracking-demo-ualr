"""Guard the requested barcode behavior while changing bottle/color inference.

These golden fingerprints were captured from commit
135f0ed468765bd7da8d40475781aec16e1818a6, before the YOLOX color change.
They require no Git installation and work in a source release. AST comparison
permits line-number/formatting changes around the original barcode functions.
Actual QR/EAN-13 decoding is exercised separately in test_vision.py.
"""
import ast
import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BARCODE_FUNCTIONS = {
    "app/vision.py": {
        "_barcode_backend": "4b8916634d8e189c66d8eeec53743b945b672159765c713fd7564517e8075d73",
        "barcode_status": "690f2fde4f7f901f538215cc12c4b19a6f2a7070e807c88482bc20953fbaa0e1",
        "_points_box": "88d014a20d18156e09a47fd992e50ca1c66c10fb11b5ff54e381fc62fcf27305",
        "decode_barcodes": "6599ab0db41f68f38c53d925aa9f57d159ef6e017e56fe825b3856a7bcd00c49",
        "_decode_frame_and_crops": "00a87fcb7b6c7d501da562edb6b6a88c210c83795167086da77ddb8ff4f6d165",
    },
    "app/ui.py": {
        "scanner_read": "6415da9a96bcd5727674c47bd3337e756bd98b8a4cd0c04c055901ac06b4116c",
        "show_barcode": "9c8232a78d55e9646321dbab71534590321baf7b0adbf326fa1ac11d3d28ff63",
    },
}
FIXTURE_SHA256 = "2e70ab04576d29553fbbee0ec0c12ddbc7779918251f0f042f2cb441e78bd7c3"


def _fingerprint(node):
    representation = ast.dump(node, include_attributes=False)
    # Python 3.12 added an empty function field; no barcode function is generic.
    representation = representation.replace(", type_params=[]", "")
    return hashlib.sha256(representation.encode("utf-8")).hexdigest()


class BarcodeInvarianceTests(unittest.TestCase):
    def test_camera_decoder_and_scanner_display_functions_are_unchanged(self):
        for filename, expected in BARCODE_FUNCTIONS.items():
            tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
            for name, fingerprint in expected.items():
                with self.subTest(file=filename, function=name):
                    functions = [node for node in ast.walk(tree)
                                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 and node.name == name]
                    self.assertEqual(len(functions), 1, f"Barcode function {name} must remain present.")
                    self.assertEqual(_fingerprint(functions[0]), fingerprint,
                                     f"The YOLOX change must leave barcode function {name} unchanged.")

    def test_synthetic_barcode_fixture_source_is_unchanged(self):
        source = (ROOT / "app/barcode_fixture.py").read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(source).hexdigest(), FIXTURE_SHA256)


if __name__ == "__main__":
    unittest.main()
