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
    led_matrix_rows: int = 64
    led_matrix_cols: int = 128
    led_matrix_chain: int = 4
    led_matrix_parallel: int = 1
    led_matrix_hardware_mapping: str = "regular"
    led_matrix_pwm_bits: int = 11
    led_matrix_brightness: int = 100
    led_matrix_gpio_slowdown: int = 2
    led_matrix_limit_refresh: int = 0

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
