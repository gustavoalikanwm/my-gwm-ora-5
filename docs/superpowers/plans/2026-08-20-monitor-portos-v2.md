# Monitor de Navios — Programação Portuária (v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para implementar esse plano tarefa por tarefa (execução inline, sem subagentes). Steps usam checkbox (`- [ ]`) para tracking.

**Goal:** Coletar a programação de navios Car Carrier do Terminal de
Veículos (TEV) do Porto de Santos via Playwright e mostrar no painel,
cruzando com a frota curada do v1.

**Architecture:** `monitor/port_parser.py` (puro, testável) separado de
`monitor/port_collector.py` (rede via Playwright, sem teste automatizado —
mesmo padrão do `ais_collector.py` no v1). `data/port_schedule.json` é
sobrescrito a cada execução (snapshot, não log append).

**Tech Stack:** Python 3.12, `playwright` (Chromium headless), `pytest`,
GitHub Actions.

**Spec:** [docs/superpowers/specs/2026-08-20-monitor-portos-v2-design.md](../specs/2026-08-20-monitor-portos-v2-design.md)

## Global Constraints

- Mesmo repo/venv do v1 (`C:\repos\my-gwm-ora-5`, `.venv` local).
- Sem subagentes — tudo inline.
- Sem dado inventado: a fixture de teste é o JSON **real** capturado do
  endpoint da Santos Brasil em 2026-08-20
  (`tests/fixtures/port_schedule_sample.json`, já commitado/presente).
- Playwright é a única forma viável (HTTP simples é bloqueado por
  fingerprint, confirmado na spec).

---

### Task 1: Parsing da programação portuária (`port_parser`)

**Files:**
- Create: `C:\repos\my-gwm-ora-5\monitor\port_parser.py`
- Test: `C:\repos\my-gwm-ora-5\tests\test_port_parser.py`
- Usa a fixture já existente: `C:\repos\my-gwm-ora-5\tests\fixtures\port_schedule_sample.json`
  (100 escalas reais do endpoint da Santos Brasil, 98 com `SRV=="CAR"` e
  2 com `SRV=="EUK"`)

**Interfaces:**
- Produces:
  - `monitor.port_parser.parse_dotnet_date(raw: str | None) -> str | None`
  - `monitor.port_parser.parse_port_entry(raw: dict) -> dict` — retorna
    `{"id": str, "navio": str, "armador": str, "eta_utc": str | None,
    "tipo_operacao": str, "servico": str}`
  - `monitor.port_parser.process_port_response(raw_json: dict) -> list[dict]`
    — lê `raw_json["VAtracacao"]`, filtra `SRV.strip() == "CAR"`, aplica
    `parse_port_entry` em cada item

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_port_parser.py
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
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -m pytest tests/test_port_parser.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'monitor.port_parser'`

- [ ] **Step 3: Implementar `monitor/port_parser.py`**

```python
import re
from datetime import datetime, timezone

_DOTNET_DATE_RE = re.compile(r"/Date\((-?\d+)\)/")


def parse_dotnet_date(raw: str | None) -> str | None:
    if not raw:
        return None
    match = _DOTNET_DATE_RE.match(raw)
    if not match:
        return None
    epoch_ms = int(match.group(1))
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()


def parse_port_entry(raw: dict) -> dict:
    return {
        "id": raw["ID"],
        "navio": raw["NAVIO"].strip(),
        "armador": raw["AGENCIA"].strip(),
        "eta_utc": parse_dotnet_date(raw.get("PREVISAO_CHEGADA")),
        "tipo_operacao": raw.get("TIPO_OPERACAO"),
        "servico": raw.get("SERVICO", "").strip(),
    }


def process_port_response(raw_json: dict) -> list[dict]:
    entries = raw_json.get("VAtracacao") or []
    car_entries = (e for e in entries if (e.get("SRV") or "").strip() == "CAR")
    return [parse_port_entry(e) for e in car_entries]
