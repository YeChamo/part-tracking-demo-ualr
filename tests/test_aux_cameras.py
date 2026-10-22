"""Auxiliary camera results never enter the primary sorting path."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.cameras import CameraChoice
from app.ui import MainWindow


class AuxCameraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='ualr-aux-camera-')
        self.root = Path(self.folder.name)
        (self.root/'data').mkdir()
        with patch('app.ui.QTimer.singleShot'):
            self.window = MainWindow(self.root)
        self.window.timer.stop()
        self.window.jobs.pool.shutdown(wait=True,cancel_futures=True)
        self.primary = CameraChoice('usb','usb:primary','Belt camera',0)
        self.aux = CameraChoice('usb','usb:aux','Label camera',1)
        self.window.camera_devices = [self.primary,self.aux]
        self.window.camera_picker.clear()
        self.window.camera_picker.addItem('Belt camera',self.primary)
        self.window.camera_picker.setCurrentIndex(0)
        self.window.refresh_auxiliary_choices()

    def tearDown(self):
        self.window.running = False
        self.window.aux_workers.clear()
        self.window.worker = None
        self.window.close()
        self.window.deleteLater()
        self.folder.cleanup()

    def test_primary_is_excluded_and_aux_worker_has_no_motion_role(self):
        self.assertEqual(self.window.aux_list.count(),1)
        self.assertEqual(self.window.aux_list.item(0).data(Qt.ItemDataRole.UserRole),self.aux.id)
        self.window.aux_list.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(self.window.aux_current_ids,{self.aux.id})

        worker = Mock()
        worker.isRunning.return_value = False
        with patch('app.ui.VideoWorker',return_value=worker) as constructor:
            self.window.start_auxiliary_workers()
        self.assertEqual(constructor.call_count,1)
        self.assertEqual(constructor.call_args.args[0]['camera_id'],self.aux.id)
        self.assertEqual(constructor.call_args.args[0]['source'],'usb')
        self.assertTrue(constructor.call_args.args[0]['auxiliary'])
        worker.start.assert_called_once()
        self.assertEqual(len(self.window.aux_workers),1)

        packet = {'frame':np.zeros((480,640,3),np.uint8),'captured':time.monotonic(),
                  'boxes':[(50,30,150,340)],'colors':['blue'],
                  'caps':[{'status':'present'}],'label_texts':['GATORADE · FROST'],
                  'brand_matches':[True], 'reasons':[[]]}
        worker.take_latest.return_value = packet
        self.window.armed = True
        self.window.client = Mock()
        self.window.update_auxiliary_views(time.monotonic())
        self.assertIn('CAP PRESENT',self.window.aux_panels[self.aux.id]['summary'].text())
        self.assertEqual(self.window.events,[])
        self.assertEqual(self.window.pending,[])
        self.assertEqual(self.window.pass_count+self.window.divert_count,0)
        self.window.client.trigger.assert_not_called()


if __name__=='__main__':
    unittest.main()
