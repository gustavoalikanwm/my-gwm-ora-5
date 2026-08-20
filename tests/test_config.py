from pathlib import Path

from monitor.config import load_config


def test_load_config_reads_target_eta_and_fleet(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "target_eta: \"2026-10-31\"\n"
        "fleet:\n"
        "  - name: \"NAVIO TESTE\"\n"
        "    mmsi: 123456789\n"
        "    imo: 9876543\n",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config["target_eta"] == "2026-10-31"
    assert config["fleet"] == [
        {"name": "NAVIO TESTE", "mmsi": 123456789, "imo": 9876543}
    ]
