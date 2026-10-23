# EtherMotion

A local Windows control station for multiple Rtelligent **EPR60** Ethernet stepper drives. Each driver has an **expandable library of saved moves**, with custom angles, motor speed, acceleration and deceleration. Build programs that run selected moves in any order, wait a chosen time or wait for a sensor input. Includes a simulator and local Ethernet triggers.

## Open it

Double-click **Start.cmd** (or **EtherMotion.exe**). The operator screen opens at **http://127.0.0.1:8765**. Keep the service window open while using the app. The bundled executable includes Python; no install or internet connection is needed. If using only the source, Python 3.10+ is required and there are no pip dependencies.

The included executable targets **64-bit x64 Windows** (Windows 10/11); use a current Edge, Chrome or Firefox browser. Extract the complete folder before launching. See **TRANSFER.txt** for copying it to another computer and **BUILDING.md** for editing the source or rebuilding the EXE.

Start with **Demo turntable**. It simulates a motor without connecting to hardware. Enter an angle and click Move. Controls are available whenever the connected driver is ready; there is no Arm step or session timeout. Stop decelerates the axis and disables its automatic triggers. Local controls are available again when it is idle.

**Example-workspace.json** contains the tested demo sequence **1 → 2 → 6 → 7 → 8**, including custom decimal angles, and an IN1 input-trigger rule. To try it, disconnect the demo driver and use **Import workspace** to select that file. Import replaces the current workspace, so export any settings you want to keep first. Reconnect the demo to run it; input rules start disabled.

It also includes **Positions 35 → 90 → 0 (set zero first)**. On the demo driver, set the current position as zero before running this program. It goes to two custom positions and returns to the start using absolute presets, with no wired inputs.

## Connect an EPR60

1. Close RT Configurator so one program controls the drive.
2. Connect the PC directly to one drive with a standard Ethernet cable. Set the PC's Ethernet adapter and the drive to the same subnet, with different addresses—for example, PC **192.168.0.10**, drive **192.168.0.11**, subnet mask **255.255.255.0**. No router or internet connection is needed. For several drives, connect the PC and drives through an Ethernet switch and give every drive a unique IP address.
3. Select **EPR60 · Axis 1**, or add an EPR60 in **Connections**. Its initial address is **192.168.0.11**, port **502**, device address **1**, matching the unit inspected in this chat.
4. Click Connect. This reads drive identity, status, operating modes and the actual pulses per revolution. It does not change drive parameters or start motion.
5. Resolve any alarm or enable/ready condition shown by the drive. The move controls are then available immediately.
6. If Setup required is shown, **Use Ethernet motion mode** selects internal command, communication control and relative movement. This changes drive modes. It does not change motor current, microsteps, I/O assignments or the enable input.
7. Enter a small move appropriate to the connected mechanism, then use Move. Verify its actual direction and distance on the mechanism before making production presets.

There is no software unlock step or 15-minute timeout. Connected controls still check the drive identity, ready/enable status, alarms, motion mode, limits and current motion. A fault or lost connection disables triggers. The software Stop is a network command, not a safety-rated emergency stop; retain the machine's physical stopping system. A PC/network/power failure can prevent the app from stopping a move.

### VPN / network adapter

The Connections form includes **Local Ethernet IP**. Leaving it blank uses Windows routing. If a VPN chooses the wrong adapter, enter the local IP belonging to the physical driver connection; in the inspected setup that was **192.168.0.10**. This binds the connection to that adapter without editing Windows routes or disabling the VPN. Another PC will need its own local adapter address.

The EPR60 manual maps switches S1=0, S2=1 to 192.168.0.11 when the factory address prefix is retained. For multiple drives, the switch combinations 02 and 03 normally yield .12 and .13. Confirm unique addresses and actual network configuration when commissioning.

## Angles, speed and presets

