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
