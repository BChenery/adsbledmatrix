#!/usr/bin/env python3
"""
WiFi Manager for ADS-B LED Display onboarding.
Handles switching between AP mode and home WiFi client mode.

Strategy:
- AP mode:  Always uses hostapd + dnsmasq for a reliable 192.168.4.1 address.
            If NetworkManager is present, wlan0 is set to unmanaged first.
- Client mode: Uses NetworkManager (nmcli) on modern Pi OS if available,
               otherwise falls back to wpa_supplicant.
"""

import argparse
import os
import sys
import time
import subprocess
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("wifi_manager")

DB_PATH = os.path.join(
    os.environ.get("ADSB_DATA_DIR", "/opt/adsbledmatrix/data"),
    "aircraft_db.sqlite3",
)
AP_SSID_PREFIX = os.environ.get("ADSB_AP_SSID_PREFIX", "ADSB-Display")
AP_PASSWORD = os.environ.get("ADSB_AP_PASSWORD", "adsbsetup")
AP_IP = "192.168.4.1"
AP_RANGE = "192.168.4.2,192.168.4.20,255.255.255.0,24h"


def run(cmd, check=True, capture=True):
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if check and result.returncode != 0:
        logger.error("Command failed (rc=%d): %s", result.returncode, result.stderr.strip())
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def get_wlan_interface():
    """Find the first wireless interface."""
    try:
        result = run(["iw", "dev"], check=False)
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == "Interface":
                return parts[1]
    except Exception as exc:
        logger.warning("Could not detect wireless interface: %s", exc)
    return "wlan0"


def get_ap_ssid():
    """Generate AP SSID with last 4 hex digits of MAC."""
    iface = get_wlan_interface()
    try:
        with open(f"/sys/class/net/{iface}/address", encoding="utf-8") as f:
            mac = f.read().strip().replace(":", "")
            suffix = mac[-4:].upper()
    except Exception:
        suffix = "0000"
    return f"{AP_SSID_PREFIX}-{suffix}"


def using_network_manager():
    """Check if NetworkManager is installed and active."""
    result = run(["systemctl", "is-active", "NetworkManager"], check=False)
    return result.returncode == 0


def nm_get_connection_uuid(name):
    result = run(["nmcli", "-g", "NAME,UUID", "connection", "show"], check=False)
    for line in result.stdout.strip().splitlines():
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 2 and parts[0] == name:
                return parts[1]
    return None


def nm_delete_connection(name):
    uuid = nm_get_connection_uuid(name)
    if uuid:
        run(["nmcli", "connection", "delete", uuid], check=False)


def nm_connect_home(ssid, password):
    """Connect to home WiFi using NetworkManager."""
    iface = get_wlan_interface()

    # Ensure NM manages the interface and clear any hostapd/dnsmasq static IP config
    _nm_set_managed(iface)
    _remove_dhcpcd_static(iface)

    # Remove stale connections
    nm_delete_connection("adsb-hotspot")
    nm_delete_connection("adsb-home")

    # Stop hostapd/dnsmasq if they were running
    run(["systemctl", "stop", "hostapd"], check=False)
    run(["systemctl", "disable", "hostapd"], check=False)
    run(["systemctl", "stop", "dnsmasq"], check=False)

    # Add home connection
    run([
        "nmcli", "connection", "add", "type", "wifi",
        "ifname", iface, "con-name", "adsb-home", "autoconnect", "yes",
        "wifi.ssid", ssid,
        "wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password,
    ])

    run(["nmcli", "connection", "up", "adsb-home"])
    setup_port_redirect()
    logger.info("Home WiFi connection started (NetworkManager): SSID=%s", ssid)


