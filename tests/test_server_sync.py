from pathlib import Path

import pytest

from server_sync import file_checksum, load_server_config


def test_load_server_config(tmp_path: Path):
    config = tmp_path / "server.json"
    config.write_text(
        '{"target": "user@example", "directory": "/srv/lifestyle-book/"}',
        encoding="utf-8",
    )

    assert load_server_config(config) == ("user@example", "/srv/lifestyle-book")


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "{}",
        '{"target": "", "directory": "/srv/lifestyle-book"}',
        '{"target": "user@example", "directory": ""}',
        '{"target": 42, "directory": "/srv/lifestyle-book"}',
        '{"target": "user@example", "directory": 42}',
    ],
)
def test_load_server_config_rejects_invalid_config(tmp_path: Path, content: str):
    config = tmp_path / "server.json"
    config.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="server config|Server config"):
        load_server_config(config)


def test_file_checksum(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_bytes(b"weight data\n")

    assert file_checksum(path) == "df1d046d1ec27e72ca30a0d5e78b393be0818423858dcad155ccf43732ed7457"
