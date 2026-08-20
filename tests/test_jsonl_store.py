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
