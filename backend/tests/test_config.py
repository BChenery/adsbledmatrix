import pytest
from httpx import AsyncClient, ASGITransport, HTTPStatusError, RequestError, Response
from fastapi import FastAPI
from app.api.config import router


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
