"""Airport code → IATA / city lookups for route display fields."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AirportInfo:
    icao: str
    iata: str
    city: str


def _norm(code: Optional[str]) -> str:
    if not code:
        return ""
    return re.sub(r"[^A-Z0-9]", "", code.strip().upper())


class AirportService:
    """Load a compact airports table and resolve ICAO/IATA → IATA + city."""

    def __init__(self, csv_path: Optional[Path] = None):
        self._path = csv_path or (settings.data_dir / "airports.csv")
        self._by_icao: Dict[str, AirportInfo] = {}
        self._by_iata: Dict[str, AirportInfo] = {}
        self._loaded = False

    def reload(self) -> int:
        self._by_icao.clear()
        self._by_iata.clear()
        self._loaded = False
        return self._ensure_loaded()

    def _ensure_loaded(self) -> int:
        if self._loaded:
            return len(self._by_icao) + len(self._by_iata)
        self._loaded = True
        path = self._path
        if not path.exists():
            logger.warning("Airports CSV not found at %s", path)
            return 0
        count = 0
        try:
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    icao = _norm(row.get("icao"))
                    iata = _norm(row.get("iata"))
                    city = (row.get("city") or "").strip()
                    if not city:
                        continue
                    if icao and len(icao) != 4:
                        icao = ""
                    if iata and len(iata) != 3:
                        iata = ""
                    if not icao and not iata:
                        continue
                    info = AirportInfo(icao=icao, iata=iata, city=city)
                    if icao:
                        self._by_icao[icao] = info
                    if iata:
                        # Prefer ICAO-backed row when multiple
                        existing = self._by_iata.get(iata)
                        if existing is None or (info.icao and not existing.icao):
                            self._by_iata[iata] = info
                    count += 1
        except Exception as exc:
            logger.warning("Failed to load airports CSV: %s", exc)
            return 0
        logger.info(
            "Loaded %d airport rows (%d ICAO, %d IATA) from %s",
            count,
            len(self._by_icao),
            len(self._by_iata),
            path,
        )
        return count

    def lookup(self, code: Optional[str]) -> Optional[AirportInfo]:
        """Resolve an ICAO (YBBN) or IATA (BNE) airport code."""
        self._ensure_loaded()
        key = _norm(code)
        if not key:
            return None
        if len(key) == 4:
            return self._by_icao.get(key)
        if len(key) == 3:
            return self._by_iata.get(key)
        # Unusual lengths: try both maps
        return self._by_icao.get(key) or self._by_iata.get(key)

    def iata(self, code: Optional[str]) -> str:
        """Three-letter IATA for a code, or the original if already IATA / unknown."""
        info = self.lookup(code)
        if info and info.iata:
            return info.iata
        key = _norm(code)
        if len(key) == 3:
            return key
        return ""

    def city(self, code: Optional[str]) -> str:
        info = self.lookup(code)
        return info.city if info else ""

    def display_values_for_route(
        self,
        origin: Optional[str],
        destination: Optional[str],
    ) -> Dict[str, str]:
        """Extra layout fields derived from route origin/destination codes."""
        o = _norm(origin)
        d = _norm(destination)
        o_iata = self.iata(o) or (o if len(o) == 3 else "---")
        d_iata = self.iata(d) or (d if len(d) == 3 else "---")
        o_city = self.city(o) or "---"
        d_city = self.city(d) or "---"
        # If lookup failed entirely and code is empty
        if not o:
            o_iata = "---"
            o_city = "---"
        if not d:
            d_iata = "---"
            d_city = "---"
        return {
            "origin_iata": o_iata if o_iata else "---",
            "destination_iata": d_iata if d_iata else "---",
            "origin_city": o_city,
            "destination_city": d_city,
            # Friendly aliases
            "from_city": o_city,
            "to_city": d_city,
            "from_iata": o_iata if o_iata else "---",
            "to_iata": d_iata if d_iata else "---",
        }


airport_service = AirportService()
