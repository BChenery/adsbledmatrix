from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime, JSON, event, text
from sqlalchemy.orm import relationship
from app.database import Base


class Aircraft(Base):
    __tablename__ = "aircraft"

    hex_code = Column(String(6), primary_key=True, index=True)
    registration = Column(String(20))
    manufacturer = Column(String(100))
    model = Column(String(100))
    type_code = Column(String(10))
    operator = Column(String(100))
    operator_icao = Column(String(3))


class AirlineLogo(Base):
    __tablename__ = "airline_logos"

    icao_code = Column(String(3), primary_key=True)
    iata_code = Column(String(2))
    name = Column(String(100))
    logo_path = Column(String(255))
    logo_url = Column(String(500))
    downloaded_at = Column(DateTime)


class UserConfig(Base):
    __tablename__ = "user_config"

    id = Column(Integer, primary_key=True)
    latitude = Column(Float, nullable=False, default=0.0)
    longitude = Column(Float, nullable=False, default=0.0)
    distance_unit = Column(String(10), nullable=False, default="km")
    altitude_unit = Column(String(10), nullable=False, default="ft")
    speed_unit = Column(String(10), nullable=False, default="kts")
    cycle_interval_sec = Column(Integer, nullable=False, default=5)
    display_mode = Column(String(20), nullable=False, default="closest")
    cycle_count = Column(Integer, nullable=False, default=3, server_default=text("3"))
    proximity_focus_enabled = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    proximity_focus_km = Column(Float, nullable=False, default=3.0, server_default=text("3.0"))
    proximity_focus_layout_id = Column(Integer, ForeignKey("layouts.id"), nullable=True)
    layout_rotation_enabled = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    layout_playlist_ids = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    layout_rotation_interval_sec = Column(Integer, nullable=False, default=30, server_default=text("30"))
    active_layout_id = Column(Integer, ForeignKey("layouts.id"), nullable=True)
    idle_layout_id = Column(Integer, ForeignKey("layouts.id"), nullable=True)
    onboarding_complete = Column(Boolean, nullable=False, default=False)
    wifi_ssid = Column(String(100))
    wifi_password = Column(String(100))
    auto_update = Column(Boolean, nullable=False, default=True)
    night_mode = Column(Boolean, nullable=False, default=False)
    night_mode_start = Column(String(5))
    night_mode_end = Column(String(5))
    sleep_mode = Column(Boolean, nullable=False, default=False)
    sleep_mode_start = Column(String(5))
    sleep_mode_end = Column(String(5))
    timezone = Column(String(50))
    led_matrix_brightness = Column(Integer, nullable=False, default=70)

    # Receiver source
    receiver_source = Column(String(20), nullable=False, default="local", server_default=text("'local'"))
    network_readsb_host = Column(String(255))
    network_readsb_port = Column(Integer, nullable=False, default=30003, server_default=text("30003"))

    active_layout = relationship("Layout", foreign_keys=[active_layout_id])
    idle_layout = relationship("Layout", foreign_keys=[idle_layout_id])
    proximity_focus_layout = relationship("Layout", foreign_keys=[proximity_focus_layout_id])


class Layout(Base):
    __tablename__ = "layouts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    width = Column(Integer, nullable=False, default=256)
    height = Column(Integer, nullable=False, default=128)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    elements = relationship(
        "LayoutElement",
        back_populates="layout",
        cascade="all, delete-orphan",
        order_by="LayoutElement.z_index",
    )


class LayoutElement(Base):
    __tablename__ = "layout_elements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    layout_id = Column(Integer, ForeignKey("layouts.id", ondelete="CASCADE"), nullable=False)
    element_type = Column(String(30), nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    z_index = Column(Integer, nullable=False, default=0)
    font_family = Column(String(50))
    font_size = Column(Integer)
    color = Column(String(7))
    bg_color = Column(String(7))
    format_str = Column("format", Text)
    data_field = Column(String(50))
    image_path = Column(String(255))
    image_url = Column(String(500))
    show_if = Column(String(100))
    extra = Column(JSON)

    # Radar element settings
    range_km = Column(Integer, default=20)
    ring_color = Column(String(7))
    dot_color = Column(String(7))
    user_dot_color = Column(String(7))
    show_rings = Column(Boolean, default=True)
    show_ticks = Column(Boolean, default=True)
    use_plane_symbol = Column(Boolean, default=False)

    layout = relationship("Layout", back_populates="elements")


class Route(Base):
    __tablename__ = "routes"

    callsign = Column(String(20), primary_key=True)
    origin = Column(String(10), nullable=False)
    destination = Column(String(10), nullable=False)


class SeenAircraftHistory(Base):
    __tablename__ = "seen_aircraft_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hex_code = Column(String(6), nullable=False, index=True)
    callsign = Column(String(20))
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    max_distance = Column(Float)
    min_distance = Column(Float)
    sightings = Column(Integer, default=1)


# Ensure only one UserConfig row exists
@event.listens_for(UserConfig, "before_insert")
def ensure_single_config(mapper, connection, target):
    target.id = 1
