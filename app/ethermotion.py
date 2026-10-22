"""Small, synchronous bridge to EtherMotion's authenticated cycle API.

This module never connects an axis, enables a trigger gate, or retries a motion
request.  A 202 response is an acknowledgement; poll ``program_status`` and its
``run_id`` to establish command-level completion.
"""
from __future__ import annotations

import ipaddress
import json
import math
import re
import socket
import time
from http.client import HTTPException
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class EtherMotionError(RuntimeError):
    """Integration failure; ``uncertain`` means a POST may have reached service."""

    def __init__(self, message, *, status_code=None, uncertain=False):
        super().__init__(message)
        self.status_code = status_code
        self.uncertain = uncertain


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class EtherMotionClient:
    """Access localhost or a numeric private/link-local LAN EtherMotion address.

    EtherMotion's discovery endpoint is available only to clients on its PC.
    The numeric LAN URL option is useful when a trusted proxy supplies that
    endpoint.  Public addresses, URL credentials, and paths are not accepted.
    """

    _PROGRAM_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
    _REQUEST_ID = re.compile(r"[A-Za-z0-9_.:-]{1,100}\Z")
    _LAN_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "169.254.0.0/16", "fc00::/7", "fe80::/10",
    ))
    _MAX_BODY = 1024 * 1024

    def __init__(self, base_url="http://127.0.0.1:8765", token="", timeout=1.0):
        self.base_url = self._validate_base_url(base_url)
        if not isinstance(token, str) or any(ord(char) < 32 for char in token):
            raise EtherMotionError("EtherMotion token must be text without control characters.")
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not 0 < timeout <= 30:
            raise EtherMotionError("EtherMotion timeout must be between 0 and 30 seconds.")
        self.token = token.strip()
        self.timeout = float(timeout)
        # Do not send credentials through an environment-configured HTTP proxy
        # or follow a service redirect to a different host/path.
        self._opener = build_opener(ProxyHandler({}), _NoRedirects())

    @classmethod
    def _validate_base_url(cls, value):
        if not isinstance(value, str):
            raise EtherMotionError("Enter an EtherMotion HTTP address.")
        try:
            parsed = urlsplit(value.strip())
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                    or any(ord(char) < 33 for char in value.strip())):
                raise ValueError
            port = parsed.port
            if port is not None and not 1 <= port <= 65535:
                raise ValueError
            host = parsed.hostname.lower()
            if host != "localhost":
                address = ipaddress.ip_address(host)
                if not address.is_loopback and not any(address in net for net in cls._LAN_NETWORKS):
                    raise ValueError
        except (ValueError, TypeError):
            raise EtherMotionError(
                "Use http(s)://localhost:PORT or a numeric loopback/private LAN address, without a path or credentials."
            ) from None
        return parsed.geturl().rstrip("/")

    def _clean_message(self, value):
        message = str(value)
        if self.token:
            message = message.replace(self.token, "[redacted]")
        return " ".join(message.split())[:500]

    def _decode(self, raw, *, status_code=None, uncertain=False):
        if len(raw) > self._MAX_BODY:
            raise EtherMotionError("EtherMotion response exceeded 1 MB.", status_code=status_code, uncertain=uncertain)
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeError, ValueError):
            raise EtherMotionError("EtherMotion returned an invalid JSON response.", status_code=status_code, uncertain=uncertain) from None
        if not isinstance(payload, dict):
            raise EtherMotionError("EtherMotion response must be a JSON object.", status_code=status_code, uncertain=uncertain)
        return payload

    def _request(self, method, path, body=None, *, expected=200, motion=False):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        data = None
        if body is not None:
            if not self.token:
                raise EtherMotionError("Discover EtherMotion or enter its trigger token before sending a command.")
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, allow_nan=False).encode("utf-8")
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                status_code = response.status
                raw = response.read(self._MAX_BODY + 1)
        except HTTPError as exc:
            status_code = exc.code
            try:
                payload = self._decode(exc.read(self._MAX_BODY + 1), status_code=status_code)
                detail = self._clean_message(payload.get("error") or payload.get("message") or "Request refused.")
            except (EtherMotionError, OSError, HTTPException):
                detail = "Request refused."
            finally:
                exc.close()
            # A 4xx refusal is definite; a server error after POST is uncertain.
            raise EtherMotionError(
                f"EtherMotion HTTP {status_code}: {detail}", status_code=status_code,
                uncertain=motion and status_code >= 500,
            ) from None
        except (URLError, OSError, TimeoutError, socket.timeout, HTTPException):
            message = "EtherMotion is unavailable or did not respond in time."
            if motion:
                message += " The command result is uncertain; do not resend with a new event ID."
            raise EtherMotionError(message, uncertain=motion) from None
        payload = self._decode(raw, status_code=status_code, uncertain=motion)
        if status_code != expected:
            raise EtherMotionError(
                f"EtherMotion returned HTTP {status_code}; expected HTTP {expected}.",
                status_code=status_code, uncertain=motion,
            )
        if payload.get("ok") is False:
            detail = self._clean_message(payload.get("error") or "Request was not accepted.")
            raise EtherMotionError(f"EtherMotion: {detail}", status_code=status_code)
        return payload

    def discover(self):
        """Read current saved configuration/runtime; never change machine state.

        The returned dict contains the local API's trigger token.  Keep it in the
        backend, not logs or browser responses.  A manually supplied token is
        never replaced silently.  Clear ``client.token`` explicitly before a
        fresh discovery if the service's token was deliberately changed.
        """
        state = self._request("GET", "/api/state")
        if not isinstance(state.get("programs"), list) or not isinstance(state.get("runtime"), dict):
            raise EtherMotionError("EtherMotion discovery is missing programs or driver runtime.")
        if (not isinstance(state.get("profiles", []), list)
                or not isinstance(state.get("presets", {}), dict)
                or not isinstance(state.get("program_runtime", {}), dict)):
            raise EtherMotionError("EtherMotion discovery contains invalid configuration or program runtime.")
        if not self.token:
            token = state.get("trigger_token")
            if isinstance(token, str) and token.strip() and not any(ord(char) < 32 for char in token):
                self.token = token.strip()
        return state

    @staticmethod
    def list_once_programs(state):
        """Return display choices only for saved cycles configured to run once."""
        programs = state.get("programs", []) if isinstance(state, dict) else []
        if not isinstance(programs, list):
            return []
        return [
            {"id": program["id"], "name": str(program.get("name") or program["id"])}
            for program in programs
            if isinstance(program, dict) and isinstance(program.get("id"), str)
            and EtherMotionClient._PROGRAM_ID.fullmatch(program["id"])
            and program.get("repeat_mode", "once") == "once"
        ]

    @classmethod
    def _program_id(cls, value):
        if not isinstance(value, str) or not cls._PROGRAM_ID.fullmatch(value):
            raise EtherMotionError("Choose a valid saved EtherMotion program ID.")
        return value

    @classmethod
    def _request_id(cls, value):
        if not isinstance(value, str) or not cls._REQUEST_ID.fullmatch(value):
            raise EtherMotionError("Use a unique event ID containing 1–100 letters, numbers, dots, colons, underscores or dashes.")
        return value

    def check_ready(self, program_id):
        """Check current Once configuration and every driver without moving it."""
        program_id = self._program_id(program_id)
        state = self.discover()
        program = next((p for p in state["programs"] if isinstance(p, dict) and p.get("id") == program_id), None)
        if program is None:
            raise EtherMotionError("The selected reject program no longer exists in EtherMotion.")
        if program.get("repeat_mode", "once") != "once":
            raise EtherMotionError("The reject program must use Once; repeating cycles cannot reject individual bottles.")
        program_runtime = state.get("program_runtime", {}).get(program_id, {})
        if not isinstance(program_runtime, dict):
            raise EtherMotionError("EtherMotion returned invalid reject-program runtime.")
        if program_runtime.get("running") or program_runtime.get("status") in ("running", "stopping"):
            raise EtherMotionError("The reject program is busy; EtherMotion does not queue cycle requests.")
        steps = program.get("steps")
        if not isinstance(steps, list) or not steps or not all(isinstance(step, dict) for step in steps):
            raise EtherMotionError("The reject program has no valid saved steps.")
        for step in steps:
            if step.get("type") not in ("delay", "move", "home", "return_zero", "wait_input"):
                raise EtherMotionError("The reject program contains an unsupported saved step.")
            if step["type"] != "delay" and not isinstance(step.get("driver_id"), str):
                raise EtherMotionError("The reject program contains a step without a driver.")
        participants = sorted({step["driver_id"] for step in steps if isinstance(step.get("driver_id"), str)})
        if not participants:
            raise EtherMotionError("The reject program must contain a driver action.")
        profiles = {p.get("id"): p for p in state.get("profiles", []) if isinstance(p, dict)}
        for driver_id in participants:
            axis = state["runtime"].get(driver_id)
            label = str(profiles.get(driver_id, {}).get("name") or driver_id)
            if not isinstance(axis, dict) or not axis.get("connected"):
                raise EtherMotionError(f"{label}: driver is disconnected.")
            if not axis.get("remote_enabled"):
                raise EtherMotionError(f"{label}: enable Ethernet triggers in EtherMotion PC events.")
            status = axis.get("status")
            if not isinstance(status, dict) or not status.get("connected"):
                raise EtherMotionError(f"{label}: driver link is unavailable.")
            if status.get("alarm") or status.get("alarm_active"):
                raise EtherMotionError(f"{label}: clear and review the drive alarm in EtherMotion.")
            if (axis.get("program_owner") or axis.get("disconnect", {}).get("running")
                    or any(status.get(key) for key in ("busy", "hardware_busy", "motion_unconfirmed", "homing_active"))):
                raise EtherMotionError(f"{label}: driver is busy or its movement is unconfirmed.")
            if not all(status.get(key) for key in ("enabled", "ready", "configured", "identity_verified")):
                raise EtherMotionError(f"{label}: driver must be enabled, ready and configured with verified identity.")
            if status.get("parameters_uncertain") or axis.get("error"):
                raise EtherMotionError(f"{label}: review the driver error or unconfirmed parameters in EtherMotion.")
        # Match EtherMotion's zero requirement: an absolute action before that
        # driver's first physical home needs an existing valid software zero.
        home_seen = set()
        for step in steps:
            driver_id = step.get("driver_id")
            if step.get("type") == "home":
                home_seen.add(driver_id)
            requires_zero = step.get("type") == "return_zero"
            if step.get("type") == "move":
                library = state.get("presets", {}).get(driver_id, [])
                slot = step.get("slot")
                if (not isinstance(library, list) or isinstance(slot, bool) or not isinstance(slot, int)
                        or not 1 <= slot <= len(library) or not isinstance(library[slot - 1], dict)):
                    raise EtherMotionError("The reject program references a missing saved move.")
                requires_zero = library[slot - 1].get("mode", "relative") == "absolute"
            if requires_zero and driver_id not in home_seen and not state["runtime"][driver_id]["status"].get("zero_valid"):
                raise EtherMotionError(f"{driver_id}: establish a valid zero in EtherMotion before this reject cycle.")
        return {"ok": True, "program_id": program_id, "program": program, "participants": participants, "state": state}

    def trigger(self, program_id, request_id, *,
                allow_send: Callable[[], bool] | None = None,
                deadline: float | None = None):
        """Recheck configuration, then send exactly one cycle request.

        ``allow_send`` is checked after the potentially blocking readiness
        request, immediately before transmission.  It lets a GUI cancel work
        while a worker is checking the drive.  ``deadline`` uses the monotonic
        clock; expired conveyor events must never be sent late.
        """
        program_id = self._program_id(program_id)
        request_id = self._request_id(request_id)
        if allow_send is not None and not callable(allow_send):
            raise EtherMotionError("The motion permission check must be callable.")
        if deadline is not None and (isinstance(deadline, bool)
                or not isinstance(deadline, (int, float)) or not math.isfinite(deadline)):
            raise EtherMotionError("The motion deadline must be a finite monotonic timestamp.")
        self.check_ready(program_id)
        if allow_send is not None and not allow_send():
            raise EtherMotionError("Divert request was cancelled before transmission; no command was sent.")
        if deadline is not None and time.monotonic() > deadline:
            raise EtherMotionError("Divert timing deadline expired before transmission; no command was sent.")
        return self._request("POST", f"/program-trigger/{program_id}", {"request_id": request_id}, expected=202, motion=True)

    def program_status(self, program_id):
        """Return command progress, including run_id, without inference."""
        program_id = self._program_id(program_id)
        return self._request("GET", f"/program-trigger/{program_id}/status")

    def stop(self, program_id, request_id):
        """Request a deceleration stop even if readiness/trigger gates failed."""
        program_id = self._program_id(program_id)
        request_id = self._request_id(request_id)
        return self._request("POST", f"/program-trigger/{program_id}/stop", {"request_id": request_id}, expected=202, motion=True)
