# Part Tracking Demo UALR

A standalone Windows conveyor demo using **YOLOX bottle and color models**, per-bottle tracking, barcode display, and saved EtherMotion programs.

- **0 = PASS:** the selected color; no movement by default, or a selected pass program.
- **1 = REJECT / DIVERT:** a different or unknown color; the selected reject program.
- Named USB/Basler camera selection, live bottle/color confidence sliders, and full-screen inspection.
- Optional return program, timed clearance, sequential cycle repeats, and CSV logs.
- Camera-free simulation and recorded-video dry runs never send motion commands.

## Download and run

Download the **Windows portable ZIP** from [Releases](https://github.com/YeChamo/part-tracking-demo-ualr/releases/latest), extract the complete folder, and double-click **Start Demo.cmd**. No Python installation is needed. Keep `_runtime`, `models`, and the other supplied folders beside `PartTrackingUALR.exe`.

The repository contains editable source; ready-to-run applications and bundled runtimes are release assets.

## Camera, models, and display

1. Click **Stop + disarm**, choose **USB camera** or **Basler / GigE**, and select your camera by name. Use **Refresh cameras** after connecting a device.
2. In **Models**, choose your **Bottle YOLOX (.onnx)** and **Color YOLOX (.onnx)** files. Configure class names/mapping under the advanced options if your exports need them.
3. In **Color + code**, choose the pass color. Click **Start inspection** and verify the boxes, color decisions, and barcode display.
4. Use **Tracking** for direction, entry/decision-line geometry, and measured belt speed. Use **Diverter** for EtherMotion programs and timing.

A saved USB camera is followed by device identity when Windows changes its index. A missing camera blocks startup; the app does not switch to the laptop camera. Manual camera index remains an explicit advanced choice.

Press **F11** or double-click the inspection view for full screen. Press **Esc** to leave full screen.

## YOLOX models and confidence

The default **Bottle model + color model** mode uses one YOLOX detector for bottle boxes and one for trained color predictions. A blank bottle-model selection uses the bundled generic COCO bottle locator. Select your own color-trained ONNX model; the bundled locator cannot predict bottle colors.

The color model's class order is read from ONNX metadata. If names are absent, enter the exact trained order, for example `orange,blue,green`. The advanced class map accepts explicit IDs such as `0:orange,1:blue,2:green`. The bottle locator class ID selects its bottle class; `-1` accepts all locator classes. For one model already trained on `orange_bottle`, `blue_bottle`, etc., choose **One model: colored bottles** and select it in the bottle model picker. Export `.pth` weights to ONNX before selecting them.

Live color decisions use YOLOX predictions exclusively, with no HSV or pixel-color fallback. Missing, conflicting, or unmapped predictions remain unknown and divert. Model/output shape and class-count mismatches block inspection startup.

The separate **Bottle confidence** and **Color confidence** controls in **Models** can be adjusted during inspection **while output is disarmed**. Changes apply to subsequent frames without reloading models, clear old tracks, and require a fresh result before output can be armed. In combined-model mode, a retained bottle box can still have unknown color when it falls below the color threshold. Existing bottle evidence must be collected again after a confidence change.

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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\Build.ps1 -Python .\.venv\Scripts\python.exe
```

Keep `models/yolox_nano.onnx` and its external `models/yolox_nano.onnx.data` together. Basler transport drivers may need installation on the target computer. The optional EtherMotion simulator test needs your separately supplied `EtherMotion.exe` in `EtherMotion/`; routine verification does not open cameras or move hardware.

## Files and privacy

Saved settings, camera identities, controller tokens, logs, environments, and generated binaries are excluded from source control. Portable releases start with an empty `data` folder. Source builds run independently of the original RemingtonVision checkout.

See [third-party notices](THIRD_PARTY_NOTICES.txt) for dependency/model provenance. EtherMotion is a separate installation; this project supplies its integration, setup notes, and simulator fixture.
