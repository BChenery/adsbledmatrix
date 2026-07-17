"""Tests for the onboarding setup screen shown on the LED matrix."""

from types import SimpleNamespace
from unittest.mock import patch

from app.services import onboarding_display


def test_build_setup_layout_contains_connection_details():
    layout = onboarding_display.build_setup_layout(ssid="ADSB-Display-AB12")
    texts = [el.format_str for el in layout.elements]

    assert layout.name == onboarding_display.SETUP_LAYOUT_NAME
    assert any("SETUP REQUIRED" in t for t in texts)
    assert any("ADSB-Display-AB12" in t for t in texts)
    assert any("adsbsetup" in t for t in texts)
    assert any("192.168.4.1" in t for t in texts)
    assert all(el.element_type == "text" for el in layout.elements)


def test_show_setup_screen_pushes_preview_layout():
    with patch("app.services.display_engine.engine") as mock_engine:
        onboarding_display.show_setup_screen()

    layout = mock_engine.set_preview_layout.call_args.args[0]
    assert layout.name == onboarding_display.SETUP_LAYOUT_NAME


def test_clear_setup_screen_clears_only_its_own_layout():
    with patch("app.services.display_engine.engine") as mock_engine:
        mock_engine.get_preview_layout.return_value = SimpleNamespace(
            name=onboarding_display.SETUP_LAYOUT_NAME
        )
        onboarding_display.clear_setup_screen()
        mock_engine.set_preview_layout.assert_called_once_with(None)

        mock_engine.reset_mock()
        mock_engine.get_preview_layout.return_value = SimpleNamespace(name="designer-draft")
        onboarding_display.clear_setup_screen()
        mock_engine.set_preview_layout.assert_not_called()


def test_show_setup_screen_swallows_engine_errors():
    with patch("app.services.display_engine.engine") as mock_engine:
        mock_engine.set_preview_layout.side_effect = RuntimeError("no hardware")
        onboarding_display.show_setup_screen()  # must not raise
