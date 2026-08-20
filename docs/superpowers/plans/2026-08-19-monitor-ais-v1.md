# Monitor de Navios — Pipeline AIS (v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (execução inline, sem subagentes — decisão explícita do projeto). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o pipeline de coleta de posições AIS (aisstream.io) de uma
frota curada de navios porta-carros + painel estático publicado via GitHub
Pages, rodando sozinho via GitHub Actions.

**Architecture:** Scripts Python puros (parsing/render testáveis sem rede),
com uma camada fina de I/O (websocket, arquivo, git) sem cobertura de teste
automatizado. Estado do projeto é o próprio repositório Git — cada execução
do cron apenda ao `.jsonl` e regenera o HTML.

**Tech Stack:** Python 3.12, `websockets`, `PyYAML`, `pytest`, GitHub Actions,
GitHub Pages (pasta `docs/`).

**Spec:** [docs/superpowers/specs/2026-08-19-monitor-navios-design.md](../specs/2026-08-19-monitor-navios-design.md)
(este plano cobre apenas o recorte v1 descrito na "Nota de fasamento" no topo
da spec — sem `port_collector`).

## Global Constraints

- Python 3.12 (usa `asyncio.timeout`, requer 3.11+).
- Zero custo: `aisstream.io` free tier, GitHub Actions free tier, GitHub
  Pages grátis (exige repo público — já decidido).
- Sem subagentes / Task tool em nenhuma etapa — tudo executado inline nesta
  sessão.
- Repositório: `gustavoalikanwm/my-gwm-ora-5` (público), clone local em
  `C:\repos\my-gwm-ora-5`.
- Sem notificação push — só painel estático.
- Sem dado inventado: a lista de frota (`config.yaml`) começa vazia; navios
  reais são adicionados manualmente depois (documentado no README), nunca
  com MMSI fictício.

---

### Task 1: Estrutura do projeto e configuração

**Files:**
- Create: `C:\repos\my-gwm-ora-5\requirements.txt`
- Create: `C:\repos\my-gwm-ora-5\monitor\__init__.py`
- Create: `C:\repos\my-gwm-ora-5\monitor\config.py`
- Create: `C:\repos\my-gwm-ora-5\config.yaml`
- Test: `C:\repos\my-gwm-ora-5\tests\test_config.py`

**Interfaces:**
- Produces: `monitor.config.load_config(path: pathlib.Path) -> dict` — dict
  com chaves `target_eta: str` (ISO `YYYY-MM-DD`) e `fleet: list[dict]` (cada
  item com `name: str`, `mmsi: int`, `imo: int`).

- [ ] **Step 1: Criar `requirements.txt`**

```
websockets>=13,<14
PyYAML>=6,<7
pytest>=8,<9
```

- [ ] **Step 2: Criar `config.yaml`**

```yaml
# Data estimada de chegada informada pela GWM (03/07/2026 + 120 dias).
target_eta: "2026-10-31"

# Frota curada de navios porta-carros (RoRo) conhecidos na rota China<->Brasil.
# Comeca vazia de proposito - nao inventar MMSI. Para adicionar um navio real:
#   1. Descubra o nome do navio (noticia, app da GWM, etc).
#   2. Busque o nome no Equasis (https://www.equasis.org) para confirmar
#      IMO/MMSI e que o tipo e "Vehicles Carrier".
#   3. Adicione um item abaixo:
#        - name: "NOME DO NAVIO"
#          mmsi: 123456789
#          imo: 9876543
fleet: []
```

- [ ] **Step 3: Criar `monitor/__init__.py` (vazio)**

- [ ] **Step 4: Escrever o teste de `load_config`**

```python
# tests/test_config.py
from pathlib import Path

from monitor.config import load_config


def test_load_config_reads_target_eta_and_fleet(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "target_eta: \"2026-10-31\"\n"
        "fleet:\n"
        "  - name: \"NAVIO TESTE\"\n"
        "    mmsi: 123456789\n"
        "    imo: 9876543\n",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config["target_eta"] == "2026-10-31"
    assert config["fleet"] == [
        {"name": "NAVIO TESTE", "mmsi": 123456789, "imo": 9876543}
    ]
```

- [ ] **Step 5: Rodar o teste e confirmar que falha**