```

- [ ] **Step 4: Rodar de novo**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -m pytest tests/test_port_parser.py -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add monitor/port_parser.py tests/test_port_parser.py tests/fixtures/port_schedule_sample.json
git commit -m "feat: parsing da programacao portuaria (Santos TEV)"
```

---

### Task 2: Segunda tabela no painel + cross-reference com a frota

**Files:**
- Modify: `C:\repos\my-gwm-ora-5\monitor\dashboard_render.py`
- Modify: `C:\repos\my-gwm-ora-5\tests\test_dashboard_render.py`

**Interfaces:**
- Consumes: entradas no formato produzido por
  `monitor.port_parser.parse_port_entry` (Task 1) — campos `navio`,
  `armador`, `eta_utc`, `tipo_operacao`.
- Modifica a assinatura pública: `render_dashboard(config, sightings,
  port_schedule, now)` — todos os call sites (incluindo
  `build_dashboard.py`, ainda não modificado nesta task) precisam do novo
  parâmetro depois desta task.

- [ ] **Step 1: Atualizar os testes existentes pra nova assinatura e adicionar os novos testes**

```python
# tests/test_dashboard_render.py — substituir o conteudo inteiro do arquivo
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
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -m pytest tests/test_dashboard_render.py -v`
Expected: FAIL — `render_dashboard()` ainda tem só 3 parâmetros (sem
`port_schedule`), então todas as chamadas com 4 argumentos dão
`TypeError`.

- [ ] **Step 3: Modificar `monitor/dashboard_render.py`**

Substituir o conteúdo inteiro do arquivo por:

```python
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
  --highlight: #134e2a;
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
h2 {
  font-size: 1.1rem;
  margin: 2rem 0 0.5rem;
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
tbody tr.na-frota {
  background: var(--highlight);
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


def _port_row(entry: dict, fleet_names: set[str]) -> str:
    row_class = ' class="na-frota"' if entry["navio"].upper() in fleet_names else ""
    return (
        f"<tr{row_class}><td>{entry['navio']}</td><td>{entry['armador']}</td>"
        f"<td>{entry['eta_utc']}</td><td>{entry['tipo_operacao']}</td></tr>"
    )


def _port_schedule_section(
    port_schedule: list[dict], fleet: list[dict], now: datetime
) -> str:
    fleet_names = {vessel["name"].upper() for vessel in fleet}
    now_iso = now.isoformat()
    future_entries = sorted(
        (e for e in port_schedule if e.get("eta_utc") and e["eta_utc"] >= now_iso),
        key=lambda e: e["eta_utc"],
    )
    if not future_entries:
        rows = (
            '<tr><td colspan="4">sem dados de programação portuária '
            "coletados ainda</td></tr>"
        )
    else:
        rows = "\n".join(_port_row(entry, fleet_names) for entry in future_entries)

    return f"""<h2>Car Carrier programados &mdash; Porto de Santos (TEV)</h2>
<div class="card">
<table>
<thead><tr><th>Navio</th><th>Armador</th><th>ETA</th><th>Tipo de operação</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>"""


def render_dashboard(
    config: dict, sightings: list[dict], port_schedule: list[dict], now: datetime
) -> str:
    days_remaining = _days_remaining(config["target_eta"], now.date())
    latest_by_mmsi = _latest_positions(sightings)
    fleet = config["fleet"]
    if fleet:
        rows = "\n".join(_fleet_row(vessel, latest_by_mmsi) for vessel in fleet)
    else:
        rows = "<tr><td colspan=\"5\">frota curada vazia</td></tr>"

    port_section = _port_schedule_section(port_schedule, fleet, now)

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
{port_section}
<p class="updated">Atualizado em {now.isoformat(timespec="minutes")}</p>
</main>
</body>
</html>
"""
```

