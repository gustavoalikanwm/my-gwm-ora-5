from datetime import datetime, timezone

from monitor.dashboard_render import render_dashboard

CONFIG = {
    "target_eta": "2026-10-31",
    "fleet": [
        {
            "name": "NAVIO COM POSICAO",
            "mmsi": 111,
            "imo": 1,
            "destination": "Paranagua",
            "eta": "2026-09-10",
        },
        {"name": "NAVIO SEM POSICAO", "mmsi": 222, "imo": 2},
    ],
}

SIGHTINGS = [
    {
        "kind": "position",
        "mmsi": 111,
        "ship_name": "NAVIO COM POSICAO",
        "latitude": -23.5,
        "longitude": -45.0,
        "timestamp_utc": "2026-08-19 10:00:00.000000 +0000 UTC",
    },
    {
        "kind": "position",
        "mmsi": 111,
        "ship_name": "NAVIO COM POSICAO",
        "latitude": -24.0,
        "longitude": -46.0,
        "timestamp_utc": "2026-08-19 16:00:00.000000 +0000 UTC",
    },
]

PORT_SCHEDULE = [
    {
        "id": "26/0001",
        "navio": "NAVIO COM POSICAO",
        "armador": "ARMADOR X",
        "eta_utc": "2026-08-25T09:00:00+00:00",
        "tipo_operacao": "Embarque",
        "servico": "CAR      Car Carrier - TEV",
    },
    {
        "id": "26/0002",
        "navio": "OUTRO NAVIO QUALQUER",
        "armador": "ARMADOR Y",
        "eta_utc": "2026-08-10T09:00:00+00:00",
        "tipo_operacao": "Descarga",
        "servico": "CAR      Car Carrier - TEV",
    },
]

NOW = datetime(2026, 8, 19, 20, 0, tzinfo=timezone.utc)


def test_render_dashboard_shows_days_remaining():
    html = render_dashboard(CONFIG, SIGHTINGS, PORT_SCHEDULE, NOW)
    assert "73 dias restantes" in html


def test_render_dashboard_shows_latest_position_per_vessel():
    html = render_dashboard(CONFIG, SIGHTINGS, PORT_SCHEDULE, NOW)
    assert "NAVIO COM POSICAO" in html
    assert "-24.000, -46.000" in html
    assert "10:00:00" not in html  # deve mostrar a posicao mais recente, nao a antiga


def test_render_dashboard_flags_vessel_without_recent_position():
    html = render_dashboard(CONFIG, SIGHTINGS, PORT_SCHEDULE, NOW)
    assert "NAVIO SEM POSICAO" in html
    assert "sem posição recente" in html


def test_render_dashboard_links_each_vessel_to_vesselfinder_by_imo():
    html = render_dashboard(CONFIG, SIGHTINGS, PORT_SCHEDULE, NOW)
    assert 'href="https://www.vesselfinder.com/vessels/details/1"' in html
    assert 'href="https://www.vesselfinder.com/vessels/details/2"' in html


def test_render_dashboard_shows_declared_destination_and_eta():
    html = render_dashboard(CONFIG, SIGHTINGS, PORT_SCHEDULE, NOW)
    assert "Paranagua" in html
    assert "2026-09-10" in html


def test_render_dashboard_shows_dash_when_no_declared_destination_or_eta():
    html = render_dashboard(CONFIG, SIGHTINGS, PORT_SCHEDULE, NOW)
    rows = html.split("<tr>")
    sem_posicao_row = next(row for row in rows if "NAVIO SEM POSICAO" in row)
    assert "<td>—</td><td>—</td>" in sem_posicao_row


def test_render_dashboard_handles_empty_fleet():
    html = render_dashboard(
        {"target_eta": "2026-10-31", "fleet": []}, [], [], NOW
    )
    assert "frota curada vazia" in html


def test_render_dashboard_shows_only_future_port_entries_sorted_by_eta():
    html = render_dashboard(CONFIG, SIGHTINGS, PORT_SCHEDULE, NOW)
    assert "OUTRO NAVIO QUALQUER" not in html  # ETA no passado (10/08 < 19/08)
    assert "ARMADOR X" in html
    assert "2026-08-25T09:00:00+00:00" in html


def test_render_dashboard_flags_port_entry_matching_curated_fleet():
    html = render_dashboard(CONFIG, SIGHTINGS, PORT_SCHEDULE, NOW)
    port_section = html[html.index("Car Carrier") :]
    row = next(
        r for r in port_section.split("<tr>") if "NAVIO COM POSICAO" in r
    )
    assert "na-frota" in row


def test_render_dashboard_shows_message_when_no_port_schedule():
    html = render_dashboard(CONFIG, SIGHTINGS, [], NOW)
    assert "sem dados de programação portuária coletados ainda" in html
