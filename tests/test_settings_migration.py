import json
from pathlib import Path
import tempfile
import unittest

from app.settings import DEFAULTS, load


class SettingsMigrationTests(unittest.TestCase):
    def configured(self, saved):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'data').mkdir()
            (root/'data'/'settings.json').write_text(json.dumps(saved))
            return load(root)

    def test_old_bottle_only_demo_gets_bundled_color_model_without_changing_camera(self):
        result=self.configured({'color_model_path':'','camera_id':'physical-usb','color_confidence':.9})
        self.assertEqual(result['color_model_path'],DEFAULTS['color_model_path'])
        self.assertEqual(result['color_backend'],'classifier')
        self.assertEqual(result['color_confidence'],.5)
        self.assertEqual(result['camera_id'],'physical-usb')

    def test_previous_custom_yolox_color_weights_keep_detector_backend(self):
        result=self.configured({'color_model_path':'trained-bottles.pth'})
        self.assertEqual(result['color_model_path'],'trained-bottles.pth')
        self.assertEqual(result['color_backend'],'yolox')

    def test_explicitly_cleared_new_color_selection_stays_cleared(self):
        result=self.configured({'color_model_path':'','color_backend':'classifier'})
        self.assertEqual(result['color_model_path'],'')
