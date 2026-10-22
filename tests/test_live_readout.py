"""Live-only operator view stays honest before and after tracking begins."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
from PySide6.QtWidgets import QApplication

from app.tracking import Track
from app.ui import MainWindow


class LiveReadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='ualr-live-readout-')
        self.root = Path(self.folder.name)
        (self.root / 'data').mkdir()
        with patch('app.ui.QTimer.singleShot'):
            self.window = MainWindow(self.root)
        self.window.timer.stop()
        self.window.jobs.pool.shutdown(wait=True, cancel_futures=True)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.folder.cleanup()

    def test_normal_launch_exposes_only_live_camera_sources(self):
        self.assertEqual(self.window.source.currentData(), 'usb')
        self.assertEqual(self.window.source.findData('simulation'), -1)
        self.assertEqual(self.window.source.findData('video'), -1)
        self.assertIn('LIVE CAMERA', self.window.badge.text())
        self.assertTrue(self.window.auto_start_saved_camera)

    def test_detected_bottle_is_visible_before_tracking_then_predicts_route(self):
        self.window.running = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        packet = {'frame': frame, 'boxes': [(240, 70, 330, 400)],
                  'colors': ['yellow'], 'color_confidences': [0.82],
                  'brand_matches': [True]}
        self.window.last_packet = packet
        self.window.update_live_inspection([], packet)
        self.assertIn('NOT TRACKED', self.window.live_title.text())
        self.assertIn('YELLOW', self.window.live_detail.text())
        self.assertEqual(self.window.live_route.text(), 'MOVE TO ENTRY')

        track = Track(id=7, bbox=packet['boxes'][0], hits=3)
        self.window.track_meta[7] = {'color': 'yellow', 'color_confidence': 0.82,
                                     'gatorade_label_match': True}
        self.window.update_live_inspection([track], packet)
        self.assertIn('#007', self.window.live_title.text())
        self.assertIn('82%', self.window.live_detail.text())
        self.assertEqual(self.window.live_route.text(), 'PREDICTED 1 · DIVERT')

        self.window.running = False
        self.window.update_live_inspection()
        self.assertEqual(self.window.live_route.text(), 'AWAITING')


if __name__ == '__main__':
    unittest.main()
