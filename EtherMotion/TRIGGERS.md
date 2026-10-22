# Ethernet trigger reference

For another application on this same PC, use the normal launcher and address `127.0.0.1`. The PC can connect directly to the EPR60 by Ethernet; no router, internet service or second computer is required. For requests from another computer, launch `Start LAN triggers.cmd` and use this PC's reachable Ethernet address. Connect a drive and enable that drive's Ethernet triggers under **PC events**. No Arm or unlock step is required. Replace `TOKEN` and `epr60-1` below with the workspace token and driver ID shown by the app. For another computer, also change `$base` to this PC's reachable Ethernet address. Move numbers start at 1 and extend to the number of saved moves (up to 256).

## Run a preset

```powershell
$base = 'http://127.0.0.1:8765'
$headers = @{ Authorization = 'Bearer TOKEN' }
$body = @{ request_id = 'cycle-000001' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/trigger/epr60-1/1" -Headers $headers -ContentType 'application/json' -Body $body
```

A saved move retains its mode: Move by adds travel; Go to position targets the chosen coordinate from zero and requires a valid zero. A Go to 0° preset can finish a program at its starting position.

A new intended movement needs a new request ID. To retry the same event after an HTTP timeout, reuse its original ID and body. Within one service run, duplicate IDs return the original result without starting another move. A reused ID for a different drive/slot or different rate parameters is rejected. Failed and uncertain requests are cached too, so repeated delivery cannot silently retry a possibly-started move.

HTTP **202** means the command was acknowledged, not completed. HTTP **409** means a valid trigger was refused (for example, busy, disconnected, not ready or alarmed). **401** means an invalid/missing token. **400** means a malformed request. A response contains `ok`, `request_id`, `driver_id`, `slot`, `operation` and `duplicate`, plus a message or error.

Requests are serialized; they are not a synchronized multi-axis command. Do not queue movement by hammering the endpoint while busy. The in-memory event cache holds up to 10,000 event IDs and then refuses new move/program-run events until restart. Stop remains available when the cache is full; new Stop events beyond the cache limit are not cached. IDs are not remembered across service restarts; physical axes restart disconnected and all trigger gates restart disabled. Reconcile the mechanism's state before enabling triggers again.

## Read state

```powershell
Invoke-RestMethod -Uri "$base/trigger/epr60-1/status" -Headers $headers
```

This returns the cached drive state, updated approximately twice a second while connected: `connected`, `remote_enabled`, and a `status` object including `busy`, `alarm`, `alarm_active`, `position_degrees`, `motion_unconfirmed` and `speed_rpm`. Zero-related fields are `zero_valid`, `zero_reason`, `position_from_zero_degrees`, `position_assumed` and `zero_source` (`manual`, `restored` or `unset`). `position_degrees` is the raw command-counter angle; use `position_from_zero_degrees` for the coordinate relative to your chosen start. Require a healthy connection and no unresolved alarm or motion uncertainty when interpreting completion. The reported angle is commanded position, not encoder feedback. A physical sensor is needed when the application must prove the mechanism reached a position.

For older clients, the legacy `armed` status field now mirrors the connection state and `arm_expires_at` is null. There is no arming gate. Check the actual driver status for readiness, alarms and busy state; the app checks these again before starting motion.

## Set zero and return to zero

With the mechanism at the intended starting position and the driver idle, record zero:

```powershell
$body = @{ request_id = 'set-start-000001' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/trigger/epr60-1/set-zero" -Headers $headers -ContentType 'application/json' -Body $body
```

This changes the PC's reference only. It does not move the motor, reset its command counter or run a homing operation. Set zero once when establishing the starting position; do not reset it before every cycle. A duplicate delivery of the same request ID returns the original result without changing zero again.

Return to the equivalent zero angle within one output-shaft turn while the motor is powered:

```powershell
$body = @{
    request_id = 'return-start-000001'
    direction = 'retrace'
    speed_rpm = 10
    accel_rps2 = 10
    decel_rps2 = 10
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/trigger/epr60-1/return-zero" -Headers $headers -ContentType 'application/json' -Body $body
```

Rates are optional for Return to zero: speed defaults to the lesser of 10 motor RPM or the profile speed limit, with acceleration/deceleration both 10 revolutions/second squared. The optional `direction` is `retrace` (default), `forward` or `backward`. Retrace uses the signed combined total from your zero, ignores completed turns, and reverses the remaining angle. Thus +350° then −40° returns −310°; +760° then −60° totals +700° and returns −340° to total +360°. Negative totals reverse forward. It is not an always-shortest return and does not follow the direction of the last individual move. Explicit forward/backward returns choose the equivalent zero in that direction. A blocked direction never silently switches to the other direction.

Other trigger operations reject rate/direction overrides; saved moves use their saved settings. Set zero and Return to zero require the same connection, drive-readiness and Ethernet-trigger gates as a preset. A running program reserves its drivers and prevents either action from interfering. Changing `direction` while reusing a request ID is a different event and is rejected; retries must use the same body.

