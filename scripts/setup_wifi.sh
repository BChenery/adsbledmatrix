#!/bin/bash
# Deprecated: use wifi_manager.py instead.
# This wrapper remains for backwards compatibility.
#
#   sudo python3 scripts/wifi_manager.py setup-ap
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/wifi_manager.py" setup-ap
