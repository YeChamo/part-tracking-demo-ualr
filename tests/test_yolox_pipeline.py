"""Model-level tests: no cameras, live motion, or inferred pixel colors."""
import tempfile
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.vendor.inference import Detection, InferenceResult
from app.yolox_pipeline import YoloXPipeline, _ModelBackend, _class_count


def detection(box=(10, 10, 100, 200), color_id=0, score=0.9, label="orange_bottle"):
    return Detection(box, score, color_id, label)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.models = {}
        self.opened = []
        self.seen = []
        owner = self

        class Backend:
            def __init__(self):
                self.cfg = None
                self.spec = None

            def open(self, cfg):
                self.cfg = cfg
                self.spec = owner.models[Path(cfg.model_path).name]
                owner.opened.append(self)

            def close(self):
                self.cfg = None

            def model_details(self):
                return self.spec["details"]

        class FakeDetector:
            def __init__(self, cfg, *, backend):
                self.cfg, self.backend = cfg, backend
                self._cfg = cfg

            def open(self):
                self.backend.open(self.cfg)

            def close(self):
                self.backend.close()

            def infer(self, frame):
                owner.seen.append((Path(self.cfg.model_path).name, frame))
                return InferenceResult(detections=self.backend.spec["detections"], inference_ms=3.5)

        self.backend_patch = patch("app.yolox_pipeline._ModelBackend", Backend)
        self.detector_patch = patch("app.yolox_pipeline.Detector", FakeDetector)
        self.backend_patch.start()
        self.detector_patch.start()
        self.addCleanup(self.backend_patch.stop)
        self.addCleanup(self.detector_patch.stop)
        self.settings = {"yolox_mode": "combined", "model_path": "colors.onnx", "image_size": 640,
                         "confidence": .25, "pass_color": "orange", "rule": "color"}
        self.model("colors.onnx", names=["orange_bottle", "blue_bottle", "other"])

    def model(self, name, *, names=None, count=None, detections=None, input_shape=None, output_shape=None):
        (self.root / name).parent.mkdir(parents=True, exist_ok=True)
        (self.root / name).touch()
        count = count or len(names or [])
        self.models[Path(name).name] = {
            "details": {"metadata": {"names": str(names)} if names is not None else {},
                        "input_shape": input_shape or [1, 3, 640, 640],
                        "output_shape": output_shape or [1, 8400, 5 + count]},
            "detections": detections or [],
        }

    def pipeline(self, **settings):
        pipe = YoloXPipeline(dict(self.settings, **settings), self.root)
        self.addCleanup(pipe.close)
        return pipe.open()

    def test_combined_uses_model_classes_for_mixed_bottles_and_pixels_do_not_change_decision(self):
        self.models["colors.onnx"]["detections"] = [detection(), detection((120, 10, 210, 200), 1, .8, "blue_bottle")]
        pipe = self.pipeline()
        black = np.zeros((240, 320, 3), dtype=np.uint8)
        white = np.full_like(black, 255)
        result = pipe.infer(black)
        self.assertEqual(result["colors"], ["orange", "blue"])
        self.assertEqual(result["color_confidences"], [.9, .8])
        self.assertEqual(result["reasons"], [[], ["YOLOX color blue (divert)"]])
        self.assertEqual(result, pipe.infer(white))
        self.assertIs(self.seen[0][1], black)

    def test_combined_white_prediction_is_distinct_from_clear_and_comes_from_model(self):
        self.model("colors.onnx", names=["white_bottle", "clear_bottle"], detections=[
            detection(color_id=0, label="white_bottle"),
            detection((120, 10, 210, 200), 1, .85, "clear_bottle"),
        ])
        pipe = self.pipeline(pass_color="white")
        black = np.zeros((240, 320, 3), dtype=np.uint8)
        result = pipe.infer(black)
        self.assertEqual(result["colors"], ["white", "clear"])
        self.assertEqual(result["reasons"], [[], ["YOLOX color clear (divert)"]])
        self.assertEqual(result["model_labels"], ["white_bottle", "clear_bottle"])
        self.assertEqual(result, pipe.infer(np.full_like(black, 255)))

    def test_combined_class_agnostic_duplicates_are_one_bottle(self):
        self.models["colors.onnx"]["detections"] = [detection(), detection((12, 12, 101, 202), 0, .8)]
        result = self.pipeline().infer(np.zeros((1, 1, 3)))
        self.assertEqual(len(result["boxes"]), 1)
        self.assertEqual(result["colors"], ["orange"])

    def test_combined_close_confidence_conflict_cannot_pass(self):
        self.models["colors.onnx"]["detections"] = [detection(), detection((12, 12, 101, 202), 1, .84, "blue_bottle")]
        result = self.pipeline().infer(np.zeros((1, 1, 3)))
        self.assertEqual(result["colors"], ["unknown"])
        self.assertEqual(result["reasons"], [["Unknown color"]])
        self.assertEqual(result["color_confidences"], [0])

    def test_combined_low_confidence_duplicate_does_not_override_clear_prediction(self):
        self.models["colors.onnx"]["detections"] = [detection(), detection(color_id=1, score=.35)]
        self.assertEqual(self.pipeline().infer(np.zeros((1, 1, 3)))["colors"], ["orange"])

    def test_unmapped_model_class_never_passes(self):
        self.models["colors.onnx"]["detections"] = [detection(color_id=2, label="other")]
        result = self.pipeline().infer(np.zeros((1, 1, 3)))
        self.assertEqual(result["colors"], ["unknown"])
        self.assertEqual(result["reasons"], [["Unknown color"]])

    def test_below_confidence_predictions_are_not_colors(self):
        pipe = self.two_models(colors=[detection(score=.24)])
        self.assertEqual(pipe.infer(np.zeros((1, 1, 3)))["colors"], ["unknown"])

    def test_no_detections_returns_parallel_empty_lists(self):
        result = self.pipeline().infer(np.zeros((1, 1, 3)))
        self.assertEqual(result, {"boxes": [], "colors": [], "color_confidences": [], "reasons": [],
                                  "inference_ms": 3.5, "model_labels": []})

    def test_explicit_csv_class_names_work_without_metadata(self):
        self.model("colors.onnx", count=2, detections=[detection(color_id=1)])
        result = self.pipeline(model_class_names="orange_bottle,blue_bottle").infer(np.zeros((1, 1, 3)))
        self.assertEqual(result["colors"], ["blue"])

    def test_explicit_color_map_supports_arbitrary_trained_labels(self):
        self.model("colors.onnx", names=["flavor_A", "flavor_B"], detections=[detection(color_id=1)])
        result = self.pipeline(color_class_map="0:orange,1:blue").infer(np.zeros((1, 1, 3)))
        self.assertEqual(result["colors"], ["blue"])

    def test_label_count_must_match_actual_output(self):
        with self.assertRaisesRegex(ValueError, "has 3 classes"):
            self.pipeline(model_class_names="orange,blue")
        self.assertTrue(self.opened)
        self.assertTrue(all(backend.cfg is None for backend in self.opened))

    def test_out_of_range_class_map_rejected(self):
        with self.assertRaisesRegex(ValueError, "below the model"):
            self.pipeline(color_class_map="0:orange,3:blue")

    def test_missing_class_configuration_rejected(self):
        self.model("colors.onnx", count=3)
        with self.assertRaisesRegex(ValueError, "at least two bottle colors"):
            self.pipeline()

    def test_pass_color_must_be_in_trained_classes(self):
        with self.assertRaisesRegex(ValueError, "pass color"):
            self.pipeline(pass_color="green")

    def test_bundled_stock_models_cannot_be_relabelled_as_color_without_metadata(self):
        for name in ("yolox_nano.onnx", "yolox_s.onnx"):
            self.model("models/" + name, count=80)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "generic bottles"):
                self.pipeline(model_path="models/" + name, color_class_map="0:orange,1:blue")
        self.assertEqual(self.opened, [])

    def test_bundled_s_cannot_be_made_a_color_model_with_explicit_class_names(self):
        self.model("models/yolox_s.onnx", count=80)
        names = ["white_bottle", "clear_bottle"] + [f"class_{index}" for index in range(2, 80)]
        with self.assertRaisesRegex(ValueError, "generic bottles"):
            self.pipeline(model_path="models/yolox_s.onnx", model_class_names=names, pass_color="white")
        self.assertEqual(self.opened, [])

    def test_bundled_s_cannot_be_the_separate_color_model(self):
        self.model("models/yolox_s.onnx", count=80)
        with self.assertRaisesRegex(ValueError, "generic bottles"):
            self.pipeline(yolox_mode="two_models", color_model_path="models/yolox_s.onnx",
                          color_class_map="0:white,1:clear", pass_color="white")
        self.assertEqual(self.opened, [])

    def test_stock_coco_metadata_rejected_when_file_renamed(self):
        names = ["person", "bottle"] + [f"other_{i}" for i in range(78)]
        self.model("colors.onnx", names=names)
        with self.assertRaisesRegex(ValueError, "COCO"):
            self.pipeline(color_class_map="0:orange,1:blue")

    def test_wrong_input_size_rejected_before_infer(self):
        self.models["colors.onnx"]["details"]["input_shape"] = [1, 3, 416, 416]
        with self.assertRaisesRegex(ValueError, "input"):
            self.pipeline()
        self.assertEqual(self.seen, [])

    def test_transposed_or_dynamic_class_output_rejected(self):
        for shape in ([1, 7, "anchors"], [1, 10, 4], [1, 10, "channels"], [10, 7]):
            with self.subTest(shape=shape):
                self.models["colors.onnx"]["details"]["output_shape"] = shape
                with self.assertRaisesRegex(ValueError, "5.C"):
                    self.pipeline()

    def two_models(self, *, bottles=None, colors=None, **settings):
        self.model("bottles.onnx", count=80, detections=bottles or [detection(color_id=39, label="bottle")])
        self.model("colors.onnx", names=["orange", "blue", "other"], detections=colors)
        return self.pipeline(yolox_mode="two_models", model_path="bottles.onnx", color_model_path="colors.onnx", **settings)

    def test_two_models_use_full_frame_and_unique_color_association(self):
        first = detection(color_id=39, label="bottle")
        second = detection((120, 10, 210, 200), 39, .9, "bottle")
        pipe = self.two_models(bottles=[first, second], colors=[detection((20, 60, 80, 100)), detection((130, 60, 190, 100), 1, .7, "blue")])
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        result = pipe.infer(frame)
        self.assertEqual(result["colors"], ["orange", "blue"])
        self.assertEqual(result["inference_ms"], 7)
        self.assertTrue(all(item[1] is frame for item in self.seen))

    def test_bundled_s_is_allowed_as_bottle_locator_with_trained_white_color_model(self):
        self.model("models/yolox_s.onnx", count=80, detections=[
            detection(color_id=39, label="bottle"),
            detection((120, 10, 210, 200), 0, .95, "person"),
        ])
        self.model("colors.onnx", names=["white", "clear"], detections=[
            detection((20, 60, 80, 100), 0, .9, "white"),
        ])
        pipe = self.pipeline(yolox_mode="two_models", model_path="models/yolox_s.onnx",
                             color_model_path="colors.onnx", pass_color="white")
        result = pipe.infer(np.zeros((240, 320, 3), dtype=np.uint8))
        self.assertEqual(len(result["boxes"]), 1)
        self.assertEqual(result["colors"], ["white"])
        self.assertEqual(result["reasons"], [[]])
        self.assertEqual(result["model_labels"], ["white"])

    def test_two_models_preserve_white_and_clear_color_predictions(self):
        self.model("bottles.onnx", count=80, detections=[
            detection(color_id=39, label="bottle"),
            detection((120, 10, 210, 200), 39, .9, "bottle"),
        ])
        self.model("colors.onnx", names=["white", "clear"], detections=[
            detection((20, 60, 80, 100), 0, .9, "white"),
            detection((130, 60, 190, 100), 1, .85, "clear"),
        ])
        pipe = self.pipeline(yolox_mode="two_models", model_path="bottles.onnx",
                             color_model_path="colors.onnx", pass_color="white")
        result = pipe.infer(np.zeros((240, 320, 3), dtype=np.uint8))
        self.assertEqual(result["colors"], ["white", "clear"])
        self.assertEqual(result["reasons"], [[], ["YOLOX color clear (divert)"]])

    def test_color_with_no_owner_does_not_assign_to_nearest_bottle(self):
        pipe = self.two_models(colors=[detection((150, 70, 180, 100))])
        self.assertEqual(pipe.infer(np.zeros((1, 1, 3)))["reasons"], [["Unknown color"]])

    def test_color_shared_between_overlapping_bottles_is_unknown_for_both(self):
        pipe = self.two_models(bottles=[detection((0, 0, 100, 100), 39), detection((60, 0, 160, 100), 39)],
                               colors=[detection((65, 30, 85, 50))])
        result = pipe.infer(np.zeros((1, 1, 3)))
        self.assertEqual(result["colors"], ["unknown", "unknown"])

    def test_two_models_conflicting_high_confidence_colors_unknown(self):
        pipe = self.two_models(colors=[detection((20, 70, 80, 110)), detection((25, 70, 85, 110), 1, .6, "blue")])
        self.assertEqual(pipe.infer(np.zeros((1, 1, 3)))["colors"], ["unknown"])

    def test_two_models_unmapped_high_confidence_class_blocks_pass(self):
        pipe = self.two_models(colors=[detection((20, 70, 80, 110)), detection((25, 70, 85, 110), 2, .8, "other")])
        self.assertEqual(pipe.infer(np.zeros((1, 1, 3)))["colors"], ["unknown"])

    def test_two_models_bottle_class_filter_and_all_classes(self):
        pipe = self.two_models(bottles=[detection(color_id=2)], colors=[detection()])
        self.assertEqual(pipe.infer(np.zeros((1, 1, 3)))["boxes"], [])
        pipe = self.two_models(bottles=[detection(color_id=2)], colors=[detection()], model_class_id=-1)
        self.assertEqual(pipe.infer(np.zeros((1, 1, 3)))["colors"], ["orange"])

    def test_missing_color_model_fails_before_loading_or_inference(self):
        with self.assertRaisesRegex(ValueError, "color model"):
            self.pipeline(yolox_mode="two_models", color_model_path="")
        self.assertEqual(self.opened, [])
        self.assertEqual(self.seen, [])

    def test_invalid_locator_class_closes_both_models(self):
        with self.assertRaisesRegex(ValueError, "locator class"):
            self.two_models(model_class_id=80)
        self.assertTrue(all(backend.cfg is None for backend in self.opened))

    def test_close_disallows_further_inference(self):
        pipe = self.pipeline()
        self.assertIn("YOLOX", pipe.describe())
        pipe.close()
        self.assertIn("closed", pipe.describe())
        with self.assertRaisesRegex(RuntimeError, "Open"):
            pipe.infer(np.zeros((1, 1, 3)))

    def test_combined_confidence_adjustments_keep_boxes_but_require_color_confidence(self):
        self.models["colors.onnx"]["detections"] = [detection(score=.6)]
        pipe = self.pipeline()
        frame = np.zeros((1, 1, 3))
        model, opened_count = pipe._parts.detector, len(self.opened)
        self.assertEqual(pipe.infer(frame)["colors"], ["orange"])
        pipe.set_confidence(.3, .7)
        result = pipe.infer(frame)
        self.assertEqual(len(result["boxes"]), 1)
        self.assertEqual(result["colors"], ["unknown"])
        self.assertEqual(result["reasons"], [["Unknown color"]])
        self.assertEqual(pipe._parts.confidence, .3)
        self.assertEqual(model._cfg.conf, .3)
        pipe.set_confidence(.3, .5)
        self.assertEqual(pipe.infer(frame)["colors"], ["orange"])
        pipe.set_confidence(.7, .5)
        self.assertEqual(pipe.infer(frame)["boxes"], [])
        self.assertIs(pipe._parts.detector, model)
        self.assertEqual(len(self.opened), opened_count)

    def test_combined_color_threshold_applies_to_conflicting_candidates(self):
        self.models["colors.onnx"]["detections"] = [detection(score=.9), detection(color_id=1, score=.84, label="blue")]
        pipe = self.pipeline()
        frame = np.zeros((1, 1, 3))
        self.assertEqual(pipe.infer(frame)["colors"], ["unknown"])
        pipe.set_confidence(.25, .88)
        self.assertEqual(pipe.infer(frame)["colors"], ["orange"])

    def test_two_model_live_confidence_changes_update_both_detectors_without_reopen(self):
        pipe = self.two_models(bottles=[detection(color_id=39, score=.65)], colors=[detection(score=.6)])
        frame = np.zeros((1, 1, 3))
        locator, color_model, opened_count = pipe._parts.detector, pipe._color.detector, len(self.opened)
        self.assertEqual(pipe.infer(frame)["colors"], ["orange"])
        pipe.set_confidence(.3, .7)
        result = pipe.infer(frame)
        self.assertEqual(len(result["boxes"]), 1)
        self.assertEqual(result["colors"], ["unknown"])
        self.assertEqual(locator._cfg.conf, .3)
        self.assertEqual(color_model._cfg.conf, .7)
        self.assertEqual(pipe._color.confidence, .7)
        pipe.set_confidence(.3, .5)
        self.assertEqual(pipe.infer(frame)["colors"], ["orange"])
        pipe.set_confidence(.7, .5)
        self.assertEqual(pipe.infer(frame)["boxes"], [])
        self.assertIs(pipe._parts.detector, locator)
        self.assertIs(pipe._color.detector, color_model)
        self.assertEqual(len(self.opened), opened_count)

    def test_invalid_confidence_changes_are_atomic(self):
        pipe = self.two_models(colors=[detection()])
        for invalid in (0, -0.1, 1.1, float("nan"), float("inf"), None, "invalid"):
            for bottle, color in ((invalid, .8), (.8, invalid)):
                with self.subTest(bottle=bottle, color=color):
                    with self.assertRaisesRegex(ValueError, "confidence"):
                        pipe.set_confidence(bottle, color)
                    self.assertEqual(pipe.settings["confidence"], .25)
                    self.assertEqual(pipe.settings["color_confidence"], .5)
                    self.assertEqual(pipe._parts.confidence, .25)
                    self.assertEqual(pipe._color.confidence, .5)
                    self.assertEqual(pipe._parts.detector._cfg.conf, .25)
                    self.assertEqual(pipe._color.detector._cfg.conf, .5)

    def test_confidence_can_be_set_before_open_and_default_color_is_point_five(self):
        self.models["colors.onnx"]["detections"] = [detection(score=.49)]
        self.assertEqual(self.pipeline().infer(np.zeros((1, 1, 3)))["colors"], ["unknown"])
        pipe = YoloXPipeline(self.settings, self.root)
        self.addCleanup(pipe.close)
        pipe.set_confidence(.2, .4)
        pipe.open()
        self.assertEqual(pipe.infer(np.zeros((1, 1, 3)))["colors"], ["orange"])
        self.assertEqual(pipe._parts.detector._cfg.conf, .2)


