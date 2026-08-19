# Monitor de navios porta-carros China → Brasil

Data: 2026-08-19
Status: aprovado para implementação

## Contexto e objetivo

O autor comprou um GWM ORA 05 (pré-reserva pague), com estimativa de entrega de
120 dias informada pela GWM em 03/07/2026 (~31/10/2026). O SAC da GWM não
fornece dados de rastreamento (sem número de booking, VIN, nome de navio ou
porto). Não é possível identificar o navio exato que carrega o veículo
específico do autor.

Objetivo do projeto: um painel gratuito, sem backend, que dê visibilidade
indireta sobre o fluxo de navios porta-carros (RoRo) saindo de portos da China
com destino a portos do Brasil — como sinal aproximado de "a onda que pode
incluir o meu carro está chegando" — combinando:

1. Posições AIS ao vivo de uma frota curada de navios RoRo conhecidos na rota
   China↔Brasil.
2. Programação pública de chegada de navios nos principais portos brasileiros
   que recebem RoRo da China, filtrada por carga tipo veículo/RoRo + origem
   China.

Não há tentativa de identificar o navio exato do veículo do autor — isso é
inviável sem dado de booking. O painel mostra sinal agregado da rota.

## Restrições

- **Zero custo.** Sem chaves de API pagas, sem servidor próprio, sem hospedagem
  paga.
