# Part Tracking Demo UALR

A standalone Windows bottle-color sorting demo with barcode reading and EtherMotion integration.

- **0 = pass:** the selected color continues on the conveyor.
- **1 = divert:** a different or unknown color requests one saved EtherMotion divert cycle.
- Named USB and Basler camera selection, saved device identity, and no fallback to the laptop camera.
- Per-bottle tracking, conveyor timing, actual barcode decoding, USB scanner input, and CSV logs.
- An animated simulation runs without cameras or motion hardware.

## Download and run

Download the **Windows portable ZIP** from [Releases](https://github.com/YeChamo/part-tracking-demo-ualr/releases/latest), extract the entire folder, and double-click **Start Demo.cmd**. No Python installation is needed. Keep `_runtime`, `models`, and the other folders beside `PartTrackingUALR.exe`.

The repository contains editable source. The ready-to-run application and bundled runtimes are release assets.

## Choose the conveyor camera

1. Click **Stop + disarm**.
2. Set **SOURCE** to **USB camera** or **Basler / GigE**.
3. Choose the camera by name in the top camera list. Click **Refresh cameras** after connecting a device.
4. Set the pass color under **Color + code**, then click **Start inspection**.

USB selection follows the physical device identity when Windows changes its index. If the saved camera is unplugged, startup stops and asks for a selection. It never substitutes the built-in camera. **Manual camera index (advanced)** remains available as an explicit fallback.

## Barcodes and motion

The camera decoder reads EAN/UPC, Code 128, QR, and other ZXing formats from actual images. Unread codes remain `UNREAD`. A keyboard-style USB scanner can also print its scan in the large barcode display using the scanner input field. Simulation barcodes are clearly labeled synthetic.

For physical diversion, configure and test an EtherMotion program with **Repeat = Once**, select it in the **EtherMotion** tab, and calibrate the conveyor timing. Simulation and video playback never send hardware output. See [EtherMotion setup](docs/ETHERMOTION_SETUP.txt) and the [complete quick start](README.txt).

The included generic COCO model locates bottles; it is not a Gatorade-specific trained model. Verify color sampling, barcode visibility, tracking, and timing with representative bottles and your camera/lighting. Belt timing assumes constant motion; the demo has no encoder or wired belt-run input.

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

Both `models/yolox_nano.onnx` and its external `models/yolox_nano.onnx.data` file must stay together. Basler transport drivers may need installation on the target machine.

The optional isolated EtherMotion simulator test needs your separately supplied `EtherMotion.exe` in `EtherMotion/`. It uses a temporary simulator-only workspace and an ephemeral port. Routine tests never move physical hardware.

## Files and privacy

Saved settings, selected camera identities, captured/runtime data, controller tokens, logs, local virtual environments, and generated binaries are excluded from source control. Portable releases start with an empty `data` folder. Source builds do not require the original RemingtonVision checkout.

See [third-party notices](THIRD_PARTY_NOTICES.txt) for bundled dependency and model provenance. EtherMotion is a separate installation; this public project includes its integration, setup notes, and simulator fixture. The public download connects to your installed EtherMotion service.
