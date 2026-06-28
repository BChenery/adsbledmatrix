from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Response
from fastapi.responses import FileResponse
from app.services.adsb_receiver import receiver
from app.services.aircraft_db import db
from app.services.geocalc import convert_distance, convert_altitude, convert_speed, format_heading
from app.services.logo_manager import logo_manager

router = APIRouter(prefix="/api/aircraft", tags=["aircraft"])


class AircraftResponse(BaseModel):
    hex_code: str
    callsign: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    altitude: Optional[int]
    ground_speed: Optional[int]
    heading: Optional[float]
    vertical_rate: Optional[int]
    squawk: Optional[str]
    distance_km: Optional[float]
    distance_display: Optional[str]
    bearing: Optional[float]
    last_seen: str
    messages: int
    registration: Optional[str]
    manufacturer: Optional[str]
    model: Optional[str]
    type_code: Optional[str]
    type_name: Optional[str]
    operator: Optional[str]
    operator_icao: Optional[str]


@router.get("/live", response_model=List[AircraftResponse])
async def get_live_aircraft():
    all_ac = receiver.get_all()
    result = []
    for ac in all_ac:
        enriched = await db.enrich(ac.hex_code)
        result.append(AircraftResponse(
            hex_code=ac.hex_code,
            callsign=ac.callsign,
            latitude=ac.latitude,
            longitude=ac.longitude,
            altitude=ac.altitude,
            ground_speed=ac.ground_speed,
            heading=ac.heading,
            vertical_rate=ac.vertical_rate,
            squawk=ac.squawk,
            distance_km=ac.distance_km,
            distance_display=f"{ac.distance_km:.1f} km" if ac.distance_km else None,
            bearing=ac.bearing,
            last_seen=ac.last_seen.isoformat(),
            messages=ac.messages,
            registration=enriched.get("registration"),
            manufacturer=enriched.get("manufacturer"),
            model=enriched.get("model"),
            type_code=enriched.get("type_code"),
            type_name=enriched.get("type_name"),
            operator=enriched.get("operator"),
            operator_icao=enriched.get("operator_icao"),
        ))
    return result


@router.get("/closest")
async def get_closest_aircraft():
    closest = receiver.get_closest(n=1)
    if not closest:
        return {"message": "No aircraft in range"}
    ac = closest[0]
    enriched = await db.enrich(ac.hex_code)
    return AircraftResponse(
        hex_code=ac.hex_code,
        callsign=ac.callsign,
        latitude=ac.latitude,
        longitude=ac.longitude,
        altitude=ac.altitude,
        ground_speed=ac.ground_speed,
        heading=ac.heading,
        vertical_rate=ac.vertical_rate,
        squawk=ac.squawk,
        distance_km=ac.distance_km,
        distance_display=f"{ac.distance_km:.1f} km" if ac.distance_km else None,
        bearing=ac.bearing,
        last_seen=ac.last_seen.isoformat(),
        messages=ac.messages,
        registration=enriched.get("registration"),
        manufacturer=enriched.get("manufacturer"),
        model=enriched.get("model"),
        type_code=enriched.get("type_code"),
        type_name=enriched.get("type_name"),
        operator=enriched.get("operator"),
        operator_icao=enriched.get("operator_icao"),
    )


@router.get("/logo/{icao}")
async def get_airline_logo(icao: str):
    """Serve the airline logo PNG for an ICAO/IATA code, applying overrides."""
    path = logo_manager.logo_path_for_icao(icao)
    if path and path.exists():
        return FileResponse(path, media_type="image/png")
    return Response(status_code=404)