@unittest.skipUnless(importlib.util.find_spec("onnxruntime"), "ONNX Runtime is optional for unit tests")
class BundledModelTests(unittest.TestCase):
    def test_real_cpu_model_symbolic_output_is_measured_and_generic_color_is_rejected(self):
        from app.vendor.inference import DetectorConfig

        root = Path(__file__).resolve().parents[1]
        model = root / "models" / "yolox_nano.onnx"
        if not model.is_file():
            self.skipTest("Bundled model is not in this checkout")
        backend = _ModelBackend()
        try:
            backend.open(DetectorConfig(model_path=str(model), device="cpu", intra_op_threads=2, inter_op_threads=1))
            details = backend.model_details()
            self.assertEqual(_class_count(details, 640), 80)
            self.assertEqual(details["output_shape"], [1, 8400, 85])
        finally:
            backend.close()
        pipeline = YoloXPipeline({"yolox_mode": "combined", "color_class_map": "0:orange,1:blue"}, root)
        with self.assertRaisesRegex(ValueError, "generic bottles"):
            pipeline.open()

    def test_real_s_cpu_model_opens_as_eighty_class_bottle_locator(self):
        from app.vendor.inference import DetectorConfig

        root = Path(__file__).resolve().parents[1]
        model = root / "models" / "yolox_s.onnx"
        if not model.is_file():
            self.skipTest("Bundled YOLOX-S model is not in this checkout")
        backend = _ModelBackend()
        try:
            backend.open(DetectorConfig(model_path=str(model), device="cpu", intra_op_threads=2, inter_op_threads=1))
            details = backend.model_details()
            self.assertEqual(_class_count(details, 640), 80)
            self.assertEqual(details["output_shape"], [1, 8400, 85])
        finally:
            backend.close()
        pipeline = YoloXPipeline({"yolox_mode": "combined", "model_path": str(model),
                                 "color_class_map": "0:white,1:clear", "pass_color": "white"}, root)
        with self.assertRaisesRegex(ValueError, "generic bottles"):
            pipeline.open()


if __name__ == "__main__":
    unittest.main()
