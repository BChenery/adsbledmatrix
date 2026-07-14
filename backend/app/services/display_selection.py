from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

FOCUS_POOL_CAP = 20
EXIT_HYSTERESIS = 1.15
MAX_PLAYLIST_SIZE = 20


@dataclass
class SelectionResult:
    aircraft: Any
    mode: str
    cycle_index: int
    focused: bool  # proximity focus
    interesting: bool = False
    interest_reason: Optional[str] = None


def normalize_display_mode(mode: Optional[str]) -> str:
    if mode in (None, ""):
        return "closest"
    if mode == "cycle3":
        return "cycle"
    return mode


def select_aircraft(
    focus_pool: Sequence[Any],
    *,
    display_mode: str,
    cycle_count: int,
    cycle_index: int,
    proximity_enabled: bool,
    proximity_km: float,
    currently_focused: bool = False,
    interesting_enabled: bool = False,
    interest_by_hex: Optional[Dict[str, Any]] = None,
    currently_interesting_hex: Optional[str] = None,
    interesting_hold_active: bool = False,
) -> SelectionResult:
    """Pick which aircraft to show.

    ``focus_pool`` must be ordered nearest-first (as from get_closest).

    Priority:
      1. Interesting alerts (if enabled) — beats proximity
      2. Proximity focus
      3. Normal closest / cycle / list
    """
    mode = normalize_display_mode(display_mode)
    n = max(1, min(int(cycle_count or 3), 10))
    pool = list(focus_pool)[:FOCUS_POOL_CAP]
    cycle_pool = pool[:n] if pool else []
    interest_by_hex = interest_by_hex or {}

    # --- 1. Interesting focus (holds, then best score) ---
    if interesting_enabled and pool:
        held_hex = (currently_interesting_hex or "").upper() or None
        if held_hex and interesting_hold_active:
            for ac in pool:
                if (getattr(ac, "hex_code", "") or "").upper() == held_hex:
                    res = interest_by_hex.get(held_hex)
                    reason = getattr(res, "primary_reason", None) if res else None
                    return SelectionResult(
                        aircraft=ac,
                        mode="interesting",
                        cycle_index=cycle_index,
                        focused=False,
                        interesting=True,
                        interest_reason=reason,
                    )

        best_ac = None
        best_score = -1.0
        best_reason: Optional[str] = None
        for ac in pool:
            hex_code = (getattr(ac, "hex_code", "") or "").upper()
            res = interest_by_hex.get(hex_code)
            if res is None or not getattr(res, "is_interesting", False):
                continue
            score = float(getattr(res, "score", 0.0) or 0.0)
            if score > best_score:
                best_score = score
                best_ac = ac
                best_reason = getattr(res, "primary_reason", None)
        if best_ac is not None:
            return SelectionResult(
                aircraft=best_ac,
                mode="interesting",
                cycle_index=cycle_index,
                focused=False,
                interesting=True,
                interest_reason=best_reason,
            )

    # --- 2. Proximity focus ---
    threshold = float(proximity_km if proximity_km is not None else 3.0)
    exit_threshold = threshold * EXIT_HYSTERESIS if currently_focused else threshold

    if proximity_enabled and pool:
        in_zone = [
            ac
            for ac in pool
            if getattr(ac, "distance_km", None) is not None and ac.distance_km <= exit_threshold
        ]
        if in_zone:
            aircraft = min(in_zone, key=lambda a: a.distance_km)
            return SelectionResult(
                aircraft=aircraft,
                mode="proximity",
                cycle_index=cycle_index,
                focused=True,
            )

    # --- 3. Normal modes ---
    if not cycle_pool:
        return SelectionResult(
            aircraft=None,
            mode=mode,
            cycle_index=0,
            focused=False,
        )

    if mode == "cycle":
        idx = cycle_index % len(cycle_pool)
        return SelectionResult(
            aircraft=cycle_pool[idx],
            mode="cycle",
            cycle_index=idx,
            focused=False,
        )

    return SelectionResult(
        aircraft=cycle_pool[0],
        mode=mode if mode in ("closest", "list") else "closest",
        cycle_index=0,
        focused=False,
    )


def select_layout_index(
    playlist_len: int,
    *,
    rotation_enabled: bool,
    current_index: int,
    advance: bool,
) -> int:
    if not rotation_enabled or playlist_len <= 0:
        return 0
    if advance:
        return (current_index + 1) % playlist_len
    return current_index % playlist_len


def resolve_playlist_ids(
    playlist_ids: Optional[List[int]],
    active_layout_id: Optional[int],
) -> List[int]:
    """Return ordered unique layout IDs, falling back to active layout."""
    ids: List[int] = []
    seen = set()
    for raw in playlist_ids or []:
        if len(ids) >= MAX_PLAYLIST_SIZE:
            break
        try:
            lid = int(raw)
        except (TypeError, ValueError):
            continue
        if lid in seen:
            continue
        seen.add(lid)
        ids.append(lid)
    if not ids and active_layout_id is not None:
        ids = [int(active_layout_id)]
    return ids
