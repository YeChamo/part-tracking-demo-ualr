# Part Tracking Demo UALR

A standalone Windows **visual bottle-tracking demo** using YOLOX detections, persistent bottle IDs, confidence scores, camera selection, and barcode display. Visual mode sends no motion commands.

Version **1.4.0 preview** packages as `PartTrackingDemoUALR-v1.4.0-Windows-x64.zip`.

- Visual tracking starts with the included real COCO YOLOX-Nano bottle detector; a separate color model is not required.
- Bottles receive IDs anywhere in the camera image, including stationary bottles in the center.
- Named USB/Basler camera selection, live bottle/color confidence sliders, and full-screen inspection.
- Optional return program, timed clearance, sequential cycle repeats, and CSV logs.
- Camera-free simulation and recorded-video dry runs never send motion commands.

## Download and run

Download the **Windows portable ZIP** from [Releases](https://github.com/YeChamo/part-tracking-demo-ualr/releases/latest), extract the complete folder, and double-click **Start Demo.cmd**. No Python installation is needed. Keep `_runtime`, `models`, and the other supplied folders beside `PartTrackingUALR.exe`.

Visual tracking and checkpoint conversion are available in the [1.4.0 preview](https://github.com/YeChamo/part-tracking-demo-ualr/releases/tag/v1.4.0-rc1).

The repository contains editable source; ready-to-run applications and bundled runtimes are release assets.

## Camera, models, and display

1. Choose **USB camera** or **Basler / GigE**, then select your camera by name. A saved, connected camera starts automatically. Use **Refresh cameras** after connecting another device.
2. Leave **Visual bottle tracking** selected. The bundled **YOLOX-Nano** bottle model is ready to use. The optional YOLOX-S model is larger and slower on CPU. A trained color model is not required for boxes and IDs.
3. Place a bottle in view. The live image shows its box, ID, and model confidence; the live readout shows current detections. Bottles do not need to cross an entry or reject line.
4. Adjust **Bottle confidence** if needed. Press **F11** for full-screen view. Barcode results remain real decoded values; unread symbols stay `UNREAD`.

The default visual-only setup hides motion controls and blocks connection, arming, and dispatch. Optional trained-color and legacy sorting settings remain available in the source; they are not needed for this demo.

A saved USB camera is followed by device identity when Windows changes its index. A missing camera blocks startup; the app does not switch to the laptop camera. Manual camera index remains an explicit advanced choice.

Press **F11** or double-click the inspection view for full screen. Press **Esc** to leave full screen.

## YOLOX models and confidence

The default **Visual bottle tracking** mode uses one included YOLOX detector for bottle boxes. In the optional **Bottle model + color model** mode, select your trained `.pth`, `.pt`, or `.onnx` file in the color/category picker. Exact trained category names can be used independently of automatic input sizing. A blank bottle-model selection uses the bundled generic COCO **YOLOX-Nano** locator. For the optional larger generic locator, select `models/yolox_s.onnx` in the bottle model picker. Both use COCO bottle class ID **39**; neither is a color-trained or Gatorade brand-trained model.

The color model's class order is read from checkpoint or ONNX metadata. If names are absent, enter the exact trained order, for example `orange,blue,green`. The advanced class map accepts explicit IDs such as `0:orange,1:blue,2:green`. The bottle locator class ID selects its bottle class; `-1` accepts all locator classes. For one model already trained on `orange_bottle`, `blue_bottle`, etc., choose **One model: colored bottles** and select it in the bottle model picker.

Live color decisions use YOLOX predictions exclusively, with no HSV or pixel-color fallback. Missing, conflicting, or unmapped predictions remain unknown and divert. Model/output shape and class-count mismatches block inspection startup.

Supported trained color labels include orange, yellow, green, blue, red, purple, clear, and **white**. White must be predicted by your color model and included in its class names or explicit mapping; the reference photo is not a white-color classifier. Other trained literal categories are supported too: select the exact pass category and keep the remaining category names in their trained output order. Generic, unknown, and ambiguous labels do not become custom categories.

The four `models/gatorade_*_reference.png` photo crops and `GatoradeLabelMatcher` in `app/gatorade.py` are optional **offline reference tools**. They are not trained weights and are not called by live bottle/color inference or routing. Live inspection does not gate bottles by a photo/logo match.

The separate **Bottle confidence** and **Color confidence** controls in **Models** can be adjusted during inspection **while output is disarmed**. Changes apply to subsequent frames without reloading models, clear old tracks, and require a fresh result before output can be armed. In combined-model mode, a retained bottle box can still have unknown color when it falls below the color threshold. Existing bottle evidence must be collected again after a confidence change.

## Checkpoint conversion and custom YOLOX graphs

Selecting `.pth` or `.pt` prepares a cached ONNX export automatically. The app bundles CPU PyTorch, ONNX, and inference-only YOLOX model definitions; conversion does not require the original RemingtonVision checkout. Preparation checks the complete checkpoint against its graph, exports on CPU, and compares Torch/ONNX output before publishing the cached model. The selected checkpoint stays in its original location. First conversion takes longer; later loads reuse a matching cache under `data/`.

The standard Nano, Tiny, S, M, L, and X YOLOX configurations are supported. Recorded custom width/depth, class count, activation, BatchNorm settings, input size, strides, and decode settings are used when present. Rectangular inputs retain their recorded height and width. Unsupported or incomplete graph information stops preparation with an explanation; the app cannot reconstruct undefined layers from a weights-only file.

For a modified graph, supply the corresponding self-contained Python experiment in **Advanced model settings**. It must define `build_model()` or `Exp().get_model()` and describe the architecture that produced the weights. The experiment runs your selected Python code and needs its own layer definitions and dependencies. An existing training experiment that imports the full training repository may need adaptation or a pre-exported ONNX file.

Inference expects batch-one FP32 NCHW YOLOX detection output `[1,N,5+C]`, using standard BGR pixels and letterboxing. Custom RGB/normalization or other preprocessing must be included in the supplied graph. Models with embedded NMS or different output contracts need an adapted export. If class names are absent, enter their exact trained order; adjacent dataset YAML files are not loaded automatically. Known color names are grouped (for example, `light_blue` and `dark_blue` become `blue`); use the advanced class map to keep those categories distinct.

A compatible inference-only base is bundled:

```python
from app.vendor.yolox_models.experiment import ExportExp

class Exp(ExportExp):
    def __init__(self):
        super().__init__()
        self.num_classes = 3
        self.depth = 0.33
        self.width = 0.50
        self.input_size = self.test_size = (384, 640)
```

Set those fields to the actual training configuration; the example is not a replacement for an unknown custom graph. Use exact trained color/category names or an explicit class map. Generic COCO classes cannot be repurposed as trained colors or custom categories.

## Optional TensorRT acceleration

The path is **checkpoint → cached ONNX → optional cached TensorRT engine**. **Acceleration** offers Automatic, ONNX CPU, TensorRT FP32, and TensorRT FP16. The normal portable download runs on CPU and includes checkpoint conversion. A GPU-capable build can use ONNX Runtime's TensorRT provider when the target computer has compatible NVIDIA hardware, driver, and TensorRT dependencies.

Engine caches are tied to the model contents, input shape, precision, GPU UUID/compute capability, driver, and runtime versions. A changed model or station gets a separate cache. Engines warm before a camera opens. If acceleration is unavailable during loading, the app reports the reason and uses CPU. A live inference failure stops inspection and disarms output. Building or warming an engine does not establish model accuracy.

The optional build pins ONNX Runtime GPU **1.23.2** with TensorRT CUDA 12 **10.9.0.34**. Keep runtime generations compatible when changing GPU dependencies; see the [ONNX Runtime TensorRT requirements](https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html#requirements).

This development laptop has Intel graphics and no usable NVIDIA GPU. CPU conversion/inference can be checked here; TensorRT hardware execution needs verification on the NVIDIA station. Engine caches and selected user models are not published with the source.

## Barcodes

The camera reads actual EAN/UPC, Code 128, QR, and other ZXing symbols. Unread codes remain `UNREAD`. Keyboard-style USB scanners can print scans through the scanner input field; those independent scans are not automatically assigned to camera tracks. Simulation codes are explicitly synthetic. Barcode display is separate from color routing.

## Conveyor and diverter timing

**The conveyor is controlled by its own hardware.** Enter measured steady belt speed in mm/s for calculations; the app does not command or stop the belt. Timing is a calibrated estimate with no encoder, belt-run input, or independent bottle/diverter position sensing.

Measure distance from the tracking decision line to the divert point, bottle length along travel, actuator move time, and a clearance margin:

```text
arrival delay = distance / belt speed + additional delay
trigger delay = arrival delay - actuator lead
bottle-clear deadline = arrival + bottle length / belt speed + clearance margin
```

Arming requires **lead >= measured move time** and **arrival delay >= lead**. Impossible deadlines are rejected instead of clamped to the present. Recalibrate after changing speed, geometry, or the mechanism.

Configure saved EtherMotion **Once** programs in **Diverter**:

- **REJECT:** the primary reject program.
- **PASS:** no movement by default, or an optional pass program.
- **Return:** an optional shared return program after either selected primary program.
- **Hold:** with a separate return, wait until **both** predicted bottle clearance and `primary completion + hold` have elapsed.
- **Repeats:** 1-10 sequential cycles per outcome. With a separate return, each repeat waits for primary completion, its hold/clearance, and return completion before the next repeat. There is no extra hold after the final return. Without a separate return, hold and clearance delay the next whole saved cycle.

Without a separate return program, the primary saved cycle must include its own physical dwell and return; the app cannot insert a hold between steps of that saved cycle. EtherMotion acceptance is followed through the matching run ID to command-level completion, which does not independently prove physical position.

Keep enough spacing for **every bottle, including PASS bottles**, to clear the entire active sequence. A busy/overlapping event disarms output rather than issuing a conflicting cycle. **Disarming cannot stop the conveyor** or establish the mechanism's physical position. Resolve the mechanism and bottle flow before resuming.

See [EtherMotion setup](docs/ETHERMOTION_SETUP.txt) and the [complete quick start](README.txt).

## Source setup and build

Use **Python 3.11 x64** on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.12.0
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\Build.ps1 -Python .\.venv\Scripts\python.exe
```

`Build.ps1` creates this demo's own `.build-venv`, installs the official CPU PyTorch wheel, and includes checkpoint export dependencies in the executable. Close the demo before building; the script refuses to replace a running application. For an optional GPU-capable bundle, use `Build.ps1 -Python .\.venv\Scripts\python.exe -TensorRT`. That installs `requirements-tensorrt.txt` in the build environment and retains GPU provider libraries; the default build excludes them. Do not install the CPU and GPU ONNX Runtime distributions together.

Keep `models/yolox_nano.onnx` and its external `models/yolox_nano.onnx.data` together. Basler transport drivers may need installation on the target computer. The optional EtherMotion simulator test needs your separately supplied `EtherMotion.exe` in `EtherMotion/`; routine verification does not open cameras or move hardware.

## Files and privacy

Saved settings, camera identities, controller tokens, logs, model-conversion/engine caches, environments, and generated binaries are excluded from source control. User-selected checkpoints are read from their selected paths and are not added to Git. Portable releases start with an empty `data` folder. Source builds run independently of the original RemingtonVision checkout. The release packager creates the new version's archive and refuses to overwrite an existing archive.

See [third-party notices](THIRD_PARTY_NOTICES.txt) for dependency/model provenance. EtherMotion is a separate installation; this project supplies its integration, setup notes, and simulator fixture.
