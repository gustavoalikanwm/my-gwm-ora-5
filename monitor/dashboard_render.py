from datetime import date, datetime

_STYLE = """
:root {
  color-scheme: light dark;
  --bg: #0f172a;
  --card: #1e293b;
  --text: #e2e8f0;
  --muted: #94a3b8;
  --accent: #38bdf8;
  --border: #334155;
  --row-alt: #16213a;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2rem 1rem;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  display: flex;
  justify-content: center;
}
main {
  width: 100%;
  max-width: 900px;
}
h1 {
  font-size: 1.5rem;
  margin: 0 0 0.5rem;
}
.subtitle {
  color: var(--muted);
  margin: 0 0 1.5rem;
}
.subtitle strong {
  color: var(--accent);
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}
th, td {
  padding: 0.75rem 1rem;
  text-align: left;
  white-space: nowrap;
}
thead th {
  background: rgba(56, 189, 248, 0.1);
  color: var(--accent);
  font-weight: 600;
  border-bottom: 1px solid var(--border);
}
tbody tr:nth-child(even) {
  background: var(--row-alt);
}
tbody td {
  border-bottom: 1px solid var(--border);
}
tbody tr:last-child td {
  border-bottom: none;
}
a {
  color: var(--accent);
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
.updated {
  color: var(--muted);
  font-size: 0.85rem;
  margin-top: 1rem;
  text-align: right;
}
"""


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


def _vesselfinder_link(vessel: dict) -> str:
    url = f"https://www.vesselfinder.com/vessels/details/{vessel['imo']}"
    return f'<a href="{url}" target="_blank" rel="noopener">{vessel["name"]}</a>'


def _fleet_row(vessel: dict, latest_by_mmsi: dict[int, dict]) -> str:
    name_cell = _vesselfinder_link(vessel)
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitor GWM ORA 05 - navios China-Brasil</title>
<style>{_STYLE}</style>
</head>
<body>
<main>
<h1>Monitor de navios porta-carros China &rarr; Brasil</h1>
<p class="subtitle">Estimativa de chegada informada pela GWM: {config['target_eta']}
(<strong>{days_remaining} dias restantes</strong>)</p>
<div class="card">
<table>
<thead><tr><th>Navio</th><th>Destino declarado</th><th>ETA declarada</th><th>Última posição</th><th>Registrado em (UTC)</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>
<p class="updated">Atualizado em {now.isoformat(timespec="minutes")}</p>
</main>
</body>
</html>
"""
