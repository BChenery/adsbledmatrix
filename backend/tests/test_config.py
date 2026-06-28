import os
from unittest.mock import patch


def test_spwm_settings_parsed_from_env():
    env = {
        "ADSB_LED_MATRIX_SPWM_ROW_ADDRESS_TYPE": "1",
        "ADSB_LED_MATRIX_SPWM_REGISTER_CONFIG": "-1",
        "ADSB_LED_MATRIX_SPWM_SCAN_ROWS": "0",
    }
    with patch.dict(os.environ, env, clear=False):
        from app.config import Settings

        settings = Settings()
        assert settings.led_matrix_spwm_row_address_type == 1
        assert settings.led_matrix_spwm_register_config == -1
        assert settings.led_matrix_spwm_scan_rows == 0


def test_rgb_sequence_parsed_from_env():
    env = {"ADSB_LED_MATRIX_LED_RGB_SEQUENCE": "BGR"}
    with patch.dict(os.environ, env, clear=False):
        from app.config import Settings

        settings = Settings()
        assert settings.led_matrix_led_rgb_sequence == "BGR"
