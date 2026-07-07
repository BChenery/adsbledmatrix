import pytest
from app.services.update_progress import (
    write_update_progress,
    read_update_progress,
    reset_update_progress,
    PROGRESS_FILE,
)


def test_write_and_read_progress():
    write_update_progress("checking", 10, "Checking for updates...")
    progress = read_update_progress()
    assert progress.status == "checking"
    assert progress.progress == 10
    assert progress.message == "Checking for updates..."


def test_progress_clamps_to_0_100():
    write_update_progress("installing", 150, "too high")
    assert read_update_progress().progress == 100
    write_update_progress("installing", -10, "too low")
    assert read_update_progress().progress == 0


def test_reset_progress():
    write_update_progress("completed", 100, "Done")
    reset_update_progress()
    progress = read_update_progress()
    assert progress.status == "idle"
    assert progress.progress == 0
