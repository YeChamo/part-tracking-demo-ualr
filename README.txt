PART TRACKING DEMO UALR 1.4.0 - VISUAL TRACKING

1. Extract the complete portable folder. Run Start Demo.cmd.
2. Select your USB or Basler camera by name. A saved connected camera starts automatically.
3. Leave Visual bottle tracking selected. The included YOLOX-Nano bottle model is ready.
4. Put a bottle anywhere in view. Boxes, stable IDs and confidence appear on the live image.
5. Adjust Bottle confidence as needed. F11 opens full screen; Esc exits full screen.

VISUAL ONLY
This setup does not connect, arm or command EtherMotion. A color-trained model and
conveyor entry/decision lines are not required for bottle tracking. No physical
PASS/REJECT action is performed. Generic YOLOX detects bottles, not bottle colors.
Barcode decoding stays separate; actual unread symbols remain UNREAD.

MODELS
The included COCO YOLOX-Nano uses bottle class 39. YOLOX-S is also supplied and is
larger/slower on CPU. You may select .pth, .pt or .onnx models. PTH/PT files convert
to verified cached ONNX automatically. Custom architectures may need their matching
Python experiment file; missing labels can be entered in exact trained order.
Synthetic runtime-test weights and photo references are not trained color models.

BUILD
The portable EXE needs no Python installation. Keep _runtime, models and supplied
folders beside it. To rebuild from source on Windows with Python 3.11 x64, run
Build.ps1. Optional NVIDIA build: Build.ps1 -TensorRT. CPU is used on this laptop.

See README.md for model contracts, optional trained-color settings, source setup,
third-party notices and advanced integration details. User settings, camera images,
controller credentials and caches are not included in public releases.
