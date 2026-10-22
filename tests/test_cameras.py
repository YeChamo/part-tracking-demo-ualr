import unittest
from unittest.mock import patch

from app.cameras import CameraChoice, discover_cameras, resolve_usb_camera


class CameraSelectionTests(unittest.TestCase):
    def setUp(self):
        self.internal = CameraChoice("usb", "usb:internal", "Laptop camera", 0)
        self.external = CameraChoice("usb", "usb:external", "USB bottle camera", 1)
        self.settings = {"camera_id": self.external.id, "camera_name": self.external.name,
                         "camera_index": 1, "camera_manual": False}

    def test_saved_external_identity_follows_index_change(self):
        external_now_zero = CameraChoice("usb", self.external.id, self.external.name, 0)
        laptop_now_one = CameraChoice("usb", self.internal.id, self.internal.name, 1)
        choice = resolve_usb_camera(self.settings, [external_now_zero, laptop_now_one])
        self.assertEqual(choice.index, 0)
        self.assertEqual(choice.id, self.external.id)

    def test_missing_external_never_falls_back_to_laptop_or_manual(self):
        for manual in (True, False):
            with self.subTest(manual=manual), self.assertRaisesRegex(RuntimeError, "USB bottle camera is not available"):
                resolve_usb_camera(dict(self.settings, camera_manual=manual, camera_index=0), [self.internal])

    def test_equal_friendly_names_do_not_confuse_identity(self):
        other = CameraChoice("usb", "usb:other", self.external.name, 1)
        intended = CameraChoice("usb", self.external.id, self.external.name, 2)
        self.assertEqual(resolve_usb_camera(self.settings, [other, intended]).index, 2)

    def test_old_numeric_setting_requires_explicit_manual_choice(self):
        with self.assertRaisesRegex(RuntimeError, "Select a camera by name"):
            resolve_usb_camera({"camera_index": 0}, [self.internal])

    def test_explicit_manual_index_does_not_require_discovery(self):
        with patch("app.cameras.discover_cameras", side_effect=AssertionError("Must not enumerate")):
            self.assertEqual(resolve_usb_camera({"camera_manual": True, "camera_index": 2}).index, 2)

    def test_invalid_manual_indices_rejected(self):
        for value in (-1, 100, True, None, "no", 1.5, float("nan")):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "manual USB camera index"):
                resolve_usb_camera({"camera_manual": True, "camera_index": value}, [])

    def test_no_devices_does_not_synthesize_camera_zero(self):
        with patch("app.cameras.sys.platform", "win32"), \
             patch("app.cameras._windows_usb_cameras", return_value=[]), \
             patch("app.cameras._basler_cameras", return_value=[]):
            self.assertEqual(discover_cameras(), [])
        with self.assertRaisesRegex(RuntimeError, "not available"):
            resolve_usb_camera(self.settings, [])

    def test_usb_discovery_error_keeps_available_basler_camera(self):
        basler = CameraChoice("basler", "basler:1234", "Basler (1234)", serial="1234")
        with patch("app.cameras.sys.platform", "win32"), \
             patch("app.cameras._windows_usb_cameras", side_effect=OSError("COM unavailable")), \
             patch("app.cameras._basler_cameras", return_value=[basler]), \
             self.assertLogs("app.cameras", level="WARNING"):
            self.assertEqual(discover_cameras(), [basler])

    def test_no_usb_enumerator_on_non_windows(self):
        with patch("app.cameras.sys.platform", "darwin"), \
             patch("app.cameras._windows_usb_cameras", side_effect=AssertionError("Windows only")), \
             patch("app.cameras._basler_cameras", return_value=[]):
            self.assertEqual(discover_cameras(), [])

    def test_resolves_again_immediately_before_start(self):
        with patch("app.cameras.discover_cameras", return_value=[self.external]) as discover:
            self.assertEqual(resolve_usb_camera(self.settings), self.external)
            discover.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
