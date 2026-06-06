import logging
from pathlib import Path
from typing import Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class LogoManager:
    """Downloads and caches airline logos."""

    # Known logo sources - try in order
    LOGO_SOURCES = [
        "https://logo.clearbit.com/{domain}",
        "https://www.flightaware.com/images/airline_logos/90p/{iata}.png",
    ]

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def get_logo(self, icao_code: str) -> Optional[Path]:
        """Return path to logo, downloading if necessary."""
        if not icao_code:
            return None
        icao = icao_code.upper()
        path = settings.logos_dir / f"{icao}.png"
        if path.exists():
            return path
        return await self._download_logo(icao, path)

    async def _download_logo(self, icao: str, dest: Path) -> Optional[Path]:
        """Attempt to download logo from known sources."""
        client = await self._get_client()

        # Try FlightAware style first (most reliable for aviation)
        urls = [
            f"https://www.flightaware.com/images/airline_logos/90p/{icao}.png",
        ]

        for url in urls:
            try:
                response = await client.get(url)
                if response.status_code == 200 and len(response.content) > 100:
                    dest.write_bytes(response.content)
                    logger.info(f"Downloaded logo for {icao} from {url}")
                    return dest
            except Exception as e:
                logger.debug(f"Failed to download logo from {url}: {e}")
                continue

        logger.warning(f"Could not find logo for airline {icao}")
        return None

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


logo_manager = LogoManager()