The PC saves each confirmed idle position and may restore it after reconnecting, assuming the mechanism did not move while off. The restored position is marked `position_assumed: true`; reconnecting does not move the driver. A checkpoint interrupted during movement is not restored as a known position. Re-establish zero after uncertain movement, slipping or manual displacement. `position_from_zero_degrees` remains cumulative; `position_phase_degrees` reports the within-turn angle. Return to zero preserves the cumulative coordinate (730° → 720°, phase 0°). Existing absolute Go to total position 0° presets still return through all stored turns. When already at a representable zero angle, Return to zero acknowledges a no-op. Older idle checkpoints need no direction-history migration.

## Stop

```powershell
$body = @{ request_id = 'stop-000001' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/trigger/epr60-1/stop" -Headers $headers -ContentType 'application/json' -Body $body
```

An authenticated Stop can be requested even if the preset-trigger gate is disabled. It disables automatic triggers and sends the drive's deceleration-stop command when connected. If the driver belongs to a running program, Stop cancels that entire program and requests Stop on all of its participating drivers. It does not remove motor power or replace a physical emergency stop. No network command can guarantee stopping after connection loss.

## Connection layout

`PLC / application → HTTP trigger → EtherMotion PC → Modbus TCP → selected EPR60`

This PC bridges the two protocols. The PC and service must remain running. For PLCs that support only Modbus TCP rather than HTTP requests, use a supported HTTP bridge or add a separately tested Modbus trigger-server adapter; this release does not expose a PLC Modbus-server register map.

The token permits motion requests: give it only to intended controllers. This service is intended for a trusted machine-control LAN; HTTP traffic is not encrypted. The app exposes no public cloud endpoint and does not alter network security settings.

## Trigger a saved cycle

Every driver participating in an HTTP-triggered program—including drivers used only for input-wait steps—must be connected, ready and have Ethernet triggers enabled. Any driver with a Go to position step also needs a valid zero before the program starts. This also applies to HTTP requests from the same PC. The run snapshots saved move values; later edits do not change a program already in progress. A workspace supports up to 128 programs, each with up to 256 steps.

The event uses the cycle's saved repeat settings: `repeat_mode` is `once`, `count` or `until_stopped`; `repeat_count` is 1–10,000; `cycle_delay_s` is the pause between repetitions, from 0 to 3600 seconds. Existing cycles without these fields run once. Set **Once** if each PC event should produce exactly one cycle. Set **Until stopped** if one event should start continuous repetition until a Stop event. Each start snapshots the settings; it does not change an existing run or queue another run.

```powershell
$headers = @{ Authorization = 'Bearer TOKEN' }
$body = @{ request_id = [guid]::NewGuid().ToString() } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/program-trigger/demo-cycle" -Headers $headers -ContentType 'application/json' -Body $body
```

Poll `GET /program-trigger/PROGRAM_ID/status` with the same Authorization header. `running`, `status`, `step_index` (zero based), `step_count`, and `error` describe the sequence. Program acceptance is HTTP202; it does not mean the steps finished. Status `completed` indicates command-level completion; it cannot prove open-loop physical positioning.

`cycle_number` is the current repetition, starting at 1; `cycles_completed` counts fully completed repetitions. `repeat_mode` and `repeat_count` report the settings captured at the start. A repeat-until-stopped run remains running during pauses between cycles and ends with `stopped` when cancelled. Relative steps add their movement on every repetition; use absolute positions ending at 0° when the intended cycle returns to the same starting position.

To cancel a program, send `POST /program-trigger/PROGRAM_ID/stop` with the same token and a fresh `request_id`. Cancellation stops current motion and all future repetitions, and disables affected Ethernet and wired input triggers. Local controls remain available once the drivers are idle. Stop does not require trigger enablement.

Program triggers share the move-trigger duplicate-event cache. Reuse the same request body for a retry of one event; generate a new request ID for a new intended run or a new deliberate Stop attempt. Re-delivering the same Stop request ID does not send another command. Do not blindly restart a failed sequence: relative moves already completed are not rolled back.

Saved cycles may include `type: "return_zero"` with `driver_id`, `direction` (`retrace`, `forward`, `backward`), `speed_rpm`, `accel_rps2` and `decel_rps2`. This uses the same rotary return semantics as the endpoint above, keeps completed turns and waits for verified command completion. It needs a valid zero before execution; an earlier successful physical `type: "home"` step on that driver can establish it. Physical Home remains a deliberate native switch search and requires its commissioned hardware. Neither return mode starts automatically on connection or workspace import.

Optional sensor input rules are under Advanced in the operator UI and do not require HTTP traffic or the LAN launcher. They are unnecessary for Ethernet-only events. The PC reads the EPR60's digital input state over its direct Ethernet connection. A physical sensor still needs to be wired to the drive. Rules sample approximately every 0.5 seconds; network delays can lengthen the interval, so use held signals and do not rely on short pulse capture. Enabling a rule captures the current input baseline and waits for a new edge. A Wait for input step accepts a level already high/low or reached later, and has a finite timeout. Input-rule and sequence execution require this PC and the app to stay running; they are not downloaded to the driver.
