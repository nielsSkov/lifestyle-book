import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app import parse_weight, period_bounds, read_series, shift_year, store_weight, within_period


def test_parse_weight():
    assert parse_weight("109.8") == Decimal("109.8")


@pytest.mark.parametrize("value", [None, "", "hello", "NaN", "29", "301"])
def test_parse_weight_rejects_invalid_values(value):
    with pytest.raises(ValueError):
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


def test_rolling_period():
    assert shift_year(date(2024, 2, 29), -1) == date(2023, 2, 28)
    today = date(2026, 7, 25)
    assert period_bounds("7d", 0, today=today) == (date(2026, 7, 19), today)
    assert period_bounds("4w", 0, today=today) == (date(2026, 6, 28), today)
    assert period_bounds("1y", 0, today=today) == (date(2025, 7, 25), today)
    assert period_bounds("all", 0, [date(2024, 5, 7), date(2026, 12, 31)], today) == (
        date(2024, 5, 7),
        date(2026, 12, 31),
    )

    dates, weights = within_period(
        [date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1)],
        [100.0, 101.0, 102.0],
        date(2025, 1, 1),
        date(2026, 1, 1),
    )
    assert dates == [date(2025, 1, 1), date(2026, 1, 1)]
    assert weights == [101.0, 102.0]