Run: `cd C:\repos\my-gwm-ora-5 && python -m pytest tests/test_config.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'monitor.config'`

- [ ] **Step 6: Implementar `monitor/config.py`**

```python
from pathlib import Path

import yaml


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

- [ ] **Step 7: Instalar dependências e rodar o teste de novo**

Run: `cd C:\repos\my-gwm-ora-5 && pip install -r requirements.txt && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add requirements.txt monitor/__init__.py monitor/config.py config.yaml tests/test_config.py
git commit -m "feat: estrutura do projeto e carregamento de config.yaml"
```

---

### Task 2: Armazenamento append-dedup (`jsonl_store`)

**Files:**
- Create: `C:\repos\my-gwm-ora-5\monitor\jsonl_store.py`
- Test: `C:\repos\my-gwm-ora-5\tests\test_jsonl_store.py`

**Interfaces:**
- Consumes: nada de tasks anteriores (módulo independente).
- Produces:
  - `monitor.jsonl_store.read_all(path: pathlib.Path) -> list[dict]`
  - `monitor.jsonl_store.append_dedup(path: pathlib.Path, new_entries: list[dict], key_fn: Callable[[dict], Hashable]) -> int`
    (retorna quantas entradas novas foram gravadas)

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_jsonl_store.py
import json

from monitor.jsonl_store import append_dedup, read_all


def test_read_all_returns_empty_list_when_file_missing(tmp_path):
    assert read_all(tmp_path / "missing.jsonl") == []


def test_append_dedup_writes_new_entries_and_skips_duplicates(tmp_path):
    path = tmp_path / "data.jsonl"
    key_fn = lambda e: (e["mmsi"], e["timestamp_utc"])

    first_batch = [{"mmsi": 1, "timestamp_utc": "t1"}, {"mmsi": 1, "timestamp_utc": "t2"}]
    added_first = append_dedup(path, first_batch, key_fn)
    assert added_first == 2
    assert read_all(path) == first_batch

    second_batch = [
        {"mmsi": 1, "timestamp_utc": "t2"},  # duplicado
        {"mmsi": 1, "timestamp_utc": "t3"},  # novo
    ]
    added_second = append_dedup(path, second_batch, key_fn)
    assert added_second == 1
    assert read_all(path) == first_batch + [{"mmsi": 1, "timestamp_utc": "t3"}]


def test_append_dedup_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "data.jsonl"
    append_dedup(path, [{"mmsi": 1, "timestamp_utc": "t1"}], lambda e: e["mmsi"])
    assert path.exists()
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd C:\repos\my-gwm-ora-5 && python -m pytest tests/test_jsonl_store.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'monitor.jsonl_store'`

- [ ] **Step 3: Implementar `monitor/jsonl_store.py`**

```python
import json
from pathlib import Path
from typing import Callable, Hashable


def read_all(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def append_dedup(
    path: Path,
    new_entries: list[dict],
    key_fn: Callable[[dict], Hashable],
) -> int:
    existing_keys = {key_fn(entry) for entry in read_all(path)}
    to_add = [entry for entry in new_entries if key_fn(entry) not in existing_keys]
    if not to_add:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for entry in to_add:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return len(to_add)
```

- [ ] **Step 4: Rodar de novo**

Run: `cd C:\repos\my-gwm-ora-5 && python -m pytest tests/test_jsonl_store.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add monitor/jsonl_store.py tests/test_jsonl_store.py
git commit -m "feat: armazenamento append-dedup em jsonl"
```

---

### Task 3: Parsing de mensagens AIS

**Files:**
- Create: `C:\repos\my-gwm-ora-5\monitor\ais_parser.py`
- Create: `C:\repos\my-gwm-ora-5\tests\fixtures\position_report.json`
- Create: `C:\repos\my-gwm-ora-5\tests\fixtures\ship_static_data.json`
- Test: `C:\repos\my-gwm-ora-5\tests\test_ais_parser.py`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces:
  - `monitor.ais_parser.parse_message(raw: dict) -> dict | None` — retorna
    `None` se `raw["MessageType"]` não for `"PositionReport"` nem
    `"ShipStaticData"`. Para `PositionReport`, retorna
    `{"kind": "position", "mmsi": int, "ship_name": str, "latitude": float,
    "longitude": float, "sog_knots": float, "cog_degrees": float,
    "timestamp_utc": str}`. Para `ShipStaticData`, retorna
    `{"kind": "static", "mmsi": int, "ship_name": str, "destination": str,
    "eta_month": int, "eta_day": int, "timestamp_utc": str}`.
  - `monitor.ais_parser.process_messages(raw_messages: list[dict]) -> list[dict]`
    — aplica `parse_message` a cada item, descarta os `None`.

