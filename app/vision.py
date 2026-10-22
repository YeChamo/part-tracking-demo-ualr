"""Single-camera bottle vision for the portable UALR conveyor demonstration.

The bundled COCO model locates generic bottles. Color checks sample exposed
liquid below the label. Barcodes are decoded from actual camera pixels only.
Camera reads and inference stay on one worker. The GUI polls a one-frame mailbox
so slow painting never queues old conveyor images.
"""
from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from .vendor.inference import Detector, DetectorConfig


REFERENCE_VERSION = 1
REFERENCE_REQUIRED = "Teach a good bottle before cap / label inspection."
PASS_COLORS = ("orange", "yellow", "green", "blue", "red", "purple", "clear", "taught")


def _liquid_features(frame: np.ndarray, bbox: Sequence[float], settings: dict | None = None) -> dict:
    settings = settings or {}
    crop = _bottle_crop(frame, bbox)
    y1 = float(settings.get("color_y1", 0.78))
    y2 = float(settings.get("color_y2", 0.94))
    if not (0.0 <= y1 < y2 <= 1.0) or y2 - y1 < 0.025:
        raise ValueError("Liquid sample must be a valid bottle-height interval.")
    zone = crop[int(256 * y1):max(int(256 * y1) + 1, int(256 * y2)), 19:109]
    hsv = cv2.cvtColor(zone, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(float)
    minimum_sat = float(settings.get("color_saturation_min", 0.20)) * 255.0
    lit = hsv[:, 2] >= 38.0
    saturated = lit & (hsv[:, 1] >= minimum_sat)
    fraction = float(saturated.mean())
    if fraction < 0.08:
        neutral = lit & (hsv[:, 1] < minimum_sat)
        clear_confidence = float(neutral.mean())
        return {"name": "clear" if clear_confidence >= 0.65 else "unknown",
                "confidence": clear_confidence, "hue": None,
                "saturated_fraction": fraction}
    if fraction < 0.15 or int(saturated.sum()) < 40:
        return {"name": "unknown", "confidence": fraction, "hue": None,
                "saturated_fraction": fraction}
    hues = hsv[saturated, 0]
    # Vote in HSV hue bands, wrapping red across 0/180. Dominance rejects mixed
    # labels/background rather than calling their average an invented liquid color.
    bands = np.select(
        [(hues < 8) | (hues >= 173), hues < 22, hues < 37,
         hues < 90, hues < 129], [0, 1, 2, 3, 4], default=5,
    )
    counts = np.bincount(bands, minlength=6)
    winner = int(counts.argmax())
    dominance = float(counts[winner]) / len(hues)
    winner_hues = hues[bands == winner]
    angles = winner_hues * (2.0 * math.pi / 180.0)
    hue = (math.atan2(float(np.sin(angles).mean()), float(np.cos(angles).mean()))
           * 180.0 / (2.0 * math.pi)) % 180.0
    confidence = dominance * min(1.0, fraction / 0.45)
    name = ("red", "orange", "yellow", "green", "blue", "purple")[winner]
    if dominance < 0.60 or confidence < 0.55:
        name = "unknown"
    return {"name": name, "confidence": confidence, "hue": hue,
            "saturated_fraction": fraction}


def classify_color(frame: np.ndarray, bbox: Sequence[float],
                   settings: dict | None = None) -> tuple[str, float]:
    """Identify liquid color and confidence; ambiguous/underexposed samples are unknown."""
    try:
        result = _liquid_features(frame, bbox, settings)
        return result["name"], float(result["confidence"])
    except (ValueError, TypeError, cv2.error):
        return "unknown", 0.0


def teach_color(frame: np.ndarray, bbox: Sequence[float], settings: dict | None = None) -> dict:
    """Return a JSON-safe liquid hue reference for the optional taught-color choice."""
    result = _liquid_features(frame, bbox, settings)
    if result["name"] == "unknown":
        raise ValueError("Liquid color is ambiguous. Adjust light and the liquid sample zone.")
    return {"version": REFERENCE_VERSION, "kind": "color", **result,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S")}


_barcode_local = threading.local()


def _barcode_backend():
    if hasattr(_barcode_local, "backend"):
        return _barcode_local.backend
    try:
        import zxingcpp
        backend = ("ZXing-C++", zxingcpp, None)
    except ImportError:
        barcode = cv2.barcode_BarcodeDetector() if hasattr(cv2, "barcode_BarcodeDetector") else None
        qr = cv2.QRCodeDetector() if hasattr(cv2, "QRCodeDetector") else None
        backend = ("OpenCV barcode / QR" if barcode is not None else "OpenCV QR only" if qr is not None else "Unavailable", barcode, qr)
    _barcode_local.backend = backend
    return backend


def barcode_status() -> tuple[bool, str]:
    name, decoder, qr = _barcode_backend()
    return decoder is not None or qr is not None, name


def _points_box(points, width: int, height: int) -> tuple[int, int, int, int]:
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    return (max(0, int(points[:, 0].min())), max(0, int(points[:, 1].min())),
            min(width, int(math.ceil(points[:, 0].max()))),
            min(height, int(math.ceil(points[:, 1].max()))))


def decode_barcodes(frame: np.ndarray) -> list[dict]:
    """Read actual symbols. Empty/undecodable symbols never become guessed data."""
    if not isinstance(frame, np.ndarray) or not frame.size:
        return []
    height, width = frame.shape[:2]
    name, decoder, qr = _barcode_backend()
    found = []
    try:
        if name == "ZXing-C++":
            for item in decoder.read_barcodes(frame):
                text = str(item.text)
                if not text or not bool(getattr(item, "valid", True)):
                    continue
                pos = item.position
                points = [(getattr(pos, key).x, getattr(pos, key).y)
                          for key in ("top_left", "top_right", "bottom_right", "bottom_left")]
                found.append({"text": text, "format": str(item.format),
                              "bbox": _points_box(points, width, height)})
            return found
        if decoder is not None:
            ok, texts, formats, points = decoder.detectAndDecodeWithType(frame)
            if ok and points is not None:
                for text, symbol_format, vertices in zip(texts, formats, points):
                    if text:
                        found.append({"text": str(text), "format": str(symbol_format),
                                      "bbox": _points_box(vertices, width, height)})
        if qr is not None:
            ok, texts, points, _ = qr.detectAndDecodeMulti(frame)
            if ok and points is not None:
                for text, vertices in zip(texts, points):
                    if text:
                        found.append({"text": str(text), "format": "QR Code",
                                      "bbox": _points_box(vertices, width, height)})
    except (cv2.error, RuntimeError, ValueError, TypeError):
        # A failed read is represented by no symbol. Never reuse old text here.
        return found
    return found


def _decode_frame_and_crops(frame: np.ndarray, boxes: list) -> list[dict]:
    found = decode_barcodes(frame)
    height, width = frame.shape[:2]
    for box in boxes[:8]:
        x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
        x2, y2 = min(width, int(box[2])), min(height, int(box[3]))
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        crop = frame[y1:y2, x1:x2]
        scale = 2.0 if crop.shape[1] < 500 else 1.0
        if scale > 1:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        for item in decode_barcodes(crop):
            a, b, c, d = item["bbox"]
            adjusted = dict(item, bbox=(x1+int(a/scale), y1+int(b/scale), x1+int(c/scale), y1+int(d/scale)))
            acx, acy = (adjusted["bbox"][0]+adjusted["bbox"][2])/2, (adjusted["bbox"][1]+adjusted["bbox"][3])/2
            if not any(old["text"] == adjusted["text"] and abs((old["bbox"][0]+old["bbox"][2])/2-acx) < 20 and abs((old["bbox"][1]+old["bbox"][3])/2-acy) < 20 for old in found):
                found.append(adjusted)
    return found


def _bottle_crop(frame: np.ndarray, bbox: Sequence[float]) -> np.ndarray:
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected a BGR camera image.")
    if len(bbox) != 4 or not all(math.isfinite(float(v)) for v in bbox):
        raise ValueError("Bottle box must contain four finite coordinates.")
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)
    x1, y1 = max(0, min(w, x1)), max(0, min(h, y1))
    x2, y2 = max(0, min(w, x2)), max(0, min(h, y2))
    if x2 - x1 < 8 or y2 - y1 < 24:
        raise ValueError("Bottle box is too small for cap / label inspection.")
    return cv2.resize(frame[y1:y2, x1:x2], (128, 256), interpolation=cv2.INTER_AREA)


def _descriptor(zone: np.ndarray) -> dict[str, Any]:
    zone = cv2.resize(zone, (64, 64), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(zone, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(zone, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256])
    hist /= max(float(hist.sum()), 1.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    texture = float(np.mean(cv2.magnitude(gx, gy))) / 255.0
    return {
        "hist": hist.reshape(-1).astype(float).tolist(),
        "mean_bgr": (zone.mean(axis=(0, 1)) / 255.0).astype(float).tolist(),
        "texture": texture,
        "contrast": float(gray.std()) / 255.0,
    }


def _features(frame: np.ndarray, bbox: Sequence[float]) -> dict[str, Any]:
    crop = _bottle_crop(frame, bbox)
    # Center strips limit belt/background contamination around tapered bottles.
    return {
        "cap": _descriptor(crop[0:56, 26:102]),
        "label": _descriptor(crop[90:200, 15:113]),
    }


def teach_reference(frame: np.ndarray, bbox: Sequence[float]) -> dict[str, Any]:
    """Return JSON-safe descriptors for one centered, upright, known-good bottle."""
    return {
        "version": REFERENCE_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "description": "Upright bottle cap (top 22%) and label (35%-78%)",
        **_features(frame, bbox),
    }


def _valid_descriptor(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    try:
        hist = np.asarray(value["hist"], dtype=float)
        color = np.asarray(value["mean_bgr"], dtype=float)
        return bool(
            hist.shape == (96,) and color.shape == (3,)
            and np.isfinite(hist).all() and np.isfinite(color).all()
            and (hist >= 0).all() and float(hist.sum()) > 0
            and math.isfinite(float(value["texture"]))
            and math.isfinite(float(value["contrast"]))
        )
    except (KeyError, TypeError, ValueError):
        return False


def inspection_error(settings: dict, reference: dict | None) -> str:
    rule = str(settings.get("rule", "color")).lower()
    if rule not in {"color", "cap_label", "cap", "all", "none", "defect_model"}:
        return "Choose a supported inspection rule."
    if rule == "color":
        target = str(settings.get("pass_color", "orange")).lower()
        if target not in PASS_COLORS:
            return "Choose a pass color."
        if target == "taught":
            try:
                valid = isinstance(reference, dict) and reference.get("kind") == "color" and reference.get("version") == REFERENCE_VERSION
                valid = valid and reference.get("name") in PASS_COLORS
                valid = valid and (reference.get("name") == "clear" or math.isfinite(float(reference["hue"])))
            except (TypeError, ValueError, KeyError):
                valid = False
            if not valid:
                return "Teach a bottle color before using taught color."
        return ""
    if rule not in {"cap_label", "cap"}:
        return ""
    required = ("cap", "label") if rule == "cap_label" else ("cap",)
    if not isinstance(reference, dict) or reference.get("version") != REFERENCE_VERSION:
        return REFERENCE_REQUIRED
    if any(not _valid_descriptor(reference.get(key)) for key in required):
        return "Reference is invalid. Teach a good bottle again."
    return ""


def _distance(current: dict, reference: dict) -> float:
    a = np.asarray(current["hist"], dtype=np.float32)
    b = np.asarray(reference["hist"], dtype=np.float32)
    color_hist = float(cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))
    color_mean = float(np.linalg.norm(
        np.asarray(current["mean_bgr"]) - np.asarray(reference["mean_bgr"])
    )) / math.sqrt(3.0)
    texture_delta = abs(float(current["texture"]) - float(reference["texture"]))
    texture_delta /= max(0.08, float(reference["texture"]), float(current["texture"]))
    contrast_delta = abs(float(current["contrast"]) - float(reference["contrast"]))
    contrast_delta /= max(0.05, float(reference["contrast"]), float(current["contrast"]))
    return min(1.0, 0.60 * color_hist + 0.18 * color_mean
               + 0.14 * texture_delta + 0.08 * contrast_delta)


def classify(frame: np.ndarray, box: Sequence[float], settings: dict,
             reference: dict | None) -> list[str]:
    """Return explicit reject reasons; missing teaching never silently passes."""
    problem = inspection_error(settings, reference)
    if problem:
        return [problem]
    rule = str(settings.get("rule", "color")).lower()
    if rule == "color":
        try:
            measured = _liquid_features(frame, box, settings)
        except (ValueError, TypeError, cv2.error):
            return ["Unknown color"]
        color = measured["name"]
        if color == "unknown":
            return ["Unknown color"]
        target = str(settings.get("pass_color", "orange")).lower()
        if target == "taught":
            if reference["name"] == "clear" or color == "clear":
                matches = reference["name"] == color
            else:
                delta = abs(float(measured["hue"]) - float(reference["hue"]))
                matches = min(delta, 180.0 - delta) <= float(settings.get("color_tolerance_h", 12.0))
        else:
            matches = color == target
        return [] if matches else [f"Color: {color} (divert)"]
    if rule == "all":
        return ["Reject every bottle (demo rule)"]
    if rule in {"none", "defect_model"}:
        return []
    try:
        features = _features(frame, box)
    except ValueError as exc:
        return [str(exc)]
    reasons = []
    if _distance(features["cap"], reference["cap"]) > float(settings.get("cap_threshold", 0.45)):
        reasons.append("Cap differs from taught bottle")
    if rule == "cap_label" and _distance(features["label"], reference["label"]) > float(settings.get("label_threshold", 0.40)):
        reasons.append("Label differs from taught bottle")
    return reasons


def _resolve(root: Path, path: str | Path) -> Path:
    value = Path(path).expanduser()
    return value if value.is_absolute() else root / value


class VideoWorker(QThread):
    """All source/vision work, with a bounded latest-result mailbox.

    ``packet`` exists for API compatibility but is deliberately never emitted.
    Poll ``take_latest()`` from a GUI timer. ``ready`` means source open, while
    each packet's ``inspection_ready`` says whether decisions are permitted.
    ``stop()`` requests termination; callers must retain this worker until its
    QThread finishes and refuse another source if the driver has not returned.
    """
    packet = Signal(object)
    fault = Signal(str)
    ready = Signal(str)

    def __init__(self, settings: dict, root: Path):
        super().__init__()
        self.settings = dict(settings)
        self.root = Path(root)
        self._stop_event = threading.Event()
        self._latest_lock = threading.Lock()
        self._latest: dict | None = None

    def take_latest(self) -> dict | None:
        with self._latest_lock:
            value, self._latest = self._latest, None
        return value

    def stop(self) -> None:
        self._stop_event.set()
        self.requestInterruption()
        with self._latest_lock:
            self._latest = None

    def _stopping(self) -> bool:
        return self._stop_event.is_set() or self.isInterruptionRequested()

    def _make_detector(self, path: Path, *, defect: bool = False) -> Detector:
        cfg = DetectorConfig(
            model_path=str(path),
            class_names=[],
            img_size=int(self.settings.get("image_size", 640)),
            conf=float(self.settings.get("defect_confidence" if defect else "confidence", 0.25)),
            max_det=50,
            device="cpu",  # portable default; no CUDA DLL or TensorRT warm-up required
            intra_op_threads=int(self.settings.get("inference_threads", 2)),
            inter_op_threads=1,
        )
        detector = Detector(cfg)
        detector.open()
        return detector

    def _open_source(self):
        source = str(self.settings.get("source", "usb")).lower()
        if source in {"basler", "gige"}:
            try:
                from pypylon import pylon
            except ImportError as exc:
                raise RuntimeError("Basler support requires the optional pypylon runtime.") from exc
            factory = pylon.TlFactory.GetInstance()
            devices = factory.EnumerateDevices()
            serial = str(self.settings.get("basler_serial", "")).strip()
            if serial:
                devices = [d for d in devices if d.GetSerialNumber() == serial]
            if not devices:
                raise RuntimeError("No matching Basler camera was found.")
            if len(devices) > 1 and not serial:
                raise RuntimeError("Multiple Basler cameras found; select a serial number.")
            camera = pylon.InstantCamera(factory.CreateDevice(devices[0]))
            try:
                camera.Open()
                # Preserve exposure, trigger, gain, ROI and all camera nodes.
                # If a hardware trigger is configured, external triggers must arrive.
                converter = pylon.ImageFormatConverter()
                converter.OutputPixelFormat = pylon.PixelType_BGR8packed
                converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
                camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            except Exception:
                camera.Close()
                raise
            return ("basler", camera, (pylon, converter)), f"Basler {devices[0].GetSerialNumber()}"
        if source in {"video", "file"}:
            path = _resolve(self.root, str(self.settings.get("video_path", "")))
            if not path.is_file():
                raise RuntimeError(f"Video file was not found: {path}")
            capture = cv2.VideoCapture(str(path))
            source_name = path.name
            kind = "video"
        elif source in {"usb", "camera"}:
            from .cameras import resolve_usb_camera
            chosen = resolve_usb_camera(self.settings)
            index = chosen.index
            api = cv2.CAP_DSHOW if __import__("sys").platform == "win32" else cv2.CAP_ANY
            capture = cv2.VideoCapture(index, api)
            source_name, kind = f"{chosen.name} (USB {index})", "usb"
        else:
            raise RuntimeError("Choose USB, Basler, or video as the source.")
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Could not open {source_name}.")
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return (kind, capture, None), source_name

    @staticmethod
    def _read_source(source) -> tuple[np.ndarray | None, float]:
        kind, camera, extra = source
        if kind == "basler":
            pylon, converter = extra
            result = camera.RetrieveResult(250, pylon.TimeoutHandling_Return)
            if result is None:
                return None, time.monotonic()
            try:
                if not result.GrabSucceeded():
                    raise RuntimeError(f"Basler grab failed: {result.GetErrorDescription()}")
                return converter.Convert(result).GetArray().copy(), time.monotonic()
            finally:
                result.Release()
        ok, frame = camera.read()
        captured = time.monotonic()
        if not ok or frame is None:
            if kind == "video":
                raise EOFError("Video ended. Inspection stopped; outputs must be disarmed.")
            raise RuntimeError("Camera stopped delivering frames. Inspection stopped.")
        return frame, captured

    @staticmethod
    def _close_source(source) -> None:
        if source is None:
            return
        kind, camera, _extra = source
        if kind == "basler":
            try:
                if camera.IsGrabbing():
                    camera.StopGrabbing()
            finally:
                camera.Close()
        else:
            camera.release()

    def run(self) -> None:
        source = detector = defect_detector = None
        try:
            reference = None
            reference_path = self.root / "data" / "reference.json"
            if reference_path.is_file():
                try:
                    reference = json.loads(reference_path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    reference = None
            problem = inspection_error(self.settings, reference)
            model_value = self.settings.get("model_path") or "models/yolox_nano.onnx"
            detector = self._make_detector(_resolve(self.root, model_value))
            if self._stopping():
                return
            if str(self.settings.get("rule", "color")) == "defect_model":
                defect_path = self.settings.get("defect_model")
                if not defect_path:
                    raise RuntimeError("Choose a YOLOX ONNX defect model for this rule.")
                defect_detector = self._make_detector(_resolve(self.root, defect_path), defect=True)
            source, source_name = self._open_source()
            if self._stopping():
                return
            self.ready.emit(source_name)
            barcode_available, barcode_decoder = barcode_status()
            last_decode = None
            last_capture = None
            fps = 0.0
            last_basler_frame = time.monotonic()
            video_interval = 0.0
            if source[0] == "video":
                source_fps = source[1].get(cv2.CAP_PROP_FPS)
                video_interval = 1.0 / source_fps if source_fps and 0.1 < source_fps < 1000 else 1.0 / 30.0
            while not self._stopping():
                began = time.monotonic()
                frame, captured = self._read_source(source)
                if self._stopping():
                    break
                if frame is None:
                    timeout = max(0.5, float(self.settings.get("camera_timeout_s", 3.0)))
                    if time.monotonic() - last_basler_frame > timeout:
                        raise RuntimeError("No Basler frames received. Check trigger and connection.")
                    continue
                last_basler_frame = captured
                result = detector.infer(frame)
                wanted_class = int(self.settings.get("model_class_id", self.settings.get("class_id", 39)))
                bottles = [d for d in result.detections if wanted_class < 0 or d.class_id == wanted_class]
                boxes = [tuple(d.xyxy) for d in bottles]
                color_results = [classify_color(frame, box, self.settings) for box in boxes]
                reasons = [classify(frame, box, self.settings, reference) for box in boxes]
                # Coordinates belong only to the image that was decoded. The UI
                # retains confirmed text on each track; replaying old coordinates
                # could attach that text to the following physical bottle.
                barcodes = []
                barcode_captured = None
                if barcode_available and (last_decode is None or captured - last_decode >= 0.10):
                    barcodes = _decode_frame_and_crops(frame, boxes)
                    last_decode = captured
                    barcode_captured = captured
                defects = []
                inference_ms = result.inference_ms
                if defect_detector is not None:
                    defect_result = defect_detector.infer(frame)
                    defects = [tuple(d.xyxy) for d in defect_result.detections]
                    inference_ms += defect_result.inference_ms
                    for index, box in enumerate(boxes):
                        if any(box[0] <= (d[0]+d[2])/2 <= box[2] and box[1] <= (d[1]+d[3])/2 <= box[3] for d in defects):
                            reasons[index].append("Defect model detection")
                else:
                    defects = [box for box, why in zip(boxes, reasons) if why and not problem]
                if last_capture is not None:
                    instantaneous = 1.0 / max(0.001, captured - last_capture)
                    fps = instantaneous if fps == 0.0 else 0.85 * fps + 0.15 * instantaneous
                last_capture = captured
                packet = {
                    "frame": frame, "boxes": boxes, "defects": defects,
                    "reasons": reasons, "captured": captured, "fps": fps,
                    "inference_ms": inference_ms, "inspection_ready": not bool(problem),
                    "inspection_error": problem,
                    "colors": [item[0] for item in color_results],
                    "color_confidences": [item[1] for item in color_results],
                    "barcodes": barcodes, "barcode_available": barcode_available,
                    "barcode_decoder": barcode_decoder, "barcode_captured": barcode_captured,
                }
                with self._latest_lock:
                    if not self._stopping():
                        self._latest = packet
                if video_interval:
                    self._stop_event.wait(max(0.0, video_interval - (time.monotonic() - began)))
        except Exception as exc:
            if not self._stopping():
                self.fault.emit(str(exc))
        finally:
            try:
                self._close_source(source)
            except Exception as exc:
                if not self._stopping():
                    self.fault.emit(f"Camera close failed: {exc}")
            for model in (detector, defect_detector):
                if model is not None:
                    model.close()
            # No old frame may be consumed after an EOF/error signal disarms UI.
            with self._latest_lock:
                self._latest = None
