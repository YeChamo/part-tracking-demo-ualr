"""EtherMotion contract tests using only a local fake HTTP service."""
import copy
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import unittest

from app.ethermotion import EtherMotionClient, EtherMotionError


def healthy_state():
    axis = {
        "connected": True, "remote_enabled": True, "program_owner": None, "error": "",
        "status": {"connected": True, "busy": False, "hardware_busy": False,
                   "alarm": 0, "alarm_active": False, "enabled": True, "ready": True,
                   "configured": True, "identity_verified": True,
                   "motion_unconfirmed": False, "zero_valid": True},
    }
    return {
        "trigger_token": "test-secret-never-log",
        "profiles": [{"id": "reject-axis", "name": "Reject gate"}],
        "programs": [{"id": "reject-once", "name": "Reject one bottle", "repeat_mode": "once",
                      "steps": [{"type": "move", "driver_id": "reject-axis", "slot": 1},
                                {"type": "delay", "seconds": 0.1},
                                {"type": "move", "driver_id": "reject-axis", "slot": 2}]}],
        "presets": {"reject-axis": [{"mode": "absolute"}, {"mode": "absolute"}]},
        "runtime": {"reject-axis": axis}, "program_runtime": {},
    }


@contextmanager
def fake_service():
    class Service:
        state = healthy_state()
        requests = []
        accepted = {}
        run_count = 0
        current = {"ok": True, "running": False, "status": "idle"}
        error_code = None
        error_body = None
        drop_response = False
        on_discover = None

    service = Service()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            service.requests.append(("GET", self.path, None, self.headers.get("Authorization")))
            if self.path == "/api/state":
                if service.on_discover:
                    service.on_discover()
                self.send_json(200, service.state)
            elif self.path == "/program-trigger/reject-once/status":
                self.send_json(200, service.current)
            else:
                self.send_json(404, {"ok": False, "error": "Not found"})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            service.requests.append(("POST", self.path, body, self.headers.get("Authorization")))
            if service.drop_response:
                self.close_connection = True
                return
            if service.error_code:
                self.send_json(service.error_code, service.error_body or {"ok": False, "error": "Refused"})
                return
            if self.headers.get("Authorization") != "Bearer " + service.state["trigger_token"]:
                self.send_json(401, {"ok": False, "error": "A valid trigger token is required."})
                return
            request_id = body["request_id"]
            if request_id in service.accepted:
                self.send_json(202, dict(service.accepted[request_id], duplicate=True))
                return
            if self.path.endswith("/stop"):
                result = {"ok": True, "request_id": request_id, "operation": "stop", "duplicate": False}
                service.current = {"ok": True, "running": False, "status": "stopped", "run_id": "run-1"}
            else:
                service.run_count += 1
                result = {"ok": True, "program_id": "reject-once", "request_id": request_id,
                          "operation": "run", "duplicate": False,
                          "message": "Program accepted. Poll status for completion."}
                service.current = {"ok": True, "running": True, "status": "running", "run_id": "run-1"}
            service.accepted[request_id] = result
            self.send_json(202, result)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    service.url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield service
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class EtherMotionTests(unittest.TestCase):
    def test_discovery_and_acknowledgement_are_not_completion(self):
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            state = client.discover()
            self.assertEqual(client.list_once_programs(state), [{"id": "reject-once", "name": "Reject one bottle"}])
            accepted = client.trigger("reject-once", "bottle-001")
            self.assertTrue(accepted["ok"])
            self.assertNotIn("status", accepted)
            self.assertEqual(client.program_status("reject-once")["status"], "running")
            service.current.update(status="completed", running=False)
            completed = client.program_status("reject-once")
            self.assertEqual(completed["run_id"], "run-1")
            self.assertEqual(completed["status"], "completed")
            post = next(request for request in service.requests if request[0] == "POST")
            self.assertEqual(post[3], "Bearer " + state["trigger_token"])

    def test_event_id_is_forwarded_unchanged_for_server_deduplication(self):
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            first = client.trigger("reject-once", "session:bottle-001")
            second = client.trigger("reject-once", "session:bottle-001")
            self.assertFalse(first["duplicate"])
            self.assertTrue(second["duplicate"])
            self.assertEqual(service.run_count, 1)
            posts = [request for request in service.requests if request[0] == "POST"]
            self.assertEqual([p[2] for p in posts], [{"request_id": "session:bottle-001"}] * 2)

    def test_repeating_program_is_blocked_even_if_changed_after_discovery(self):
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            client.discover()
            service.state["programs"][0]["repeat_mode"] = "until_stopped"
            self.assertEqual(client.list_once_programs(service.state), [])
            with self.assertRaisesRegex(EtherMotionError, "Once"):
                client.trigger("reject-once", "bottle-002")
            self.assertFalse(any(r[0] == "POST" for r in service.requests))

    def test_unhealthy_or_wait_only_participant_blocks_motion(self):
        scenarios = [
            ("connected", False, False), ("remote_enabled", False, False),
            ("busy", True, True), ("alarm_active", True, True),
            ("ready", False, True), ("motion_unconfirmed", True, True),
            ("zero_valid", False, True), ("identity_verified", False, True),
        ]
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            for key, value, nested in scenarios:
                with self.subTest(key=key):
                    service.state = healthy_state()
                    axis = service.state["runtime"]["reject-axis"]
                    (axis["status"] if nested else axis)[key] = value
                    with self.assertRaises(EtherMotionError):
                        client.trigger("reject-once", "bottle-unhealthy")
            service.state = healthy_state()
            service.state["runtime"]["reject-axis"]["status"].pop("ready")
            with self.assertRaisesRegex(EtherMotionError, "ready"):
                client.trigger("reject-once", "bottle-ready-field-missing")
            service.state = healthy_state()
            service.state["programs"][0]["steps"].append({"type": "wait_input", "driver_id": "sensor-axis", "input": 1, "level": True})
            service.state["runtime"]["sensor-axis"] = copy.deepcopy(service.state["runtime"]["reject-axis"])
            service.state["runtime"]["sensor-axis"]["remote_enabled"] = False
            with self.assertRaisesRegex(EtherMotionError, "Ethernet triggers"):
                client.trigger("reject-once", "bottle-wait")
            self.assertFalse(any(r[0] == "POST" for r in service.requests))

    def test_refusal_is_not_retried_and_token_is_redacted(self):
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            service.error_code = 409
            service.error_body = {"ok": False, "error": "Busy " + service.state["trigger_token"]}
            with self.assertRaises(EtherMotionError) as caught:
                client.trigger("reject-once", "bottle-refused")
            self.assertEqual(caught.exception.status_code, 409)
            self.assertFalse(caught.exception.uncertain)
            self.assertNotIn(service.state["trigger_token"], str(caught.exception))
            self.assertEqual(sum(r[0] == "POST" for r in service.requests), 1)

    def test_lost_post_response_is_uncertain_and_is_not_retried(self):
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            service.drop_response = True
            with self.assertRaises(EtherMotionError) as caught:
                client.trigger("reject-once", "bottle-lost")
            self.assertTrue(caught.exception.uncertain)
            self.assertEqual(sum(r[0] == "POST" for r in service.requests), 1)

    def test_stop_bypasses_readiness_and_preserves_operation(self):
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            client.discover()
            service.state["runtime"]["reject-axis"]["remote_enabled"] = False
            result = client.stop("reject-once", "stop-001")
            self.assertEqual(result["operation"], "stop")
            self.assertEqual(service.requests[-1][1], "/program-trigger/reject-once/stop")

    def test_cancellation_during_readiness_check_prevents_post(self):
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            permission = threading.Event()
            permission.set()
            service.on_discover = permission.clear
            with self.assertRaisesRegex(EtherMotionError, "cancelled") as caught:
                client.trigger("reject-once", "bottle-cancelled", allow_send=permission.is_set)
            self.assertFalse(caught.exception.uncertain)
            self.assertTrue(any(request[1] == "/api/state" for request in service.requests))
            self.assertFalse(any(request[0] == "POST" for request in service.requests))

    def test_deadline_is_rechecked_after_readiness_check(self):
        with fake_service() as service:
            client = EtherMotionClient(service.url)
            deadline = time.monotonic() + 0.05
            service.on_discover = lambda: time.sleep(0.08)
            with self.assertRaisesRegex(EtherMotionError, "deadline expired") as caught:
                client.trigger("reject-once", "bottle-expired", deadline=deadline)
            self.assertFalse(caught.exception.uncertain)
            self.assertFalse(any(request[0] == "POST" for request in service.requests))

    def test_active_permission_and_future_deadline_accept_once(self):
        with fake_service() as service:
            result = EtherMotionClient(service.url).trigger(
                "reject-once", "bottle-permitted", allow_send=lambda: True,
                deadline=time.monotonic() + 5,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(sum(request[0] == "POST" for request in service.requests), 1)

    def test_unavailable_service_has_clear_error(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        unused_port = server.server_port
        server.server_close()
        with self.assertRaisesRegex(EtherMotionError, "unavailable"):
            EtherMotionClient(f"http://127.0.0.1:{unused_port}", timeout=0.05).discover()

    def test_base_url_rejects_public_hosts_paths_and_credentials(self):
        for url in ("http://8.8.8.8:8765", "https://example.com", "http://127.0.0.1/api", "http://user:pass@127.0.0.1", "file:///tmp", "http://127.0.0.1?x=y", "http://0.0.0.0"):
            with self.subTest(url=url), self.assertRaises(EtherMotionError):
                EtherMotionClient(url)
        for url in ("http://localhost:8765/", "http://192.168.0.11:8765", "https://[::1]:8765", "http://[fd00::1]:8765"):
            self.assertTrue(EtherMotionClient(url).base_url)

    def test_program_and_event_identifiers_cannot_add_paths(self):
        client = EtherMotionClient()
        with self.assertRaises(EtherMotionError):
            client.program_status("../../api/state")
        with self.assertRaises(EtherMotionError):
            client.stop("reject-once", "event\nAuthorization: secret")


if __name__ == "__main__":
    unittest.main()
