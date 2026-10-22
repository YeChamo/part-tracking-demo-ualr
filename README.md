# Part Tracking Demo UALR

A standalone Windows Gatorade bottle-color sorting demo with barcode reading and EtherMotion integration.

- **0 = pass:** the selected color continues on the conveyor.
- **1 = divert:** a different or unknown color requests one saved EtherMotion divert cycle.
- Named USB and Basler camera selection, saved device identity, and no fallback to the laptop camera.
- Per-bottle tracking, conveyor timing, actual barcode decoding, USB scanner input, and CSV logs.
- An animated simulation runs without cameras or motion hardware.

The bundled **YOLOX-S** COCO model detects bottles. Gatorade mode measures exposed
drink color within each detection and separately checks for a visible Gatorade
label. The app still makes its existing two-way decision: the selected color
passes (`0`), and a different or uncertain color diverts (`1`). Label evidence
is shown and logged; a rear-facing or unreadable label does not change routing.

## Run the Gatorade demo

Build this version from source using the commands below, or use its v1.2.0
Windows portable ZIP when published under [Releases](https://github.com/YeChamo/part-tracking-demo-ualr/releases).
Extract the whole ZIP and double-click **Start Demo.cmd**. The portable build
needs no Python installation. Keep `_runtime`, `models`, and the other folders
beside `PartTrackingUALR.exe`.

The repository contains editable source; releases bundle the runtime.

## Choose the conveyor camera

1. Click **Stop + disarm**.
2. Set **SOURCE** to **USB camera** or **Basler / GigE**.
3. Choose the camera by name in the top camera list. Click **Refresh cameras** after connecting a device.
4. Set the pass color under **Color + code** (blue is the default). Leave **Color
   sampling** on **Gatorade exposed body**, then click **Start inspection**.

Blue, yellow, and white are the supplied bottle colors. The simulation includes
these colors plus the older demo colors. For a camera run, start with output
disarmed and check live boxes, colors, track IDs, and line crossings before
enabling a physical diverter. A recorded video is always a dry run.

USB selection follows the physical device identity when Windows changes its index. If the saved camera is unplugged, startup stops and asks for a selection. It never substitutes the built-in camera. **Manual camera index (advanced)** remains available as an explicit fallback.

## Barcodes and motion

The camera decoder reads EAN/UPC, Code 128, QR, and other ZXing formats from actual images. Unread codes remain `UNREAD`. A keyboard-style USB scanner can also print its scan in the large barcode display using the scanner input field. Simulation barcodes are clearly labeled synthetic.

For physical diversion, configure and test an EtherMotion program with **Repeat = Once**, select it in the **EtherMotion** tab, and calibrate the conveyor timing. Simulation and video playback never send hardware output. See [EtherMotion setup](docs/ETHERMOTION_SETUP.txt) and the [complete quick start](README.txt).

The YOLOX-S weights are a general COCO bottle detector; color and label evidence
are separate processing. In the supplied 13 photos, the demo finds and correctly
colors all 13 bottles; visible-label matching succeeds in 9. Those photos show
three bottles in one setting, so live camera validation remains necessary. The
color choice is an observation, not a calibrated probability. Belt timing assumes
constant motion; the demo has no encoder or wired belt-run input.

## Source setup and build

Use **Python 3.11 x64** on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

To build the portable executable:

```powershell
.\Build.ps1 -Python .\.venv\Scripts\python.exe
```

`models/yolox_s.onnx` is the default model and must stay beside the executable
with the Gatorade label-reference images in `models`. The old nano model remains
available as an optional override. Basler transport drivers may need installation
on the target machine.

The optional isolated EtherMotion simulator test needs your separately supplied `EtherMotion.exe` in `EtherMotion/`. It uses a temporary simulator-only workspace and an ephemeral port. Routine tests never move physical hardware.

## Files and privacy

Saved settings, selected camera identities, captured/runtime data, controller tokens, logs, local virtual environments, and generated binaries are excluded from source control. Portable releases start with an empty `data` folder. Source builds do not require the original RemingtonVision checkout.

See [third-party notices](THIRD_PARTY_NOTICES.txt) for bundled dependency and model provenance. EtherMotion is a separate installation; this public project includes its integration, setup notes, and simulator fixture. The public download connects to your installed EtherMotion service.
