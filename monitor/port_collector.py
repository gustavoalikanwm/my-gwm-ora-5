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
    # A chamada com dataInicial preenchido so respondeu depois de uma
    # chamada de "aquecimento" com dataInicial vazio primeiro (observado ao
    # vivo: a mesma chamada direto deu 404, mas funcionou apos o warm-up).
    warmup_url = _build_api_url("")
    api_url = _build_api_url(date.today().isoformat())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(TEV_PAGE_URL)
        page.evaluate(
            """
            (url) => fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}})
                .then((r) => r.text())
            """,
            warmup_url,
        )
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
