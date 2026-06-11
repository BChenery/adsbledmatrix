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
curl -s http://localhost:8080/api/health 2>/dev/null || echo "API not responding"
echo ""

echo "--- Network Interfaces ---"
ip addr show | grep -E "(wlan|eth)" -A 3 || true
echo ""

echo "--- WiFi Manager Status ---"
sudo systemctl status adsbledmatrix-wifi --no-pager || true
echo ""

echo "--- Database Check ---"
sqlite3 /opt/adsbledmatrix/data/aircraft_db.sqlite3 "SELECT COUNT(*) FROM aircraft;" 2>/dev/null || echo "DB query failed"
echo ""

echo "=== End Diagnostics ==="
