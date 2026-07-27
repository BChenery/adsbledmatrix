"""Type-aware aircraft silhouettes for the LED radar marker.

Classifies ICAO type codes (via localadsb icao_aircraft_types.json when available)
into a small set of top-down shapes: helicopter, light GA, turboprop, jet,
heavy jet, and jumbo. Shapes are intentionally simple so they stay legible on
a low-resolution LED matrix.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

Point = Tuple[float, float]
Polygon = List[Point]

# Prefer the localadsb copy, fall back to project root if present.
_ICAO_TYPES_PATHS = [
    Path(__file__).resolve().parents[3] / "data" / "localadsb" / "icao_aircraft_types.json",
    Path(__file__).resolve().parents[3] / "icao_aircraft_types.json",
]

# Icon classes rendered on the radar.
ICON_HELICOPTER = "helicopter"
ICON_LIGHT_GA = "light_ga"
ICON_TURBOPROP = "turboprop"
ICON_JET = "jet"
ICON_HEAVY = "heavy"
ICON_JUMBO = "jumbo"

# Explicit type-code overrides for well-known families (used when ICAO metadata
# is missing, or to refine edge cases).
_TYPE_OVERRIDES: Dict[str, str] = {
    # Helicopters
    "R22": ICON_HELICOPTER,
    "R44": ICON_HELICOPTER,
    "R66": ICON_HELICOPTER,
    "B06": ICON_HELICOPTER,
    "B06T": ICON_HELICOPTER,
    "B407": ICON_HELICOPTER,
    "B412": ICON_HELICOPTER,
    "B429": ICON_HELICOPTER,
    "EC20": ICON_HELICOPTER,
    "EC25": ICON_HELICOPTER,
    "EC30": ICON_HELICOPTER,
    "EC35": ICON_HELICOPTER,
    "EC45": ICON_HELICOPTER,
    "EC55": ICON_HELICOPTER,
    "EC75": ICON_HELICOPTER,
    "A109": ICON_HELICOPTER,
    "A119": ICON_HELICOPTER,
    "A139": ICON_HELICOPTER,
    "A169": ICON_HELICOPTER,
    "A189": ICON_HELICOPTER,
    "H60": ICON_HELICOPTER,
    "S92": ICON_HELICOPTER,
    "S76": ICON_HELICOPTER,
    "AS50": ICON_HELICOPTER,
    "AS55": ICON_HELICOPTER,
    "AS65": ICON_HELICOPTER,
    "H160": ICON_HELICOPTER,
    "MI8": ICON_HELICOPTER,
    "MI17": ICON_HELICOPTER,
    # Light GA / Cessna-class
    "C150": ICON_LIGHT_GA,
    "C152": ICON_LIGHT_GA,
    "C170": ICON_LIGHT_GA,
    "C172": ICON_LIGHT_GA,
    "C177": ICON_LIGHT_GA,
    "C182": ICON_LIGHT_GA,
    "C185": ICON_LIGHT_GA,
    "C206": ICON_LIGHT_GA,
    "C207": ICON_LIGHT_GA,
    "C210": ICON_LIGHT_GA,
    "PA28": ICON_LIGHT_GA,
    "PA32": ICON_LIGHT_GA,
    "PA38": ICON_LIGHT_GA,
    "PA46": ICON_LIGHT_GA,
    "P28A": ICON_LIGHT_GA,
    "P28B": ICON_LIGHT_GA,
    "P28R": ICON_LIGHT_GA,
    "BE33": ICON_LIGHT_GA,
    "BE35": ICON_LIGHT_GA,
    "BE36": ICON_LIGHT_GA,
    "M20P": ICON_LIGHT_GA,
    "SR20": ICON_LIGHT_GA,
    "SR22": ICON_LIGHT_GA,
    "DA40": ICON_LIGHT_GA,
    "DA20": ICON_LIGHT_GA,
    "RV7": ICON_LIGHT_GA,
    "RV8": ICON_LIGHT_GA,
    "RV10": ICON_LIGHT_GA,
    "RV12": ICON_LIGHT_GA,
    # Turboprops / regional twin props
    "C208": ICON_TURBOPROP,
    "PC12": ICON_TURBOPROP,
    "TBM7": ICON_TURBOPROP,
    "TBM8": ICON_TURBOPROP,
    "TBM9": ICON_TURBOPROP,
    "BE20": ICON_TURBOPROP,
    "BE30": ICON_TURBOPROP,
    "B350": ICON_TURBOPROP,
    "DH8A": ICON_TURBOPROP,
    "DH8B": ICON_TURBOPROP,
    "DH8C": ICON_TURBOPROP,
    "DH8D": ICON_TURBOPROP,
    "AT43": ICON_TURBOPROP,
    "AT45": ICON_TURBOPROP,
    "AT72": ICON_TURBOPROP,
    "AT73": ICON_TURBOPROP,
    "AT75": ICON_TURBOPROP,
    "AT76": ICON_TURBOPROP,
    "SF34": ICON_TURBOPROP,
    "E120": ICON_TURBOPROP,
    "D328": ICON_TURBOPROP,
    "JS32": ICON_TURBOPROP,
    "JS41": ICON_TURBOPROP,
    # Heavy widebodies
    "B762": ICON_HEAVY,
    "B763": ICON_HEAVY,
    "B764": ICON_HEAVY,
    "B772": ICON_HEAVY,
    "B773": ICON_HEAVY,
    "B77L": ICON_HEAVY,
    "B77W": ICON_HEAVY,
    "B778": ICON_HEAVY,
    "B779": ICON_HEAVY,
    "B788": ICON_HEAVY,
    "B789": ICON_HEAVY,
    "B78X": ICON_HEAVY,
    "A306": ICON_HEAVY,
    "A30B": ICON_HEAVY,
    "A310": ICON_HEAVY,
    "A332": ICON_HEAVY,
    "A333": ICON_HEAVY,
    "A338": ICON_HEAVY,
    "A339": ICON_HEAVY,
    "A342": ICON_HEAVY,
    "A343": ICON_HEAVY,
    "A345": ICON_HEAVY,
    "A346": ICON_HEAVY,
    "A359": ICON_HEAVY,
    "A35K": ICON_HEAVY,
    "IL96": ICON_HEAVY,
    # Jumbos / four-engine heavies
    "B741": ICON_JUMBO,
    "B742": ICON_JUMBO,
    "B743": ICON_JUMBO,
    "B744": ICON_JUMBO,
    "B748": ICON_JUMBO,
    "B74R": ICON_JUMBO,
    "B74S": ICON_JUMBO,
    "A124": ICON_JUMBO,
    "A225": ICON_JUMBO,
    "A380": ICON_JUMBO,
    "A388": ICON_JUMBO,
    "A3ST": ICON_JUMBO,
}

# Polygons point up (nose = north / heading 0°). Coordinates are relative to centre.
# Keep extents roughly ±4–6 px so markers stay readable on a dense radar.
_SYMBOLS: Dict[str, Polygon] = {
    # Generic twin-jet airliner (A320 / B737 class) — original silhouette.
    ICON_JET: [
        (0, -4),
        (-3, 2),
        (-1, 1),
        (0, 3),
        (1, 1),
        (3, 2),
    ],
    # High-wing light GA (Cessna-style): short straight wings, prop spinner, tailplane.
    ICON_LIGHT_GA: [
        (0, -5),
        (-1, -3),
        (-4, -1),
        (-1, -1),
        (-1, 3),
        (-2, 4),
        (0, 3),
        (2, 4),
        (1, 3),
        (1, -1),
        (4, -1),
        (1, -3),
    ],
    # Twin turboprop / regional: wing engines as mid-wing bulges, T-tail-ish aft.
    ICON_TURBOPROP: [
        (0, -4),
        (-1, -2),
        (-4, 0),
        (-5, 1),
        (-3, 1),
        (-1, 0),
        (-1, 3),
        (-2, 4),
        (0, 3),
        (2, 4),
        (1, 3),
        (1, 0),
        (3, 1),
        (5, 1),
        (4, 0),
        (1, -2),
    ],
    # Heavy widebody: longer fuselage, wider wings.
    ICON_HEAVY: [
        (0, -5),
        (-5, 2),
        (-1, 1),
        (-1, 3),
        (0, 5),
        (1, 3),
        (1, 1),
        (5, 2),
    ],
    # Jumbo / four-engine: wide span + engine nacelle steps on the wings.
    ICON_JUMBO: [
        (0, -5),
        (-1, -3),
        (-5, 1),
        (-4, 0),
        (-3, 1),
        (-1, 0),
        (-1, 3),
        (-2, 5),
        (0, 4),
        (2, 5),
        (1, 3),
        (1, 0),
        (3, 1),
        (4, 0),
        (5, 1),
        (1, -3),
    ],
    # Helicopter top-down: main rotor disc left–right, cabin, tail boom + tail rotor.
    ICON_HELICOPTER: [
        (0, -2),
        (-1, -1),
        (-5, 0),
        (-1, 0),
        (-1, 3),
        (-2, 4),
        (0, 5),
        (2, 4),
        (1, 3),
        (1, 0),
        (5, 0),
        (1, -1),
    ],
}

_HELI_NAME_RE = re.compile(
    r"helicopter|rotorcraft|gyroplane|gyrocopter|autogyro",
    re.IGNORECASE,
)
_JUMBO_NAME_RE = re.compile(r"\b(747|a380|an-?124|an-?225)\b", re.IGNORECASE)
_HEAVY_NAME_RE = re.compile(
    r"\b(777|787|a330|a340|a350|a300|a310|il-?96|md-?11|dc-?10)\b",
    re.IGNORECASE,
)
_BIZJET_NAME_RE = re.compile(
    r"""
    citation|mustang|m2\b|cj[1234]|
    gulfstream|global\s*express|glex|
    learjet|lear\s*jet|
    falcon\s*\d|dassault\s*falcon|
    challenger|global\s*5|global\s*6|
    phenom|legacy\s*5|praetor|
    hawker|premier|horizon|
    eclipse|vision\s*jet|sf50|
    embraer\s*legacy|embraer\s*phenom|
    bombardier\s*global|bombardier\s*challenger|
    cessna\s*citation|beechjet|hawker\s*800|
    pc-?24|pilatus\s*pc-?24
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ICAO type-code prefixes / exact codes commonly used for business jets.
_BIZJET_CODES = frozenset(
    {
        # Cessna Citation family
        "C25A",
        "C25B",
        "C25C",
        "C25M",
        "C500",
        "C501",
        "C525",
        "C526",
        "C550",
        "C551",
        "C560",
        "C56X",
        "C650",
        "C680",
        "C68A",
        "C700",
        "C750",
        "C25A",
        # Gulfstream
        "GLF2",
        "GLF3",
        "GLF4",
        "GLF5",
        "GLF6",
        "GL5T",
        "GL7T",
        "GLEX",
        "GA6C",
        "GA5C",
        "GA7C",
        # Bombardier Challenger / Global
        "CL30",
        "CL35",
        "CL60",
        "CL6B",
        "GLEX",
        # Learjet
        "LJ23",
        "LJ24",
        "LJ25",
        "LJ28",
        "LJ31",
        "LJ35",
        "LJ40",
        "LJ45",
        "LJ55",
        "LJ60",
        "LJ70",
        "LJ75",
        "LJ85",
        # Dassault Falcon
        "FA10",
        "FA20",
        "FA50",
        "FA7X",
        "FA8X",
        "F2TH",
        "F900",
        "F2TH",
        # Embraer Phenom / Legacy / Praetor
        "E50P",
        "E55P",
        "E35L",
        "E545",
        "E550",
        "E55P",
        "PRM1",
        # Hawker / Beechjet
        "H25A",
        "H25B",
        "H25C",
        "BE40",
        "BE4W",
        "PRM1",
        # Others
        "EA50",
        "SF50",
        "HDJT",
        "GALX",
        "SBR1",
        "PC24",
        "ASTR",
        "WW24",
        "H25B",
    }
)
_BIZJET_PREFIXES = (
    "C25",
    "C56",
    "C68",
    "C75",
    "GLF",
    "GLE",
    "GL5",
    "GL7",
    "CL3",
    "CL6",
    "LJ",
    "FA1",
    "FA2",
    "FA5",
    "FA7",
    "FA8",
    "F2T",
    "F90",
    "E50",
    "E55",
    "E35",
    "H25",
    "BE4",
    "HDJ",
    "GAL",
    "SBR",
    "PC24",
    "SF50",
    "EA50",
    "WW24",
    "ASTR",
    "GA5C",
    "GA6C",
    "GA7C",
)

