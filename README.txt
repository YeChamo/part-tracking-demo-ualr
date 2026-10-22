UALR PART TRACKING DEMO
YOLOX bottle/color models, tracking, barcode display, and EtherMotion routing
Version 1.3.0 candidate - PartTrackingDemoUALR-v1.3.0-Windows-x64.zip

GET STARTED

Double-click Start Demo.cmd or PartTrackingUALR.exe. Keep the complete supplied
folder together: _runtime, models, and data belong beside the executable. The
portable app runs independently of RemingtonVision and needs no Python install.

Choose Simulation as SOURCE, choose the pass color under Color + code, and
click Start inspection. Simulation bottles, colors, and codes are synthetic.
Simulation and recorded video cannot send hardware motion commands.

The controls are grouped into four tabs:
  Models       - bottle/color YOLOX files, live confidence, advanced class setup.
  Color + code - pass color, video input, and barcode controls.
  Tracking     - direction, entry/decision lines, measured belt speed and scale.
  Diverter     - EtherMotion connection, PASS/REJECT/return programs and timing.

Press F11 or double-click the inspection view for full screen. Esc exits it.
Stop + disarm stops inspection and clears pending tracking work.

0 = PASS. Selected color; no movement by default, or the selected PASS program.
1 = REJECT / DIVERT. Different/unknown color; the selected REJECT program.
These numbers are routing decisions, not motor angles or electrical outputs.
Saved EtherMotion moves define the mechanism's actual motion.

CHOOSE THE CAMERA AND YOLOX MODELS

Stop inspection before changing camera, source, model files, geometry, or timing.
Choose USB camera or Basler / GigE, then choose the camera BY NAME in the toolbar.
Use Refresh cameras after plugging one in. No camera is selected automatically.
A saved USB device is found by its identity even if Windows changes its index.
A missing selected device blocks startup; the laptop camera is not substituted.
Manual camera index is an explicit advanced fallback.

In Models, choose Bottle model + color model and select your Bottle YOLOX
and Color YOLOX files (.pth, .pt, or .onnx). Leave Read saved model settings
checked and click Load / convert models. Names, input dimensions, and recorded
model settings are read automatically. A blank bottle selection uses the bundled
generic COCO YOLOX-Nano bottle locator. The optional larger YOLOX-S locator is
models\yolox_s.onnx; select it explicitly in the bottle picker. Both use COCO
bottle class ID 39. Neither supplies trained bottle-color or Gatorade-brand
predictions. The second model must be trained for your selected colors or
categories and can be a .pth, .pt, or .onnx file. Trained literal categories
are supported independently of automatic input sizing; use the exact pass
category name and the correct trained output order.
The detector supplies tracking boxes, and learned color-class predictions are
associated with each bottle. There is no HSV or pixel-color fallback.

Advanced model options use the exact class order from ONNX metadata or your
explicit class-name list, for example orange,blue,green. If IDs need mapping,
use Class -> color such as 0:orange,1:blue,2:green. Set the bottle locator class
ID to its bottle class, or -1 for all locator classes. Do not relabel generic
COCO classes as colors. The bundled locator is neither a color-trained model
nor a Gatorade/Gator brand-trained detector.

Supported trained color labels are orange, yellow, green, blue, red, purple,
clear, and white. White requires a trained YOLOX color class and correct class
names/mapping, just like the other colors. It is not derived from photo pixels.
Other trained literal categories are supported; generic/unknown bottle labels
or ambiguous color labels are not invented sorting categories.

The four models\gatorade_*_reference.png photo crops and GatoradeLabelMatcher
in app\gatorade.py are optional OFFLINE reference assets/tools only. The crops
are not trained weights. No photo/logo match gates live bottles, determines
their color, or changes tracking/routing.

For one model already trained on orange_bottle, blue_bottle, etc., choose One
model: colored bottles and select it in the bottle model picker. Its predictions
supply both boxes and colors. Selected .pth/.pt checkpoints convert to cached
ONNX automatically; there is no separate manual export step.
Missing/incompatible model setup or class-count mismatch blocks camera startup.

CHECKPOINTS, CUSTOM GRAPHS, AND OPTIONAL TENSORRT

