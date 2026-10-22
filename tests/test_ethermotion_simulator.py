"""Opt-in end-to-end test of the bundled EtherMotion executable.

Set UALR_RUN_ETHERMOTION_SIM_TEST=1 to run. This uses a temporary workspace
containing only simulator profiles and an ephemeral loopback port. It never
contacts the normal EtherMotion service or any physical drive.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid

from app.ethermotion import EtherMotionClient, EtherMotionError


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@unittest.skipUnless(os.environ.get("UALR_RUN_ETHERMOTION_SIM_TEST") == "1",
                     "Opt-in isolated executable simulator integration")
class EtherMotionSimulatorIntegrationTests(unittest.TestCase):
    def test_completed_once_duplicate_and_active_stop_disables_gate(self):
        import psutil  # Test cleanup follows only this Popen's owned descendants.

        root = Path(__file__).resolve().parents[1]
        executable = root / "EtherMotion" / "EtherMotion.exe"
        fixture = root / "EtherMotion" / "UALR-simulator-workspace.json"
        self.assertTrue(executable.is_file())
        fixture_bytes = fixture.read_bytes()
        workspace = json.loads(fixture_bytes.decode("utf-8-sig"))
        profiles = workspace.get("profiles")
        self.assertIsInstance(profiles, list)
        self.assertTrue(profiles)
        self.assertTrue(all(profile.get("kind") == "simulator" for profile in profiles),
                        "Refuse to launch any workspace containing a physical profile")
        self.assertTrue(all(program.get("repeat_mode") == "once" for program in workspace["programs"]))
        marker = "UALR-ISOLATED-" + uuid.uuid4().hex
        workspace = copy.deepcopy(workspace)
        for profile in workspace["profiles"]:
            profile["name"] = marker
        for program in workspace["programs"]:
            program["name"] = marker
        driver_id = workspace["profiles"][0]["id"]
        program_id = workspace["programs"][0]["id"]
        process = None
        owned_descendants = []
        output = {}
        # TemporaryDirectory removes only its explicitly created temporary tree.
        # No saved user workspace or original EtherMotion files are modified.
        with tempfile.TemporaryDirectory(prefix="ualr-simulator-test-") as directory:
            temporary_root = Path(directory).resolve()
            workspace_path = temporary_root / "workspace.json"
            self.assertEqual(workspace_path.parent, temporary_root)
            workspace_path.write_text(json.dumps(workspace, indent=2), encoding="utf-8")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            validation = subprocess.run(
                [str(executable), "--export-workspace", str(workspace_path)],
                cwd=str(temporary_root), capture_output=True, text=True,
                timeout=30, creationflags=flags,
            )
            self.assertEqual(validation.returncode, 0, "Bundled EtherMotion rejected simulator fixture")
            validated = json.loads(validation.stdout)
            self.assertTrue(all(p.get("kind") == "simulator" for p in validated["profiles"]))
            self.assertEqual({p["name"] for p in validated["profiles"]}, {marker})
            workspace_path.write_text(json.dumps(validated, indent=2), encoding="utf-8")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            self.assertNotEqual(port, 8765)
            self.assertGreater(port, 1024)
            base_url = f"http://127.0.0.1:{port}"
            self.assertEqual(urlsplit(base_url).hostname, "127.0.0.1")
            opener = build_opener(ProxyHandler({}), _NoRedirects())

            def operator_request(path, body=None, csrf=""):
                # Every request is constrained to the test's exact endpoint.
                self.assertTrue(path.startswith("/api/"))
                self.assertNotEqual(urlsplit(base_url).port, 8765)
                headers = {"Accept": "application/json"}
                data = None
                if body is not None:
                    headers.update({"Content-Type": "application/json", "X-App-Token": csrf})
                    data = json.dumps(body).encode("utf-8")
                request = Request(base_url + path, data=data, headers=headers,
                                  method="POST" if body is not None else "GET")
                with opener.open(request, timeout=2) as response:
                    return json.loads(response.read(1024 * 1024))

            def assert_isolated(state):
                actual = state.get("profiles", [])
                self.assertTrue(actual)
                self.assertTrue(all(p.get("kind") == "simulator" for p in actual))
                self.assertEqual({p["name"] for p in actual}, {marker})
                self.assertEqual({p["id"] for p in actual}, {p["id"] for p in validated["profiles"]})
                self.assertEqual(state.get("trigger_port"), port)
                self.assertFalse(state.get("lan_enabled"))

            try:
                process = subprocess.Popen(
                    [str(executable), "--data", str(workspace_path), "--port", str(port), "--no-browser"],
                    cwd=str(temporary_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
                self.assertGreater(process.pid, 0)
                deadline = time.monotonic() + 20
                state = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(f"Isolated EtherMotion exited with code {process.returncode}")
                    try:
                        state = operator_request("/api/state")
                        break
                    except OSError:
                        time.sleep(0.05)
                self.assertIsNotNone(state, "Isolated EtherMotion did not start within 20 seconds")
                # Verify the nonce before sending the first state-changing request.
                assert_isolated(state)
                owned_descendants = psutil.Process(process.pid).children(recursive=True)
                csrf = operator_request("/api/session")["csrf_token"]
                connected = operator_request("/api/connect", {"id": driver_id}, csrf)["state"]
                assert_isolated(connected)
                self.assertEqual(connected["runtime"][driver_id]["status"]["device_id"], "SIMULATOR")
                enabled = operator_request("/api/remote", {"id": driver_id, "enabled": True}, csrf)["state"]
                assert_isolated(enabled)
                client = EtherMotionClient(base_url, timeout=2)
                discovered = client.discover()
                assert_isolated(discovered)
                self.assertTrue(any(p["id"] == program_id for p in client.list_once_programs(discovered)))
                self.assertEqual(client.check_ready(program_id)["participants"], [driver_id])
                initial_run = client.program_status(program_id).get("run_id")
                request_id = "ualr-test-" + uuid.uuid4().hex
                accepted = client.trigger(program_id, request_id)
                self.assertTrue(accepted["ok"])
                self.assertFalse(accepted["duplicate"])
                statuses = []
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    current = client.program_status(program_id)
                    statuses.append(current)
                    if current.get("run_id") != initial_run and current.get("status") == "completed" and not current.get("running"):
                        break
                    if current.get("status") in {"failed", "error", "stopped"}:
                        self.fail("Simulator cycle failed: " + str(current.get("error") or current.get("status")))
                    time.sleep(0.025)
                self.assertEqual(current.get("status"), "completed")
                completed_run = current["run_id"]
                self.assertNotEqual(completed_run, initial_run)
                self.assertEqual(current["cycles_completed"], 1)
                self.assertEqual(current["completed_steps"], 3)
                after = client.discover()
                assert_isolated(after)
                self.assertAlmostEqual(after["runtime"][driver_id]["status"]["position_degrees"], 0.0, places=6)
                duplicate = client.trigger(program_id, request_id)
                self.assertTrue(duplicate["duplicate"])
                time.sleep(0.4)
                unchanged = client.program_status(program_id)
                self.assertEqual(unchanged["run_id"], completed_run)
                self.assertEqual(unchanged["cycles_completed"], 1)
                self.assertFalse(unchanged["running"])

                # Capture idle-Stop semantics without assuming that it disables
                # remote gates in this EtherMotion version. Active Stop below
                # must disable the gate and block any following motion request.
                client.stop(program_id, "ualr-idle-stop-" + uuid.uuid4().hex)
                idle_stopped = client.discover()
                assert_isolated(idle_stopped)
                idle_remote_enabled = idle_stopped["runtime"][driver_id]["remote_enabled"]
                if not idle_remote_enabled:
                    operator_request("/api/remote", {"id": driver_id, "enabled": True}, csrf)
                client.trigger(program_id, "ualr-active-stop-run-" + uuid.uuid4().hex)
                active = client.program_status(program_id)
                self.assertNotEqual(active["run_id"], completed_run)
                self.assertTrue(active["running"])
                stop_ack = client.stop(program_id, "ualr-active-stop-" + uuid.uuid4().hex)
                self.assertTrue(stop_ack["ok"])
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    stopped = client.program_status(program_id)
                    if not stopped.get("running"):
                        break
                    time.sleep(0.025)
                self.assertFalse(stopped.get("running"))
                self.assertEqual(stopped.get("status"), "stopped")
                final = client.discover()
                assert_isolated(final)
                self.assertFalse(final["runtime"][driver_id]["remote_enabled"])
                with self.assertRaises(EtherMotionError):
                    client.trigger(program_id, "ualr-after-stop-" + uuid.uuid4().hex)
                self.assertEqual(client.program_status(program_id)["run_id"], active["run_id"])
                output = {"port": port, "simulator_profiles": len(validated["profiles"]),
                          "completed_cycles": current["cycles_completed"], "completed_steps": current["completed_steps"],
                          "returned_command_position_degrees": after["runtime"][driver_id]["status"]["position_degrees"],
                          "duplicate_request_did_not_restart": True,
                          "idle_stop_remote_enabled": idle_remote_enabled,
                          "active_stop_disabled_remote_gate": True, "physical_profiles": 0}
            finally:
                if process is not None:
                    try:
                        if process.poll() is None:
                            owned_descendants = psutil.Process(process.pid).children(recursive=True)
                    except psutil.NoSuchProcess:
                        pass
                    # Onefile executables can have a bootloader child. Terminate
                    # only processes obtained from this exact Popen's family.
                    for child in reversed(owned_descendants):
                        try:
                            child.terminate()
                        except psutil.NoSuchProcess:
                            pass
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    _gone, surviving = psutil.wait_procs(owned_descendants, timeout=3)
                    for child in surviving:
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    _gone, surviving = psutil.wait_procs(surviving, timeout=3)
                    self.assertFalse(surviving, "Owned simulator executable did not terminate")
                self.assertEqual(fixture.read_bytes(), fixture_bytes)
        print("Isolated EtherMotion simulator evidence: " + json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
