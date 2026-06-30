from app.services.rollout import is_in_rollout


def test_zero_percentage_excludes_all():
    assert is_in_rollout("any", "v1.0.0", 0) is False


def test_hundred_percentage_includes_all():
    assert is_in_rollout("any", "v1.0.0", 100) is True


def test_rollout_is_deterministic():
    assert is_in_rollout("device-a", "v1.0.0", 50) == is_in_rollout("device-a", "v1.0.0", 50)


def test_different_devices_can_differ():
    results = {is_in_rollout(f"device-{i}", "v1.0.0", 50) for i in range(100)}
    assert len(results) == 2


def test_widening_rollout_keeps_existing_devices_in():
    """A device that is included at a lower percentage stays included when the
    percentage increases.
    """
    device_id = "stable-device"
    release_tag = "v2.0.0"
    at_25 = is_in_rollout(device_id, release_tag, 25)
    at_50 = is_in_rollout(device_id, release_tag, 50)
    if at_25:
        assert at_50 is True
