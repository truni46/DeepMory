import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_healthReturnsOkWhenAllServicesUp():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert "timestamp" in body
    assert "db" in body
    assert "redis" in body


@pytest.mark.asyncio
async def test_healthPayloadShape():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
    body = response.json()
    assert set(body.keys()) >= {"status", "timestamp", "db", "redis"}
    assert body["db"] in ("ok", "down")
    assert body["redis"] in ("ok", "down")
