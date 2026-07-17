"""Unit tests for the WiFi scan helpers in scripts/wifi_manager.py."""

from scripts.wifi_manager import (
    _split_nmcli_terse,
    dbm_to_quality,
    dedupe_strongest,
    parse_iw_scan,
    parse_nmcli_wifi,
)

IW_SCAN_SAMPLE = """BSS 11:22:33:44:55:66(on wlan0)
\tcapability: ESS Privacy ShortPreamble (0x0431)
\tsignal: -45.00 dBm
\tSSID: HomeNet
\tRSN:\t * Version: 1
BSS aa:bb:cc:dd:ee:ff(on wlan0)
\tcapability: ESS (0x0001)
\tsignal: -80.00 dBm
\tSSID:
BSS 77:88:99:aa:bb:cc(on wlan0)
\tcapability: ESS (0x0001)
\tsignal: -60.00 dBm
\tSSID: OpenNet
BSS 11:22:33:44:55:67(on wlan0)
\tsignal: -70.00 dBm
\tSSID: HomeNet
\tWPA:\t * Version: 1
"""

NMCLI_SAMPLE = "HomeNet:80:WPA2\nCafe\\:Guest:55:WPA1 WPA2\n:30:--\nOpenNet:60:--\n"


def test_parse_iw_scan_extracts_ssid_signal_security():
    networks = parse_iw_scan(IW_SCAN_SAMPLE)
    by_ssid = {n["ssid"]: n for n in networks}

    homenet = [n for n in networks if n["ssid"] == "HomeNet"]
    assert {n["signal"] for n in homenet} == {100, 60}  # -45 dBm and -70 dBm duplicates
    assert all(n["secured"] for n in homenet)
    assert by_ssid["OpenNet"]["signal"] == 80
    assert by_ssid["OpenNet"]["secured"] is False
    assert "" in by_ssid  # hidden network still parsed (filtered later)


def test_parse_iw_scan_handles_empty_output():
    assert parse_iw_scan("") == []


def test_parse_nmcli_wifi_handles_escapes_and_open_networks():
    networks = parse_nmcli_wifi(NMCLI_SAMPLE)
    by_ssid = {n["ssid"]: n for n in networks}

    assert by_ssid["HomeNet"] == {"ssid": "HomeNet", "signal": 80, "secured": True}
    assert by_ssid["Cafe:Guest"]["secured"] is True  # escaped colon in SSID
    assert by_ssid["OpenNet"]["secured"] is False  # "--" security means open
    assert by_ssid[""]["signal"] == 30  # hidden network, filtered by dedupe


def test_dedupe_strongest_drops_hidden_and_sorts():
    networks = parse_iw_scan(IW_SCAN_SAMPLE)
    result = dedupe_strongest(networks)

    ssids = [n["ssid"] for n in result]
    assert "" not in ssids
    # strongest HomeNet (-45 dBm) wins over the -70 dBm duplicate
    assert result[0] == {"ssid": "HomeNet", "signal": 100, "secured": True}
    assert ssids == sorted(ssids, key=lambda s: -next(n["signal"] for n in result if n["ssid"] == s))


def test_dedupe_drops_masked_hidden_ssids():
    assert dedupe_strongest([{"ssid": "\\x00\\x00", "signal": 50, "secured": True}]) == []


def test_dbm_to_quality_clamps_and_tolerates_junk():
    assert dbm_to_quality(-50) == 100
    assert dbm_to_quality(-100) == 0
    assert dbm_to_quality(-30) == 100
    assert dbm_to_quality("junk") == 0


def test_split_nmcli_terse_only_splits_unescaped_colons():
    assert _split_nmcli_terse("a\\:b:c") == ["a:b", "c"]
    assert _split_nmcli_terse("a:b:c") == ["a", "b", "c"]
