from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {
    'source': 'simulation', 'camera_index': 0, 'camera_id': '', 'camera_name': '',
    'camera_manual': False, 'basler_serial': '', 'video_path': '',
    'visual_only': True,
    'model_path': 'models/yolox_nano.onnx', 'model_class_id': 39, 'image_size': 640,
    'yolox_mode': 'tracking', 'model_class_names': '',
    'color_model_path': 'models/color/distilV4_student.onnx', 'color_backend': 'classifier',
    'color_class_names': '', 'color_class_map': '', 'color_image_size': 640,
    'auto_model_config': True, 'inference_backend': 'cpu',
    'model_architecture': 'auto', 'color_architecture': 'auto',
    'model_experiment_path': '', 'color_experiment_path': '',
    'confidence': .20, 'color_confidence': .50, 'rule': 'tracking', 'pass_color': 'blue',
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
                # Upgrade the old bottle-only demo once; an explicitly cleared
                # color selection in the current version remains cleared.
                if 'color_backend' not in saved and not saved.get('color_model_path'):
                    result['color_model_path'] = DEFAULTS['color_model_path']
                    result['color_confidence'] = DEFAULTS['color_confidence']
                elif 'color_backend' not in saved and saved.get('color_model_path'):
                    result['color_backend'] = 'yolox'
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
