#!/bin/bash
set -e

echo "=== ADSB LED Matrix Diagnostics ==="
echo "Date: $(date)"
echo ""

echo "--- readsb Service ---"
sudo systemctl status readsb --no-pager || true
echo ""

echo "--- readsb Process / Logs (last 30 lines) ---"
sudo journalctl -u readsb --no-pager -n 30 || true
echo ""

echo "--- RTL-SDR Device Detection ---"
rtl_test -t 2>/dev/null || echo "rtl_test failed"
lsusb | grep -i rtl || echo "No RTL device in lsusb"
echo ""

echo "--- SBS Port Test (5 second sample) ---"
timeout 5 nc localhost 30003 || true
echo ""

echo "--- Backend Service ---"
sudo systemctl status adsbledmatrix --no-pager || true
echo ""

echo "--- Backend Logs (last 30 lines) ---"
sudo journalctl -u adsbledmatrix --no-pager -n 30 || true
echo ""

echo "--- API Health Check ---"
curl -s http://localhost:8080/api/system/health 2>/dev/null || echo "API not responding"
echo ""

echo "--- Network Interfaces ---"
ip addr show | grep -E "(wlan|eth)" -A 3 || true
echo ""

echo "--- WiFi Manager Status ---"
sudo systemctl status adsbledmatrix-wifi --no-pager || true
echo ""

echo "--- WiFi Manager Logs (last 50 lines) ---"
sudo journalctl -u adsbledmatrix-wifi --no-pager -n 50 || true
echo ""

echo "--- Saved WiFi Config ---"
sqlite3 /opt/adsbledmatrix/data/aircraft_db.sqlite3 "SELECT onboarding_complete, wifi_ssid, wifi_password FROM user_config;" 2>/dev/null || echo "DB query failed"
echo ""

echo "--- NetworkManager Connections ---"
nmcli connection show 2>/dev/null || echo "nmcli not available"
echo ""

echo "--- Active Network Connections ---"
nmcli connection show --active 2>/dev/null || echo "nmcli not available"
echo ""

echo "--- Wireless Device State ---"
nmcli device show wlan0 2>/dev/null | grep -E "(GENERAL.STATE|GENERAL.MTU|IP4.ADDRESS|IP4.GATEWAY)" || echo "wlan0 not managed by NM"
echo ""

echo "--- Database Check ---"
sqlite3 /opt/adsbledmatrix/data/aircraft_db.sqlite3 "SELECT COUNT(*) FROM aircraft;" 2>/dev/null || echo "DB query failed"
echo ""

echo "=== End Diagnostics ==="
