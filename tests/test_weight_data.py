import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from weight_data import parse_weight, read_series, store_weight, validate_csv


def write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "data.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_weight():
    assert parse_weight("109.8") == Decimal("109.8")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "Enter a valid weight"),
        ("", "Enter a valid weight"),
        ("hello", "Enter a valid weight"),
        ("NaN", "Weight must be between 30 and 300 kg"),
        ("29", "Weight must be between 30 and 300 kg"),
        ("301", "Weight must be between 30 and 300 kg"),
    ],
)
def test_parse_weight_rejects_invalid_values(value: str | None, message: str):
    with pytest.raises(ValueError, match=message):
        parse_weight(value)


def test_store_and_overwrite_weight(tmp_path: Path):
    path = tmp_path / "weight.csv"
    store_weight(path, date(2026, 7, 25), Decimal("109.4"))

    dates, weights = read_series(path)
    assert dates == [date(2026, 7, 25)]
    assert weights == [109.4]

    store_weight(path, date(2026, 7, 25), Decimal("109.5"))

    with path.open(newline="", encoding="utf-8") as csv_file:
        assert list(csv.reader(csv_file)) == [
            ["date", "weight_kg"],
            ["2026-07-25", "109.5"],
        ]


def test_validate_csv(tmp_path: Path):
    path = write_csv(
        tmp_path,
        "date,weight_kg\n2026-07-25,109.8\n2026-07-26,109.7\n",
    )
    assert validate_csv(path) == 2


def test_validate_csv_rejects_duplicate_or_unsorted_dates(tmp_path: Path):
    path = write_csv(
        tmp_path,
        "date,weight_kg\n2026-07-25,109.8\n2026-07-25,109.7\n",
    )
    with pytest.raises(ValueError, match="unique and increasing"):
        validate_csv(path)


def test_validate_csv_rejects_bad_header(tmp_path: Path):
    path = write_csv(tmp_path, "day,weight\n2026-07-25,109.8\n")
    with pytest.raises(ValueError, match="Expected header"):
        validate_csv(path)
