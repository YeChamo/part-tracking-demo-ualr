"""Single-camera bottle vision for the portable UALR conveyor demonstration.

YOLOX supplies bottle locations; the selected vision mode supplies colors.
Barcodes are decoded from actual camera pixels only.
Camera reads and inference stay on one worker. The GUI polls a one-frame mailbox
so slow painting never queues old conveyor images.
"""
from __future__ import annotations

import math
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from .yolox_pipeline import YoloXPipeline
from .gatorade_pipeline import GatoradePipeline


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
        self._requested_confidence: tuple[float, float] | None = None
        self._confidence_revision = 0

    def update_confidence(self, bottle: float, color: float) -> int:
        """Queue thresholds for the next inference; never mutate a running model."""
        if not all(math.isfinite(value) and 0 < value <= 1 for value in (bottle,color)):
            raise ValueError("Confidence must be greater than zero and at most one.")
        with self._latest_lock:
            self._requested_confidence = (float(bottle),float(color))
            self._confidence_revision += 1
            self._latest = None
            return self._confidence_revision

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
        source = pipeline = None
        try:
            if self.settings.get("rule", "color") != "color":
                raise RuntimeError("Live inspection requires the YOLOX color sorting rule.")
            pipeline_type = (GatoradePipeline if self.settings.get("yolox_mode") == "gatorade"
                             else YoloXPipeline)
            pipeline = pipeline_type(self.settings, self.root)
            pipeline.open()
            if self._stopping():
                return
            source, source_name = self._open_source()
            if self._stopping():
                return
            self.ready.emit(source_name + " • " + pipeline.describe())
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
                with self._latest_lock:
                    confidence_revision = self._confidence_revision
                    requested, self._requested_confidence = self._requested_confidence, None
                if requested is not None:
                    pipeline.set_confidence(*requested)
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
                result = pipeline.infer(frame)
                boxes = result["boxes"]
                reasons = result["reasons"]
                # Coordinates belong only to the image that was decoded. The UI
                # retains confirmed text on each track; replaying old coordinates
                # could attach that text to the following physical bottle.
                barcodes = []
                barcode_captured = None
                if barcode_available and (last_decode is None or captured - last_decode >= 0.10):
                    barcodes = _decode_frame_and_crops(frame, boxes)
                    last_decode = captured
                    barcode_captured = captured
                defects = [box for box, why in zip(boxes, reasons) if why]
                if last_capture is not None:
                    instantaneous = 1.0 / max(0.001, captured - last_capture)
                    fps = instantaneous if fps == 0.0 else 0.85 * fps + 0.15 * instantaneous
                last_capture = captured
                packet = {
                    "frame": frame, "boxes": boxes, "defects": defects,
                    "reasons": reasons, "captured": captured, "fps": fps,
                    "inference_ms": result["inference_ms"], "inspection_ready": True,
                    "inspection_error": "",
                    "colors": result["colors"],
                    "color_confidences": result["color_confidences"],
                    "model_labels": result["model_labels"], "vision_pipeline": pipeline.describe(),
                    "brand_matches": result.get("brand_matches", []),
                    "inspection_ms": result.get("inspection_ms", 0.0),
                    "confidence_revision": confidence_revision,
                    "barcodes": barcodes, "barcode_available": barcode_available,
                    "barcode_decoder": barcode_decoder, "barcode_captured": barcode_captured,
                }
                with self._latest_lock:
                    if not self._stopping() and confidence_revision == self._confidence_revision:
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
            if pipeline is not None:
                pipeline.close()
            # No old frame may be consumed after an EOF/error signal disarms UI.
            with self._latest_lock:
                self._latest = None
