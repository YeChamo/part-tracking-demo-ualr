PART TRACKING DEMO UALR 1.5.1 - BOTTLE TRACKING AND COLOR SORTING

1. Pull the Git repository, or extract the complete portable ZIP. Run Start Demo.cmd.
   Git includes the EXE and supplied models. A missing runtime is downloaded from
   the pinned v1.4.0-rc1 release (407 MB), checked by size/SHA-256 and self-test,
   then installed without replacing the EXE, models or saved settings. Use the
   full portable ZIP when the station needs to start offline. Python is not needed.
2. Select your USB or Basler camera by name. A saved connected camera starts automatically.
3. Leave Visual preview selected initially. YOLOX-Nano locates bottles; the included
   trained color neural network classifies their inner bottle-body crop.
4. Put a bottle anywhere in view. Boxes, stable IDs and confidence appear on the live image.
5. Adjust Bottle confidence as needed. F11 opens full screen; Esc exits full screen.

OTHER PC / OFFLINE EXE
The Offline EXE release contains the complete app, Python runtime and models.
Run it to extract PartTrackingDemoUALR-1.5.1 beside itself and open the app.
It needs no PowerShell setup, internet or installed Python. Later starts keep
using that extracted folder and its settings. Requires Windows 10/11 x64.
If using the portable ZIP instead, extract all folders, including _runtime.
Setup script failures are recorded in data/runtime-setup-error.txt.

SORTING MODE
In Models choose EtherMotion sorting and click Apply mode / restart app.
After restart, in Diverter connect the separate EtherMotion installation and select
saved Once programs. Choose the pass color and calibrate belt/actuator timing.
The selected color passes; other colors and unknown results divert. Output starts
disarmed and must be armed explicitly. The conveyor uses its own controller.
Actual conveyor/diverter operation has not been validated on this laptop.

Visual preview hides motion controls and blocks connection, arming and commands.
Bottle boxes and stable IDs can appear anywhere in view, including stationary
bottles. Barcode decoding stays separate; actual unread symbols remain UNREAD.

MODELS
If loading reports output shape [1,N,5+C], stop and click Models ->
Use included bottle + color models. This restores and checks the correct
detector/classifier pairing without changing your camera or EtherMotion setup.

The included COCO YOLOX-Nano uses bottle class 39. YOLOX-S is also supplied and is
larger/slower on CPU. Generic YOLOX locates bottles; it does not classify colors.
The bundled models/color/distilV4_student.onnx is a trained MobileNetV3 network,
with 13 color outputs including blue, yellow and white. It was trained on
procedural garment images, not bottles. The fixed crop was calibrated on three
product photos; this does not establish independent bottle or conveyor accuracy.
Two bottles in the blue product photo were detected and classified blue. Read models/color/MODEL_CARD.md and
PROVENANCE.txt for provenance, input format, limitations and MIT license details.
Lighting, reflections, pose and labels can affect results; unknowns remain unknown.

Select YOLOX color detector to use your own trained color/category detector.
You may select .pth, .pt or .onnx models. PTH/PT files convert
to verified cached ONNX automatically. Custom architectures may need their matching
Python experiment file; missing labels can be entered in exact trained order.
Synthetic runtime-test weights and photo references are not trained color models.
Bottle confidence and Color confidence can change live while output is disarmed;
changes clear old tracks and require fresh evidence before arming.

BUILD
The portable EXE needs no Python installation. Keep _runtime, models and supplied
folders beside it. To rebuild from source on Windows with Python 3.11 x64, run
Build Demo.cmd or Build.ps1. A verified Python 3.11 environment is reused without
reinstalling dependencies; otherwise a private .build-venv is prepared. The staged
EXE/runtime must pass self-test before replacing installed files. A failed swap
restores the old pair. Close the app before building; the script never kills it.
Optional NVIDIA build: Build.ps1 -TensorRT. CPU is used on this laptop; NVIDIA
execution needs testing on compatible station hardware. See README.md for details.

See README.md for model contracts, sorting/timing settings, source setup,
third-party notices and advanced integration details. User settings, camera images,
controller credentials and caches are not included in public releases.
