"""Compile tiny synthetic packages; extract-only never executes native fixtures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


@unittest.skipUnless(os.name == "nt", "Windows .NET packaging check")
class OfflineLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.workspace = tempfile.TemporaryDirectory(prefix="ualr-offline-tests-")
        cls.folder = Path(cls.workspace.name)
        cls.powershell = Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        names = ["PartTrackingUALR.exe", "_runtime/python311.dll", "_runtime/vcruntime140.dll",
                 "_runtime/vcruntime140_1.dll", "_runtime/ucrtbase.dll", "_runtime/base_library.zip",
                 "_runtime/PySide6/QtCore.pyd", "_runtime/torch/lib/torch_cpu.dll",
                 "_runtime/onnxruntime/capi/onnxruntime_pybind11_state.pyd", "models/yolox_nano.onnx",
                 "models/yolox_nano.onnx.data", "models/yolox_s.onnx", "models/color/distilV4_student.onnx"]
        for variant in ("valid", "unsafe", "missing"):
            archive = cls.folder / (variant + ".zip")
            with zipfile.ZipFile(archive, "w") as package:
                for name in names:
                    if variant == "missing" and name == "models/yolox_nano.onnx.data":
                        continue
                    package.writestr("PartTrackingDemoUALR/" + name, b"Synthetic packaging fixture; never execute")
                if variant == "unsafe":
                    package.writestr("PartTrackingDemoUALR/../escaped.txt", b"must not escape")
            executable = cls.folder / (variant + ".exe")
            built = subprocess.run([str(cls.powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                    str(cls.root / "BuildOffline.ps1"), "-Archive", str(archive),
                                    "-Output", str(executable)], capture_output=True, text=True,
                                   timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
            if built.returncode:
                raise AssertionError("Windows PowerShell build failed: " + built.stdout + built.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def extract(self, variant, destination):
        return subprocess.run([str(self.folder / (variant + ".exe")), "--extract-only", "--destination",
                               str(destination)], capture_output=True, text=True, timeout=30,
                              creationflags=subprocess.CREATE_NO_WINDOW)

    def test_extract_cache_preserves_operator_data(self):
        destination = self.folder / "cache-install"
        self.assertEqual(self.extract("valid", destination).returncode, 0)
        self.assertTrue((destination / "_runtime/python311.dll").is_file())
        data = destination / "data"
        data.mkdir()
        saved = data / "settings.json"
        saved.write_text('{"operator":"preserved"}')
        self.assertEqual(self.extract("valid", destination).returncode, 0)
        self.assertEqual(saved.read_text(), '{"operator":"preserved"}')

    def test_existing_unrecognized_directory_is_not_overwritten(self):
        destination = self.folder / "operator-directory"
        destination.mkdir()
        original = destination / "important.txt"
        original.write_text("operator data")
        self.assertNotEqual(self.extract("valid", destination).returncode, 0)
        self.assertEqual(original.read_text(), "operator data")
        self.assertEqual(list(destination.iterdir()), [original])

    def test_cache_rejects_corrupted_python_dll_without_overwriting(self):
        destination = self.folder / "damaged-install"
        self.assertEqual(self.extract("valid", destination).returncode, 0)
        python_dll = destination / "_runtime/python311.dll"
        python_dll.write_bytes(b"corrupted")
        self.assertNotEqual(self.extract("valid", destination).returncode, 0)
        self.assertEqual(python_dll.read_bytes(), b"corrupted")

    def test_zip_traversal_is_refused_before_installation(self):
        destination = self.folder / "unsafe-install"
        self.assertNotEqual(self.extract("unsafe", destination).returncode, 0)
        self.assertFalse(destination.exists())
        self.assertFalse((self.folder / "escaped.txt").exists())

    def test_missing_external_model_data_does_not_install(self):
        destination = self.folder / "incomplete-install"
        self.assertNotEqual(self.extract("missing", destination).returncode, 0)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
