import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.updater import UpdateService


@pytest.mark.asyncio
async def test_check_for_update_parses_release_assets():
    svc = UpdateService()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tag_name": "v1.2.3",
        "body": "Test release",
        "published_at": "2026-06-30T00:00:00Z",
        "assets": [
            {"name": "adsbledmatrix-v1.2.3.tar.gz", "browser_download_url": "http://example.com/archive.tar.gz"},
            {"name": "adsbledmatrix-v1.2.3.tar.gz.sha256", "browser_download_url": "http://example.com/checksum.sha256"},
            {"name": "rollout.json", "browser_download_url": "http://example.com/rollout.json"},
        ],
    }

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    svc._client = mock_client
    result = await svc.check_for_update()

    assert result["latest_version"] == "1.2.3"
    assert result["update_available"] is True
    assert result["download_url"] == "http://example.com/archive.tar.gz"
    assert result["checksum_url"] == "http://example.com/checksum.sha256"
    assert result["rollout_url"] == "http://example.com/rollout.json"