- **Sem scraping de serviços que proíbem isso nos termos de uso**
  (MarineTraffic/VesselFinder ficam de fora). Fontes usadas:
  - [aisstream.io](https://aisstream.io) — API AIS gratuita via WebSocket, sem
    necessidade de antena/receptor próprio.
  - Páginas públicas de programação de navios de autoridades portuárias
    brasileiras (dado público oficial, não é serviço de terceiro com ToS
    restritivo).
  - [Equasis](https://www.equasis.org) — banco de dados marítimo público e
    gratuito, usado manualmente para consultar tipo de navio/IMO/MMSI ao
    montar a lista curada de frota.
- **Sem notificação push.** Só painel (o autor decidiu não usar
  Telegram/e-mail).
- **Repositório público** (`gustavoalikanwm/my-gwm-ora-5`) — decisão explícita
  do autor para viabilizar GitHub Pages grátis (Pages em repo privado exige
  GitHub Pro). O conteúdo publicado é só dado de navio/porto — nenhuma
  informação pessoal do autor.
- **Execução sempre inline** — sem uso de subagentes/Task tool. Todo o
  código e automação rodam como scripts diretos (GitHub Actions → Python),
  sem orquestração multi-agente.
- Navios RoRo que trazem carros da GWM não são exclusivos da marca — são
  compartilhados com outros fabricantes. A frota curada reflete "navios RoRo
  ativos na rota", não "navios da GWM".

## Arquitetura

```
GitHub Actions (cron, a cada 6h, + workflow_dispatch manual)
   │
   ├─► collectors/ais_collector.py
   │     conecta aisstream.io (API key em GitHub Secret AISSTREAM_API_KEY)
   │     assina só os MMSI da frota curada (config.yaml)
   │     escuta ~90s, captura PositionReport + ShipStaticData
   │     dedup por (mmsi, timestamp) → apenda em data/ais_sightings.jsonl
   │
   ├─► collectors/port_collector.py
   │     fetch das páginas públicas de programação (Itaguaí, Paranaguá, Suape)
   │     filtra linhas: carga contém veículo/RoRo E origem é porto chinês
   │     dedup por (porto, navio, eta) → apenda em data/port_schedule.jsonl
   │
   ├─► dashboard/build_dashboard.py
   │     lê os dois .jsonl + config.yaml
   │     gera docs/index.html (contagem regressiva, tabela de frota com
   │     última posição conhecida, tabela de navios anunciados nos portos BR,
   │     timestamp da última coleta, avisos de falha parcial)
   │
   └─► git commit + push (se algo mudou) → GitHub Pages redeploya
        automaticamente a partir de docs/
```

Sem backend, sem servidor de longa duração — o estado é o próprio repositório
Git (cada commit é um snapshot histórico dos arquivos `.jsonl`).

## Componentes

| Componente | Responsabilidade |
|---|---|
| `config.yaml` | Data estimada de chegada (31/10/2026); lista curada de frota RoRo (nome, MMSI, IMO); URLs das páginas de programação dos portos monitorados |
| `collectors/ais_collector.py` | Coleta de posição AIS via aisstream.io, filtrado pela frota curada |
| `collectors/port_collector.py` | Coleta da programação portuária pública, filtrada por carga RoRo/veículo + origem China |
| `dashboard/build_dashboard.py` | Gera `docs/index.html` a partir dos dados coletados |
| `.github/workflows/monitor.yml` | Cron + `workflow_dispatch`; roda os coletores, gera o painel, commita e faz push |
| `tests/` | Testes unitários dos parsers e do gerador de painel (ver seção Testes) |

A lista curada de frota é mantida manualmente, documentada no `README.md`
(processo: buscar navio por nome/IMO no Equasis, confirmar tipo "Vehicles
Carrier", adicionar MMSI ao `config.yaml`). Não há descoberta automática de
novos navios — está fora do escopo do v1.

## Fluxo de dados

1. Checkout do repositório.
2. `ais_collector.py`: conecta ao aisstream.io, assina os MMSI configurados,
   escuta ~90s, grava posições novas (dedup por `mmsi`+`timestamp`).
3. `port_collector.py`: para cada porto configurado, faz `GET` na página
   pública, parseia linhas, filtra por carga RoRo/veículo + origem China,
   grava entradas novas (dedup por `porto`+`navio`+`eta`).
4. `build_dashboard.py`: lê `config.yaml` + os dois `.jsonl`, calcula dias
   restantes até a data estimada, monta as tabelas de frota e de programação
   portuária, gera `docs/index.html`.
5. Se houve mudança em `data/*.jsonl` ou `docs/index.html`: `git commit` +
   `git push` usando o `GITHUB_TOKEN` padrão da Action.
6. GitHub Pages redeploya automaticamente a partir de `docs/`.

## Tratamento de erro

Princípio: falha parcial não derruba a execução nem perde dado já coletado.

| Falha | Comportamento |
|---|---|
| aisstream.io indisponível / timeout na conexão | Loga aviso, segue sem novas posições nesta rodada; painel mostra "última posição conhecida: X (há N dias)" |
| Página de um porto muda de layout / fica indisponível | Erro isolado por porto (`try`/`except` individual); os outros portos continuam sendo coletados; painel mostra aviso "⚠️ Suape: falha na coleta às HH:MM" |
| Nenhum navio da frota é avistado por muitos dias | Não é erro — é esperado em travessia oceânica sem estação AIS terrestre próxima; painel deixa isso explícito |
| Workflow falha antes do commit | `git commit`/`push` não roda nessa execução; nenhum dado é perdido (os `.jsonl` só existem em memória/working tree até o commit); próximo cron tenta de novo |

## Testes

| O quê | Como |
|---|---|
| Parser da programação portuária | Testes unitários com fixture de HTML salvo localmente (sem rede); trava o parser contra o formato atual da página |
| Filtro de carga (RoRo/veículo + origem China) | Casos de tabela: linha que deve casar, linha que não deve (contêiner comum, origem diferente) |
| Parsing de mensagens AIS (`ShipStaticData`/`PositionReport`) | Testes unitários com mensagens JSON de exemplo gravadas; lógica de parsing separada da lógica de conexão websocket |
| Geração do painel | Dado `config.yaml` + `.jsonl` fixos, checa que o HTML gerado contém os elementos esperados |
| Ponta a ponta | `workflow_dispatch` manual + inspeção do log da Action e do Pages publicado — smoke test manual, não automatizado |

Sem teste automatizado contra rede real de terceiros (aisstream.io, páginas
dos portos) — ficaria frágil. A defesa contra mudança de layout é o fixture de
HTML congelado, que quebra localmente antes de virar problema em produção.

## Fora de escopo (v1)

- Identificar o navio exato do veículo do autor (inviável sem dado de
  booking).
- Descoberta automática de novos navios RoRo na rota (a frota é curada
  manualmente).
- Notificações push (Telegram/e-mail) — só painel.
- Hospedagem paga ou API AIS paga.
