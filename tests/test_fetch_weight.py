import stat
from pathlib import Path

import pytest

from fetch_weight import install_download
from server_sync import file_checksum

VALID_CSV = "date,weight_kg\n2026-07-25,109.8\n2026-07-26,109.7\n"


def test_install_download_validates_and_replaces_atomically(tmp_path: Path):
    destination = tmp_path / "weight.csv"
    destination.write_text("existing data\n", encoding="utf-8")
    download = tmp_path / ".weight.csv.download"
    download.write_text(VALID_CSV, encoding="utf-8")

    row_count = install_download(download, destination, file_checksum(download))

    assert row_count == 2
    assert destination.read_text(encoding="utf-8") == VALID_CSV
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not download.exists()


def test_install_download_preserves_existing_file_on_checksum_failure(tmp_path: Path):
    destination = tmp_path / "weight.csv"
    destination.write_text("existing data\n", encoding="utf-8")
    download = tmp_path / ".weight.csv.download"
    download.write_text(VALID_CSV, encoding="utf-8")

    with pytest.raises(RuntimeError, match="does not match"):
        install_download(download, destination, "incorrect")

    assert destination.read_text(encoding="utf-8") == "existing data\n"


def test_install_download_preserves_existing_file_on_validation_failure(tmp_path: Path):
    destination = tmp_path / "weight.csv"
    destination.write_text("existing data\n", encoding="utf-8")
    download = tmp_path / ".weight.csv.download"
    download.write_text("invalid,data\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected header"):
        install_download(download, destination, file_checksum(download))

    assert destination.read_text(encoding="utf-8") == "existing data\n"
