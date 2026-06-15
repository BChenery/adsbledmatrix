#!/bin/bash
# Verification script for ADS-B LED Display

PASS=0
FAIL=0

check() {
  if [ "$1" -eq 0 ]; then
    echo "✓ $2"
    PASS=$((PASS+1))
  else
    echo "✗ $2"
    FAIL=$((FAIL+1))
  fi
}

echo "=== ADS-B LED Display Verification ==="

# Git version
git -C /opt/adsbledmatrix log --oneline -1 2>/dev/null
check $? "Project installed at /opt/adsbledmatrix"

# SPI
ls /dev/spi* >/dev/null 2>&1
check $? "SPI enabled (/dev/spi* present)"

# Audio blacklisted
if lsmod 2>/dev/null | grep -q snd_bcm2835; then
  check 1 "Onboard audio module not loaded"
else
  check 0 "Onboard audio module not loaded"
fi

# rgbmatrix importable
cd /opt/adsbledmatrix || exit 1
# shellcheck source=/dev/null
source venv/bin/activate
python3 -c "from rgbmatrix import RGBMatrix, RGBMatrixOptions" 2>/dev/null
check $? "rpi-rgb-led-matrix Python bindings installed"

# Service running as root
UVICORN_PID=$(pgrep -f "uvicorn app.main:app" | head -n1)
if [ -n "$UVICORN_PID" ]; then
  UVICORN_USER=$(ps -o user= -p "$UVICORN_PID" | tr -d ' ')
  if [ "$UVICORN_USER" = "root" ]; then
    check 0 "adsbledmatrix service running as root"
  else
    check 1 "adsbledmatrix service running as root (found user=$UVICORN_USER)"
  fi
else
  check 1 "adsbledmatrix service running"
fi

# API health
curl -sf http://localhost:8080/api/system/health >/dev/null 2>&1
check $? "API responding (/api/system/health)"

# Display diagnostics
DIAG=$(curl -sf http://localhost:8080/api/display/diagnostics 2>/dev/null)
if [ -n "$DIAG" ]; then
  echo "--- Display diagnostics ---"
  echo "$DIAG"
  echo "$DIAG" | grep -q '"hardware_mode": true' && check 0 "Hardware mode enabled" || check 1 "Hardware mode enabled"
else
  check 1 "Display diagnostics endpoint responding"
fi

# Trigger test pattern
TEST=$(curl -sf -X POST http://localhost:8080/api/display/test 2>/dev/null)
if [ -n "$TEST" ]; then
  echo "--- Test pattern result ---"
  echo "$TEST"
  echo "$TEST" | grep -q '"success": true' && check 0 "Test pattern triggered" || check 1 "Test pattern triggered"
else
  check 1 "Test pattern endpoint responding"
fi

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