def nm_wait_for_connection(timeout=60):
    """Wait for WiFi to obtain an IP address."""
    iface = get_wlan_interface()
    for i in range(timeout):
        state = run(["nmcli", "-g", "GENERAL.STATE", "device", "show", iface], check=False)
        if "connected" in state.stdout.lower():
            ip = run(["nmcli", "-g", "IP4.ADDRESS", "device", "show", iface], check=False)
            if ip.stdout.strip():
                logger.info("Home WiFi connected with IP: %s", ip.stdout.strip().split(",")[0])
                return True
        if i % 10 == 0:
            logger.info("Waiting for home WiFi connection... (%d/%d)", i, timeout)
        time.sleep(1)
    logger.warning("Home WiFi connection timed out after %d seconds", timeout)
    return False


def _is_iptables_rule_present():
    result = run(["iptables", "-t", "nat", "-S", "PREROUTING"], check=False)
    target = "-p tcp --dport 80 -j REDIRECT --to-ports 8080"
    return target in result.stdout


def setup_port_redirect():
    """Redirect port 80 to 8080 so http://192.168.4.1 works without :8080."""
    if _is_iptables_rule_present():
        logger.info("Port 80->8080 redirect already present")
        return
    run(["iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp", "--dport", "80", "-j", "REDIRECT", "--to-ports", "8080"])
    logger.info("Added port 80 -> 8080 redirect")
    # Attempt to persist rules if netfilter-persistent is available
    if os.path.exists("/usr/sbin/netfilter-persistent"):
        run(["netfilter-persistent", "save"], check=False)
    elif os.path.exists("/usr/sbin/iptables-save"):
        try:
            with open("/etc/iptables.ipv4.nat", "w") as f:
                subprocess.run(["iptables-save"], stdout=f, check=True)
        except Exception as exc:
            logger.warning("Could not persist iptables rules: %s", exc)


def _backup_file(path):
    backup = path + ".adsb-backup"
    if os.path.exists(path) and not os.path.exists(backup):
        import shutil
        shutil.copy2(path, backup)


NM_UNMANAGED_CONF = "/etc/NetworkManager/conf.d/99-adsb-unmanaged-wlan.conf"


def _nm_set_unmanaged(iface):
    """Tell NetworkManager to leave the interface alone (persistent across boots)."""
    conf = f"""[keyfile]
unmanaged-devices=interface-name:{iface}
"""
    os.makedirs(os.path.dirname(NM_UNMANAGED_CONF), exist_ok=True)
    with open(NM_UNMANAGED_CONF, "w", encoding="utf-8") as f:
        f.write(conf)
    run(["nmcli", "device", "set", iface, "managed", "no"], check=False)
    logger.info("Set %s unmanaged by NetworkManager", iface)


def _nm_set_managed(iface):
    """Allow NetworkManager to manage the interface again."""
    if os.path.exists(NM_UNMANAGED_CONF):
        os.remove(NM_UNMANAGED_CONF)
    run(["nmcli", "device", "set", iface, "managed", "yes"], check=False)
    logger.info("Set %s managed by NetworkManager", iface)


def _remove_dhcpcd_static(iface):
    """Remove our static IP block from dhcpcd.conf so client mode gets DHCP."""
    path = "/etc/dhcpcd.conf"
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        skip = False
        for line in lines:
            if line.strip().startswith(f"interface {iface}"):
                skip = True
                continue
            if skip and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                skip = False
            if skip:
                continue
            new_lines.append(line)
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        logger.info("Removed static IP entry for %s from %s", iface, path)
    except Exception as exc:
        logger.warning("Could not update %s: %s", path, exc)


