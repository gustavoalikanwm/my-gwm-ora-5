import json
from pathlib import Path

from monitor.port_parser import (
    parse_dotnet_date,
    parse_port_entry,
    process_port_response,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "port_schedule_sample.json").read_text(
        encoding="utf-8"
    )
)


def test_parse_dotnet_date_converts_epoch_millis_to_iso_utc():
    assert parse_dotnet_date("/Date(1672657200000)/") == "2023-01-02T11:00:00+00:00"


def test_parse_dotnet_date_handles_none_and_empty():
    assert parse_dotnet_date(None) is None
    assert parse_dotnet_date("") is None


def test_parse_port_entry_extracts_and_normalizes_fields():
    raw = FIXTURE["VAtracacao"][0]

    entry = parse_port_entry(raw)

    assert entry == {
        "id": "23/0115",
        "navio": "INTEGRADOR",
        "armador": "ROR",
        "eta_utc": "2023-01-02T11:00:00+00:00",
        "tipo_operacao": "Embarque",
        "servico": "CAR      Car Carrier - TEV",
    }


def test_process_port_response_filters_only_car_service_and_parses_real_fixture():
    entries = process_port_response(FIXTURE)

    assert len(entries) == 98
    assert all(e["navio"] for e in entries)
    assert {"id", "navio", "armador", "eta_utc", "tipo_operacao", "servico"} <= set(
        entries[0].keys()
    )
