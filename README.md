# Part Tracking Demo UALR

A standalone Windows Gatorade conveyor demo using **YOLOX-S bottle detection**, exposed drink color, orange-cap inspection, label OCR, per-bottle tracking, barcode display, and saved EtherMotion programs.

- **0 = PASS:** the selected color; no movement by default, or a selected pass program.
- **1 = REJECT / DIVERT:** a different or unknown color; the selected reject program.
- Named USB/Basler camera selection, live bottle/color confidence sliders, and full-screen inspection.
- Optional return program, timed clearance, sequential cycle repeats, and CSV logs.
- Live inspection starts on a saved camera when present; reject output remains disarmed.
- Optional auxiliary USB/Basler cameras inspect independently and never send diverter commands.

## Download and run

Build this version from source using the commands below, or use its v1.4.1
Windows portable ZIP when published under [Releases](https://github.com/YeChamo/part-tracking-demo-ualr/releases).
Extract the complete folder and double-click **Start Demo.cmd**. The portable
build needs no Python installation. Keep `_runtime`, `models`, and the other
supplied folders beside `PartTrackingUALR.exe`.

The repository contains editable source; ready-to-run applications and bundled runtimes are release assets.

## Camera, models, and display

1. Choose **USB camera** or **Basler / GigE** and select your camera by name. A saved connected camera opens automatically. Use **Refresh cameras** after connecting a device.
2. In **Models**, leave **Gatorade demo** selected. A blank bottle-model field uses the included YOLOX-S file. Other modes accept trained color ONNX models.
3. In **Inspections**, choose the pass color. Watch live cap status, OCR text, color support, and label evidence. Cap and label results are informational. A bottle beyond the entry line is marked **not tracked** until it enters the lane. The event table records a decision only after a tracked bottle crosses the decision line.
4. In **Cameras**, check any auxiliary cameras before starting. The top-bar camera is primary and alone controls sorting. Auxiliary views show independent inspection; they do not assign a shared bottle ID or command motion.
5. Use **Tracking** for direction, entry/decision-line geometry, and measured belt speed. Use **Diverter** for EtherMotion programs and timing.

A saved USB camera is followed by device identity when Windows changes its index. A missing camera blocks startup; the app does not switch to the laptop camera. Manual camera index remains an explicit advanced choice.

Press **F11** or double-click the inspection view for full screen. Press **Esc** to leave full screen.

## YOLOX models and confidence

The default **Gatorade demo** mode uses the bundled YOLOX-S COCO detector for bottle boxes, then measures exposed drink color within each box. Blue, yellow, and white are represented in the supplied examples. A separate visible-label check is shown and logged as supporting evidence; a rear-facing or unreadable label does not change routing. The model weights are a generic bottle detector, not a Gatorade-trained detector.

The cap inspection looks for the orange closure shown on the supplied bottles. It reports **present**, **missing**, or **unknown** when the top is clipped or visual evidence is inconclusive. Its result is logged for every primary-camera decision but never changes routing. A live uncapped bottle with its orange tamper band still attached reported **missing** across 12 consecutive frames; check more bottles and viewpoints before finalizing the rule. Other cap styles need their own inspection profile.

RapidOCR reads actual visible label text in the background. Recognized words appear in the live readout and CSV when they can be associated with the same bottle region. Label text and geometric Gatorade-label matches are evidence, not routing rules; rear-facing, small, or blurred labels can remain unread. The current 640×480 view of the uncapped bottle shows a large stylized G but yielded no readable text. Background OCR keeps camera detection responsive.

The detector and color inspection found the expected bottle color in all 13
supplied photos (6 blue, 4 yellow, 3 white) and in tests with reduced exposure,
increased exposure, moderate warm/cool channel shifts, blur, and smaller frames.
The color sampler corrects bounded camera channel casts when the scene has a
credible neutral reference. The visible-label check matched 8 compressed video
frames. These photos share a setting, so verify camera exposure, glare,
placement, and color readings on the intended conveyor before enabling physical
output. A missing bottle detection cannot cause a divert decision.

The **Two trained models** mode uses one YOLOX detector for bottle boxes and one for trained color predictions. A blank bottle-model selection in that mode uses the bundled generic COCO bottle locator. Select your own color-trained ONNX model.

The color model's class order is read from ONNX metadata. If names are absent, enter the exact trained order, for example `orange,blue,green`. The advanced class map accepts explicit IDs such as `0:orange,1:blue,2:green`. The bottle locator class ID selects its bottle class; `-1` accepts all locator classes. For one model already trained on `orange_bottle`, `blue_bottle`, etc., choose **Combined trained model** and select it in the bottle model picker. Export `.pth` weights to ONNX before selecting them.

In the trained-color modes, decisions use YOLOX predictions exclusively. Missing, conflicting, or unmapped predictions remain unknown and divert. Model/output shape and class-count mismatches block inspection startup. Gatorade demo mode uses a separate drink-color sampler; unknown samples also divert.

The separate **Bottle confidence** and **Color confidence** controls in **Models** can be adjusted during inspection **while output is disarmed**. In Gatorade mode, color confidence is sample support rather than a trained-model probability. Changes apply to subsequent frames without reloading models, clear old tracks, and require a fresh result before output can be armed. In combined-model mode, a retained bottle box can still have unknown color when it falls below the color threshold.

## Barcodes

The camera reads actual EAN/UPC, Code 128, QR, and other ZXing symbols. Unread codes remain `UNREAD`. Keyboard-style USB scanners can print scans through the scanner input field; those independent scans are not automatically assigned to camera tracks. Barcode display is separate from color routing.

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

## Demo-day run-through

1. Run `PartTrackingUALR.exe --self-test` from the extracted portable folder (or `python run.py --self-test` from source). Confirm `data/runtime-check.json` reports `ok: true`.
2. Select the actual camera by name. A saved connected camera opens on launch; the app never arms output automatically.
3. Keep output disarmed while you check blue, yellow, and white bottles at the actual belt speed, lighting, position, and orientation. Use **Inspections** to set the pass color; cap and label results are informational. Test every auxiliary camera independently. Check uncapped bottles when samples become available.
4. Check the decision line, the measured belt speed and field width, and the EtherMotion Once cycle. Arming is available only for fresh live-camera results after the timing and controller checks.
5. Keep bottles separated during the demo. Stop + disarm if the camera loses the bottle, color reads unknown, or motion timing differs from the measured cycle.

The optional real-photo regression is `python -m unittest tests.test_gatorade_examples -v` when the supplied `examples` folder sits beside this repository. Its augmented cases support setup checks but do not replace a live conveyor trial.

The [outside-photo cap check](docs/OPEN_BOTTLE_IMAGE_EVAL.md) records open-bottle results across indoor and studio scenes, along with missed and duplicate detections. Run the same inspection on additional local stills with `python scripts/evaluate_bottle_images.py <image-or-folder>`.

## Source setup and build

Use **Python 3.11 x64** on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\Build.ps1 -Python .\.venv\Scripts\python.exe
```

Keep `models/yolox_s.onnx` and the Gatorade label reference images beside the portable app. The older nano model and its external `.data` file remain available for trained-color locator mode. Basler transport drivers may need installation on the target computer. The optional EtherMotion simulator test needs your separately supplied `EtherMotion.exe` in `EtherMotion/`; routine verification does not open cameras or move hardware.

## Files and privacy

Saved settings, camera identities, controller tokens, logs, environments, and generated binaries are excluded from source control. Portable releases start with an empty `data` folder. Source builds run independently of the original RemingtonVision checkout.

See [third-party notices](THIRD_PARTY_NOTICES.txt) for dependency/model provenance. EtherMotion is a separate installation; this project supplies its integration, setup notes, and simulator fixture.