The portable application includes CPU PyTorch and ONNX export dependencies.
Its pipeline is .pth/.pt -> cached ONNX -> optional TensorRT engine cache.
Your checkpoint stays at its selected path. Cached conversions and engines
live under data/ and are excluded from source control and release archives.
First conversion takes longer; matching later loads reuse the prepared model.

Standard YOLOX Nano/Tiny/S/M/L/X and recorded custom graph settings are
supported. Class names, image dimensions (including rectangular inputs),
activation, BatchNorm parameters, and output/decode settings are used when
recorded. Preparation admits the complete weights into the matching graph and
checks Torch/ONNX numerical output before publishing a converted model.

For a modified YOLOX graph, select its Python experiment in Advanced model
settings. It must define build_model() or Exp().get_model(). The bundled base
app.vendor.yolox_models.experiment.ExportExp supports self-contained inference
experiments. Your experiment must describe the actual training graph and have
its custom layer code/dependencies available. Training-only imports may need
adaptation. Undefined layers cannot be recovered from weights alone; in that
case supply the missing graph configuration or an ONNX export from training.

Acceleration can be Automatic, ONNX CPU, TensorRT FP32, or TensorRT FP16. The
normal portable bundle runs on CPU. A GPU-capable build additionally needs a
compatible NVIDIA GPU/driver and TensorRT runtime on the target computer.
The GPU dependency overlay pins ONNX Runtime GPU 1.23.2 and TensorRT CUDA 12
10.9.0.34 together; arbitrary TensorRT upgrades can break compatibility.
Engine caches are tied to model contents, input shape, precision, GPU identity,
driver, and runtime versions. They warm before camera startup. Unavailable
acceleration during load reports a CPU fallback; live inference errors stop
inspection and disarm output. An engine build is not an accuracy test.

This laptop has Intel graphics and no usable NVIDIA GPU; TensorRT execution
must be checked on the NVIDIA station. Barcode decoding remains independent.

Use the separate Bottle confidence and Color confidence sliders under Models during a live
inspection while OUTPUT IS DISARMED. They apply on subsequent frames without
reloading the models. A confidence change resets tracks; wait for a fresh
result and recheck it before arming. Existing bottles must collect new tracking
evidence. In one-model mode a bottle may retain a box but become unknown when
its class score is below the separate color threshold. Unknown color diverts.

Use one lane and separated bottles. Check every trained color using real
bottles and the actual lighting/viewpoint. Models can miss or merge touching,
cropped, or reflective bottles. A missed bottle creates no tracked event; an
on-screen count is not an independent count of every physical bottle.

For a video dry run choose Video file and the file under Color + code. Close
other software that owns the camera. Basler requires compatible pylon transport
support; select its serial when multiple devices are present. Another computer
may need Basler's transport-driver installation even with the wrapper bundled.

BARCODES

Camera barcode text appears only when the decoder reads an actual symbol.
Unread codes remain UNREAD. Present enough code pixels, focus, exposure, and
contrast. Simulation codes are explicitly synthetic. Barcode display is
separate from the color routing rule.

For a keyboard-style USB scanner, click the scanner input below LAST BARCODE,
scan, and press Enter (many scanners append Enter). The text is displayed and
logged in data\scanner-YYYYMMDD.csv. This independent scanner read is not
assigned automatically to a camera bottle. The session CSV and Export CSV
preserve camera-decoded codes associated with tracked bottle decisions.

TRACKING AND THE HARDWARE-CONTROLLED CONVEYOR

The conveyor is controlled by its own hardware. Belt speed is a MEASURED input
for timing, not a command to the motor. This app cannot start or stop the belt.
Measure steady speed in mm/s by timing a known distance. Enter the real camera
field width in mm and verify scale with a measured object.

Choose actual travel direction. New identities enter at the incoming entry
zone. The leading edge crossing the decision line creates one bottle decision;
right-to-left mirrors the geometry. Keep entry visible before the line. Fresh
detections drive crossings; missing/reused frames do not invent events.
Confirmed reject evidence stays with its identity. A mismatch not yet confirmed
at the line diverts as unconfirmed inspection. Stop/restart or changing setup
clears tracking; keep bottles clear of the line during restart.

