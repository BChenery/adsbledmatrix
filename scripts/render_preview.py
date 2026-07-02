#!/usr/bin/env python3
"""Render previews of all default layouts to PNG for visual inspection."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from PIL import Image
from app.services.display_engine import DisplayEngine, RenderContext

LAYOUTS_PATH = PROJECT_ROOT / "data" / "default_layouts.json"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "superpowers" / "specs"


def make_namespace(d):
    if isinstance(d, dict):
        return SimpleNamespace(**{k: make_namespace(v) for k, v in d.items()})
    if isinstance(d, list):
        return [make_namespace(i) for i in d]
    return d


def main():
    engine = DisplayEngine()
    with open(LAYOUTS_PATH) as f:
        layouts = json.load(f)

    aircraft = SimpleNamespace(
        hex_code="ABC123",
        callsign="QFA123",
        altitude=10500,
        ground_speed=245,
        heading=135,
        distance_km=12.4,
        vertical_rate=1200,
        squawk="1234",
        messages=42,
        last_seen=__import__("datetime").datetime.utcnow(),
        bearing=45,
    )
    enriched = {
        "registration": "VH-OQI",
        "manufacturer": "Boeing",
        "model": "737-838",
        "type_code": "B738",
        "type_name": "Boeing 737-800",
        "operator": "Qantas",
        "operator_icao": "QFA",
    }
    user_config = SimpleNamespace(
        distance_unit="km",
        altitude_unit="ft",
        speed_unit="kts",
    )
    route = SimpleNamespace(origin="SYD", destination="MEL")

    ctx = RenderContext(
        aircraft=aircraft,
        enriched=enriched,
        user_config=user_config,
        is_idle=False,
        cycle_index=0,
        total_cycles=1,
        route=route,
        all_routes={"QFA123": route},
    )
    idle_ctx = RenderContext(
        aircraft=None,
        enriched=None,
        user_config=user_config,
        is_idle=True,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for layout_data in layouts:
        layout = make_namespace(layout_data)
        ctx_to_use = idle_ctx if "Idle" in layout.name else ctx
        img = engine._render_layout(layout, ctx_to_use)
        out_path = OUTPUT_DIR / f"preview_{layout.name.replace(' / ', '_').replace(' ', '_').lower()}.png"
        img.save(out_path)
        print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
