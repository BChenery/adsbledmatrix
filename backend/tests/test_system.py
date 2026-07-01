import pytest
from app.api.system import trigger_update


@pytest.mark.asyncio
async def test_post_update_returns_status():
    result = await trigger_update()
    assert result == {
        "status": "manual updates are applied by systemd; check status with GET /api/system/update"
    }
