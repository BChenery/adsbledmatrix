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

        await conn.run_sync(_add_missing_columns)
