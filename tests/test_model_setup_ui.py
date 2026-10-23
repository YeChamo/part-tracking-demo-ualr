"""Model selection and preparation gates, without opening a real camera."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from app.ui import MainWindow


class Signal:
    def __init__(self): self.callbacks=[]
    def connect(self,callback): self.callbacks.append(callback)
    def emit(self,*args):
        for callback in self.callbacks: callback(*args)


class Preparation:
    def __init__(self,settings,root,parent):
        self.settings=dict(settings); self.active=False; self.stopped=False
        self.progress=Signal(); self.prepared=Signal(); self.fault=Signal(); self.finished=Signal()
    def start(self): self.active=True
    def isRunning(self): return self.active
    def stop(self): self.stopped=True; self.active=False


class Camera:
    def __init__(self,preparing,source_started=None):
        self.preparing_models=preparing; self.source_started_at=source_started; self.stopped=False
    def take_latest(self): return None
    def stop(self): self.stopped=True
    def isRunning(self): return False


class ModelSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        (self.root/'data').mkdir()
        (self.root/'data'/'settings.json').write_text('{"visual_only":false,"yolox_mode":"two_models","rule":"color"}',encoding='utf-8')
        with patch('app.ui.QTimer.singleShot'): self.window=MainWindow(self.root,smoke_test=True)
        self.window.timer.stop(); self.window.jobs.pool.shutdown(wait=True,cancel_futures=True)
        self.window.jobs=Mock()
    def tearDown(self):
        self.window.owns_motion=False; self.window.worker=None; self.window.model_preparer=None
        self.window.close(); self.temp.cleanup()
    def test_checkpoint_picker_and_independent_custom_experiments(self):
        with patch('app.ui.QFileDialog.getOpenFileName',return_value=('D:/weights/bottles.pth','')) as dialog:
            self.window.path_buttons['model_path'].click()
        self.assertEqual(self.window.fields['model_path'].text(),'D:/weights/bottles.pth')
        self.assertIn('*.pth',dialog.call_args.args[-1])
        self.assertIn('*.onnx',dialog.call_args.args[-1])
        self.assertIn('model_experiment_path',self.window.fields)
        self.assertIn('color_experiment_path',self.window.fields)
        self.assertTrue(self.window.fields['auto_model_config'].isChecked())
    def test_prepare_reads_classes_without_silently_changing_pass_target(self):
        target=self.window.fields['pass_color'].currentText().casefold()
        with patch('app.ui.ModelPreparationWorker',Preparation): self.window.prepare_models()
        worker=self.window.model_preparer
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.path_buttons['model_path'].isEnabled())
        worker.prepared.emit({'colors':['pink','fruit punch'],'models':[]})
        combo=self.window.fields['pass_color']
        self.assertEqual(combo.currentText(),target)
        self.assertEqual([combo.itemText(i) for i in range(combo.count())],['pink','fruit punch'])
        combo.setCurrentText('Fruit Punch')
        worker.active=False; worker.finished.emit()
        self.window.collect_settings()
        self.assertEqual(self.window.settings['pass_color'],'fruit punch')
        self.assertTrue(self.window.start_button.isEnabled())
    def test_stop_cancels_preparation_and_cannot_arm_output(self):
        with patch('app.ui.ModelPreparationWorker',Preparation): self.window.prepare_models()
        worker=self.window.model_preparer
        self.window.stop()
        self.assertTrue(worker.stopped)
        self.assertFalse(self.window.armed)
        self.assertFalse(self.window.send_gate.is_set())
    def test_conversion_is_not_mistaken_for_a_camera_timeout(self):
        self.window.settings['source']='usb'; self.window.running=True
        self.window.started_at=time.monotonic()-25
        self.window.worker=Camera(True)
        self.window.tick()
        self.assertTrue(self.window.running)
        self.window.worker.preparing_models=False
        self.window.worker.source_started_at=time.monotonic()
        self.window.tick()
        self.assertTrue(self.window.running)
        self.window.worker.source_started_at=time.monotonic()-16
        with self.assertLogs(level='ERROR'): self.window.tick()
        self.assertFalse(self.window.running)
        self.assertTrue(self.window.worker.stopped)


if __name__=='__main__': unittest.main()
