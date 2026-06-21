import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from app.api.config import router


app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_geocode_address_success(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return [
                {
                    "display_name": "Sydney Opera House, Sydney, Australia",
                    "lat": "-33.8568",
                    "lon": "151.2153",
                }
            ]

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=Sydney%20Opera%20House")

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Sydney Opera House, Sydney, Australia"
    assert data["latitude"] == -33.8568
    assert data["longitude"] == 151.2153


@pytest.mark.asyncio
async def test_geocode_address_not_found(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return []

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=nowheresville")

    assert response.status_code == 404
    assert "Address not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_geocode_service_error(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            from httpx import HTTPStatusError, Response
            raise HTTPStatusError(
                "rate limited",
                request=None,
                response=Response(429, text="rate limited"),
            )

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=Sydney")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_geocode_empty_query():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/geocode?q=")

    assert response.status_code == 422
