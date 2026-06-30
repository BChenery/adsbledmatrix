import hashlib


def is_in_rollout(device_id: str, release_tag: str, percentage: int) -> bool:
    """Deterministically decide if this device is in the rollout bucket.

    The bucket is computed from a hash of the device ID and release tag so
    that the same device always makes the same decision for a given release,
    while the rollout can be widened without reshuffling devices into new
    buckets.
    """
    if percentage <= 0:
        return False
    if percentage >= 100:
        return True
    bucket_input = f"{device_id}:{release_tag}".encode()
    bucket = int(hashlib.sha256(bucket_input).hexdigest(), 16) % 100
    return bucket < percentage
