import json
from datetime import datetime, timezone
from pathlib import Path

from monitor.config import load_config
from monitor.dashboard_render import render_dashboard
from monitor.jsonl_store import read_all


def _read_port_schedule(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    config = load_config(Path("config.yaml"))
    sightings = read_all(Path("data/ais_sightings.jsonl"))
    port_schedule = _read_port_schedule(Path("data/port_schedule.json"))
    html = render_dashboard(config, sightings, port_schedule, datetime.now(timezone.utc))
    output_path = Path("docs/index.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"painel gerado em {output_path}")


if __name__ == "__main__":
    main()