- [ ] **Step 1: Criar as fixtures com os exemplos reais da doc do aisstream.io**

```json
// tests/fixtures/position_report.json
{
  "MessageType": "PositionReport",
  "Message": {
    "PositionReport": {
      "MessageID": 1,
      "RepeatIndicator": 0,
      "UserID": 245473000,
      "Valid": true,
      "NavigationalStatus": 7,
      "RateOfTurn": 0,
      "Sog": 12.3,
      "PositionAccuracy": true,
      "Longitude": 3.590816666666667,
      "Latitude": 51.44458833333333,
      "Cog": 45.2,
      "TrueHeading": 17,
      "Timestamp": 12,
      "SpecialManoeuvreIndicator": 0,
      "Spare": 0,
      "Raim": true,
      "CommunicationState": 59916
    }
  },
  "MetaData": {
    "MMSI": 245473000,
    "ShipName": "TEST VESSEL",
    "latitude": 51.44458833333333,
    "longitude": 3.590816666666667,
    "time_utc": "2026-08-19 18:22:32.318353 +0000 UTC"
  }
}
```

```json
// tests/fixtures/ship_static_data.json
{
  "MessageType": "ShipStaticData",
  "Message": {
    "ShipStaticData": {
      "MessageID": 5,
      "RepeatIndicator": 0,
      "UserID": 257069200,
      "Valid": true,
      "AisVersion": 2,
      "ImoNumber": 9353333,
      "CallSign": "LBHF",
      "Name": "TEST VESSEL",
      "Type": 70,
      "Dimension": {"A": 20, "B": 27, "C": 7, "D": 7},
      "FixType": 1,
      "Eta": {"Month": 10, "Day": 31, "Hour": 6, "Minute": 0},
      "MaximumStaticDraught": 4.5,
      "Destination": "BR SSZ",
      "Dte": false,
      "Spare": false
    }
  },
  "MetaData": {
    "MMSI": 257069200,
    "ShipName": "TEST VESSEL",
    "time_utc": "2026-08-19 18:22:32.318353 +0000 UTC"
  }
}
```

- [ ] **Step 2: Escrever os testes**

```python
# tests/test_ais_parser.py
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
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `cd C:\repos\my-gwm-ora-5 && python -m pytest tests/test_ais_parser.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'monitor.ais_parser'`

- [ ] **Step 4: Implementar `monitor/ais_parser.py`**

```python
def _parse_position_report(raw: dict) -> dict | None:
    if raw.get("MessageType") != "PositionReport":
        return None
    report = raw["Message"]["PositionReport"]
    meta = raw["MetaData"]
    return {
        "kind": "position",
        "mmsi": meta["MMSI"],
        "ship_name": meta.get("ShipName", "").strip(),
        "latitude": report["Latitude"],
        "longitude": report["Longitude"],
        "sog_knots": report.get("Sog"),
        "cog_degrees": report.get("Cog"),
        "timestamp_utc": meta["time_utc"],
    }


def _parse_ship_static_data(raw: dict) -> dict | None:
    if raw.get("MessageType") != "ShipStaticData":
        return None
    static = raw["Message"]["ShipStaticData"]
    meta = raw["MetaData"]
    eta = static.get("Eta", {})
    return {
        "kind": "static",
        "mmsi": meta["MMSI"],
        "ship_name": meta.get("ShipName", "").strip(),
        "destination": static.get("Destination", "").strip(),
        "eta_month": eta.get("Month"),
        "eta_day": eta.get("Day"),
        "timestamp_utc": meta["time_utc"],
    }


def parse_message(raw: dict) -> dict | None:
    return _parse_position_report(raw) or _parse_ship_static_data(raw)


def process_messages(raw_messages: list[dict]) -> list[dict]:
    parsed = (parse_message(raw) for raw in raw_messages)
    return [entry for entry in parsed if entry is not None]
