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
