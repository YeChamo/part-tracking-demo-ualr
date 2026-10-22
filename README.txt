UALR PART TRACKING DEMO
Color sorting, bottle tracking, barcode display, and EtherMotion reject cycles

GET STARTED

Double-click Start Demo.cmd or PartTrackingUALR.exe in this folder. Keep the complete folder
together: the bundled runtime, models, and data folder belong beside the app.
The packaged application runs independently of the RemingtonVision checkout.
No Python installation is needed to run the packaged Windows executable.

Select Simulation as SOURCE. In Color + code, select the pass color, and click
Start inspection. The Conveyor tab holds direction and timing. EtherMotion holds the
live-output connection. Stop + disarm ends inspection and clears queued events.
The colored bottles, barcodes, and inspection results in Simulation are
synthetic demonstration data. They do not prove live detection or decoding.
Simulation and recorded video cannot send hardware reject commands.

0 = PASS. The bottle matches the selected pass color and continues straight.
1 = DIVERT. The bottle is a different color or could not be inspected reliably.
These are routing decisions, not motor angles or raw digital-output values.
EtherMotion's selected saved cycle controls the actual reject mechanism.

COLOR SORTING AND BARCODES

Choose the color that should continue straight using the pass-color setting
(pass_color). Named choices cover orange, yellow, green, blue, red, purple, and
clear. Other colors take the divert route. Color inspection samples the
lower liquid/body region of each detected upright bottle to reduce cap/label
interference. Use one lane, separate bottles, a fixed camera, steady lighting,
a simple background, and upright bottles. Reflections, transparent liquid,
labels, tinted plastic, shadows, or changed lighting can alter the color result.
Verify the displayed result with real examples of every color before a run.

Barcode text is displayed only when a decoder reads it. An unread code remains
UNREAD; the application does not invent a barcode from the bottle's identity.
Simulation uses clearly synthetic demo codes. For live decoding, present the
printed code to the camera with enough pixels, focus, exposure, and contrast.
The basic routing rule uses color; displaying a barcode is separate from that
color decision.

A USB barcode scanner that types like a keyboard can also be used. Click the
scanner input box below LAST BARCODE, scan the code, and press Enter (many
scanners append Enter automatically). The received text is displayed and
appended to data\scanner-YYYYMMDD.csv. This is an independent scanner read; it
is not automatically assigned to a camera-tracked bottle. The main session CSV
and Export CSV keep the camera barcode associated with each bottle decision.

LIVE CAMERA OR RECORDED VIDEO

Stop the current run before changing source, rule, direction, or timing.
Choose USB camera or Basler as SOURCE, then pick the camera BY NAME in the
top toolbar. Use Refresh cameras after plugging one in. The first camera is
never selected automatically. The demo remembers the selected USB device's
identity, even when Windows changes its number. A missing selected camera
stops startup; it never falls back to the laptop camera. Manual camera index
is an explicit advanced fallback, enabled only when that option is chosen.
For video, choose Video file as SOURCE and select the file under Color + code.
Close other software that owns the camera. Basler needs its compatible pylon/pypylon runtime and transport
support; choose a serial when more than one Basler is connected. A video is a
dry run and cannot actuate the rejector. Another computer may require the
Basler pylon transport/driver installation even when the application and its
Python camera wrapper are bundled.

The bundled generic COCO bottle detector finds the COCO bottle class. It is not
a Gatorade/Gator brand-trained detector. It can miss or merge bottles,
particularly touching bottles, cropped
bottles, glare, and unfamiliar viewpoints. Use the confidence control and clear
spacing while checking the overlay. A missed bottle produces no tracked reject
event; an on-screen count is not independent evidence of every physical part.

TRACKING AND TIMING

Select the actual travel direction. New identities start in the entry zone at
the incoming side of the image. A tracked bottle receives one decision when its
leading edge crosses the decision line. Right-to-left mirrors the geometry.
Keep the entry zone visible so each bottle is seen before reaching the line.
Fresh detections drive decisions; missing or reused frames do not synthesize
crossing events. Confirmed reject evidence remains attached to that identity.
Unknown color diverts immediately. Confirmation suppresses transient upstream
noise; a mismatch still awaiting confirmation at the decision line diverts as
unconfirmed inspection rather than being counted as a pass.
Stopping or changing the setup clears pending tracking/timing work for a clean
restart. Keep bottles clear of the decision line when restarting a live run.

Measure belt speed in mm/s by timing a known conveyor distance. Enter the real
camera field width in mm, and verify it against a measured object/scale. Speed
settings describe belt motion; they do not command the conveyor motor.
The timing assumes a steady belt speed. It is not encoder-synchronized tracking.

Measure the distance along belt travel from the on-screen decision line to the
physical reject point. Travel time in milliseconds = distance_mm / belt_speed
* 1000. Additional delay adds time; actuator lead subtracts the actuator's
response time. Calibrate from low-speed trials with known bottles and the
rejector's return cycle. Allow enough bottle spacing for the entire saved
cycle to finish. EtherMotion refuses a new cycle while its drivers/program are
busy; requests are not queued or retried as later bottles.

ETHERMOTION REJECT OUTPUT

See docs\ETHERMOTION_SETUP.txt for the complete setup.
The existing EtherMotion installation is expected at:
%USERPROFILE%\Desktop\EtherMotion
The usual local endpoint is http://127.0.0.1:8765.

Open EtherMotion, configure and test a saved Once reject cycle, connect every
participating driver, and enable each driver's Ethernet triggers in PC events.
In this demo, discover EtherMotion and choose that saved program. Readiness
checks read configuration/status; they do not connect or enable a physical
driver. Enable live output deliberately for a live USB/Basler camera run.
Output starts disarmed every launch; the saved settings never arm hardware.
Only route 1 requests the reject cycle. Route 0 continues without a reject call.
Use Open EtherMotion to open the motion application and Discover / check
connection to read its saved Once programs. Enable live divert output is a
deliberate live-camera action. Export CSV saves the displayed event history.

An accepted HTTP 202 means EtherMotion accepted the command, not that movement
completed. Completion belongs to that returned run ID and EtherMotion's drive
command-counter/stopped checks. This is not independent shaft-position sensing.
Do not resend a timed-out or uncertain event as a new bottle. Resolve the cycle
state in EtherMotion before resuming output.

The included EtherMotion\UALR-simulator-workspace.json has one simulator and
one Once cycle. Its +12 degree / dwell / -12 degree moves are simulator examples,
not recommended values for a physical rejector. It contains no physical driver,
trigger token, automatic input rule, or machine position reference. Importing
any workspace replaces EtherMotion's workspace: export an existing setup first.

SAVED FILES

Settings are stored under data\settings.json in this demo folder. Each launch
opens Simulation with output disarmed; the saved live recipe fields remain
available. Keep the folder writable. Source, model assets, and tests are included for further
programming; the packaged app does not import the original RemingtonVision
project. Hardware/network timing and actual bottle performance still need to
be verified on the intended conveyor.

Third-party package versions, local source provenance, and copied license
notices are documented in THIRD_PARTY_NOTICES.txt and licenses\.