```

- [ ] **Step 5: Rodar de novo**

Run: `cd C:\repos\my-gwm-ora-5 && python -m pytest tests/test_ais_parser.py -v`
Expected: PASS (4 testes)

- [ ] **Step 6: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add monitor/ais_parser.py tests/test_ais_parser.py tests/fixtures/position_report.json tests/fixtures/ship_static_data.json
git commit -m "feat: parsing de mensagens AIS (PositionReport/ShipStaticData)"
```

---

### Task 4: Geração do painel

**Files:**
- Create: `C:\repos\my-gwm-ora-5\monitor\dashboard_render.py`
- Create: `C:\repos\my-gwm-ora-5\monitor\build_dashboard.py`
- Test: `C:\repos\my-gwm-ora-5\tests\test_dashboard_render.py`

**Interfaces:**
- Consumes: `monitor.config.load_config` (Task 1), `monitor.jsonl_store.read_all` (Task 2). Sightings têm o formato produzido por `monitor.ais_parser.parse_message` (Task 3): campo `"kind"` é `"position"` ou `"static"`, e para `"position"` existem `mmsi`, `latitude`, `longitude`, `timestamp_utc`.
- Produces: `monitor.dashboard_render.render_dashboard(config: dict, sightings: list[dict], now: datetime.datetime) -> str` (HTML completo).

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_dashboard_render.py
from datetime import datetime, timezone

from monitor.dashboard_render import render_dashboard

