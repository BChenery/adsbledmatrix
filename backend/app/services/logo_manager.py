import csv
import logging
import re
import shutil
import tempfile
import zipfile
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

# Airlines that are branded as another airline. The target logo is always used
# even if a logo for the original ICAO exists locally.
_LOGO_DISPLAY_ALIASES: Dict[str, str] = {
    "QLK": "QFA",     # QantasLink flights carry Qantas branding
}

# The aircraft database sometimes stores IATA codes (or wrong codes) in the
# operator_icao field. Map those to the real ICAO used in the logo filenames.
# These are only used as a fallback when the original code's logo is missing.
_LOGO_ICAO_OVERRIDES: Dict[str, str] = {
    "VA": "VOZ",      # Virgin Australia
    "VIR": "VOZ",     # Virgin Australia (wrong ICAO in some DBs)
    "JQ": "JST",      # Jetstar
    "JJP": "JST",     # Jetstar (wrong ICAO in some DBs)
    "TT": "TGW",      # Tigerair
    "TGG": "TGW",     # Tigerair (wrong ICAO in some DBs)
    "NZ": "ANZ",      # Air New Zealand
}

# Operators expected on the VH- Australian aircraft register. Used as a sanity
# check to avoid showing a foreign airline logo for a locally-registered aircraft
# when only the callsign prefix or operator code is ambiguous.
_AUSTRALIAN_OPERATOR_ICAOS: set[str] = {
    "QFA", "QLK", "VOZ", "JST", "TGW", "RXA", "UTY",
    "ANO", "ATM", "NJS", "SHA", "PEL", "MCK", "OZJ",
    "ELA", "HZA", "AAA", "ORC", "FJI", "ANZ", "RFDS",
}


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

    def logo_path_for_icao(self, icao_code: str) -> Optional[Path]:
        """Return the local logo path for an ICAO, applying known overrides."""
        if not icao_code:
            return None
        icao = icao_code.upper()
        # Hard display aliases always take precedence (e.g. QantasLink -> Qantas).
        forced_alias = _LOGO_DISPLAY_ALIASES.get(icao)
        if forced_alias:
            path = settings.logos_dir / f"{forced_alias}.png"
            if path.exists():
                return path
        # Otherwise prefer the code's own logo, falling back to override targets.
        candidates = [icao, _LOGO_ICAO_OVERRIDES.get(icao)]
        for candidate in candidates:
            if not candidate:
                continue
            path = settings.logos_dir / f"{candidate}.png"
            if path.exists():
                return path
        return None

    def logo_path_for_aircraft(
        self,
        operator_icao: Optional[str],
        callsign: Optional[str],
        registration: Optional[str] = None,
    ) -> Optional[Path]:
        """Return the local logo path for an aircraft, using the callsign prefix first.

        Aircraft are often wet-leased or operated by a different company from the
        one selling the flight (e.g. an Alliance Airlines aircraft flying a Virgin
        Australia VOZ service). The callsign prefix is a much better indicator of
        the brand that should be shown on the display than the registered operator.

        Falls back to the operator ICAO logo when no callsign is available or the
        prefix cannot be resolved to a known airline.
        """
        resolved_icao: Optional[str] = None
        if callsign:
            prefix_icao = self._callsign_prefix_to_icao(callsign, registration)
            if prefix_icao:
                resolved_icao = (
                    _LOGO_DISPLAY_ALIASES.get(prefix_icao)
                    or _LOGO_ICAO_OVERRIDES.get(prefix_icao, prefix_icao)
                )
                path = settings.logos_dir / f"{resolved_icao}.png"
                if path.exists():
                    return path

        if registration and registration.upper().strip().startswith("VH-"):
            candidate = resolved_icao
            if not candidate and operator_icao:
                # Normalise operator_icao the same way callsign prefixes are,
                # so wrong-code entries like "VA" map to "VOZ" before the
                # Australian-operator sanity check.
                icao = operator_icao.upper()
                candidate = _LOGO_ICAO_OVERRIDES.get(icao, icao)
            if candidate and candidate.upper() not in _AUSTRALIAN_OPERATOR_ICAOS:
                return self._unknown_path()

        if operator_icao:
            return self.logo_path_for_icao(operator_icao)

        return None

    def _callsign_prefix_to_icao(
        self, callsign: str, registration: Optional[str] = None
    ) -> Optional[str]:
        """Extract the airline code from a callsign and normalise it to ICAO.

        The prefix is the leading 2-3 alphabetic characters. If the prefix matches
        a known IATA code, the corresponding ICAO code is returned instead.

        The FD prefix is ambiguous: Thai AirAsia uses FD callsigns with HS-
        registrations, while the Royal Flying Doctor Service uses FD callsigns on
        VH- registered aircraft.
        """
        match = re.match(r"^([A-Z]{2,3})", callsign.upper().strip())
        if not match:
            return None
        prefix = match.group(1)
        if prefix == "FD":
            reg = (registration or "").upper().strip()
            if reg.startswith("HS-"):
                return "AIQ"
            if reg.startswith("VH-") or not reg:
                return "RFDS"
        # IATA codes are two letters; ICAO codes are three letters.
        return self._iata_to_icao.get(prefix, prefix)

    async def _download_logo(self, icao: str, dest: Path) -> Optional[Path]:
        """Attempt to download logo from multiple sources, resize, and save."""
        client = await self._get_client()
        iata = self._icao_to_iata.get(icao)
        name = self._icao_to_name.get(icao, "")

        urls = []
        # Primary: Jxck-S/airline-logos curated repo (GitHub raw, fast & reliable)
        urls.append(f"https://raw.githubusercontent.com/Jxck-S/airline-logos/main/radarbox_logos/{icao}.png")
        urls.append(f"https://raw.githubusercontent.com/Jxck-S/airline-logos/main/flightaware_logos/{icao}.png")
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
            # Threshold the alpha channel to remove anti-aliased colour fringes
            # that show as stray red/blue dots on low-resolution LED matrices.
            r, g, b, a = img.split()
            a = a.point(lambda p: 255 if p > 64 else 0)
            img = Image.merge("RGBA", (r, g, b, a))
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

    async def bulk_import_from_github(
        self, repo_url: str = "https://github.com/Jxck-S/airline-logos", overwrite: bool = False
    ) -> Dict[str, int]:
        """Download the airline-logos repo and import all PNG logos locally.

        Args:
            repo_url: URL of the Jxck-S/airline-logos repository.
            overwrite: If True, replace existing local logos with the
                Radarbox-first source priority. If False, skip existing files.
        """
        import asyncio

        zip_url = f"{repo_url.rstrip('/')}/archive/refs/heads/main.zip"
        client = await self._get_client()
        downloaded = 0
        skipped = 0
        failed = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            zip_path = tmp_path / "airline-logos.zip"

            logger.info(f"Downloading airline logos archive from {zip_url}")
            response = await client.get(zip_url)
            response.raise_for_status()
            zip_path.write_bytes(response.content)

            extract_path = tmp_path / "extracted"
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_path)

            # The archive extracts to airline-logos-main/
            repo_root = next(extract_path.iterdir())
            flightaware_dir = repo_root / "flightaware_logos"
            radarbox_dir = repo_root / "radarbox_logos"

            # Build a per-ICAO lookup, preferring Radarbox over FlightAware.
            logo_choices: Dict[str, Path] = {}
            for source in (radarbox_dir, flightaware_dir):
                if not source.exists():
                    continue
                for png_file in source.glob("*.png"):
                    icao = png_file.stem.upper()
                    # Skip non-ICAO filenames
                    if not icao.isalpha():
                        skipped += 1
                        continue
                    if icao not in logo_choices:
                        logo_choices[icao] = png_file

            tasks = []
            for icao, png_file in logo_choices.items():
                dest = settings.logos_dir / f"{icao}.png"
                if dest.exists() and not overwrite:
                    skipped += 1
                    continue
                tasks.append(self._import_bulk_logo(icao, png_file, dest))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.warning(f"Bulk logo import error: {result}")
                        failed += 1
                    elif result:
                        downloaded += 1
                    else:
                        failed += 1

        logger.info(f"Bulk logo import complete: {downloaded} downloaded, {skipped} skipped, {failed} failed")
        return {"downloaded": downloaded, "skipped": skipped, "failed": failed}

    async def _import_bulk_logo(self, icao: str, source: Path, dest: Path) -> bool:
        """Resize and copy a single logo from the bulk import."""
        try:
            data = source.read_bytes()
            resized = self._resize_image(data)
            if not resized:
                return False
            dest.write_bytes(resized)
            iata = self._icao_to_iata.get(icao)
            name = self._icao_to_name.get(icao, "")
            await self._record_logo(icao, iata, name, dest, str(source))
            return True
        except Exception as e:
            logger.warning(f"Failed to import logo for {icao}: {e}")
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


logo_manager = LogoManager()
