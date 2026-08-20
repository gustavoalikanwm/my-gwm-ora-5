# my-gwm-ora-5

Monitor gratuito de navios porta-carros (RoRo) na rota China -> Brasil,
como sinal indireto da chegada de um GWM ORA 05 comprado em pre-reserva
(sem dado de booking/VIN/navio fornecido pela GWM - rastreamento do navio
exato nao e possivel, ver `docs/superpowers/specs/`).

Painel publicado via GitHub Pages a partir de `docs/index.html`, atualizado
a cada 6h por um workflow do GitHub Actions. Cada navio da frota curada tem
um link direto para a pagina publica dele no VesselFinder (atalho de
consulta manual, sem raspagem).

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
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows
python -m pytest -v
AISSTREAM_API_KEY=... python -m monitor.ais_collector
python -m monitor.build_dashboard
```

## Escopo

Este e o v1 (so pipeline AIS). Coleta de programacao portuaria brasileira
(v2) esta fora de escopo - ver nota de fasamento na spec.