- **Move by** adds a relative movement from the present command position. **Go to position** moves to a coordinate measured from your chosen zero. For example, repeating Move by 90° adds another quarter turn; repeating Go to 90° stays at 90°. Both accept custom decimal angles and multiple turns. A Go to position preset can target 0°; a relative move must be nonzero. Positive and negative values request opposite directions. Physical clockwise/counterclockwise depends on wiring and the drive direction setting.
- **90°** is a quarter turn; **180°** is a half turn; **360°** is one full turn. **450°** is one and a quarter turns.
- **Gear ratio** means motor revolutions per output revolution. Leave it at **1** for motor-shaft degrees. With a 5:1 reduction, use **5** to enter output-shaft degrees. Verify the mechanism before assuming 1:1 output motion.
- Pulse count = angle / 360 × gear ratio × the drive's actual pulses per motor revolution. The result rounds to the nearest whole pulse, halfway away from zero. The UI shows the achievable angle. Microsteps are command resolution, not a guarantee of mechanical accuracy.
- Speed is **motor RPM**, a whole number. Output degrees/second = motor RPM × 6 / gear ratio. Acceleration/deceleration use motor revolutions per second squared, whole numbers in the documented 10–1000 range. Profile speed and per-move angle limits are editable; they are not cumulative travel limits.
- **Position from zero** tracks the drive's command counter relative to the starting position you chose. EPR60 is open loop; this is not encoder feedback or proof that the mechanism reached the commanded position. A restored position is marked **assumed** because the app cannot verify that the mechanism stayed still while powered off.
- **Load** copies a preset into the editor. **Save** overwrites that PC preset slot. **Run** explicitly starts that saved preset. Loading or saving does not move the motor.
- **Save setup to drive** sends the EPR60 save-current-parameters command, independently of the PC move library. The move library, programs and input-trigger rules remain on the PC; this command does not install them in the drive. Verify drive-parameter retention with a controlled power cycle during commissioning.

Six sample moves are supplied as editable examples. **Add move** expands the library, up to 256 moves per driver; the first six are not a limit. Nothing runs automatically on startup. Multiple drivers are independently controlled; this version does not provide synchronized multi-axis interpolation, continuous jog or servo-brand adapters.

## EPR60 advanced settings and mechanical homing

Choose an EPR60 driver, open **Advanced**, then read its current settings. Running current, standby percentage and standby delay are independent for each drive. These control motor current, not supply voltage. Review the selected driver's old and new values before applying; the app checks and reads back each change. Changes remain in drive RAM until you explicitly save to the drive. Applying changes invalidates that driver's position reference. Establish zero again before motion.

After a live read, the loaded fields can be edited as drafts even when the drive is unavailable for writes. The notice above them explains what must be resolved before **Review changes** becomes available. Editing a draft sends nothing to the drive. A fresh read is still required after movement, Stop, disconnection or five minutes; switching to a different driver never carries the draft across.

Load an RTConfigurator `.rtcfg` file to inspect its values and explanations without connecting hardware. The catalog covers all 300 file addresses; only the supported current and rate fields can be edited. Imported files are never automatically applied. Use **Read all parameters** for the homing configuration and other reference fields.

The dedicated **Review Home movement** control starts EPR60 mechanical homing with register 287=4 after you confirm **Start Home movement**. It requires a configured and tested wired home or limit switch, explicit confirmation, a timeout and a sampled travel stop threshold. Configure the switch, direction, speeds and offset in RTConfigurator first. The threshold is software monitoring and can overshoot between reads; it is not a physical travel limit. An interrupted or failed home leaves zero invalid. A successful, stopped home establishes EtherMotion zero at the drive's reported final position. Open-loop command feedback cannot verify actual shaft travel.

See [EPR60-ADVANCED.md](EPR60-ADVANCED.md) for parameter meanings, persistence, homing requirements and the difference between physical homing and returning to a chosen coordinate.

## Choose zero and return to the starting position

No input pins or home switch are required for a manually chosen zero:

