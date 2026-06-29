"""Stable device identifier utility.

Returns a deterministic, opaque identifier for the device. The identifier is
derived from well-known system IDs when available, and falls back to a
persisted UUID when those are unavailable.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

MACHINE_ID_PATH = Path("/etc/machine-id")
DBUS_MACHINE_ID_PATH = Path("/var/lib/dbus/machine-id")
SYS_CLASS_NET_PATH = Path("/sys/class/net")
PERSISTED_ID_PATH = Path("/opt/adsbledmatrix/.device-id")

_SKIPPED_IFACE_PREFIXES = (
    "lo",
    "docker",
    "veth",
    "br-",
    "virbr",
    "tun",
    "tap",
)

# Caches the generated UUID only when the persist path cannot be written.
_unwritable_fallback_uuid: str | None = None


def _read_machine_id(path: Path) -> str | None:
    """Return stripped contents of a machine-id file if it exists and is non-empty."""
    try:
        contents = path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return contents if contents else None


def _first_mac_address() -> str | None:
    """Return the first non-zero MAC address found under /sys/class/net."""
    try:
        entries = sorted(SYS_CLASS_NET_PATH.iterdir())
    except OSError:
        return None

    for entry in entries:
        if any(entry.name.startswith(prefix) for prefix in _SKIPPED_IFACE_PREFIXES):
            continue

        address_file = entry / "address"
        try:
            address = address_file.read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            continue

        cleaned = address.replace(":", "").lower()
        if cleaned and cleaned != "000000000000":
            return cleaned

    return None


def _persisted_uuid() -> str:
    """Return a persisted UUID, creating and saving one if necessary.

    If the persist path cannot be written, cache the generated UUID in a
    module-level variable so the same value is returned for the lifetime of
    this process.
    """
    global _unwritable_fallback_uuid
    if _unwritable_fallback_uuid is not None:
        return _unwritable_fallback_uuid

    try:
        contents = PERSISTED_ID_PATH.read_text(encoding="utf-8").strip()
        if contents:
            return contents
    except (OSError, ValueError):
        pass

    generated = str(uuid.uuid4())
    try:
        PERSISTED_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
        PERSISTED_ID_PATH.write_text(generated + "\n", encoding="utf-8")
    except OSError:
        # If we cannot persist, cache the generated UUID for this process.
        _unwritable_fallback_uuid = generated

    return generated


def _choose_source() -> str:
    """Choose the best available source for a stable device identifier."""
    machine_id = _read_machine_id(MACHINE_ID_PATH)
    if machine_id is not None:
        return machine_id

    dbus_machine_id = _read_machine_id(DBUS_MACHINE_ID_PATH)
    if dbus_machine_id is not None:
        return dbus_machine_id

    mac_address = _first_mac_address()
    if mac_address is not None:
        return mac_address

    return _persisted_uuid()


def get_device_id() -> str:
    """Return a stable, opaque 32-character hex device identifier."""
    source = _choose_source()
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return digest[:32]