Timing uses steady speed and elapsed time, with no encoder, wired belt-run
signal, or independent bottle/shaft/diverter position sensor. It is a calibrated
estimate. Stalls, slip, speed changes, or a stopped belt invalidate the estimate.

Measure from the on-screen decision line to the physical divert point:
  arrival delay = distance_mm / belt_speed_mm_s + additional_delay_ms / 1000
  trigger delay = arrival delay - actuator_lead_ms / 1000
  bottle-clear deadline = arrival + bottle_length_mm / belt_speed_mm_s
                          + clearance_margin_ms / 1000

Measure actuator move time, set lead >= move time, and ensure arrival delay >=
lead. Arming rejects impossible timing instead of clamping late triggers.
The first primary command has an arrival/move-time deadline; late or busy
commands disarm output. Recalibrate speed, geometry, lead, and clearance using
low-speed trials with representative bottles.

DIVERTER PROGRAMS, HOLD, AND REPEATS

See docs\ETHERMOTION_SETUP.txt for commissioning details. EtherMotion normally
runs from %USERPROFILE%\Desktop\EtherMotion, with service http://127.0.0.1:8765.
Discover it under Diverter and select saved programs with Repeat = Once.

REJECT program: the primary program for route 1.
PASS program: optional primary program for route 0; blank means no movement.
Return program: optional shared return after a selected PASS or REJECT primary.
Hold: delay after primary completion when coordinating the next stage.
Repeats: 1-10 sequential cycles, selected independently for PASS and REJECT.

With a separate return, each repeat runs:
  primary -> matching-run completion -> wait until BOTH bottle clearance AND
  primary completion + hold -> return -> matching-run completion.
The next repeat starts after that return finishes. There is no added hold after
the final return. A blank PASS program never runs the shared return by itself.

Without a separate return, the primary saved program must contain its own
physical dwell and return. The app cannot insert a hold between its saved
steps. Between repeats it waits for the completed primary, the hold, and
predicted bottle clearance before requesting the next whole saved cycle.

Provide enough spacing for ALL bottles, including PASS bottles, to avoid an
active sequence. A pass bottle can reach an extended/busy mechanism even if
its own route requests no movement. Busy/overlapping bottle events disarm
output. DISARMING DOES NOT STOP THE BELT or prove that the mechanism retracted.
Resolve the mechanism state and physical bottle flow before resuming.

Configure/test every program in EtherMotion, connect participating drivers,
and enable their Ethernet triggers in PC events. Discovery/readiness checks
read state; they do not connect/enable physical drivers, set zero, or move them.
Live output must be armed deliberately for a live USB/Basler run. Every launch
starts in Simulation with output disarmed; saving settings never arms hardware.

HTTP 202 means accepted, not movement completed. The matching run ID and drive
command-counter/stopped status establish command-level completion, not actual
shaft position or physical bottle diversion. Never resend an uncertain event
as a new bottle. Inspect that run in EtherMotion before resuming.

The simulator fixture EtherMotion\UALR-simulator-workspace.json contains a
simulated +12 degree / dwell / -12 degree Once cycle. It is not a physical
rejector preset. Importing a workspace replaces EtherMotion's current workspace;
export an existing setup first. Start EtherMotion Simulator.cmd instead opens
an isolated simulator workspace on port 8766. No physical driver is configured.

SAVED FILES AND SOURCE

Settings live under data\settings.json. Keep the folder writable. Local camera
identities, controller tokens, settings, logs, and generated binaries are not
published in source control. Releases start with an empty data folder.

Editable source is in app/ and run.py. Build.ps1 rebuilds the portable app.
The default build installs CPU PyTorch from its official wheel index. An
optional Build.ps1 -TensorRT installs requirements-tensorrt.txt in this demo's
own build environment and retains GPU provider libraries. Close the demo first;
building refuses to replace its runtime while it is open. Do not install CPU
and GPU ONNX Runtime distributions together. README.md has source setup commands.
Verify Demo.cmd runs checks without opening cameras or sending motion.
Package versions and licenses are in THIRD_PARTY_NOTICES.txt and licenses\.
Actual detection, hardware timing, and physical clearances need verification on
the intended conveyor.
