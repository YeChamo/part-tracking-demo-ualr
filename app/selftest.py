"""Exercise the packaged native runtimes without opening cameras or motor APIs."""
from __future__ import annotations

import json
import time
from pathlib import Path


def check_runtime(root: Path) -> int:
    report = {'ok': False, 'camera_opened': False, 'motion_requested': False, 'checks': {}}
    checks = report['checks']
    try:
        import cv2
        import numpy as np
        import pypylon.pylon
        from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork
        from .barcode_fixture import demo_barcode, ean13_bgr
        from .vision import barcode_status, decode_barcodes
        from .vendor.inference import Detector, DetectorConfig
        checks['native_imports'] = True
        from .cameras import discover_cameras
        checks['camera_names'] = [camera.name for camera in discover_cameras()]
        available, decoder = barcode_status()
        checks['barcode_decoder'] = decoder
        code = demo_barcode(123)
        decoded = decode_barcodes(ean13_bgr(code))
        checks['ean13_decoded'] = available and any(item['text'] == code for item in decoded)
        if not checks['ean13_decoded']:
            raise RuntimeError('Bundled decoder did not read the generated EAN-13.')
        checks['bundled_models'] = {}
        started = time.monotonic()
        for filename in ('yolox_nano.onnx','yolox_s.onnx'):
            cfg = DetectorConfig(model_path=str(root / 'models' / filename),
                                 class_names=[str(i) for i in range(80)], img_size=640,
                                 conf=.25, device='cpu', intra_op_threads=2)
            with Detector(cfg) as detector:
                result = detector.infer(np.zeros((480, 640, 3), dtype=np.uint8))
                checks['model_backend'] = detector.describe()
                checks['blank_detections'] = len(result.detections)
                checks['bundled_models'][filename] = {'backend':detector.describe(),
                                                      'blank_detections':len(result.detections)}
        checks['model_load_and_infer_ms'] = round((time.monotonic()-started)*1000)
        from .model_classes import build_color_map
        checks['yolox_color_class_map'] = build_color_map(['blue_bottle','yellow_bottle','white_bottle'],class_count=3)
        checks['trained_color_model_required'] = True
        # Synthetic checkpoint exercises the packaged converter, not accuracy.
        import torch
        from .vendor.yolox_models import build_model
        from .checkpoint_export import prepare_model
        checkpoint=root/'data'/'selftest-yolox.pth'
        graph=build_model(2,.33,.125)
        torch.save({'model':graph.state_dict(),'names':['orange','blue'],
                    'test_size':[160,160],
                    'yolox_inference_config':{'schema_version':1,'architecture':'yolox_pafpn',
                        'depth':.33,'width':.125,'depthwise':False,'act':'silu',
                        'normalization':{'type':'batchnorm2d','eps':.001,'momentum':.03}}},checkpoint)
        del graph
        converted=prepare_model(checkpoint,root,image_size=None)
        from .yolox_pipeline import YoloXPipeline
        setup={'yolox_mode':'combined','model_path':str(converted),'pass_color':'orange',
               'auto_model_config':True,'inference_backend':'cpu','rule':'color'}
        pipeline=YoloXPipeline(setup,root)
        try:
            pipeline.open(); converted_result=pipeline.infer(np.zeros((160,160,3),dtype=np.uint8))
            checks['checkpoint_export']={'synthetic_weights':True,'torch':torch.__version__,
                                          'onnx_exported':converted.is_file(),
                                          'pipeline_inference':True}
        finally:
            pipeline.close()
        experiment=root/'data'/'selftest-experiment.py'
        experiment.write_text('from yolox.exp import Exp as BaseExp\n'
                              'class Exp(BaseExp):\n'
                              '    def __init__(self):\n'
                              '        super().__init__()\n'
                              '        self.num_classes=2\n'
                              '        self.depth=.33\n'
                              '        self.width=.125\n'
                              '        self.test_size=(160,160)\n',encoding='utf-8')
        configured=prepare_model(checkpoint,root,image_size=None,experiment_path=str(experiment))
        checks['checkpoint_export']['custom_experiment_exported']=configured.is_file()
        from .tracking import BottleTracker, TrackingConfig
        from .simulation import Simulation, WIDTH, HEIGHT
        from .settings import DEFAULTS
        for direction in ('ltr','rtl'):
            settings = {**DEFAULTS, 'direction':direction}
            sim, tracker = Simulation(), BottleTracker(TrackingConfig(direction=direction))
            decisions = []
            for step in range(900):
                boxes,reasons = sim.update(1/30,settings)
                _,out = tracker.update(boxes,reasons,1+step/30,WIDTH,HEIGHT)
                decisions.extend(out)
            if len(decisions)<10 or len({d.id for d in decisions})!=len(decisions):
                raise RuntimeError('Conveyor tracker failed '+direction)
            checks['simulation_'+direction] = {'bottles':len(decisions),'pass':sum(not d.bad for d in decisions),'divert':sum(d.bad for d in decisions)}
        report['ok'] = True
    except Exception as exc:
        report['error'] = str(exc)
    (root / 'data' / 'runtime-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['ok'] else 1
