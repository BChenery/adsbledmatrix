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
