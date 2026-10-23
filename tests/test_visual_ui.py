"""Visual tracking keeps useful live IDs without any hardware-output path."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import numpy as np
from PySide6.QtWidgets import QApplication

from app.tracking import Decision
from app.ui import MainWindow


class _Camera:
    def __init__(self):
        self.packet=None
        self.preparing_models=False
        self.source_started_at=time.monotonic()

    def take_latest(self):
        value,self.packet=self.packet,None
        return value

    def isRunning(self): return False
    def stop(self): pass


class VisualUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ualr-visual-ui-')
        self.root=Path(self.temp.name)
        (self.root/'data').mkdir()
        with patch('app.ui.QTimer.singleShot'):
            self.window=MainWindow(self.root)
        self.window.timer.stop()
        self.window.jobs.pool.shutdown(wait=True,cancel_futures=True)
        self.window.jobs=Mock()

    def tearDown(self):
        self.window.worker=None
        self.window.model_preparer=None
        self.window.owns_motion=self.window.output_busy=False
        self.window.close()
        self.window.deleteLater()
        self.temp.cleanup()

    def packet(self,box=(270,90,350,400),score=.92):
        return {'frame':np.zeros((480,640,3),dtype=np.uint8),'captured':time.monotonic(),
                'boxes':[box],'reasons':[[]],'model_labels':['bottle'],'confidences':[score],
                'colors':['unknown'],'color_confidences':[0.0],'barcodes':[],
                'inspection_ready':True,'visual_only':True,'confidence_revision':0}

    def test_visual_layout_has_model_preparation_and_no_routing_or_motion_surfaces(self):
        self.assertTrue(self.window.visual_only)
        self.assertEqual(self.window.fields['yolox_mode'].currentData(),'tracking')
        self.assertIn('model_experiment_path',self.window.fields)
        self.assertIn('model_architecture',self.window.fields)
        self.assertIn('inference_backend',self.window.fields)
        self.assertTrue(self.window.prepare_models_button.isEnabled())
        self.assertTrue(self.window.fields['confidence'].isEnabled())
        diverter=next(i for i in range(self.window.tabs.count()) if self.window.tabs.tabText(i)=='Diverter')
        self.assertFalse(self.window.tabs.isTabVisible(diverter))
        self.assertTrue(self.window.stat_cards['output'].isHidden())
        self.assertTrue(self.window.stat_cards['divert'].isHidden())
        self.assertFalse(self.window.table.isColumnHidden(2))
        self.assertTrue(self.window.table.isColumnHidden(4))
        self.assertFalse(self.window.arm.isEnabled())
        self.assertFalse(self.window.connect_button.isEnabled())
        with patch('app.ui.QFileDialog.getOpenFileName',return_value=('D:/models/bottles.pth','')) as picker:
            self.window.path_buttons['model_path'].click()
        self.assertEqual(self.window.fields['model_path'].text(),'D:/models/bottles.pth')
        self.assertIn('*.pth',picker.call_args.args[-1])

    def test_centered_stationary_bottle_keeps_visible_id_model_and_confidence(self):
        camera=_Camera()
        self.window.worker=camera
        self.window.running=True
        self.window.started_at=time.monotonic()
        for score in (.92,.94,.93):
            camera.packet=self.packet(score=score)
            self.window.tick()
        self.assertEqual([track.id for track in self.window.tracker.tracks],[1])
        self.assertIn('#001',self.window.live_title.text())
        self.assertIn('BOTTLE',self.window.live_detail.text())
        self.assertIn('93%',self.window.live_detail.text())
        self.assertEqual(self.window.live_route.text(),'TRACKING')
        self.assertEqual(self.window.table.rowCount(),1)
        self.assertEqual(self.window.stats['total'].text(),'1')
        self.assertEqual(self.window.stats['pass'].text(),'1')
        self.assertEqual(self.window.pending,[])
        self.window.jobs.submit.assert_not_called()

    def test_visual_api_guards_block_all_motion_even_with_stale_armed_state(self):
        controller=Mock()
        self.window.client=controller
        self.window.running=self.window.armed=self.window.owns_motion=True
        self.window.output_busy=True
        self.window.send_gate.set()
        self.window.program.addItem('Should never run','reject-once')
        self.window.pending=[(0,1,{'output':'SCHEDULED'})]
        with patch('app.ui.EtherMotionClient') as client,patch('app.ui.subprocess.Popen') as launch:
            self.window.decision(Decision(1,True,['test'],time.monotonic(),(20,20,60,120)))
            self.window.dispatch_due(time.monotonic())
            self.window.start_sequence_program('reject-once')
            self.window.resume_sequence(time.monotonic()+100)
            self.window.poll_motion()
            self.window.request_motion_stop()
            self.window.launch_ethermotion()
            self.window.toggle_arm(True)
            self.window.discover()
        self.assertEqual(controller.mock_calls,[])
        self.window.jobs.submit.assert_not_called()
        client.assert_not_called(); launch.assert_not_called()
        self.assertFalse(self.window.armed)
        self.assertFalse(self.window.send_gate.is_set())
        self.assertEqual(self.window.pending,[])
        self.assertEqual(self.window.events,[])

    def test_visual_csv_retains_barcode_and_contains_no_routing_claims(self):
        camera=_Camera(); self.window.worker=camera
        self.window.running=True; self.window.started_at=time.monotonic()
        packet=self.packet()
        packet['barcodes']=[{'text':'5901234123457','format':'EAN-13','bbox':(280,180,320,250)}]
        camera.packet=packet
        self.window.tick()
        self.assertEqual(self.window.barcode_text.text(),'5901234123457')
        target=self.root/'tracks.csv'; self.window.write_csv(target)
        with target.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream); rows=list(reader)
        self.assertEqual(rows[0]['barcode'],'5901234123457')
        self.assertEqual(rows[0]['model_label'],'bottle')
        self.assertNotIn('decision',reader.fieldnames)
        self.assertNotIn('output',reader.fieldnames)

    def test_fullscreen_uses_same_visual_state_without_creating_another_source(self):
        camera=_Camera(); self.window.worker=camera
        with patch('app.ui.VideoWorker') as worker,patch('app.ui.cv2.VideoCapture') as capture:
            self.window.toggle_fullscreen()
            self.assertIs(self.window.fullscreen.view.main,self.window)
            self.assertTrue(self.window.fullscreen.view.main.visual_only)
            self.window.toggle_fullscreen()
        self.assertIs(self.window.worker,camera)
        worker.assert_not_called(); capture.assert_not_called()

    def test_color_prediction_is_shown_and_exported_with_bottle_id(self):
        camera=_Camera(); self.window.worker=camera
        self.window.running=True; self.window.started_at=time.monotonic()
        packet=self.packet(); packet.update(colors=['blue'],color_confidences=[.81])
        camera.packet=packet; self.window.tick()
        self.assertIn('BLUE 81%',self.window.live_evidence.text())
        self.assertIn('BLUE 81%',self.window.visual_track_title(self.window.tracker.tracks[0]))
        self.assertEqual(self.window.table.item(0,2).text(),'BLUE')
        target=self.root/'colors.csv'; self.window.write_csv(target)
        with target.open(encoding='utf-8-sig',newline='') as stream: row=next(csv.DictReader(stream))
        self.assertEqual(row['color'],'blue')
        self.assertAlmostEqual(float(row['color_confidence']),.81)

    def test_ethermotion_mode_restart_saves_routing_and_does_not_arm(self):
        self.window.operation_mode.setCurrentIndex(1)
        with patch('app.ui.subprocess.Popen') as launch,patch.object(self.window,'close'):
            self.window.apply_operation_mode()
        launch.assert_called_once()
        saved=json.loads((self.root/'data'/'settings.json').read_text())
        self.assertFalse(saved['visual_only'])
        self.assertEqual(saved['yolox_mode'],'two_models')
        self.assertEqual(saved['rule'],'color')
        self.assertFalse(self.window.armed)
        self.assertFalse(self.window.send_gate.is_set())

    def test_mode_cannot_restart_while_tracking_or_motion_is_active(self):
        self.window.operation_mode.setCurrentIndex(1)
        for state in ('running','armed','arming','owns_motion'):
            setattr(self.window,state,True)
            with patch('app.ui.subprocess.Popen') as launch:
                self.window.apply_operation_mode()
            launch.assert_not_called()
            setattr(self.window,state,False)


if __name__=='__main__': unittest.main()