CONFIG = {
    "target_eta": "2026-10-31",
    "fleet": [
        {"name": "NAVIO COM POSICAO", "mmsi": 111, "imo": 1},
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


def test_render_dashboard_handles_empty_fleet():
    html = render_dashboard({"target_eta": "2026-10-31", "fleet": []}, [], NOW)
    assert "frota curada vazia" in html
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd C:\repos\my-gwm-ora-5 && python -m pytest tests/test_dashboard_render.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'monitor.dashboard_render'`

- [ ] **Step 3: Implementar `monitor/dashboard_render.py`**

```python
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


def _fleet_row(vessel: dict, latest_by_mmsi: dict[int, dict]) -> str:
    position = latest_by_mmsi.get(vessel["mmsi"])
    if position is None:
        return (
            f"<tr><td>{vessel['name']}</td>"
            f"<td colspan=\"2\">sem posição recente</td></tr>"
        )
    coords = f"{position['latitude']:.3f}, {position['longitude']:.3f}"
    return (
        f"<tr><td>{vessel['name']}</td><td>{coords}</td>"
        f"<td>{position['timestamp_utc']}</td></tr>"
    )


def render_dashboard(config: dict, sightings: list[dict], now: datetime) -> str:
    days_remaining = _days_remaining(config["target_eta"], now.date())
    latest_by_mmsi = _latest_positions(sightings)
    fleet = config["fleet"]
    if fleet:
        rows = "\n".join(_fleet_row(vessel, latest_by_mmsi) for vessel in fleet)
    else:
        rows = "<tr><td colspan=\"3\">frota curada vazia</td></tr>"

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
<thead><tr><th>Navio</th><th>Última posição</th><th>Registrado em (UTC)</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<p><small>Atualizado em {now.isoformat(timespec="minutes")}</small></p>
</body>
</html>
"""
```

- [ ] **Step 4: Rodar de novo**

Run: `cd C:\repos\my-gwm-ora-5 && python -m pytest tests/test_dashboard_render.py -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Implementar `monitor/build_dashboard.py` (CLI, sem teste automatizado)**

```python
from datetime import datetime, timezone
from pathlib import Path

from monitor.config import load_config
from monitor.dashboard_render import render_dashboard
from monitor.jsonl_store import read_all


def main() -> None:
    config = load_config(Path("config.yaml"))
    sightings = read_all(Path("data/ais_sightings.jsonl"))
    html = render_dashboard(config, sightings, datetime.now(timezone.utc))
    output_path = Path("docs/index.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"painel gerado em {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Rodar manualmente e confirmar a saída**

Run: `cd C:\repos\my-gwm-ora-5 && python -m monitor.build_dashboard`
Expected: imprime `painel gerado em docs\index.html`; o arquivo `docs/index.html`
existe e contém `"frota curada vazia"` (config.yaml ainda não tem navios).

- [ ] **Step 7: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add monitor/dashboard_render.py monitor/build_dashboard.py tests/test_dashboard_render.py docs/index.html
git commit -m "feat: geracao do painel estatico (docs/index.html)"
```

---

### Task 5: Coletor AIS (rede)

**Files:**
- Create: `C:\repos\my-gwm-ora-5\monitor\ais_collector.py`

**Interfaces:**
- Consumes: `monitor.config.load_config` (Task 1), `monitor.ais_parser.process_messages` (Task 3), `monitor.jsonl_store.append_dedup` (Task 2).
- Produces: `monitor.ais_collector.collect_raw_messages(api_key: str, mmsi_list: list[int], listen_seconds: int) -> list[dict]` (async — coroutine; camada de rede, sem teste automatizado, conforme decidido na spec).

Sem teste automatizado aqui (rede real de terceiro) — a lógica testável
(`process_messages`) já foi coberta na Task 3. Verificação é manual via
`workflow_dispatch` na Task 6.

- [ ] **Step 1: Implementar `monitor/ais_collector.py`**

```python
import asyncio
import json
import os
import sys
from pathlib import Path

import websockets

from monitor.ais_parser import process_messages
from monitor.config import load_config
from monitor.jsonl_store import append_dedup

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
LISTEN_SECONDS = 90


async def collect_raw_messages(
    api_key: str, mmsi_list: list[int], listen_seconds: int = LISTEN_SECONDS
) -> list[dict]:
    raw_messages: list[dict] = []
    async with websockets.connect(AISSTREAM_URL) as ws:
        subscribe = {
            "APIKey": api_key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FiltersShipMMSI": [str(mmsi) for mmsi in mmsi_list],
        }
        await ws.send(json.dumps(subscribe))
        try:
            async with asyncio.timeout(listen_seconds):
                async for raw in ws:
                    raw_messages.append(json.loads(raw))
        except TimeoutError:
            pass
    return raw_messages


def _sighting_key(entry: dict) -> tuple:
    return (entry["mmsi"], entry["kind"], entry["timestamp_utc"])


def main() -> None:
    config = load_config(Path("config.yaml"))
    api_key = os.environ.get("AISSTREAM_API_KEY")
    if not api_key:
        print("AISSTREAM_API_KEY nao configurada - pulando coleta AIS", file=sys.stderr)
        return

    mmsi_list = [vessel["mmsi"] for vessel in config["fleet"]]
    if not mmsi_list:
        print("frota curada vazia em config.yaml - nada para coletar", file=sys.stderr)
        return

    try:
        raw_messages = asyncio.run(collect_raw_messages(api_key, mmsi_list))
    except Exception as exc:
        print(f"falha na coleta AIS: {exc}", file=sys.stderr)
        return

    sightings = process_messages(raw_messages)
    added = append_dedup(Path("data/ais_sightings.jsonl"), sightings, _sighting_key)
    print(f"{added} nova(s) leitura(s) AIS gravada(s)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificar que o módulo importa sem erro**

Run: `cd C:\repos\my-gwm-ora-5 && python -c "import monitor.ais_collector"`
Expected: nenhuma saída, sem traceback.

- [ ] **Step 3: Rodar a suíte completa de testes antes de commitar**

Run: `cd C:\repos\my-gwm-ora-5 && python -m pytest -v`
Expected: todos os testes das Tasks 1-4 continuam passando (nenhum teste
novo nesta task).

- [ ] **Step 4: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add monitor/ais_collector.py
git commit -m "feat: coletor AIS via aisstream.io"
```

---

### Task 6: Workflow do GitHub Actions, GitHub Pages e README

**Files:**
- Create: `C:\repos\my-gwm-ora-5\.github\workflows\monitor.yml`
- Create: `C:\repos\my-gwm-ora-5\README.md`

**Interfaces:**
- Consumes: `python -m monitor.ais_collector` e `python -m monitor.build_dashboard` (Tasks 4 e 5) como comandos de linha de comando.
- Produces: nada consumido por outra task — é o último passo do v1.

- [ ] **Step 1: Criar `.github/workflows/monitor.yml`**

```yaml
name: Monitor de navios

on:
  schedule:
    - cron: "0 */6 * * *"
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  collect-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Instalar dependencias
        run: pip install -r requirements.txt

      - name: Coletar posicoes AIS
        env:
          AISSTREAM_API_KEY: ${{ secrets.AISSTREAM_API_KEY }}
        run: python -m monitor.ais_collector

      - name: Gerar painel
        run: python -m monitor.build_dashboard

      - name: Commitar mudancas
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ais_sightings.jsonl docs/index.html
          git diff --cached --quiet || git commit -m "chore: atualiza dados de monitoramento"
          git push
```

- [ ] **Step 2: Criar `README.md`**

```markdown
# my-gwm-ora-5

Monitor gratuito de navios porta-carros (RoRo) na rota China -> Brasil,
como sinal indireto da chegada de um GWM ORA 05 comprado em pre-reserva
(sem dado de booking/VIN/navio fornecido pela GWM - rastreamento do navio
exato nao e possivel, ver `docs/superpowers/specs/`).

Painel publicado via GitHub Pages a partir de `docs/index.html`, atualizado
a cada 6h por um workflow do GitHub Actions.

## Como adicionar um navio a frota curada

1. Descubra o nome do navio (noticia, imprensa, app da GWM).
2. Busque o nome no [Equasis](https://www.equasis.org) (gratuito, precisa de
   conta) e confirme o IMO/MMSI e que o tipo do navio e "Vehicles Carrier".
3. Adicione em `config.yaml`:

   ```yaml
   fleet:
     - name: "NOME DO NAVIO"
       mmsi: 123456789
       imo: 9876543
   ```

4. Commit e push - a proxima execucao do workflow ja assina esse MMSI.

## Configuracao do secret AISSTREAM_API_KEY

1. Crie uma conta gratuita em https://aisstream.io e gere uma API key.
2. No GitHub: Settings -> Secrets and variables -> Actions -> New repository
   secret -> nome `AISSTREAM_API_KEY`, valor = a chave gerada.

## Rodando localmente

```bash
pip install -r requirements.txt
python -m pytest -v
AISSTREAM_API_KEY=... python -m monitor.ais_collector
python -m monitor.build_dashboard
```

## Escopo

Este e o v1 (so pipeline AIS). Coleta de programacao portuaria brasileira
(v2) esta fora de escopo - ver nota de fasamento na spec.
```

- [ ] **Step 3: Habilitar GitHub Pages a partir da pasta `docs/` (requer confirmação antes de mudar a config do repo)**

Run (após confirmação): `cd C:\repos\my-gwm-ora-5 && gh api repos/gustavoalikanwm/my-gwm-ora-5/pages -X POST -f "source[branch]=master" -f "source[path]=/docs"`
Expected: resposta JSON com `"status"` e uma `"html_url"` do tipo
`https://gustavoalikanwm.github.io/my-gwm-ora-5/`.

- [ ] **Step 4: Commit e push**

```bash
cd C:\repos\my-gwm-ora-5
git add .github/workflows/monitor.yml README.md
git commit -m "feat: workflow de coleta/publicacao + readme"
git push
```

- [ ] **Step 5: Disparar o workflow manualmente e verificar ponta a ponta**

Run: `cd C:\repos\my-gwm-ora-5 && gh workflow run monitor.yml && sleep 30 && gh run list --workflow=monitor.yml --limit 1`
Expected: execução com status `success` (ou, na primeira vez sem
`AISSTREAM_API_KEY` configurada, sucesso mesmo assim — o coletor apenas
loga e sai sem falhar, conforme tratamento de erro da spec).

- [ ] **Step 6: Confirmar o painel publicado**

Run: `cd C:\repos\my-gwm-ora-5 && sleep 60 && curl -s https://gustavoalikanwm.github.io/my-gwm-ora-5/ | grep -o "Monitor de navios"`
Expected: imprime `Monitor de navios` (Pages já serviu o HTML gerado).

---

## Fora de escopo deste plano

- Coletor de programação portuária (`port_collector.py`) — v2, plano e spec
  próprios, começando por validar 1 porto real.
- Preenchimento da frota curada com navios reais — feito manualmente pelo
  usuário depois, seguindo o README (evita MMSI inventado no plano).
