"""Passive camera discovery and identity-based selection for the demo.

Windows devices are enumerated through the same DirectShow category/order used
by OpenCV CAP_DSHOW. Reading device properties never opens a capture stream.
An explicit saved identity must still exist at Start; a missing external camera
must never silently select the laptop's camera at the old integer index.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import sys
from typing import Iterable


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraChoice:
    kind: str
    id: str
    name: str
    index: int = -1
    serial: str = ""
    device_path: str = ""


def _windows_usb_cameras() -> list[CameraChoice]:
    """Read DirectShow monikers and property bags; do not bind capture filters.

    Only Windows' own COM libraries are needed. Each successful CoInitializeEx
    is balanced with CoUninitialize, including S_FALSE. RPC_E_CHANGED_MODE
    means the calling thread already has a usable apartment, which we leave
    alone. Each VARIANT and every acquired interface/string is released.

    References:
    https://learn.microsoft.com/windows/win32/directshow/using-the-system-device-enumerator
    https://github.com/opencv/opencv/blob/4.10.0/modules/videoio/src/cap_dshow.cpp
    """
    import ctypes as ct
    import uuid

    class GUID(ct.Structure):
        _fields_ = [("data1", ct.c_uint32), ("data2", ct.c_uint16),
                    ("data3", ct.c_uint16), ("data4", ct.c_ubyte * 8)]

        def __init__(self, value: str):
            super().__init__()
            ct.memmove(ct.byref(self), uuid.UUID(value).bytes_le, 16)

    HRESULT = ct.c_int32
    ULONG = ct.c_uint32
    pointer = ct.c_void_p
    pointer_ref = ct.POINTER(pointer)
    guid_ref = ct.POINTER(GUID)
    # WinDLL rather than OleDLL preserves HRESULT values for our own checks.
    ole32 = ct.WinDLL("ole32")
    oleaut32 = ct.WinDLL("oleaut32")
    ole32.CoInitializeEx.argtypes = [pointer, ULONG]
    ole32.CoInitializeEx.restype = HRESULT
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    ole32.CoCreateInstance.argtypes = [guid_ref, pointer, ULONG, guid_ref, pointer_ref]
    ole32.CoCreateInstance.restype = HRESULT
    ole32.CoTaskMemFree.argtypes = [pointer]
    ole32.CoTaskMemFree.restype = None
    oleaut32.VariantInit.argtypes = [pointer]
    oleaut32.VariantInit.restype = None
    oleaut32.VariantClear.argtypes = [pointer]
    oleaut32.VariantClear.restype = HRESULT

    def method(obj, slot, result_type, *argument_types):
        vtable = ct.cast(obj, ct.POINTER(ct.POINTER(pointer))).contents
        return ct.WINFUNCTYPE(result_type, pointer, *argument_types)(vtable[slot])

    def release(obj):
        if obj:
            method(obj, 2, ULONG)(obj)

    def read_string(bag, key):
        # VARIANT is 24 bytes on Win64 and 16 on Win32. BSTR is at offset 8.
        variant = ct.create_string_buffer(24 if ct.sizeof(pointer) == 8 else 16)
        oleaut32.VariantInit(variant)
        try:
            hr = method(bag, 3, HRESULT, ct.c_wchar_p, pointer, pointer)(bag, key, variant, None)
            if hr < 0 or ct.c_uint16.from_buffer(variant).value != 8:  # VT_BSTR
                return ""
            value = pointer.from_buffer(variant, 8).value
            return ct.wstring_at(value).strip() if value else ""
        finally:
            oleaut32.VariantClear(variant)

    def display_name(moniker):
        value = pointer()
        try:
            # IMoniker::GetDisplayName follows the 8 inherited interface slots.
            hr = method(moniker, 20, HRESULT, pointer, pointer, pointer_ref)(
                moniker, None, None, ct.byref(value))
            return ct.wstring_at(value).strip() if hr >= 0 and value else ""
        finally:
            if value:
                ole32.CoTaskMemFree(value)

    # COINIT_MULTITHREADED. Existing STA threads can still enumerate devices.
    initialized = int(ole32.CoInitializeEx(None, 0))
    if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE
        raise OSError(f"Camera device enumeration could not initialize COM ({initialized:#x}).")
    dev_enum, enum = pointer(), pointer()
    try:
        clsid_enum = GUID("62BE5D10-60EB-11D0-BD3B-00A0C911CE86")
        iid_enum = GUID("29840822-5B84-11D0-BD3B-00A0C911CE86")
        video_category = GUID("860BB310-5D01-11D0-BD3B-00A0C911CE86")
        iid_bag = GUID("55272A00-42CB-11CE-8135-00AA004BB851")
        hr = ole32.CoCreateInstance(ct.byref(clsid_enum), None, 1, ct.byref(iid_enum), ct.byref(dev_enum))
        if hr < 0:
            raise OSError(f"Camera device enumerator is unavailable ({hr:#x}).")
        hr = method(dev_enum, 3, HRESULT, guid_ref, pointer_ref, ULONG)(
            dev_enum, ct.byref(video_category), ct.byref(enum), 0)
        if hr == 1:  # S_FALSE: no video input devices in this category.
            return []
        if hr < 0 or not enum:
            raise OSError(f"Camera device list is unavailable ({hr:#x}).")
        devices = []
        index = 0
        while True:
            moniker, fetched = pointer(), ULONG()
            hr = method(enum, 3, HRESULT, ULONG, pointer_ref, ct.POINTER(ULONG))(
                enum, 1, ct.byref(moniker), ct.byref(fetched))
            if hr < 0:
                release(moniker)
                raise OSError(f"Camera device enumeration failed ({hr:#x}).")
            if hr == 1 or not fetched.value:
                release(moniker)
                break
            bag = pointer()
            try:
                hr = method(moniker, 9, HRESULT, pointer, pointer, guid_ref, pointer_ref)(
                    moniker, None, None, ct.byref(iid_bag), ct.byref(bag))
                if hr >= 0 and bag:
                    name = read_string(bag, "FriendlyName") or read_string(bag, "Description")
                    path = read_string(bag, "DevicePath") or display_name(moniker)
                    # A friendly name alone is not unique (two equal cameras).
                    if path:
                        devices.append(CameraChoice(
                            kind="usb", id=f"usb:{path.casefold()}",
                            name=name or f"Camera {index}", index=index, device_path=path))
            finally:
                release(bag)
                release(moniker)
            # Retain raw moniker order used by OpenCV's getDevice(index).
            index += 1
        return devices
    finally:
        release(enum)
        release(dev_enum)
        if initialized >= 0:
            ole32.CoUninitialize()


def _basler_cameras() -> list[CameraChoice]:
    try:
        from pypylon import pylon
    except ImportError:
        return []
    devices = []
    for item in pylon.TlFactory.GetInstance().EnumerateDevices():
        serial = str(item.GetSerialNumber()).strip()
        if not serial:
            continue
        model = str(item.GetModelName()).strip()
        devices.append(CameraChoice(kind="basler", id=f"basler:{serial}",
                                    name=f"{model or 'Basler'} ({serial})", serial=serial))
    return devices


def discover_cameras() -> list[CameraChoice]:
    """Return cameras without opening them. Optional SDK/driver failures are local.

    On platforms without the Windows device enumerator the UI can offer its
    explicit manual index option. No fabricated camera 0 entry is returned.
    """
    found = []
    if sys.platform == "win32":
        try:
            found.extend(_windows_usb_cameras())
        except Exception:
            log.warning("USB camera discovery failed", exc_info=True)
    try:
        found.extend(_basler_cameras())
    except Exception:
        log.warning("Basler camera discovery failed", exc_info=True)
    return found


def resolve_usb_camera(settings: dict, devices: Iterable[CameraChoice] | None = None) -> CameraChoice:
    """Resolve an explicit saved camera identity to its current DirectShow index.

    A selected stable ID takes precedence over the old index or manual flag.
    Numeric indices are accepted only when the operator selected manual mode.
    """
    saved_id = str(settings.get("camera_id") or "").strip()
    if saved_id:
        choices = discover_cameras() if devices is None else list(devices)
        matches = [item for item in choices if item.kind == "usb" and item.id.casefold() == saved_id.casefold()]
        if len(matches) == 1 and matches[0].index >= 0:
            return matches[0]
        name = str(settings.get("camera_name") or "Selected USB camera").strip()
        raise RuntimeError(f"{name} is not available. Reconnect it, refresh cameras, and select it again.")
    if settings.get("camera_manual") is True:
        value = settings.get("camera_index")
        try:
            if isinstance(value, bool) or int(value) != float(value):
                raise ValueError
            index = int(value)
            if not 0 <= index <= 99:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            raise RuntimeError("Choose a manual USB camera index from 0 to 99.") from None
        return CameraChoice(kind="usb", id="", name=f"Manual USB camera {index}", index=index)
    raise RuntimeError("Select a camera by name, or explicitly choose a manual camera index.")
