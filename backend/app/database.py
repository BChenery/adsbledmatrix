from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

DATABASE_URL = f"sqlite+aiosqlite:///{settings.db_path}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    # Import models so all tables are registered on Base before create_all runs.
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def migrate_db():
    """Apply lightweight SQLite migrations that SQLAlchemy create_all won't handle."""
    async with engine.begin() as conn:
        def _add_missing_columns(sync_conn):
            from sqlalchemy import text
            result = sync_conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_config'")
            )
            if not result.fetchone():
                return
            result = sync_conn.execute(text("PRAGMA table_info(user_config)"))
            columns = {row[1] for row in result}
            if "led_matrix_brightness" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN led_matrix_brightness INTEGER NOT NULL DEFAULT 70")
                )

            # Network receiver settings
            if "receiver_source" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN receiver_source VARCHAR(20) NOT NULL DEFAULT 'local'")
                )
            if "network_readsb_host" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN network_readsb_host TEXT")
                )
            if "network_readsb_port" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN network_readsb_port INTEGER NOT NULL DEFAULT 30003")
                )
            if "night_mode_sleep" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN night_mode_sleep BOOLEAN NOT NULL DEFAULT 0")
                )
            if "sleep_mode" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN sleep_mode BOOLEAN NOT NULL DEFAULT 0")
                )
            if "sleep_mode_start" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN sleep_mode_start VARCHAR(5)")
                )
            if "sleep_mode_end" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN sleep_mode_end VARCHAR(5)")
                )
            if "timezone" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN timezone VARCHAR(50)")
                )

            # Proximity focus, cycle count, layout playlist
            if "cycle_count" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN cycle_count INTEGER NOT NULL DEFAULT 3")
                )
            if "proximity_focus_enabled" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN proximity_focus_enabled BOOLEAN NOT NULL DEFAULT 0")
                )
            if "proximity_focus_km" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN proximity_focus_km FLOAT NOT NULL DEFAULT 3.0")
                )
            if "proximity_focus_layout_id" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN proximity_focus_layout_id INTEGER")
                )
            if "layout_rotation_enabled" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN layout_rotation_enabled BOOLEAN NOT NULL DEFAULT 0")
                )
            if "layout_playlist_ids" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN layout_playlist_ids JSON NOT NULL DEFAULT '[]'")
                )
            if "layout_rotation_interval_sec" not in columns:
                sync_conn.execute(
                    text("ALTER TABLE user_config ADD COLUMN layout_rotation_interval_sec INTEGER NOT NULL DEFAULT 30")
                )

            # Interesting aircraft alerts
            interesting_cols = [
                ("interesting_alerts_enabled", "BOOLEAN NOT NULL DEFAULT 1"),
                ("interesting_record_range_km", "FLOAT NOT NULL DEFAULT 50.0"),
                ("interesting_rare_sightings", "INTEGER NOT NULL DEFAULT 3"),
                ("interesting_absent_days", "INTEGER NOT NULL DEFAULT 30"),
                ("interesting_warmup_days", "INTEGER NOT NULL DEFAULT 45"),
                ("interesting_layout_id", "INTEGER"),
                ("interesting_hold_sec", "INTEGER NOT NULL DEFAULT 8"),
            ]
            for col_name, col_type in interesting_cols:
                if col_name not in columns:
                    sync_conn.execute(
                        text(f"ALTER TABLE user_config ADD COLUMN {col_name} {col_type}")
                    )

            # Old default (7) ended warmup far too soon → every plane looked "new".
            # Bump only rows still on the previous default so custom values stay.
            try:
                sync_conn.execute(
                    text(
                        "UPDATE user_config SET interesting_warmup_days = 45 "
                        "WHERE interesting_warmup_days = 7"
                    )
                )
            except Exception:
                pass

            # Seen aircraft history columns (table may already exist without new fields)
            result = sync_conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='seen_aircraft_history'"
                )
            )
            if result.fetchone():
                result = sync_conn.execute(text("PRAGMA table_info(seen_aircraft_history)"))
                hist_cols = {row[1] for row in result}
                if "type_code" not in hist_cols:
                    sync_conn.execute(
                        text("ALTER TABLE seen_aircraft_history ADD COLUMN type_code VARCHAR(10)")
                    )
                if "last_visit_start" not in hist_cols:
                    sync_conn.execute(
                        text(
                            "ALTER TABLE seen_aircraft_history "
                            "ADD COLUMN last_visit_start DATETIME"
                        )
                    )
                # Best-effort unique index on hex_code (ignore if duplicates exist)
                try:
                    sync_conn.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS "
                            "ix_seen_aircraft_history_hex_code_unique "
                            "ON seen_aircraft_history (hex_code)"
                        )
                    )
                except Exception:
                    pass

            # Radar element settings added after initial schema
            result = sync_conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='layout_elements'")
            )
            if not result.fetchone():
                return
            result = sync_conn.execute(text("PRAGMA table_info(layout_elements)"))
            columns = {row[1] for row in result}
            radar_columns = [
                ("range_km", "INTEGER DEFAULT 20"),
                ("ring_color", "VARCHAR(7)"),
                ("dot_color", "VARCHAR(7)"),
                ("user_dot_color", "VARCHAR(7)"),
                ("show_rings", "BOOLEAN DEFAULT 1"),
                ("show_ticks", "BOOLEAN DEFAULT 1"),
                ("use_plane_symbol", "BOOLEAN DEFAULT 0"),
            ]
            for col_name, col_type in radar_columns:
                if col_name not in columns:
                    sync_conn.execute(
                        text(f"ALTER TABLE layout_elements ADD COLUMN {col_name} {col_type}")
                    )

        await conn.run_sync(_add_missing_columns)
