# Monitor de navios — v2: programação portuária (Porto de Santos, TEV)

Data: 2026-08-20
Status: aprovado para implementação

## Contexto

O v1 (`2026-08-19-monitor-navios-design.md`) entregou o pipeline AIS. Este
documento cobre o v2: coleta da programação de navios do **Terminal de
Veículos (TEV) do Porto de Santos**, adiada no v1 porque as páginas de
programação portuária pesquisadas inicialmente pareciam JS-heavy demais
para raspar sem Playwright.

## Descoberta que viabiliza o v2

Investigação ao vivo (2026-08-20) achou um endpoint JSON público por trás
da página de atracação da Santos Brasil:

```
GET https://santosbrasil.com.br/v2021/lista-de-atracacao/pesquisa
    ?unidade=tecon-santos&lista=lista-de-atracacao&atracadouro=TEV
    &pesquisa=&dataInicial=&dataFinal=&statusNavio=
```

Retorna JSON estruturado (campo `VAtracacao`, lista de escalas) já com o
navio, armador e uma tag própria do porto **`SERVICO`/`JOINT` = "CAR Car
Carrier - TEV"** — o porto já classifica o tipo de navio, não precisamos
inferir isso via lista curada. Não há campo de origem/procedência: o sinal
usado é "é Car Carrier no Terminal de Veículos", não "vem da China".

**Mas**: o endpoint (e a própria página) retorna 404 pra requisição HTTP
simples (`curl`/`requests`, mesmo com headers de navegador copiados) —
bloqueio anti-bot por fingerprint (provavelmente TLS/JA3), não por
cookie/sessão. Testado e confirmado: funciona normal num navegador real
(via Playwright), falha em HTTP puro. Por isso o v2 usa **Playwright**
(Chromium headless, ainda gratuito) em vez de `requests`.

O JSON retornado cobre um histórico completo (não só futuro — a amostra
capturada tinha entradas de 2022 a 2026); o filtro por "só escalas
futuras" é responsabilidade da camada de renderização, não da coleta.

## Arquitetura

```
GitHub Actions (mesmo cron do v1, a cada 6h)
   │
   ├─► monitor/ais_collector.py        (v1, inalterado)
   │
   ├─► monitor/port_collector.py       (novo)
   │     abre Chromium via Playwright
   │     visita a pagina do TEV (estabelece fingerprint real de navegador)
   │     chama o endpoint JSON via fetch() dentro da própria página
   │     sobrescreve data/port_schedule.json (SNAPSHOT, não log append)
   │
   ├─► monitor/build_dashboard.py      (modificado)
   │     lê data/port_schedule.json (se existir) alem do que já lia
   │     passa pro render_dashboard
   │
   └─► git commit + push (data/port_schedule.json condicional, como o
        data/ais_sightings.jsonl do v1)
```

`data/port_schedule.json` é um **snapshot** (sobrescrito a cada execução),
diferente de `data/ais_sightings.jsonl` (log append-only) — programação
portuária é "estado atual conhecido", não uma série histórica que faça
sentido acumular indefinidamente.

## Componentes

| Componente | Responsabilidade |
|---|---|
| `monitor/port_parser.py` | Funções puras: converte data .NET (`/Date(ms)/`) pra ISO UTC; extrai `id`/`navio`/`armador`/`eta_utc`/`tipo_operacao`/`servico` de cada escala; filtra só `SRV == "CAR"` (dupla checagem, mesmo já filtrando `atracadouro=TEV` na query) |
| `monitor/port_collector.py` | Camada de rede (Playwright) — sem teste automatizado, mesmo padrão do `ais_collector.py` no v1 |
| `monitor/dashboard_render.py` | Ganha uma segunda tabela: escalas futuras de Car Carrier no TEV, com coluna indicando se o nome do navio bate com algum item da frota curada (`config.yaml`) |
| `monitor/build_dashboard.py` | Lê `data/port_schedule.json` (lista vazia se o arquivo não existir) |
| `.github/workflows/monitor.yml` | Instala Playwright + Chromium (`playwright install --with-deps chromium`), roda o novo coletor, inclui `data/port_schedule.json` no commit condicional |

## Fluxo de dados

1. `port_collector.py`: Playwright abre Chromium, navega pra
   `https://santosbrasil.com.br/v2021/lista-de-atracacao?...&atracadouro=TEV`,
   depois executa `fetch()` do endpoint `/pesquisa` dentro da página (herda
   o contexto/fingerprint do navegador real).
2. Resposta JSON é parseada por `port_parser.process_port_response()`.
3. `data/port_schedule.json` é **sobrescrito** com o snapshot atual
   (lista de dicts já normalizados).
4. `build_dashboard.py` lê esse arquivo (ou `[]` se não existir/vazio),
   filtra escalas com `eta_utc` no futuro (`>= now`), ordena por ETA, e
   passa pro `render_dashboard`.
5. `render_dashboard` desenha a segunda tabela, marcando com destaque
   qualquer `navio` que bata (case-insensitive, nome exato) com algum item
   de `config["fleet"]`.

## Tratamento de erro

Mesmo princípio do v1 — falha parcial não derruba a execução:

| Falha | Comportamento |
|---|---|
| Playwright/Chromium falha ao instalar ou navegar (site fora, bloqueio mudou) | `port_collector.py` loga aviso e sai sem sobrescrever `data/port_schedule.json` — painel continua mostrando o último snapshot válido conhecido |
| Endpoint muda de formato (campo renomeado, `SRV` some) | `parse_port_entry` deixando de achar uma chave esperada lança `KeyError` — isso propaga e o coletor loga e sai (mesmo padrão acima); não há tentativa de "adivinhar" um novo formato |
| `data/port_schedule.json` nunca foi gerado (primeira execução, ou toda vez que falhou) | Painel mostra "sem dados de programação portuária coletados ainda" — não é erro |

## Testes

| O quê | Como |
|---|---|
| `parse_dotnet_date` | Casos: timestamp válido, `None`, string vazia |
| `parse_port_entry` / `process_port_response` | Fixture `tests/fixtures/port_schedule_sample.json` — **dado real**, capturado ao vivo do endpoint da Santos Brasil em 2026-08-20 (100 escalas reais, de 2022 a 2026), não inventado |
| Filtro `SRV == "CAR"` | A fixture real já é 100% Car Carrier (TEV só recebe esse tipo), então o teste de filtro usa um caso sintético adicional (uma linha com `SRV` diferente) pra provar que o filtro de fato exclui |
| `dashboard_render` — segunda tabela + cross-reference com frota | Testes unitários com config/port_schedule fixos, sem rede |
| `port_collector.py` (Playwright) | Sem teste automatizado (rede + navegador real de terceiro) — verificação é manual via `workflow_dispatch`, mesmo padrão do `ais_collector.py` |

## Fora de escopo (v2)

- Outros portos/terminais além do TEV de Santos — se a Santos Brasil
  cobrir bem o volume de veículos relevante, não há necessidade imediata
  de mais fontes (YAGNI); adicionar outro porto é um v3 se necessário.
- Filtro por origem/procedência — o endpoint não expõe esse dado.
- Autenticação/login — o endpoint é público, só bloqueado por
  fingerprint, não por credencial.
