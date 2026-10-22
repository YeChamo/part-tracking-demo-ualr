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