# Fallback logo kinds used when no airline brand logo is available.
LOGO_FALLBACK_HELICOPTER = "helicopter"
LOGO_FALLBACK_PROP = "prop"
LOGO_FALLBACK_BIZJET = "bizjet"
LOGO_FALLBACK_AIRLINER = "airliner"


@lru_cache(maxsize=1)
def _load_icao_types() -> Dict[str, Dict[str, str]]:
    for path in _ICAO_TYPES_PATHS:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                logger.debug("Loaded ICAO aircraft types from %s (%d entries)", path, len(data))
                return data
        except FileNotFoundError:
            continue
        except Exception as exc:
            logger.warning("Failed to load ICAO aircraft types from %s: %s", path, exc)
    logger.warning("ICAO aircraft types unavailable; falling back to type-code heuristics")
    return {}


def classify_aircraft_icon(
    type_code: Optional[str] = None,
    type_name: Optional[str] = None,
) -> str:
    """Return an icon class for the given ICAO type code / human name."""
    code = (type_code or "").strip().upper()
    name = (type_name or "").strip()

    if code and code in _TYPE_OVERRIDES:
        return _TYPE_OVERRIDES[code]

    if name and _HELI_NAME_RE.search(name):
        return ICON_HELICOPTER

    meta = _load_icao_types().get(code) if code else None
    if meta:
        desc = (meta.get("desc") or "").upper()
        wtc = (meta.get("wtc") or "").upper()
        category = desc[0] if desc else ""
        engines = desc[1] if len(desc) >= 2 and desc[1].isdigit() else ""
        engine_type = desc[2] if len(desc) >= 3 else ""

        if category in ("H", "G"):
            return ICON_HELICOPTER

        # Four+ engine jets, or three-engine heavies → jumbo silhouette.
        if engine_type == "J" and engines in ("3", "4", "6", "8"):
            return ICON_JUMBO

        if engine_type == "J" and wtc == "H":
            return ICON_HEAVY

        # Twin/ multi turboprop or multi piston → turboprop shape.
        if engine_type == "T" and engines and engines != "1":
            return ICON_TURBOPROP
        if engine_type == "P" and engines and engines not in ("", "1"):
            return ICON_TURBOPROP
        # Single turboprop (C208, PC12) still reads as light/utility GA-ish but
        # turboprop shape with engine nacelle is more distinctive.
        if engine_type == "T" and engines == "1":
            return ICON_TURBOPROP

        # Single-engine piston light aircraft (Cessna / Piper class).
        if engine_type == "P" and engines == "1" and wtc in ("L", "", "-"):
            return ICON_LIGHT_GA

        if engine_type == "J":
            return ICON_JET

        if wtc == "L":
            return ICON_LIGHT_GA

    # Name-based fallbacks when metadata / overrides miss.
    if name and _JUMBO_NAME_RE.search(name):
        return ICON_JUMBO
    if name and _HEAVY_NAME_RE.search(name):
        return ICON_HEAVY

    # Prefix heuristics for common families when the ICAO table is missing.
    if code:
        if code.startswith(("B74", "A38", "A12", "A22")):
            return ICON_JUMBO
        if code.startswith(("B77", "B78", "B76", "A33", "A34", "A35", "A30")):
            return ICON_HEAVY
        if code.startswith(("C15", "C17", "C18", "C20", "C21", "PA2", "P28", "SR2", "DA4")):
            return ICON_LIGHT_GA
        if code.startswith(("DH8", "AT7", "AT4", "BE2", "SF3", "JS3", "JS4", "PC1", "TBM")):
            return ICON_TURBOPROP
        if code.startswith(("EC", "AS5", "AS6", "R2", "R4", "R6", "B40", "B41", "H6")):
            return ICON_HELICOPTER

    return ICON_JET


