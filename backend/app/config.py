import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent


class Settings(BaseSettings):
    # App
    app_name: str = "ADS-B LED Display"
    version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Paths
    data_dir: Path = PROJECT_ROOT / "data"
    db_path: Path = PROJECT_ROOT / "data" / "aircraft_db.sqlite3"
    logos_dir: Path = PROJECT_ROOT / "data" / "airline_logos"
    default_layouts_path: Path = PROJECT_ROOT / "data" / "default_layouts.json"

    # ADS-B
    readsb_host: str = "127.0.0.1"
    readsb_port: int = 30003  # SBS/BaseStation format
    readsb_beast_port: int = 30005  # Beast binary format
    aircraft_timeout_seconds: int = 60

    # Display
    # Default is a 256x128 display made of four 128x64 P2 panels wired in a
    # single HUB75 chain with a serpentine (U-mapper) bottom row:
    #
    #   Panel 1 (UL) -> Panel 2 (UR) -> Panel 3 (BR) -> Panel 4 (BL)
    #
    # Total logical display: 256x128 pixels.
    # This requires a single-channel HUB75 adapter board and an external 5V PSU.
    led_matrix_rows: int = 64
    led_matrix_cols: int = 128
    led_matrix_chain: int = 4
    led_matrix_parallel: int = 1
    led_matrix_hardware_mapping: str = "regular"
    led_matrix_pixel_mapper: str = "U-mapper"
    led_matrix_row_address_type: int = 0
    led_matrix_multiplexing: int = 0
    led_matrix_panel_type: str = ""  # e.g. "FM6126A"
    led_matrix_pwm_bits: int = 7
    led_matrix_brightness: int = 70
    led_matrix_gpio_slowdown: int = 4
    led_matrix_limit_refresh: int = 0
    led_matrix_flip_vertical: bool = False

    # Update
    github_repo: str = "BChenery/adsbledmatrix"
    update_check_interval_hours: int = 24
    auto_update: bool = True

    # Onboarding
    ap_ssid_prefix: str = "ADSB-Display"
    ap_password: str = "adsbsetup"

    # Logos
    auto_download_logos: bool = False
    logos_source_repo: str = "Jxck-S/airline-logos"

    # Mock data for development/demo
    mock_aircraft: bool = False

    class Config:
        env_prefix = "ADSB_"
        env_file = ".env"


settings = Settings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.logos_dir.mkdir(parents=True, exist_ok=True)
