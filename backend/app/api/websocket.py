import asyncio
import json
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.adsb_receiver import receiver
from app.services.aircraft_db import db
from app.services.route_service import route_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

connected_clients: Set[WebSocket] = set()


async def broadcast_aircraft():
    """Background task to broadcast aircraft updates to all connected websockets."""
    while True:
        await asyncio.sleep(1)
        if not connected_clients:
            continue

        recent = receiver.get_recent(n=20)
        data = []
        for ac in recent:
            enriched = await db.enrich(ac.hex_code)
            route = await route_service.lookup(ac.callsign) if ac.callsign else None
            data.append({
                "hex_code": ac.hex_code,
                "callsign": ac.callsign,
                "altitude": ac.altitude,
                "ground_speed": ac.ground_speed,
                "heading": ac.heading,
                "distance_km": ac.distance_km,
                "distance_display": f"{ac.distance_km:.1f} km" if ac.distance_km else None,
                "vertical_rate": ac.vertical_rate,
                "registration": enriched.get("registration"),
                "model": enriched.get("model"),
                "operator": enriched.get("operator"),
                "operator_icao": enriched.get("operator_icao"),
                "type_code": enriched.get("type_code"),
                "type_name": enriched.get("type_name"),
                "messages": ac.messages,
                "last_seen": ac.last_seen.isoformat() if ac.last_seen else None,
                "bearing": ac.bearing,
                "route": f"{route.origin}-{route.destination}" if route else None,
                "origin": route.origin if route else None,
                "destination": route.destination if route else None,
            })

        message = json.dumps({"type": "aircraft", "data": data})
        disconnected = set()
        for client in connected_clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.add(client)

        for client in disconnected:
            connected_clients.discard(client)


@router.websocket("/ws/aircraft")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")
    try:
        while True:
            # Keep connection alive, wait for any message
            data = await websocket.receive_text()
            # Echo back or handle commands
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")
    except Exception:
        connected_clients.discard(websocket)