def legacy_setup_ap():
    """Setup AP using hostapd + dnsmasq."""
    ssid = get_ap_ssid()
    iface = get_wlan_interface()

    # Packages should already be installed by install.sh; do NOT apt-get here
    # because this script may run during boot before the network is fully up.

    # Stop competing services
    run(["systemctl", "stop", "hostapd"], check=False)
    run(["systemctl", "stop", "dnsmasq"], check=False)
    run(["systemctl", "stop", f"wpa_supplicant@{iface}"], check=False)
    run(["systemctl", "disable", f"wpa_supplicant@{iface}"], check=False)

    # systemd-resolved can grab port 53 and block dnsmasq
    resolved_check = run(["systemctl", "is-active", "systemd-resolved"], check=False)
    if resolved_check.returncode == 0:
        logger.info("Stopping systemd-resolved to free port 53 for dnsmasq")
        run(["systemctl", "stop", "systemd-resolved"], check=False)
        run(["systemctl", "disable", "systemd-resolved"], check=False)

    # Configure hostapd
    hostapd_conf = f"""interface={iface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={AP_PASSWORD}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
    with open("/etc/hostapd/hostapd.conf", "w", encoding="utf-8") as f:
        f.write(hostapd_conf)

    run(["sed", "-i", 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|', "/etc/default/hostapd"], check=False)

    # Configure dnsmasq
    dnsmasq_conf = f"""interface={iface}
dhcp-range={AP_RANGE}
address=/#/{AP_IP}
"""
    with open("/etc/dnsmasq.conf", "w", encoding="utf-8") as f:
        f.write(dnsmasq_conf)

    # Static IP via dhcpcd (avoid duplicate entries)
    dhcpcd_entry = f"""interface {iface}
    static ip_address={AP_IP}/24
    nohook wpa_supplicant
"""
    try:
        with open("/etc/dhcpcd.conf", "r", encoding="utf-8") as f:
            content = f.read()
        if "nohook wpa_supplicant" not in content:
            with open("/etc/dhcpcd.conf", "a", encoding="utf-8") as f:
                f.write("\n" + dhcpcd_entry)
    except Exception as exc:
        logger.warning("Could not update /etc/dhcpcd.conf: %s", exc)

    # Ensure the interface has the static IP (dhcpcd may not be active on Bookworm)
    run(["ip", "link", "set", iface, "up"], check=False)
    run(["ip", "addr", "flush", "dev", iface], check=False)
    run(["ip", "addr", "add", f"{AP_IP}/24", "dev", iface], check=False)
    logger.info("Assigned static IP %s/24 to %s", AP_IP, iface)

    # Enable and start services
    run(["systemctl", "unmask", "hostapd"], check=False)
    run(["systemctl", "enable", "hostapd"], check=False)
    run(["systemctl", "enable", "dnsmasq"], check=False)
    run(["systemctl", "start", "hostapd"], check=False)
    run(["systemctl", "start", "dnsmasq"], check=False)
    logger.info("AP mode active: SSID=%s Password=%s IP=%s", ssid, AP_PASSWORD, AP_IP)


def _escape_wpa_string(s):
    """Escape quotes and backslashes for wpa_supplicant.conf."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def legacy_connect_home(ssid, password):
    """Connect to home WiFi using wpa_supplicant."""
    iface = get_wlan_interface()

    # Stop AP services and remove the static IP block so we can DHCP on the home network
    run(["systemctl", "stop", "hostapd"], check=False)
    run(["systemctl", "disable", "hostapd"], check=False)
    run(["systemctl", "stop", "dnsmasq"], check=False)
    _remove_dhcpcd_static(iface)

    # Write wpa_supplicant config
    safe_ssid = _escape_wpa_string(ssid)
    safe_psk = _escape_wpa_string(password)
    wpa_conf = f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=GB

