from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {
    'source': 'simulation', 'camera_index': 0, 'camera_id': '', 'camera_name': '',
    'camera_manual': False, 'basler_serial': '', 'video_path': '',
    'model_path': '', 'model_class_id': 39, 'image_size': 640,
    'yolox_mode': 'gatorade', 'gatorade_label_check': True,
    'label_ocr': True, 'aux_camera_ids': [],
    'model_class_names': '', 'color_model_path': '',
    'color_class_names': '', 'color_class_map': '', 'color_image_size': 640,
    'confidence': .25, 'color_confidence': .50, 'rule': 'color', 'pass_color': 'blue',
    'direction': 'ltr', 'line': .80, 'entry': .30,
    'confirm_frames': 3, 'max_miss': .4, 'belt_speed': 200.0, 'field_width': 1000.0,
    'distance_mm': 100.0, 'delay_ms': 0, 'lead_ms': 200, 'every_n': 4,
    'move_ms': 150, 'bottle_length_mm': 80.0, 'clearance_ms': 100,
    'hold_ms': 500, 'reject_cycles': 1, 'pass_cycles': 1,
    'pass_program_id': '', 'return_program_id': '',
    'base_url': 'http://127.0.0.1:8765', 'program_id': '',
    'ethermotion_path': str(Path.home() / 'Desktop' / 'EtherMotion' / 'EtherMotion.exe'),
}


def load(root: Path) -> dict:
    result = DEFAULTS.copy()
    path = root / 'data' / 'settings.json'
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(saved, dict):
                result.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except (ValueError, OSError):
            pass
    return result


def save(root: Path, settings: dict) -> None:
    folder = root / 'data'
    folder.mkdir(exist_ok=True)
    target = folder / 'settings.json'
    temporary = folder / 'settings.tmp'
    temporary.write_text(json.dumps({k: settings[k] for k in DEFAULTS}, indent=2), encoding='utf-8')
    os.replace(temporary, target)
