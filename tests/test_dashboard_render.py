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

NOW = datetime(2026, 8, 19, 20, 0, tzinfo=timezone.utc)


def test_render_dashboard_shows_days_remaining():
    html = render_dashboard(CONFIG, SIGHTINGS, NOW)
    assert "73 dias restantes" in html


def test_render_dashboard_shows_latest_position_per_vessel():
    html = render_dashboard(CONFIG, SIGHTINGS, NOW)
    assert "NAVIO COM POSICAO" in html
    assert "-24.000, -46.000" in html
    assert "10:00:00" not in html  # deve mostrar a posicao mais recente, nao a antiga


def test_render_dashboard_flags_vessel_without_recent_position():
    html = render_dashboard(CONFIG, SIGHTINGS, NOW)
    assert "NAVIO SEM POSICAO" in html
    assert "sem posição recente" in html


def test_render_dashboard_links_each_vessel_to_vesselfinder_by_imo():
    html = render_dashboard(CONFIG, SIGHTINGS, NOW)
    assert 'href="https://www.vesselfinder.com/vessels/details/1"' in html
    assert 'href="https://www.vesselfinder.com/vessels/details/2"' in html


def test_render_dashboard_shows_declared_destination_and_eta():
    html = render_dashboard(CONFIG, SIGHTINGS, NOW)
    assert "Paranagua" in html
    assert "2026-09-10" in html


def test_render_dashboard_shows_dash_when_no_declared_destination_or_eta():
    html = render_dashboard(CONFIG, SIGHTINGS, NOW)
    rows = html.split("<tr>")
    sem_posicao_row = next(row for row in rows if "NAVIO SEM POSICAO" in row)
    assert "<td>—</td><td>—</td>" in sem_posicao_row


def test_render_dashboard_handles_empty_fleet():
    html = render_dashboard({"target_eta": "2026-10-31", "fleet": []}, [], NOW)
    assert "frota curada vazia" in html