- [ ] **Step 4: Rodar de novo**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -m pytest tests/test_dashboard_render.py -v`
Expected: PASS (9 testes)

- [ ] **Step 5: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add monitor/dashboard_render.py tests/test_dashboard_render.py
git commit -m "feat: segunda tabela no painel com programacao portuaria + cross-reference com a frota"
```

---

### Task 3: `build_dashboard.py` lê o snapshot portuário

**Files:**
- Modify: `C:\repos\my-gwm-ora-5\monitor\build_dashboard.py`

**Interfaces:**
- Consumes: `monitor.dashboard_render.render_dashboard` com a nova
  assinatura de 4 parâmetros (Task 2).
- Sem teste automatizado (é o mesmo CLI já sem teste no v1); verificação é
  manual, rodando o script.

- [ ] **Step 1: Modificar `monitor/build_dashboard.py`**

Substituir o conteúdo inteiro do arquivo por:

```python
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
```

- [ ] **Step 2: Rodar manualmente e confirmar a saída**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -m monitor.build_dashboard`
Expected: imprime `painel gerado em docs\index.html`; `docs/index.html`
contém `"sem dados de programação portuária coletados ainda"` (ainda não
existe `data/port_schedule.json` neste ponto do plano).

- [ ] **Step 3: Rodar a suíte completa antes de commitar**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -m pytest -v`
Expected: todos os testes (Tasks 1 e 2 + testes do v1) passam.

- [ ] **Step 4: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add monitor/build_dashboard.py docs/index.html
git commit -m "feat: build_dashboard le o snapshot da programacao portuaria"
```

---

### Task 4: Coletor via Playwright (`port_collector`)

**Files:**
- Create: `C:\repos\my-gwm-ora-5\monitor\port_collector.py`
- Modify: `C:\repos\my-gwm-ora-5\requirements.txt`

**Interfaces:**
- Consumes: `monitor.port_parser.process_port_response` (Task 1).
- Produces: `monitor.port_collector.main()` — CLI, sem teste automatizado
  (rede real de terceiro via navegador, mesmo padrão do
  `ais_collector.py`).

- [ ] **Step 1: Adicionar `playwright` ao `requirements.txt`**

```
websockets>=13,<14
PyYAML>=6,<7
pytest>=8,<9
playwright>=1.47,<2
```

- [ ] **Step 2: Implementar `monitor/port_collector.py`**

```python
import json
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

from monitor.port_parser import process_port_response

TEV_PAGE_URL = (
    "https://santosbrasil.com.br/v2021/lista-de-atracacao"
    "?titulo=Terminal+de+Ve%C3%ADculos+(TEV)&unidade=tecon-santos"
    "&lista=lista-de-atracacao&atracadouro=TEV"
)
def _build_api_url(data_inicial: str) -> str:
    return (
        "https://santosbrasil.com.br/v2021/lista-de-atracacao/pesquisa"
        "?unidade=tecon-santos&lista=lista-de-atracacao&atracadouro=TEV"
        f"&pesquisa=&dataInicial={data_inicial}&dataFinal=&statusNavio="
    )


def fetch_port_schedule_raw() -> dict:
    # Sem dataInicial o endpoint devolve um dump historico antigo (visto em
    # 2026-08-20: entradas de 2023) em vez da programacao futura - a pagina
    # real preenche esse filtro via JS antes de chamar o endpoint.
    api_url = _build_api_url(date.today().isoformat())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(TEV_PAGE_URL)
        raw_text = page.evaluate(
            """
            (url) => fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}})
                .then((r) => r.text())
            """,
            api_url,
        )
        browser.close()
        return json.loads(raw_text)


