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
