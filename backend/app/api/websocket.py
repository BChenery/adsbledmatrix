import asyncio
import json
import logging
import math
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.adsb_receiver import receiver
from app.services.aircraft_db import db
from app.services.airport_service import airport_service
from app.services.logo_manager import logo_manager
from app.services.route_service import route_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

connected_clients: Set[WebSocket] = set()

# A single hung send used to stall the whole live-page feed.
_SEND_TIMEOUT_SECONDS = 2.0


def _json_safe(value: Any) -> Any:
    """Make values JSON-safe. NaN/Inf would otherwise break the browser parser."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _distance_display(distance_km: Optional[float]) -> Optional[str]:
    if distance_km is None:
        return None
    safe = _json_safe(float(distance_km))
    if safe is None:
        return None
    return f"{safe:.1f} km"


async def serialize_live_aircraft(limit: int = 20) -> List[Dict[str, Any]]:
    """Build the payload shared by the websocket snapshot and periodic broadcast."""
    data: List[Dict[str, Any]] = []
    for ac in receiver.get_recent(n=limit):
        try:
            enriched = await db.enrich(ac.hex_code)
        except Exception:
            logger.exception("Failed to enrich %s for live feed", ac.hex_code)
            enriched = {}
        route = None
        if ac.callsign:
            try:
                route = await route_service.lookup(ac.callsign)
            except Exception:
                logger.exception("Failed to look up route for %s", ac.callsign)
        airline = logo_manager.airline_display_name(
            operator_icao=enriched.get("operator_icao"),
            callsign=ac.callsign,
            registration=enriched.get("registration"),
            operator_name=enriched.get("operator"),
        )
        origin = getattr(route, "origin", None) if route is not None else None
        destination = getattr(route, "destination", None) if route is not None else None
        airport_fields = airport_service.display_values_for_route(origin, destination)
        data.append(
            {
                "hex_code": ac.hex_code,
                "callsign": ac.callsign,
                "latitude": _json_safe(ac.latitude),
                "longitude": _json_safe(ac.longitude),
                "altitude": ac.altitude,
                "ground_speed": ac.ground_speed,
                "heading": _json_safe(ac.heading),
                "distance_km": _json_safe(ac.distance_km),
                "distance_display": _distance_display(ac.distance_km),
                "vertical_rate": ac.vertical_rate,
                "registration": enriched.get("registration"),
                "model": enriched.get("model"),
                "operator": enriched.get("operator"),
                "operator_icao": enriched.get("operator_icao"),
                "airline": airline,
                "type_code": enriched.get("type_code"),
                "type_name": enriched.get("type_name"),
                "messages": ac.messages,
                "last_seen": ac.last_seen.isoformat() if ac.last_seen else None,
                "bearing": _json_safe(ac.bearing),
                "route": f"{origin}-{destination}" if route else None,
                "origin": origin,
                "destination": destination,
                "origin_iata": airport_fields.get("origin_iata"),
                "destination_iata": airport_fields.get("destination_iata"),
                "origin_city": airport_fields.get("origin_city"),
                "destination_city": airport_fields.get("destination_city"),
            }
        )
    return data


async def aircraft_message() -> str:
    payload = {"type": "aircraft", "data": await serialize_live_aircraft()}
    return json.dumps(payload, allow_nan=False)


async def _send_text(client: WebSocket, message: str) -> None:
    await asyncio.wait_for(client.send_text(message), timeout=_SEND_TIMEOUT_SECONDS)


async def broadcast_aircraft():
    """Background task to broadcast aircraft updates to all connected websockets."""
    while True:
        try:
            await asyncio.sleep(1)
            clients = list(connected_clients)
            if not clients:
                continue

            message = await aircraft_message()
            disconnected: Set[WebSocket] = set()
            for client in clients:
                try:
                    await _send_text(client, message)
                except Exception:
                    disconnected.add(client)

            for client in disconnected:
                connected_clients.discard(client)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Aircraft websocket broadcast failed")


@router.websocket("/ws/aircraft")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info("WebSocket client connected. Total: %s", len(connected_clients))
    try:
        # Push current traffic immediately so the live page is not empty
        # if the periodic broadcaster is delayed or stuck on another client.
        try:
            await _send_text(websocket, await aircraft_message())
        except Exception:
            logger.exception("Failed to send aircraft snapshot")

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await _send_text(websocket, json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WebSocket client error", exc_info=True)
    finally:
        connected_clients.discard(websocket)
        logger.info("WebSocket client disconnected. Total: %s", len(connected_clients))
