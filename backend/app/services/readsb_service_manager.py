import logging
import subprocess
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services.adsb_receiver import receiver

logger = logging.getLogger(__name__)

NETWORK_FLAG_FILE = Path(settings.data_dir) / ".network_receiver_enabled"


def _run_systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def is_readsb_available() -> bool:
    """Return True if systemctl and readsb.service are present."""
    result = _run_systemctl("status", "readsb.service")
    # status returns 0 if active, 3 if inactive but unit exists, 4 if unit missing
    return result.returncode in (0, 3)


def start_readsb() -> None:
    if not is_readsb_available():
        logger.info("readsb.service not available; skipping start")
        return
    logger.info("Starting readsb.service")
    result = _run_systemctl("start", "readsb.service")
    if result.returncode != 0:
        logger.warning(f"Failed to start readsb.service: {result.stderr.strip()}")


def stop_readsb() -> None:
    if not is_readsb_available():
        logger.info("readsb.service not available; skipping stop")
        return
    logger.info("Stopping readsb.service")
    result = _run_systemctl("stop", "readsb.service")
    if result.returncode != 0:
        logger.warning(f"Failed to stop readsb.service: {result.stderr.strip()}")


def _resolve_receiver_config(config) -> tuple[str, int]:
    if config.receiver_source == "network" and config.network_readsb_host:
        return config.network_readsb_host, config.network_readsb_port
    return "127.0.0.1", 30003


def set_network_flag(enabled: bool) -> None:
    if enabled:
        NETWORK_FLAG_FILE.touch(exist_ok=True)
    else:
        NETWORK_FLAG_FILE.unlink(missing_ok=True)


def apply_receiver_source(config) -> None:
    """Apply receiver source configuration: endpoint + local service state + flag file."""
    host, port = _resolve_receiver_config(config)
    receiver.set_endpoint(host, port)

    if config.receiver_source == "network":
        set_network_flag(True)
        stop_readsb()
    else:
        set_network_flag(False)
        start_readsb()