1. Position the mechanism at the intended start, using small **Move by** commands as needed.
2. While it is idle, click **Set this position as 0°**. This records a coordinate on the PC; it does not move the motor or reset the drive's internal counter.
3. Save custom **Go to position** presets such as 35°, 90°, -20° and 0°. Put them in a program, in any order.
4. Use **Return to 0°** or its Ethernet event to return to the zero angle within one turn. The default **Retrace current turn** adds up all movement from your zero, ignores completed turns, and reverses the remaining angle. Set zero once at the intended starting position, rather than before every cycle.

The app saves the last confirmed idle position on this PC. After reconnecting or restarting, it can restore that position even if the drive's command counter reset, **assuming nobody moved the mechanism while it was off**. The display marks this as an assumed position. Reconnection does not move the drive. Request Return to 0° when desired.

Before sending movement, the saved position is marked incomplete. Power loss, a crash or lost communication during movement can leave the final position unknown; that record cannot be restored as a known idle position. Reposition the mechanism and set zero again. Also re-zero after known slipping, a stall, manual movement, or a mechanical/gearing change. The app cannot detect every physical displacement or interrupted move. Profiles and pulse scale must match for a saved reference to be restored.

Zero is a coordinate, not an automatic homing routine. From version 1.3.0, **Return to 0°** treats each full 360° output-shaft turn as an equivalent zero. It uses the combined total from your zero, not just the last move. Positive total travel returns backward through its remaining angle; negative total travel returns forward:

| Previous travel | Return travel with Retrace current turn | Total position after return |
| --- | --- | --- |
| Forward 350° | Backward 350° | 0° |
| Forward 730° | Backward 10° | 720° |
| Backward 730° | Forward 10° | −720° |
| Forward 350°, then backward 40° | Backward 310° | 0° |
| Forward 760°, then backward 60° | Backward 340° | 360° |
| Backward 760°, then forward 60° | Forward 340° | −360° |

This is not the always-shortest route: forward 350° returns backward 350°, as requested, rather than completing another 10° forward. A return already at an equivalent zero sends no movement. **Forward only (+)** and **Backward only (−)** explicitly choose the next zero in that direction; an active limit rejects the request rather than silently reversing it. The screen previews the signed travel. Direction signs follow the drive's command convention, not a universal physical clockwise direction.

The main **Total position from zero** remains cumulative, and **Within this turn** shows the rotary angle. Returning to the zero angle does not reset or move the saved reference: 720° total is 0° within the turn. Existing **Go to total position** presets remain cumulative, so a saved absolute 0° still unwinds to the original total coordinate. This preserves existing saved-cycle behavior. Use the dedicated Return to zero button or Ethernet endpoint when whole turns should be ignored.

The saved total position is enough to calculate the return; no separate direction history is required, including for older idle checkpoints. Return targets use actual drive pulses and gearing, rounded once, so achievable angles can differ slightly from the requested degrees. Very coarse resolution that cannot represent one output turn is refused. Actual travel must fit the configured move limit, and all normal readiness, zero-reference and motion checks still apply.

## Saved cycles and PC events

Use **Cycles** to put moves in the order you want. For example: Axis 1 / move 1 → move 2 → wait 0.5 seconds → move 6 → move 7 → move 8. Move numbers are stable library references; adding a move does not renumber the existing ones. There can be up to 128 programs, each with up to 256 steps.

Home is optional. The Home controls in Advanced and Cycles offer **Return to saved rotary zero** or **Find physical home switch**. Saved-zero return requires an existing valid zero, offers retrace/forward/backward and uses its selected move rates. It preserves completed turns just like the manual Return to 0° control. Physical Home uses the EPR60's Modbus switch search: select its driver, set timeout/travel monitoring limits and confirm its wired switch and physical stopping system have been tested. The drive does not know its physical zero without that reference. Physical Home must complete and save zero before the next step. A failure or Stop ends the cycle; a successful physical Home can establish zero for a later absolute move or saved-zero return. Existing saved Home steps keep their physical meaning.

