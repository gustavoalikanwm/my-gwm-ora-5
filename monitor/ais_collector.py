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
