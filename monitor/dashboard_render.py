from datetime import date, datetime


def _days_remaining(target_eta: str, today: date) -> int:
    return (date.fromisoformat(target_eta) - today).days


def _latest_positions(sightings: list[dict]) -> dict[int, dict]:
    latest: dict[int, dict] = {}
    for entry in sightings:
        if entry.get("kind") != "position":
            continue
        mmsi = entry["mmsi"]
        current = latest.get(mmsi)
        if current is None or entry["timestamp_utc"] > current["timestamp_utc"]:
            latest[mmsi] = entry
    return latest


def _marinetraffic_link(vessel: dict) -> str:
    url = f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{vessel['mmsi']}"
    return f'<a href="{url}" target="_blank" rel="noopener">{vessel["name"]}</a>'


def _fleet_row(vessel: dict, latest_by_mmsi: dict[int, dict]) -> str:
    name_cell = _marinetraffic_link(vessel)
    destination = vessel.get("destination") or "—"
    eta = vessel.get("eta") or "—"
    declared_cells = f"<td>{destination}</td><td>{eta}</td>"

    position = latest_by_mmsi.get(vessel["mmsi"])
    if position is None:
        return (
            f"<tr><td>{name_cell}</td>{declared_cells}"
            f"<td colspan=\"2\">sem posição recente</td></tr>"
        )
    coords = f"{position['latitude']:.3f}, {position['longitude']:.3f}"
    return (
        f"<tr><td>{name_cell}</td>{declared_cells}<td>{coords}</td>"
        f"<td>{position['timestamp_utc']}</td></tr>"
    )


def render_dashboard(config: dict, sightings: list[dict], now: datetime) -> str:
    days_remaining = _days_remaining(config["target_eta"], now.date())
    latest_by_mmsi = _latest_positions(sightings)
    fleet = config["fleet"]
    if fleet:
        rows = "\n".join(_fleet_row(vessel, latest_by_mmsi) for vessel in fleet)
    else:
        rows = "<tr><td colspan=\"5\">frota curada vazia</td></tr>"

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Monitor GWM ORA 05 - navios China-Brasil</title>
</head>
<body>
<h1>Monitor de navios porta-carros China &rarr; Brasil</h1>
<p>Estimativa de chegada informada pela GWM: {config['target_eta']}
({days_remaining} dias restantes)</p>
<table>
<thead><tr><th>Navio</th><th>Destino declarado</th><th>ETA declarada</th><th>Última posição</th><th>Registrado em (UTC)</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<p><small>Atualizado em {now.isoformat(timespec="minutes")}</small></p>
</body>
</html>
"""