network={{
    ssid="{safe_ssid}"
    psk="{safe_psk}"
    key_mgmt=WPA-PSK
}}
"""
    wpa_path = f"/etc/wpa_supplicant/wpa_supplicant-{iface}.conf"
    with open(wpa_path, "w", encoding="utf-8") as f:
        f.write(wpa_conf)
    run(["chmod", "600", wpa_path])

    # Enable and start wpa_supplicant
    run(["systemctl", "enable", f"wpa_supplicant@{iface}"], check=False)
    run(["systemctl", "restart", f"wpa_supplicant@{iface}"], check=False)
    run(["systemctl", "restart", "dhcpcd"], check=False)
    setup_port_redirect()
    logger.info("Home WiFi connection started (legacy): SSID=%s", ssid)


def legacy_wait_for_connection(timeout=60):
    """Wait for wpa_supplicant to get an IP."""
    iface = get_wlan_interface()
    for i in range(timeout):
        result = run(["ip", "addr", "show", iface], check=False)
        if "inet " in result.stdout and AP_IP not in result.stdout:
            logger.info("Home WiFi connected on %s", iface)
            return True
        if i % 10 == 0:
            logger.info("Waiting for home WiFi connection... (%d/%d)", i, timeout)
        time.sleep(1)
    logger.warning("Home WiFi connection timed out after %d seconds", timeout)
    return False


def read_config_from_db():
    """Read onboarding state and WiFi credentials from the app database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT onboarding_complete, wifi_ssid, wifi_password FROM user_config WHERE id=1"
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "onboarding_complete": bool(row[0]),
                "wifi_ssid": row[1],
                "wifi_password": row[2],
            }
    except Exception as exc:
        logger.warning("Could not read DB at %s: %s", DB_PATH, exc)
    return {"onboarding_complete": False, "wifi_ssid": None, "wifi_password": None}


def cmd_setup_ap(_args):
    iface = get_wlan_interface()
    if using_network_manager():
        # Take wlan0 away from NetworkManager so hostapd can own it reliably
        _nm_set_unmanaged(iface)
        # Also delete any NM connections for this interface so they don't compete
        nm_delete_connection("adsb-hotspot")
        nm_delete_connection("adsb-home")
    legacy_setup_ap()
    setup_port_redirect()


def cmd_connect_home(args):
    config = read_config_from_db()
    ssid = args.ssid or config.get("wifi_ssid")
    password = args.password or config.get("wifi_password")
    if not ssid or not password:
        logger.error("No WiFi credentials provided. Pass --ssid / --password or store them in the DB.")
        sys.exit(1)

    if using_network_manager():
        nm_connect_home(ssid, password)
        if not nm_wait_for_connection(timeout=60):
            logger.warning("Home WiFi failed, falling back to AP mode")
            cmd_setup_ap(args)
            sys.exit(1)
    else:
        legacy_connect_home(ssid, password)
        if not legacy_wait_for_connection(timeout=60):
            logger.warning("Home WiFi failed, falling back to AP mode")
            cmd_setup_ap(args)
            sys.exit(1)


def cmd_auto(_args):
    config = read_config_from_db()
    if config["onboarding_complete"] and config.get("wifi_ssid") and config.get("wifi_password"):
        logger.info("Onboarding complete with home WiFi configured; attempting connection")
        cmd_connect_home(_args)
    else:
        logger.info("Onboarding incomplete or no home WiFi stored; starting AP mode")
        cmd_setup_ap(_args)


def cmd_status(_args):
    iface = get_wlan_interface()
    result = run(["iw", "dev", iface, "info"], check=False)
    print(result.stdout)
    print("---")
    nm = using_network_manager()
    print(f"NetworkManager active: {nm}")
    if nm:
        result = run(["nmcli", "connection", "show", "--active"], check=False)
        print(result.stdout)


def main():
    parser = argparse.ArgumentParser(description="ADS-B LED Display WiFi Manager")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup-ap", help="Create WiFi access point")

    p_home = sub.add_parser("connect-home", help="Connect to home WiFi")
    p_home.add_argument("--ssid", help="WiFi SSID")
    p_home.add_argument("--password", help="WiFi password")

    sub.add_parser("auto", help="Auto-configure based on DB state")
    sub.add_parser("status", help="Show WiFi status")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "setup-ap":
        cmd_setup_ap(args)
    elif args.command == "connect-home":
        cmd_connect_home(args)
    elif args.command == "auto":
        cmd_auto(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
