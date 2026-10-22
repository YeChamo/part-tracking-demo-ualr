"""Headless tests of confidence editing; no cameras or motion hardware."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from app.confidence_control import ConfidenceControl


class ConfidenceControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.control = ConfidenceControl()
        self.events = QSignalSpy(self.control.valueChanged)

    def tearDown(self):
        self.control.close()
        self.control.deleteLater()

    def assert_percent(self, percent):
        self.assertEqual(self.control.value(), percent / 100.0)
        self.assertEqual(self.control.slider.value(), percent)
        self.assertEqual(self.control.spin.value(), percent)

    def test_default_is_synchronized_without_initial_signal(self):
        self.assert_percent(25)
        self.assertEqual(self.events.count(), 0)

    def test_slider_changes_normalized_value_and_numeric_entry_once(self):
        self.control.slider.setValue(68)
        self.assert_percent(68)
        self.assertEqual(self.events.count(), 1)
        self.assertEqual(self.events.at(0), [.68])

    def test_numeric_entry_changes_slider_once(self):
        self.control.spin.setValue(42)
        self.assert_percent(42)
        self.assertEqual(self.events.count(), 1)
        self.assertEqual(self.events.at(0), [.42])

    def test_programmatic_value_synchronizes_once_and_ignores_same_value(self):
        self.control.setValue(.77)
        self.assert_percent(77)
        self.assertEqual(self.events.count(), 1)
        self.control.setValue(.77)
        self.control.slider.setValue(77)
        self.control.spin.setValue(77)
        self.assertEqual(self.events.count(), 1)

    def test_rounds_to_whole_percent_points(self):
        self.control.setValue(.264)
        self.assert_percent(26)
        self.assertEqual(self.events.count(), 1)
        self.control.setValue(.261)
        self.assertEqual(self.events.count(), 1)

    def test_range_endpoints_are_allowed_and_child_inputs_are_bounded(self):
        self.control.setValue(.05)
        self.assert_percent(5)
        self.control.setValue(.99)
        self.assert_percent(99)
        self.control.slider.setValue(0)
        self.assert_percent(5)
        self.control.spin.setValue(100)
        self.assert_percent(99)

    def test_invalid_programmatic_values_raise_without_mutating_or_emitting(self):
        for value in (float("nan"), float("inf"), -float("inf"), -.2, .049, 1, None, "invalid"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.control.setValue(value)
                self.assert_percent(25)
        self.assertEqual(self.events.count(), 0)

    def test_invalid_initial_values_raise(self):
        for value in (float("nan"), float("inf"), -.1, 1, None, "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ConfidenceControl(value)

    def test_custom_initial_value(self):
        control = ConfidenceControl(.8)
        self.addCleanup(control.deleteLater)
        self.assertEqual(control.value(), .8)
        self.assertEqual(control.slider.value(), 80)
        self.assertEqual(control.spin.value(), 80)

    def test_parent_enabled_state_propagates_to_both_inputs(self):
        self.control.setEnabled(False)
        self.assertFalse(self.control.slider.isEnabled())
        self.assertFalse(self.control.spin.isEnabled())
        self.control.setEnabled(True)
        self.assertTrue(self.control.slider.isEnabled())
        self.assertTrue(self.control.spin.isEnabled())


if __name__ == "__main__":
    unittest.main()
