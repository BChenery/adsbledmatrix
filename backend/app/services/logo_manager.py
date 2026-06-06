import csv
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

import httpx
from PIL import Image
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import AirlineLogo

logger = logging.getLogger(__name__)

# Target size for all cached logos
LOGO_SIZE = (96, 96)


class LogoManager:
    """Downloads, resizes, and caches airline logos."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._iata_to_icao: Dict[str, str] = {}
        self._icao_to_iata: Dict[str, str] = {}
        self._icao_to_name: Dict[str, str] = {}
        self._load_airline_codes()

    def _load_airline_codes(self) -> None:
        """Load ICAO↔IATA mapping from airlines.csv."""
        csv_path = settings.data_dir / "airlines.csv"
        if not csv_path.exists():
            logger.warning(f"Airline codes CSV not found: {csv_path}")
            return

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    icao = row.get("icao", "").strip().upper()
                    iata = row.get("iata", "").strip().upper()
                    name = row.get("name", "").strip()
                    if icao and iata:
                        self._icao_to_iata[icao] = iata
                        self._iata_to_icao[iata] = icao
                        self._icao_to_name[icao] = name
        except Exception as e:
            logger.warning(f"Failed to load airline codes: {e}")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        return self._client

    async def get_logo(self, icao_code: str) -> Optional[Path]:
        """Return path to logo. Local files are preferred.

        If the logo is not available locally and auto-download is enabled,
        attempts to download from configured sources.
        Falls back to UNKNOWN.png if no logo can be found.
        """
        if not icao_code:
            return self._unknown_path()

        icao = icao_code.upper()
        path = settings.logos_dir / f"{icao}.png"
        if path.exists():
            return path

        if settings.auto_download_logos:
            downloaded = await self._download_logo(icao, path)
            if downloaded:
                return downloaded

        return self._unknown_path()

    def _unknown_path(self) -> Path:
        return settings.logos_dir / "UNKNOWN.png"

    async def _download_logo(self, icao: str, dest: Path) -> Optional[Path]:
        """Attempt to download logo from multiple sources, resize, and save."""
        client = await self._get_client()
        iata = self._icao_to_iata.get(icao)
        name = self._icao_to_name.get(icao, "")

        urls = []
        # Primary: Jxck-S/airline-logos curated repo (GitHub raw, fast & reliable)
        urls.append(f"https://raw.githubusercontent.com/Jxck-S/airline-logos/main/flightaware_logos/{icao}.png")
        urls.append(f"https://raw.githubusercontent.com/Jxck-S/airline-logos/main/radarbox_logos/{icao}.png")
        # Secondary: Google Flights CDN (high-quality)
        if iata:
            urls.append(f"https://www.gstatic.com/flights/airline_logos/70px/{iata}.png")
        # Tertiary: FlightAware direct (uses ICAO directly)
        urls.append(f"https://www.flightaware.com/images/airline_logos/90p/{icao}.png")

        for url in urls:
            try:
                response = await client.get(url)
                if response.status_code == 200 and len(response.content) > 200:
                    resized = self._resize_image(response.content)
                    if resized:
                        dest.write_bytes(resized)
                        logger.info(f"Downloaded logo for {icao} from {url}")
                        await self._record_logo(icao, iata, name, dest, url)
                        return dest
            except Exception as e:
                logger.debug(f"Failed to download logo from {url}: {e}")
                continue

        logger.warning(f"Could not find logo for airline {icao}")
        return None

    def _resize_image(self, data: bytes) -> Optional[bytes]:
        """Resize downloaded image to standard LOGO_SIZE with transparency."""
        try:
            img = Image.open(BytesIO(data))
            # Convert to RGBA for consistent handling
            img = img.convert("RGBA")
            # Resize using high-quality downsampling
            img = img.resize(LOGO_SIZE, Image.LANCZOS)
            # Save to bytes
            out = BytesIO()
            img.save(out, format="PNG", optimize=True)
            return out.getvalue()
        except Exception as e:
            logger.debug(f"Image resize failed: {e}")
            return None

    async def _record_logo(self, icao: str, iata: Optional[str], name: str, path: Path, url: str) -> None:
        """Upsert logo metadata into the database."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = sqlite_insert(AirlineLogo).values(
                    icao_code=icao,
                    iata_code=iata,
                    name=name,
                    logo_path=str(path),
                    logo_url=url,
                    downloaded_at=datetime.utcnow(),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[AirlineLogo.icao_code],
                    set_={
                        "iata_code": iata,
                        "name": name,
                        "logo_path": str(path),
                        "logo_url": url,
                        "downloaded_at": datetime.utcnow(),
                    },
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to record logo in DB for {icao}: {e}")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


logo_manager = LogoManager()
