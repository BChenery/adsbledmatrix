from app.services.aircraft_db import AircraftDatabase, db


def test_casa_registration_keys_from_tail_callsign():
    assert AircraftDatabase._casa_registration_keys("AF4") == ["VHAF4"]
    assert AircraftDatabase._casa_registration_keys("VHAF4") == ["VHAF4"]
    assert AircraftDatabase._casa_registration_keys("VH-AF4") == ["VHAF4"]
    # Airline flight numbers must not be turned into a VH- tail.
    assert AircraftDatabase._casa_registration_keys("QF12") == []
    assert AircraftDatabase._casa_registration_keys("AFR004") == []


def test_casa_from_callsign_resolves_vh_af4():
    row = db._casa_from_callsign("7C00D2", "AF4")
    assert row is not None
    assert row["registration"] == "VH-AF4"
    assert row["type_code"] == "C414"
    assert row["operator"] and "Angel Flight" in row["operator"]


def test_casa_from_callsign_ignores_foreign_hex():
    assert db._casa_from_callsign("394C19", "AF4") is None
