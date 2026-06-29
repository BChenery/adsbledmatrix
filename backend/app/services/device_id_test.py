import re
from pathlib import Path

import pytest

import app.services.device_id as device_id_module


@pytest.fixture(autouse=True)
def reset_module_state(monkeypatch, tmp_path):
    """Point persisted ID path into tmp_path and clear cached module state."""
    monkeypatch.setattr(device_id_module, "PERSISTED_ID_PATH", tmp_path / ".device-id")
    monkeypatch.setattr(device_id_module, "_unwritable_fallback_uuid", None)


class TestGetDeviceId:
    def test_machine_id_is_preferred(self, monkeypatch, tmp_path):
        """Machine ID files should be preferred over MAC and generated UUIDs."""
        etc_machine_id = tmp_path / "etc-machine-id"
        etc_machine_id.write_text("preferred-machine-id\n")

        # A MAC address is also available but should be ignored.
        net_dir = tmp_path / "sys-class-net"
        iface_dir = net_dir / "eth0"
        iface_dir.mkdir(parents=True)
        (iface_dir / "address").write_text("aa:bb:cc:dd:ee:ff\n")

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "SYS_CLASS_NET_PATH", net_dir)

        result = device_id_module.get_device_id()

        expected = device_id_module.hashlib.sha256(
            b"preferred-machine-id"
        ).hexdigest()[:32]
        assert result == expected

    def test_dbus_machine_id_fallback(self, monkeypatch, tmp_path):
        """dbus machine-id is used when /etc/machine-id is missing."""
        etc_machine_id = tmp_path / "etc-machine-id-missing"
        dbus_machine_id = tmp_path / "dbus-machine-id"
        dbus_machine_id.write_text("dbus-machine-id-value\n")

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "DBUS_MACHINE_ID_PATH", dbus_machine_id)

        result = device_id_module.get_device_id()

        expected = device_id_module.hashlib.sha256(
            b"dbus-machine-id-value"
        ).hexdigest()[:32]
        assert result == expected

    def test_mac_address_fallback(self, monkeypatch, tmp_path):
        """A non-zero MAC address is used when machine IDs are unavailable."""
        etc_machine_id = tmp_path / "etc-machine-id-missing"
        dbus_machine_id = tmp_path / "dbus-machine-id-missing"
        net_dir = tmp_path / "sys-class-net"
        iface_dir = net_dir / "wlan0"
        iface_dir.mkdir(parents=True)
        (iface_dir / "address").write_text("00:11:22:33:44:55\n")

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "DBUS_MACHINE_ID_PATH", dbus_machine_id)
        monkeypatch.setattr(device_id_module, "SYS_CLASS_NET_PATH", net_dir)

        result = device_id_module.get_device_id()

        expected = device_id_module.hashlib.sha256(
            b"001122334455"
        ).hexdigest()[:32]
        assert result == expected

    def test_mac_address_skips_zero_address(self, monkeypatch, tmp_path):
        """All-zero MAC addresses are skipped."""
        etc_machine_id = tmp_path / "etc-machine-id-missing"
        dbus_machine_id = tmp_path / "dbus-machine-id-missing"
        net_dir = tmp_path / "sys-class-net"

        zero_iface = net_dir / "dummy0"
        zero_iface.mkdir(parents=True)
        (zero_iface / "address").write_text("00:00:00:00:00:00\n")

        valid_iface = net_dir / "eth0"
        valid_iface.mkdir(parents=True)
        (valid_iface / "address").write_text("12:34:56:78:9a:bc\n")

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "DBUS_MACHINE_ID_PATH", dbus_machine_id)
        monkeypatch.setattr(device_id_module, "SYS_CLASS_NET_PATH", net_dir)

        result = device_id_module.get_device_id()

        expected = device_id_module.hashlib.sha256(
            b"123456789abc"
        ).hexdigest()[:32]
        assert result == expected

    def test_generated_uuid_fallback(self, monkeypatch, tmp_path):
        """A UUID is generated and persisted when no system IDs are available."""
        etc_machine_id = tmp_path / "etc-machine-id-missing"
        dbus_machine_id = tmp_path / "dbus-machine-id-missing"
        net_dir = tmp_path / "sys-class-net-empty"
        net_dir.mkdir(parents=True)

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "DBUS_MACHINE_ID_PATH", dbus_machine_id)
        monkeypatch.setattr(device_id_module, "SYS_CLASS_NET_PATH", net_dir)

        result = device_id_module.get_device_id()

        assert len(result) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", result)
        assert device_id_module.PERSISTED_ID_PATH.exists()

    def test_returned_id_is_stable(self, monkeypatch, tmp_path):
        """The same inputs must produce the same identifier."""
        etc_machine_id = tmp_path / "etc-machine-id"
        etc_machine_id.write_text("stable-machine-id\n")
        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)

        first = device_id_module.get_device_id()
        second = device_id_module.get_device_id()

        assert first == second

    def test_returned_id_is_32_hex_chars(self, monkeypatch, tmp_path):
        """The returned identifier is a 32-character lowercase hex string."""
        etc_machine_id = tmp_path / "etc-machine-id"
        etc_machine_id.write_text("hex-test-machine-id\n")
        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)

        result = device_id_module.get_device_id()

        assert len(result) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", result)

    def test_persisted_uuid_is_reused(self, monkeypatch, tmp_path):
        """A previously persisted UUID is reused on subsequent calls."""
        etc_machine_id = tmp_path / "etc-machine-id-missing"
        dbus_machine_id = tmp_path / "dbus-machine-id-missing"
        net_dir = tmp_path / "sys-class-net-empty"
        net_dir.mkdir(parents=True)

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "DBUS_MACHINE_ID_PATH", dbus_machine_id)
        monkeypatch.setattr(device_id_module, "SYS_CLASS_NET_PATH", net_dir)

        first = device_id_module.get_device_id()
        second = device_id_module.get_device_id()

        assert first == second
        assert device_id_module.PERSISTED_ID_PATH.exists()

    def test_empty_machine_id_falls_through(self, monkeypatch, tmp_path):
        """An empty /etc/machine-id file falls through to the next fallback."""
        etc_machine_id = tmp_path / "etc-machine-id"
        etc_machine_id.write_text("\n")
        dbus_machine_id = tmp_path / "dbus-machine-id"
        dbus_machine_id.write_text("dbus-fallback-id\n")

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "DBUS_MACHINE_ID_PATH", dbus_machine_id)

        result = device_id_module.get_device_id()

        expected = device_id_module.hashlib.sha256(
            b"dbus-fallback-id"
        ).hexdigest()[:32]
        assert result == expected

    def test_mac_address_skips_virtual_interfaces(self, monkeypatch, tmp_path):
        """Virtual/transient network interfaces are skipped in MAC fallback."""
        etc_machine_id = tmp_path / "etc-machine-id-missing"
        dbus_machine_id = tmp_path / "dbus-machine-id-missing"
        net_dir = tmp_path / "sys-class-net"

        virtual_interfaces = [
            ("lo", "00:11:22:33:44:01"),
            ("docker0", "00:11:22:33:44:02"),
            ("veth0", "00:11:22:33:44:03"),
            ("br-abc123", "00:11:22:33:44:04"),
            ("virbr0", "00:11:22:33:44:05"),
            ("tun0", "00:11:22:33:44:06"),
            ("tap0", "00:11:22:33:44:07"),
        ]
        for name, address in virtual_interfaces:
            iface_dir = net_dir / name
            iface_dir.mkdir(parents=True)
            (iface_dir / "address").write_text(address + "\n")

        valid_iface = net_dir / "eth0"
        valid_iface.mkdir(parents=True)
        (valid_iface / "address").write_text("aa:bb:cc:dd:ee:ff\n")

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "DBUS_MACHINE_ID_PATH", dbus_machine_id)
        monkeypatch.setattr(device_id_module, "SYS_CLASS_NET_PATH", net_dir)

        result = device_id_module.get_device_id()

        expected = device_id_module.hashlib.sha256(
            b"aabbccddeeff"
        ).hexdigest()[:32]
        assert result == expected

    def test_unwritable_persist_path_caches_uuid(self, monkeypatch, tmp_path):
        """If the persist path cannot be written, the UUID is cached in-process."""
        etc_machine_id = tmp_path / "etc-machine-id-missing"
        dbus_machine_id = tmp_path / "dbus-machine-id-missing"
        net_dir = tmp_path / "sys-class-net-empty"
        net_dir.mkdir(parents=True)

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir(mode=0o555)

        monkeypatch.setattr(device_id_module, "MACHINE_ID_PATH", etc_machine_id)
        monkeypatch.setattr(device_id_module, "DBUS_MACHINE_ID_PATH", dbus_machine_id)
        monkeypatch.setattr(device_id_module, "SYS_CLASS_NET_PATH", net_dir)
        monkeypatch.setattr(
            device_id_module, "PERSISTED_ID_PATH", readonly_dir / ".device-id"
        )

        try:
            first = device_id_module.get_device_id()
            second = device_id_module.get_device_id()
        finally:
            readonly_dir.chmod(0o755)

        assert first == second
        assert len(first) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", first)
        assert not (readonly_dir / ".device-id").exists()