During motion, **Stop and disconnect** cancels the owning cycle/Home, sends deceleration Stop and waits for confirmed idle before closing the connection. Failure to confirm Stop keeps the connection open when possible and displays the reason. Stop remains available and another press sends another request. Disconnecting a network cable alone does not stop autonomous drive motion. After an interrupted physical Home or uncertain power loss, establish zero again.

A Home row runs each time the sequence reaches it, including every repeated cycle. Homing switch assignments, direction, speeds and offsets are commissioned in RTConfigurator; they are not selected by the saved move library. Other participating drivers remain reserved while Home runs. When transferring a workspace or changing the mechanism, verify its switches and travel again before running saved Home steps.

Choose how the saved cycle runs:

- **Once:** complete the steps once per click or PC event.
- **A set number of times:** repeat the steps 1–10,000 times.
- **Until stopped:** keep repeating until Stop, a fault or a lost connection ends the run.

An optional 0–3600 second pause separates repetitions. The screen shows the current cycle and completed cycles. The app keeps control of participating drivers between repetitions and during the pause. Nothing repeats merely because you save a cycle or reopen the app; click Start cycle or send its PC event. A cycle received while already running is rejected rather than queued.

While a cycle runs, the screen checks progress four times per second. Very short steps can still finish between updates, so each row retains a **Done** count across all repetitions in the current run. The count increases only after that step completes and resets when a new run starts. **Already at target** identifies a completed move that needed no travel. Move completion is verified against the drive's command counter and stopped state; it is not an independent measurement of physical shaft movement. Editing a sequence hides its old row counts until the next run.

Each repetition runs the saved moves exactly as written. Relative moves add travel each time: a cycle containing only Move by 90° keeps adding quarter turns. To repeat the same path and return to the start, use positions such as **35° → 90° → 0°** after establishing zero. Repetition does not automatically return to zero or undo completed moves.

Three step types are supported:

- **Move:** choose a driver and one of its saved moves. The program waits for command completion before advancing.
- **Delay:** wait 0–3600 seconds.
- **Wait for input:** choose a driver's IN1–IN6 signal, the desired high/low level and a timeout of 0.1–3600 seconds. A timeout fails the program and requests Stop; it does not silently skip the condition. High means the drive reports the input as on; verify signal polarity with the actual wiring.

Connect every driver used by the cycle, then press Start cycle. A program can mix relative moves and positions from zero; every driver using a Go to position preset must have a valid zero before starting. The program reserves drivers referenced by both moves and input waits, so manual moves, changing zero and other programs cannot interfere. Stop cancels the entire cycle, including future repetitions, requests a deceleration stop on its participating drives and disables their automatic triggers. It does not add a lock to local controls. Disconnects, alarms, loss of a required zero, or motion-completion timeouts also abort the program. A stopped motor whose command counter has not reached the requested target fails the program. Editing saved moves during a run affects the next run; each run takes a snapshot of its sequence and move values.

An **input trigger rule** starts a program when a selected digital input changes low→high or high→low. Up to 128 rules can be saved. Rules start disabled and must be enabled for each session; connect the input's source driver and every driver used by the program first. Enabling a rule captures the present level, so an already-high signal does not immediately fire a rising-edge rule. Triggers received while the program or a participating driver is busy are skipped, not queued. Sensor inputs are polled approximately every 0.5 seconds, and network delays can extend that interval. Use held signals long enough to be observed; short pulses may be missed. Configure and wire the drive's input functions appropriately during commissioning. The app does not alter I/O assignments.

The simulator provides input toggles so you can try wait conditions and input-trigger rules without hardware. Input simulation never writes real driver outputs.

