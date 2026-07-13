import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport, HTTPStatusError, RequestError, Response
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.api import config as config_module
from app.api.config import ConfigUpdate, ProbeReceiverRequest, router, get_db
from app import database as database_module
from app.models import Base, UserConfig


app = FastAPI()
app.include_router(router)


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ""

    def json(self):
        import json

        if self._payload is not None:
            return self._payload
        return json.loads(self.text)

    def raise_for_status(self):
        pass


class FakeClient:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, *args, **kwargs):
        if self._exception is not None:
            raise self._exception
        return self._response


@pytest.fixture
def fake_httpx_client(monkeypatch):
    def _patch(response=None, exception=None):
        def _factory(*args, **kwargs):
            return FakeClient(response=response, exception=exception)

        monkeypatch.setattr("httpx.AsyncClient", _factory)

    return _patch


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await test_engine.dispose()


@pytest_asyncio.fixture
async def app_with_db(db_session):
    """FastAPI app with the config router and an overridden DB dependency."""
    test_app = FastAPI()

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.include_router(router)

    config = UserConfig(id=1)
    db_session.add(config)
    await db_session.commit()

    return test_app


@pytest.mark.asyncio
async def test_geocode_address_success(fake_httpx_client):
    fake_httpx_client(
        response=FakeResponse(
            payload=[
                {
                    "display_name": "Sydney Opera House, Sydney, Australia",
                    "lat": "-33.8568",
                    "lon": "151.2153",
                }
            ]
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=Sydney%20Opera%20House")

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Sydney Opera House, Sydney, Australia"
    assert data["latitude"] == -33.8568
    assert data["longitude"] == 151.2153


@pytest.mark.asyncio
async def test_geocode_address_not_found(fake_httpx_client):
    fake_httpx_client(response=FakeResponse(payload=[]))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=nowheresville")

    assert response.status_code == 404
    assert "Address not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_geocode_service_error(fake_httpx_client):
    fake_httpx_client(
        exception=HTTPStatusError(
            "rate limited",
            request=None,
            response=Response(429, text="rate limited"),
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=Sydney")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_geocode_network_error(fake_httpx_client):
    fake_httpx_client(exception=RequestError("network failure"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=Sydney")

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_geocode_malformed_json(fake_httpx_client):
    fake_httpx_client(response=FakeResponse(text="not json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=Sydney")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_geocode_missing_keys(fake_httpx_client):
    fake_httpx_client(response=FakeResponse(payload=[{"display_name": "Somewhere"}]))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=Somewhere")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_geocode_non_numeric_lat_lon(fake_httpx_client):
    fake_httpx_client(
        response=FakeResponse(
            payload=[
                {
                    "display_name": "Nowhere",
                    "lat": "not-a-number",
                    "lon": "also-not-a-number",
                }
            ]
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=Nowhere")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_geocode_empty_query():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=")

    assert response.status_code == 422


def test_settings_version_read_from_version_file(monkeypatch, tmp_path):
    """Settings.version should be read from PROJECT_ROOT/VERSION."""
    monkeypatch.delenv("ADSB_VERSION", raising=False)

    version_file = tmp_path / "VERSION"
    version_file.write_text("1.2.3\n")

    import app.config as config_module

    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)

    from app.config import Settings

    settings = Settings()
    assert settings.version == "1.2.3"


def test_settings_version_fallback_when_version_file_missing(monkeypatch, tmp_path):
    """Settings.version should fall back to '0.1.0' when VERSION is missing."""
    monkeypatch.delenv("ADSB_VERSION", raising=False)

    import app.config as config_module

    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)

    from app.config import Settings

    settings = Settings()
    assert settings.version == "0.1.0"


def test_settings_version_env_override(monkeypatch, tmp_path):
    """ADSB_VERSION environment variable should override the VERSION file."""
    monkeypatch.setenv("ADSB_VERSION", "9.9.9")

    version_file = tmp_path / "VERSION"
    version_file.write_text("1.2.3\n")

    import app.config as config_module

    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)

    from app.config import Settings

    settings = Settings()
    assert settings.version == "9.9.9"


@pytest.mark.asyncio
async def test_user_config_has_receiver_columns(monkeypatch):
    """UserConfig receiver columns should exist with correct null/default rules."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database_module, "engine", test_engine)

    try:
        await database_module.init_db()
        await database_module.migrate_db()

        async with test_engine.begin() as conn:
            def _check(sync_conn):
                result = sync_conn.execute(text("PRAGMA table_info(user_config)"))
                columns = {row[1]: row for row in result}

                assert "receiver_source" in columns
                assert "network_readsb_host" in columns
                assert "network_readsb_port" in columns

                rs = columns["receiver_source"]
                assert rs[3] == 1, "receiver_source should be NOT NULL"
                assert rs[4] == "'local'", "receiver_source should default to 'local'"

                port = columns["network_readsb_port"]
                assert port[3] == 1, "network_readsb_port should be NOT NULL"
                assert port[4] == "30003", "network_readsb_port should default to 30003"

                host = columns["network_readsb_host"]
                assert host[3] == 0, "network_readsb_host should be nullable"

            await conn.run_sync(_check)
    finally:
        await test_engine.dispose()


def test_invalid_receiver_source_rejected():
    with pytest.raises(ValueError, match="receiver_source must be"):
        ConfigUpdate(receiver_source="satellite")


def test_invalid_port_rejected():
    with pytest.raises(ValueError, match="network_readsb_port"):
        ConfigUpdate(receiver_source="network", network_readsb_host="10.0.0.158", network_readsb_port=70000)


def test_port_boundary_values():
    assert ConfigUpdate(network_readsb_port=1).network_readsb_port == 1
    assert ConfigUpdate(network_readsb_port=65535).network_readsb_port == 65535

    with pytest.raises(ValueError, match="network_readsb_port"):
        ConfigUpdate(network_readsb_port=0)

    with pytest.raises(ValueError, match="network_readsb_port"):
        ConfigUpdate(network_readsb_port=65536)


def test_probe_receiver_request_validates_empty_host():
    with pytest.raises(ValueError, match="host must not be empty"):
        ProbeReceiverRequest(host="", port=30003)

    with pytest.raises(ValueError, match="host must not be empty"):
        ProbeReceiverRequest(host="   ", port=30003)


def test_probe_receiver_request_validates_port():
    with pytest.raises(ValueError, match="port must be between"):
        ProbeReceiverRequest(host="10.0.0.1", port=0)

    with pytest.raises(ValueError, match="port must be between"):
        ProbeReceiverRequest(host="10.0.0.1", port=70000)


@pytest.mark.asyncio
async def test_test_receiver_success_with_sbs_data():
    reader = AsyncMock()
    writer = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    reader.readline = AsyncMock(return_value=b"MSG,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22")

    with patch("app.api.config.asyncio.open_connection", new_callable=AsyncMock, return_value=(reader, writer)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/config/test-receiver", json={"host": "10.0.0.1", "port": 30003})

    assert response.status_code == 200
    data = response.json()
    assert data["reachable"] is True
    assert "SBS" in data["message"]


@pytest.mark.asyncio
async def test_test_reader_connection_failure():
    with patch(
        "app.api.config.asyncio.open_connection",
        new_callable=AsyncMock,
        side_effect=ConnectionRefusedError("Connection refused"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/config/test-receiver", json={"host": "10.0.0.1", "port": 30003})

    assert response.status_code == 200
    data = response.json()
    assert data["reachable"] is False
    assert "Cannot connect" in data["message"]


@pytest.mark.asyncio
async def test_test_receiver_invalid_port_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response_zero = await client.post("/api/config/test-receiver", json={"host": "10.0.0.1", "port": 0})
        response_high = await client.post("/api/config/test-receiver", json={"host": "10.0.0.1", "port": 70000})

    assert response_zero.status_code == 422
    assert response_high.status_code == 422


@pytest.mark.asyncio
async def test_test_receiver_empty_host_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response_empty = await client.post("/api/config/test-receiver", json={"host": "", "port": 30003})
        response_whitespace = await client.post("/api/config/test-receiver", json={"host": "   ", "port": 30003})

    assert response_empty.status_code == 422
    assert response_whitespace.status_code == 422


@pytest.mark.asyncio
async def test_update_config_applies_receiver_source_when_changed(app_with_db, monkeypatch):
    calls = []

    async def fake_apply(config):
        calls.append(config.receiver_source)

    monkeypatch.setattr(config_module, "apply_receiver_source", fake_apply)

    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
        response = await client.put(
            "/api/config",
            json={"receiver_source": "network", "network_readsb_host": "10.0.0.1", "network_readsb_port": 30003},
        )

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0] == "network"


@pytest.mark.asyncio
async def test_update_config_does_not_apply_receiver_source_for_unrelated_changes(app_with_db, monkeypatch):
    calls = []

    async def fake_apply(config):
        calls.append(config.receiver_source)

    monkeypatch.setattr(config_module, "apply_receiver_source", fake_apply)

    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
        response = await client.put("/api/config", json={"latitude": 12.34})

    assert response.status_code == 200
    assert len(calls) == 0


@pytest.mark.asyncio
async def test_update_config_rejects_network_without_host(app_with_db):
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
        response = await client.put("/api/config", json={"receiver_source": "network"})

    assert response.status_code == 422
    assert "network_readsb_host is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_config_allows_network_when_host_already_persisted(app_with_db, db_session):
    from sqlalchemy import update
    from app.models import UserConfig as ConfigModel

    await db_session.execute(update(ConfigModel).where(ConfigModel.id == 1).values(network_readsb_host="10.0.0.1"))
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
        response = await client.put("/api/config", json={"receiver_source": "network"})

    assert response.status_code == 200
    data = response.json()
    assert data["receiver_source"] == "network"
    assert data["network_readsb_host"] == "10.0.0.1"


@pytest.mark.asyncio
async def test_get_config_response_schema(app_with_db):
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
        response = await client.get("/api/config")

    assert response.status_code == 200
    data = response.json()
    assert "receiver_source" in data
    assert "network_readsb_host" in data
    assert "network_readsb_port" in data
    assert "timezone" in data


@pytest.mark.asyncio
async def test_update_config_detects_timezone_from_lat_long(app_with_db):
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
        response = await client.put("/api/config", json={"latitude": -33.8568, "longitude": 151.2153})

    assert response.status_code == 200
    data = response.json()
    assert data["timezone"] == "Australia/Sydney"


async def test_update_config_fills_default_night_sleep_times(app_with_db):
    """Enabling night/sleep without times must persist UI defaults so windows activate."""
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as client:
        response = await client.put(
            "/api/config",
            json={
                "night_mode": True,
                "sleep_mode": True,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["night_mode"] is True
    assert data["night_mode_start"] == "22:00"
    assert data["night_mode_end"] == "06:00"
    assert data["sleep_mode"] is True
    assert data["sleep_mode_start"] == "23:00"
    assert data["sleep_mode_end"] == "06:00"
