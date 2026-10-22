"""Cap verdicts and real label reading stay evidence-based."""
from __future__ import annotations

from pathlib import Path
import unittest

import cv2
import numpy as np
from types import SimpleNamespace

from app.inspections import LabelReader, has_gatorade_text, inspect_orange_cap
from app.gatorade_pipeline import GatoradePipeline
from app.settings import DEFAULTS


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT.parent / 'examples'


class CapInspectionTests(unittest.TestCase):
    def test_visible_orange_cap_and_missing_cap(self):
        frame = np.full((320, 200, 3), 180, np.uint8)
        box = (40, 30, 160, 300)
        frame[30:60,55:145] = (25, 135, 240)
        self.assertEqual(inspect_orange_cap(frame,box)['status'],'present')
        frame[30:60,55:145] = (180, 180, 180)
        self.assertEqual(inspect_orange_cap(frame,box)['status'],'missing')
        self.assertEqual(inspect_orange_cap(frame,(40,0,160,300))['status'],'unknown')

    def test_thin_tamper_band_does_not_count_as_cap(self):
        frame = np.full((480,640,3),180,np.uint8)
        box = (29,168,135,450)
        frame[189:198,50:116] = (25,135,240)
        self.assertEqual(inspect_orange_cap(frame,box)['status'],'missing')

    def test_warm_background_through_open_neck_does_not_count_as_cap(self):
        frame = np.full((480,640,3),180,np.uint8)
        box = (50,50,190,430)
        amber = cv2.cvtColor(np.uint8([[[19,125,150]]]),cv2.COLOR_HSV2BGR)[0,0]
        frame[50:118,71:169] = amber
        ring = cv2.cvtColor(np.uint8([[[10,180,180]]]),cv2.COLOR_HSV2BGR)[0,0]
        frame[110:120,71:169] = ring
        self.assertEqual(inspect_orange_cap(frame,box)['status'],'missing')

    @unittest.skipUnless((ROOT/'data'/'live-uncapped-2026-10-22.jpg').is_file(),
                         'live uncapped sample is local workstation data')
    def test_live_uncapped_sample_with_orange_tamper_band(self):
        frame = cv2.imread(str(ROOT/'data'/'live-uncapped-2026-10-22.jpg'))
        pipeline = GatoradePipeline({**DEFAULTS,'label_ocr':False},ROOT).open()
        try:
            result = pipeline.infer(frame)
            self.assertEqual(result['colors'],['yellow'])
            self.assertEqual(result['caps'][0]['status'],'missing')
        finally:
            pipeline.close()

    @unittest.skipUnless((ROOT/'data'/'live-uncapped-1280.jpg').is_file(),
                         'higher-resolution camera sample is local workstation data')
    def test_high_resolution_uncapped_sample_retains_yellow_color(self):
        frame = cv2.imread(str(ROOT/'data'/'live-uncapped-1280.jpg'))
        pipeline = GatoradePipeline({**DEFAULTS,'label_ocr':False},ROOT).open()
        try:
            result = pipeline.infer(frame)
            self.assertEqual(result['colors'],['yellow'])
            self.assertEqual(result['caps'][0]['status'],'missing')
        finally:
            pipeline.close()

    def test_missing_cap_is_informational_even_with_stale_setting(self):
        frame = np.full((320,200,3),180,np.uint8)
        box = (40,30,160,300)
        detection = SimpleNamespace(xyxy=box,class_id=39,label='bottle',score=.9)
        model = SimpleNamespace(infer=lambda _frame: SimpleNamespace(
            detections=[detection],inference_ms=1.0))
        for enabled in (False,True):
            pipeline = GatoradePipeline({**DEFAULTS,'pass_color':'white',
                                         'cap_reject':enabled,'label_ocr':False},ROOT)
            pipeline.detector = model
            result = pipeline.infer(frame)
            self.assertEqual(result['caps'][0]['status'],'missing')
            self.assertEqual(result['reasons'][0],[])

    @unittest.skipUnless(EXAMPLES.is_dir(), 'supplied examples are outside this checkout')
    def test_visible_caps_in_supplied_bottles(self):
        pipeline = GatoradePipeline({**DEFAULTS,'gatorade_label_check':False,'label_ocr':False},ROOT).open()
        try:
            found = {'present':0,'unknown':0,'missing':0}
            for path in sorted(EXAMPLES.glob('*.jpg')):
                frame = cv2.imread(str(path))
                result = pipeline.infer(frame)
                self.assertTrue(result['caps'],path.name)
                found[result['caps'][0]['status']] += 1
            self.assertEqual(found['present'],8)
            self.assertEqual(found['unknown'],5)  # cap is clipped at frame edge
            self.assertEqual(found['missing'],0)
        finally:
            pipeline.close()


class LabelReadingTests(unittest.TestCase):
    @unittest.skipUnless((EXAMPLES/'WIN_20261022_11_04_03_Pro.jpg').is_file(),
                         'supplied examples are outside this checkout')
    def test_ocr_reads_gatorade_and_flavor_from_actual_bottle(self):
        frame = cv2.imread(str(EXAMPLES/'WIN_20261022_11_04_03_Pro.jpg'))
        crop = frame[615:1760,175:675]
        lines = LabelReader().read(crop)
        self.assertTrue(has_gatorade_text(lines))
        self.assertTrue(any('FROST' in item['text'].upper() for item in lines))


if __name__ == '__main__':
    unittest.main()