With your direct local Ethernet connection, the PC runs the program and communicates with the driver over that cable. No internet or router is required. For multiple drives from one PC Ethernet adapter, use a small Ethernet switch and a unique IP per drive. The PC and app must stay running for software sequences and triggers.

## Saving and handoff

Driver profiles, saved moves, programs and input-trigger definitions persist automatically in **%LOCALAPPDATA%\EtherMotion\workspace.json**. Trigger enablement never persists; controls have no arming requirement. **Export workspace** downloads a portable JSON backup without the trigger token. Stop programs and disconnect all drivers before importing a workspace; imports do not connect or move hardware.

The current zero reference and remembered position are stored separately on this PC. They are excluded from workspace exports and cleared by workspace import, so a backup does not transfer an old machine position to a different mechanism. Saved presets retain their relative/position mode and custom angle.

For another PC, double-click **Create transfer ZIP.cmd**. It refreshes **Transfer-workspace.json** from this PC's saved settings and creates a dated ZIP beside this folder, containing the executable, complete source, tests, build recipe and documentation. On the destination PC, extract the ZIP, launch **Start.cmd**, and import **Transfer-workspace.json**. You can also zip/copy the entire folder yourself; refresh the snapshot first if settings have changed. The snapshot is not updated by normal app use.

The transfer helper excludes trigger tokens and position checkpoints, and clears **Local Ethernet IP** in its exported copy so it does not bind to the previous PC's adapter. Verify network addresses, routing and gearing on the new installation, and set zero on the mechanism. The original PC's settings are unchanged. The destination's Ethernet trigger token is local to that installation; update the calling controller to use it. Import replaces the destination workspace, so export anything you want to keep first.

Before publishing the ZIP, the helper checks **BUILDINFO.json** against the executable and every application source/interface file. If the source or EXE has changed, rebuild with **Build.cmd** first. Both a fresh settings export and an existing snapshot are validated by the application's workspace validator before inclusion.

If you launched with a custom `--data` file, pass its path to the helper: `powershell -NoProfile -ExecutionPolicy Bypass -File ".\Create transfer ZIP.ps1" -WorkspacePath "D:\My settings\workspace.json"`. Without that option, it reads `%LOCALAPPDATA%\EtherMotion\workspace.json`; when no saved workspace exists it retains an existing transfer snapshot, or includes just the example if there is no snapshot.

## Ethernet triggers

For a trigger from another program on this same PC, use **http://127.0.0.1:8765** with the normal launcher. For requests from a different computer/controller, close the local service and launch **Start LAN triggers.cmd**. That controller must reach this PC's Ethernet IP and TCP port 8765. Windows firewall rules may need to permit that listener on the intended network; the app does not change firewall or VPN settings. The operator UI remains accessible only from this PC.

In **PC events**, enable triggers for the selected drive or every drive used by your cycle. Copy its token and generated request example. Triggers use **HTTP with JSON**, not raw Modbus coils. A PLC needs HTTP-client support or a bridge; drive communication itself remains Modbus TCP.

See **TRIGGERS.md** for move/program run, Set zero, Return to zero, status and Stop examples. Ethernet events can run a complete sequence ending in a Go to 0° preset; no digital input pins are required. Wired input rules are optional advanced controls. The service must remain running for triggers. Trigger acceptance acknowledges a command, not physical completion. No trigger is queued: requests while the drive/program is busy are rejected.

## Scope and validation

The EPR60 adapter uses the manufacturer's documented register map. Writes are enabled only for identity **0xE060**, the identity read from the user's EPR60; a different identity is readable but blocked from writes until explicitly verified. Other stepper/servo models require their own tested adapters even if RT Configurator also supports them.