def main() -> None:
    try:
        raw_json = fetch_port_schedule_raw()
    except Exception as exc:
        print(f"falha na coleta da programacao portuaria: {exc}", file=sys.stderr)
        return

    entries = process_port_response(raw_json)
    output_path = Path("data/port_schedule.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(entries)} escala(s) de car carrier gravada(s) em data/port_schedule.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Instalar as dependências (inclui o Chromium do Playwright)**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\pip.exe install -r requirements.txt && .\.venv\Scripts\python.exe -m playwright install chromium`
Expected: instala sem erro (o Chromium é ~150-300MB, pode demorar).

- [ ] **Step 4: Verificar que o módulo importa sem erro**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -c "import monitor.port_collector"`
Expected: nenhuma saída, sem traceback.

- [ ] **Step 5: Rodar manualmente contra o site real**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -m monitor.port_collector`
Expected: imprime `N escala(s) de car carrier gravada(s) em
data/port_schedule.json` com N > 0, **ou**, se o bloqueio anti-bot tiver
mudado, imprime `falha na coleta da programacao portuaria: ...` sem
traceback (comportamento aceitável dado o tratamento de erro da spec — se
isso acontecer, reportar antes de continuar, não adivinhar um fix).

- [ ] **Step 6: Rodar a suíte completa**

Run: `cd C:\repos\my-gwm-ora-5 && .\.venv\Scripts\python.exe -m pytest -v`
Expected: todos os testes continuam passando (nenhum teste novo nesta
task).

- [ ] **Step 7: Commit**

```bash
cd C:\repos\my-gwm-ora-5
git add requirements.txt monitor/port_collector.py data/port_schedule.json
git commit -m "feat: coletor da programacao portuaria via Playwright (Santos TEV)"
```

---

### Task 5: Workflow do GitHub Actions

**Files:**
- Modify: `C:\repos\my-gwm-ora-5\.github\workflows\monitor.yml`

**Interfaces:**
- Consumes: `python -m monitor.port_collector` (Task 4) como comando de
  linha de comando.
- Produces: nada consumido por outra task — último passo do v2.

- [ ] **Step 1: Modificar `.github/workflows/monitor.yml`**

Substituir o conteúdo inteiro do arquivo por:

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

      - name: Instalar Chromium do Playwright
        run: python -m playwright install --with-deps chromium

      - name: Coletar posicoes AIS
        env:
          AISSTREAM_API_KEY: ${{ secrets.AISSTREAM_API_KEY }}
        run: python -m monitor.ais_collector

      - name: Coletar programacao portuaria (Santos TEV)
        run: python -m monitor.port_collector

      - name: Gerar painel
        run: python -m monitor.build_dashboard

      - name: Commitar mudancas
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/index.html
          [ -f data/ais_sightings.jsonl ] && git add data/ais_sightings.jsonl
          [ -f data/port_schedule.json ] && git add data/port_schedule.json
          git diff --cached --quiet || git commit -m "chore: atualiza dados de monitoramento"
          git push
```

- [ ] **Step 2: Commit e push**

```bash
cd C:\repos\my-gwm-ora-5
git add .github/workflows/monitor.yml
git commit -m "feat: workflow instala Playwright e roda o coletor portuario"
git push
```

- [ ] **Step 3: Disparar o workflow manualmente e verificar ponta a ponta**

Run: `cd C:\repos\my-gwm-ora-5 && gh workflow run monitor.yml`
Depois, poll `gh run list --workflow=monitor.yml --limit 1 --json
status,conclusion,databaseId --jq '.[0]'` até `status` virar `completed`
(a instalação do Chromium deixa essa execução mais lenta que as do v1 —
pode passar de 2 minutos).
Expected: `conclusion` = `success`. Se falhar, inspecionar
`gh run view <id> --log-failed` antes de tentar qualquer fix — não
adivinhar a causa.

- [ ] **Step 4: Confirmar o painel publicado**

Run: `curl -s "https://gustavoalikanwm.github.io/my-gwm-ora-5/?v2=1"`
Expected: a resposta contém `Car Carrier` e pelo menos um navio real da
Santos Brasil (não só a mensagem de "sem dados").

---

## Fora de escopo deste plano

- Outros portos/terminais além do TEV de Santos.
- Filtro por origem/procedência (endpoint não expõe esse dado).
