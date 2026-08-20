import json
from pathlib import Path

from monitor.ais_parser import parse_message, process_messages

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_message_handles_position_report():
    raw = load_fixture("position_report.json")

    parsed = parse_message(raw)

    assert parsed == {
        "kind": "position",
        "mmsi": 245473000,
        "ship_name": "TEST VESSEL",
        "latitude": 51.44458833333333,
        "longitude": 3.590816666666667,
        "sog_knots": 12.3,
        "cog_degrees": 45.2,
        "timestamp_utc": "2026-08-19 18:22:32.318353 +0000 UTC",
    }


def test_parse_message_handles_ship_static_data():
    raw = load_fixture("ship_static_data.json")

    parsed = parse_message(raw)

    assert parsed == {
        "kind": "static",
        "mmsi": 257069200,
        "ship_name": "TEST VESSEL",
        "destination": "BR SSZ",
        "eta_month": 10,
        "eta_day": 31,
        "timestamp_utc": "2026-08-19 18:22:32.318353 +0000 UTC",
    }


def test_parse_message_returns_none_for_unknown_type():
    assert parse_message({"MessageType": "StandardClassBPositionReport"}) is None


def test_process_messages_discards_unknown_types():
    raw_messages = [
        load_fixture("position_report.json"),
        {"MessageType": "StandardClassBPositionReport"},
        load_fixture("ship_static_data.json"),
    ]

    result = process_messages(raw_messages)

    assert len(result) == 2
    assert result[0]["kind"] == "position"
    assert result[1]["kind"] == "static"