**Power indication compatibility:** The [English EP manual](https://www.rtelligentglobal.com/uploads/Rtelligent-EPR60-Series-User-Manual2.pdf), p. 28, defines status bit 10 as POW. The [Chinese EPR60/EPT60 manual](https://www.rtelligent.com/uploads/%E6%B7%B1%E5%9C%B3%E9%94%90%E7%89%B9EPR60%E6%AD%A5%E8%BF%9B%E9%A9%B1%E5%8A%A8%E5%99%A8%E4%BD%BF%E7%94%A8%E6%89%8B%E5%86%8C.pdf), p. 29, also defines POW but contradictorily labels bits 8–15 reserved and always zero. EtherMotion retains the raw POW indication for diagnostics and treats an unset bit as unknown, not proof of missing power. An unset POW bit alone does not block Move; identity, enabled/ready status, alarms, operating modes, idle state and limits still apply. No firmware-specific POW behavior or bus-voltage scaling is assumed from this discrepancy.

**Stopped-state compatibility (1.2.1):** The inspected EPR60, firmware 15, reported command speed −1 RPM after Return to 0° even though MOV was clear, its command counter reached the target, and the operator confirmed the motor had stopped. EtherMotion now confirms this particular state using at least three unchanged counter readings spanning 0.5 seconds, with the drive healthy and ready. A move must reach its exact command target; an acknowledged Stop may finish at an intermediate position. Changing counters, other nonzero speeds, unsupported firmware, or a moving/faulted drive remain blocked. The raw speed reading stays visible. This is compatibility handling for the observed device, not a manufacturer-documented speed tolerance or a measurement of physical shaft position.

Validation covers packet framing, register writes against a mock device, motion conversion, simulated motion, persistence and API controls. **No real motor was moved, configured or saved while building this app. Physical motion and EEPROM retention still require commissioning on the actual mechanism.**

Version 1.2.2 adds an independent local Modbus TCP emulator, end-to-end HTTP tests and endurance checks for thousands of angle operations. It also fixes reconnect-reference validation and browser races around Save, driver selection, event targets and Stop. See **TESTING.md** for results and commands to repeat the tests.

Reference: [Rtelligent EPR60 / EP Series User Manual](https://www.rtelligentglobal.com/uploads/Rtelligent-EPR60-Series-User-Manual2.pdf), pp. 11–18 connection/protocol, pp. 26–29 status, pp. 35–37 modes, pp. 45–47 motion/save parameters, pp. 57–58 motion examples.

## Source layout

- `app.py`: local operator API, workspace storage, trigger authentication and duplicate-event handling.
- `drive.py`: EPR60 Modbus TCP adapter and motion simulator.
- `programs.py`: sequence execution, driver reservation, timed waits and digital input events.
- `epr60_parameters.py`: documented parameter catalog, allowed settings and offline RTConfigurator parsing.
- `homing.py`: explicit Modbus mechanical homing, monitoring, cancellation and position checkpoints.
- `static/`: offline browser interface.
- `EtherMotion.exe`: bundled Windows application in the handoff package, including the Python runtime.
- `Start.cmd` and `Start LAN triggers.cmd`: local-only and LAN-listener launchers; they use the executable when present and otherwise launch the included Python source.
- `Create transfer ZIP.cmd` / `.ps1`, `Transfer-workspace.json`, `TRANSFER.txt` and `QUICKSTART.txt`: refreshable settings export, first-use instructions and complete portable package.
- `Build.cmd`, `build.py`, `requirements-build.txt` and `BUILDING.md`: repeatable Windows EXE build from the included source. Source edits require rebuilding the EXE or running `python app.py` directly.
- `BUILDINFO.json`: build version, runtime/tool versions and source/EXE fingerprints used to reject mismatched packages.
- `README.md` and `TRIGGERS.md`: operation, handoff and HTTP API instructions.
- `tests/`: automated checks using simulators, a mock Modbus peer and loopback HTTP. Run from this folder with `python -m unittest discover -s tests` (Python required for source tests only). Optional frontend readiness checks run with `node tests/test_ui_readiness.js`.

The source is included for maintenance. Implement and validate a separate protocol adapter before adding another drive model; never reuse EPR60 register addresses on an unverified servo.