def is_bizjet_type(
    type_code: Optional[str] = None,
    type_name: Optional[str] = None,
) -> bool:
    """True for business jets (Citation, Gulfstream, Lear, Falcon, …)."""
    code = (type_code or "").strip().upper()
    name = (type_name or "").strip()

    if code:
        if code in _BIZJET_CODES:
            return True
        if any(code.startswith(prefix) for prefix in _BIZJET_PREFIXES):
            # Avoid airline families that share a short prefix (none currently).
            return True

    if name and _BIZJET_NAME_RE.search(name):
        return True

    # ICAO doc 8643: light twin-jets with WTC L are almost always light bizjets
    # (CJ2 etc.). Medium twin-jets are ambiguous (CRJ vs Citation X), so only
    # apply the metadata rule for WTC L.
    if code:
        meta = _load_icao_types().get(code)
        if meta:
            desc = (meta.get("desc") or "").upper()
            wtc = (meta.get("wtc") or "").upper()
            if len(desc) >= 3 and desc[0] == "L" and desc[2] == "J" and wtc == "L":
                # Exclude small fighter/trainer jets that are also L*J/L.
                if not code.startswith(("F1", "F1", "T3", "T3", "L39", "MB3", "HAW")):
                    return True
    return False


def classify_logo_fallback(
    type_code: Optional[str] = None,
    type_name: Optional[str] = None,
) -> str:
    """Pick a silhouette class for the no-airline-logo fallback.

    Returns one of LOGO_FALLBACK_* so private GA / helos / bizjets do not all
    share the generic airliner UNKNOWN.png.
    """
    icon = classify_aircraft_icon(type_code, type_name)
    if icon == ICON_HELICOPTER:
        return LOGO_FALLBACK_HELICOPTER
    if icon in (ICON_LIGHT_GA, ICON_TURBOPROP):
        return LOGO_FALLBACK_PROP
    if is_bizjet_type(type_code, type_name):
        return LOGO_FALLBACK_BIZJET
    return LOGO_FALLBACK_AIRLINER


def aircraft_icon_polygon(
    type_code: Optional[str] = None,
    type_name: Optional[str] = None,
    icon_class: Optional[str] = None,
) -> Polygon:
    """Return the unrotated polygon for the classified aircraft icon."""
    cls = icon_class or classify_aircraft_icon(type_code, type_name)
    return list(_SYMBOLS.get(cls, _SYMBOLS[ICON_JET]))


def all_icon_classes() -> Sequence[str]:
    return (
        ICON_HELICOPTER,
        ICON_LIGHT_GA,
        ICON_TURBOPROP,
        ICON_JET,
        ICON_HEAVY,
        ICON_JUMBO,
    )
