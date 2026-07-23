import asyncio
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, List
from app.services.geocalc import haversine_distance, calculate_bearing
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LiveAircraft:
    hex_code: str
    callsign: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[int] = None
    ground_speed: Optional[int] = None
    heading: Optional[float] = None
    vertical_rate: Optional[int] = None
    squawk: Optional[str] = None
    last_seen: datetime = field(default_factory=datetime.utcnow)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    messages: int = 0
    distance_km: Optional[float] = None
    bearing: Optional[float] = None

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.last_seen = datetime.utcnow()
        self.messages += 1

    def is_stale(self, timeout: int = settings.aircraft_timeout_seconds) -> bool:
        return datetime.utcnow() - self.last_seen > timedelta(seconds=timeout)


class ADSBReceiver:
    """Reads SBS/BaseStation format from readsb TCP port 30003."""

    # Reconnect if no SBS bytes arrive for this long (half-open / stalled TCP).
    # Quiet airspace can still produce heartbeats from distant aircraft; 45s is
    # long enough to avoid thrashing while recovering stuck sessions quickly.
    STALL_TIMEOUT_SECONDS = 45.0

    def __init__(self):
        self.aircraft: Dict[str, LiveAircraft] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []
        self._user_lat: Optional[float] = None
        self._user_lon: Optional[float] = None
        self._mock_defs: List[dict] = []
        self._readsb_host = settings.readsb_host
        self._readsb_port = settings.readsb_port
        self._connected = False
        self._last_data_at: Optional[datetime] = None

    @property
    def connected(self) -> bool:
        """True while a TCP session is open and not yet stalled."""
        if not self._connected or self._last_data_at is None:
            return False
        idle = (datetime.utcnow() - self._last_data_at).total_seconds()
        return idle < self.STALL_TIMEOUT_SECONDS

    @property
    def endpoint(self) -> tuple[str, int]:
        return self._readsb_host, self._readsb_port

    async def set_endpoint(self, host: str, port: int) -> None:
        endpoint_changed = host != self._readsb_host or port != self._readsb_port
        self._readsb_host = host
        self._readsb_port = port

        task_alive = self._task is not None and not self._task.done()
        # Skip restart when the endpoint is unchanged and the read loop is healthy.
        if not endpoint_changed and task_alive:
            return

        # Restart when the endpoint changed, or recover a dead/stopped task that
        # was previously started (e.g. after a failed stop during config save).
        if self._running or self._task is not None:
            await self.stop()
            await self.start()

    def set_user_location(self, lat: Optional[float], lon: Optional[float]):
        self._user_lat = lat
        self._user_lon = lon
        self._recalculate_distances()

    def register_callback(self, callback: Callable):
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def start(self):
        if self._running:
            return
        self._running = True
        if settings.mock_aircraft:
            self._task = asyncio.create_task(self._mock_loop())
            logger.info("ADSB receiver started (mock mode)")
        else:
            self._task = asyncio.create_task(self._read_loop())
            logger.info("ADSB receiver started")

    async def stop(self):
        self._running = False
        task = self._task
        self._task = None
        self._connected = False
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                # Peer resets and similar close races are common on SBS streams;
                # never let them fail config saves or leave the task orphaned.
                logger.debug("Receiver task ended with error during stop: %s", e)
        logger.info("ADSB receiver stopped")

    async def _close_writer(self, writer) -> None:
        if writer is None:
            return
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            # Closing a reset SBS socket often raises ConnectionResetError.
            pass

    async def _read_loop(self):
        while self._running:
            writer = None
            retry_delay = 1.0
            try:
                reader, writer = await asyncio.open_connection(
                    self._readsb_host, self._readsb_port
                )
                self._connected = True
                self._last_data_at = datetime.utcnow()
                logger.info(
                    f"Connected to readsb at {self._readsb_host}:{self._readsb_port}"
                )
                buffer = ""
                while self._running:
                    try:
                        data = await asyncio.wait_for(
                            reader.read(4096), timeout=10.0
                        )
                        if not data:
                            logger.warning("readsb connection closed by peer")
                            break
                        self._last_data_at = datetime.utcnow()
                        buffer += data.decode("utf-8", errors="ignore")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            self._parse_line(line.strip())
                    except asyncio.TimeoutError:
                        # Drop zombies even when the wire is quiet.
                        self._clean_stale()
                        idle = (
                            (datetime.utcnow() - self._last_data_at).total_seconds()
                            if self._last_data_at
                            else 0.0
                        )
                        if idle >= self.STALL_TIMEOUT_SECONDS:
                            logger.warning(
                                "readsb stall: no data for %.0fs, reconnecting",
                                idle,
                            )
                            break
                        continue
            except asyncio.CancelledError:
                self._connected = False
                raise
            except Exception as e:
                self._connected = False
                logger.warning(f"readsb connection error: {e}, retrying in 5s...")
                retry_delay = 5.0
            finally:
                self._connected = False
                await self._close_writer(writer)
            # Pause before reconnect so we don't spin on a hard fail / stall.
            if self._running:
                await asyncio.sleep(retry_delay)

    def _parse_line(self, line: str):
        # SBS/BaseStation format (CSV)
        # MSG,1,1,1,406A86,1,2024/01/15,12:34:56.789,2024/01/15,12:34:56.789,BAW123,...
        if not line.startswith("MSG,"):
            return
        parts = line.split(",")
        if len(parts) < 22:
            return

        msg_type = parts[1]
        hex_code = parts[4].strip().upper()
        if not hex_code:
            return

        # Parse datetime
        date_str = f"{parts[6]} {parts[7]}"
        try:
            timestamp = datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S.%f")
        except ValueError:
            timestamp = datetime.utcnow()

        # last_seen is always wall-clock receive time (set in LiveAircraft.update).
        # Do not trust the feeder's SBS clock for staleness.
        updates: dict = {}

        if msg_type in ("1", "5", "6"):  # ES ID, Surveillance ID, ADS-R ID
            callsign = parts[10].strip()
            if callsign:
                updates["callsign"] = callsign

        if msg_type in ("2", "3", "7", "8"):  # ES surface/ airborne position
            altitude = self._safe_int(parts[11])
            if altitude is not None:
                updates["altitude"] = altitude
            lat = self._safe_float(parts[14])
            lon = self._safe_float(parts[15])
            if lat is not None:
                updates["latitude"] = lat
            if lon is not None:
                updates["longitude"] = lon

        if msg_type in ("2", "4", "7", "8"):  # Surface/ES airborne velocity
            ground_speed = self._safe_int(parts[12])
            if ground_speed is not None:
                updates["ground_speed"] = ground_speed
            heading = self._safe_float(parts[13])
            if heading is not None:
                updates["heading"] = heading
            vertical_rate = self._safe_int(parts[16])
            if vertical_rate is not None:
                updates["vertical_rate"] = vertical_rate

        if msg_type in ("5", "6", "7", "8"):  # Squawk
            squawk = parts[17].strip()
            if squawk:
                updates["squawk"] = squawk

        # Update aircraft record
        if hex_code not in self.aircraft:
            self.aircraft[hex_code] = LiveAircraft(
                hex_code=hex_code, first_seen=timestamp
            )

        self.aircraft[hex_code].update(**updates)

        # Calculate distance if we have position
        self._update_distance(self.aircraft[hex_code])

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self.aircraft[hex_code])
            except Exception:
                pass

        # Clean stale aircraft periodically
        self._clean_stale()

    async def _mock_loop(self):
        """Generate fake aircraft orbiting the user's location for demo/dev."""
        if not self._mock_defs:
            self._mock_defs = [
                {"hex": "406A86", "callsign": "BAW123", "alt": 32000, "speed": 450, "dist": 5.0, "angle": 0},
                {"hex": "7C6B08", "callsign": "QFA45", "alt": 28000, "speed": 380, "dist": 12.0, "angle": 72},
                {"hex": "A8B1C2", "callsign": "DAL456", "alt": 15000, "speed": 250, "dist": 3.5, "angle": 144},
                {"hex": "C3D4E5", "callsign": "AAL789", "alt": 41000, "speed": 490, "dist": 20.0, "angle": 216},
                {"hex": "F6A7B8", "callsign": "UAE201", "alt": 36000, "speed": 470, "dist": 8.0, "angle": 288},
            ]

        while self._running:
            if self._user_lat is None or self._user_lon is None:
                await asyncio.sleep(2)
                continue

            for ac_def in self._mock_defs:
                hex_code = ac_def["hex"]
                ac_def["angle"] = (ac_def["angle"] + 0.3) % 360

                # Approximate lat/lon from polar offset
                rad = math.radians(ac_def["angle"])
                delta_lat = (ac_def["dist"] * math.cos(rad)) / 111.0
                delta_lon = (ac_def["dist"] * math.sin(rad)) / (
                    111.0 * math.cos(math.radians(self._user_lat))
                )

                lat = self._user_lat + delta_lat
                lon = self._user_lon + delta_lon

                if hex_code not in self.aircraft:
                    self.aircraft[hex_code] = LiveAircraft(
                        hex_code=hex_code, first_seen=datetime.utcnow()
                    )

                self.aircraft[hex_code].update(
                    callsign=ac_def["callsign"],
                    altitude=ac_def["alt"] + random.randint(-200, 200),
                    ground_speed=ac_def["speed"] + random.randint(-15, 15),
                    heading=(ac_def["angle"] + 90) % 360,
                    vertical_rate=random.choice([-1200, -600, 0, 0, 0, 600, 1200]),
                    latitude=lat,
                    longitude=lon,
                    last_seen=datetime.utcnow(),
                )
                self._update_distance(self.aircraft[hex_code])

                for callback in self._callbacks:
                    try:
                        callback(self.aircraft[hex_code])
                    except Exception:
                        pass

            self._clean_stale()
            await asyncio.sleep(1)

    def _update_distance(self, ac: LiveAircraft):
        if (
            self._user_lat is not None
            and self._user_lon is not None
            and ac.latitude is not None
            and ac.longitude is not None
        ):
            ac.distance_km = haversine_distance(
                self._user_lat, self._user_lon, ac.latitude, ac.longitude
            )
            ac.bearing = calculate_bearing(
                self._user_lat, self._user_lon, ac.latitude, ac.longitude
            )

    def _recalculate_distances(self):
        for ac in self.aircraft.values():
            self._update_distance(ac)

    def _clean_stale(self):
        stale = [hex_code for hex_code, ac in self.aircraft.items() if ac.is_stale()]
        for hex_code in stale:
            del self.aircraft[hex_code]

    def get_closest(self, n: int = 1) -> List[LiveAircraft]:
        """Return the N closest aircraft with valid positions."""
        valid = [
            ac
            for ac in self.aircraft.values()
            if ac.distance_km is not None and not ac.is_stale()
        ]
        valid.sort(key=lambda ac: ac.distance_km or float("inf"))
        return valid[:n]

    def get_recent(self, n: int = 20) -> List[LiveAircraft]:
        """Return the N most recently seen aircraft, regardless of position."""
        valid = [ac for ac in self.aircraft.values() if not ac.is_stale()]
        valid.sort(key=lambda ac: ac.last_seen, reverse=True)
        return valid[:n]

    def get_all(self) -> List[LiveAircraft]:
        self._clean_stale()
        return list(self.aircraft.values())

    @staticmethod
    def _safe_int(value: str) -> Optional[int]:
        try:
            return int(value.strip())
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _safe_float(value: str) -> Optional[float]:
        try:
            return float(value.strip())
        except (ValueError, AttributeError):
            return None


# Global singleton instance
receiver = ADSBReceiver()
