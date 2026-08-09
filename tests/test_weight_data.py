import csv
import math
import stat
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from weight_data import (
    delete_weight,
    parse_measurement_date,
    parse_weight,
    read_series,
    store_series,
    store_weight,
    validate_csv,
)


def write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "data.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_weight():
    assert parse_weight("109.8") == Decimal("109.8")
    assert parse_weight("109,8") == Decimal("109.8")
    assert parse_weight("0") == Decimal("0")
    assert parse_weight("700") == Decimal("700")


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "hello",
        "NaN",
        "Infinity",
        "-0.1",
        "701",
    ],
)
def test_parse_weight_rejects_invalid_values(value: str | None):
    with pytest.raises(ValueError, match="valid weight|between 0 and 700"):
        parse_weight(value)


def test_parse_measurement_date():
    today = date(2026, 8, 3)

    assert parse_measurement_date("2026-07-25", today) == date(2026, 7, 25)
    assert parse_measurement_date("2026-08-03", today) == today


@pytest.mark.parametrize("value", [None, "", "not-a-date"])
def test_parse_measurement_date_rejects_invalid_values(value: str | None):
    with pytest.raises(ValueError, match="valid measurement date"):
        parse_measurement_date(value, date(2026, 8, 3))


def test_parse_measurement_date_rejects_future_dates():
    with pytest.raises(ValueError, match="future"):
        parse_measurement_date("2026-08-04", date(2026, 8, 3))


def test_store_and_overwrite_weight(tmp_path: Path):
    path = tmp_path / "weight.csv"
    store_weight(path, date(2026, 7, 25), Decimal("109.4"))

    dates, weights = read_series(path)
    assert dates == [date(2026, 7, 25)]
    assert weights == [109.4]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    store_weight(path, date(2026, 7, 25), Decimal("109.5"))

    with path.open(newline="", encoding="utf-8") as csv_file:
        assert list(csv.reader(csv_file)) == [
            ["date", "weight_kg"],
            ["2026-07-25", "109.5"],
        ]


def test_store_weight_inserts_historical_measurement_without_filling_gaps(tmp_path: Path):
    path = write_csv(
        tmp_path,
        "date,weight_kg\n2026-07-25,109.8\n2026-07-29,109.4\n",
    )

    store_weight(path, date(2026, 7, 27), Decimal("109.6"))

    assert path.read_text(encoding="utf-8") == (
        "date,weight_kg\n2026-07-25,109.8\n2026-07-27,109.6\n2026-07-29,109.4\n"
    )


def test_delete_weight_removes_only_selected_measurement(tmp_path: Path):
    path = write_csv(
        tmp_path,
        "date,weight_kg\n2026-07-25,109.8\n2026-07-27,109.6\n2026-07-29,109.4\n",
    )

    assert delete_weight(path, date(2026, 7, 27)) is True
    assert delete_weight(path, date(2026, 7, 26)) is False
    assert path.read_text(encoding="utf-8") == (
        "date,weight_kg\n2026-07-25,109.8\n2026-07-29,109.4\n"
    )


def test_delete_weight_can_remove_last_measurement(tmp_path: Path):
    path = write_csv(tmp_path, "date,weight_kg\n2026-07-25,109.8\n")

    assert delete_weight(path, date(2026, 7, 25)) is True
    assert path.read_text(encoding="utf-8") == "date,weight_kg\n"


def test_validate_csv(tmp_path: Path):
    path = write_csv(
        tmp_path,
        "date,weight_kg\n2026-07-25,109.8\n2026-07-26,109.7\n",
    )
    assert validate_csv(path) == 2


@pytest.mark.parametrize(
    "rows",
    [
        "2026-07-25,109.8\n2026-07-25,109.7\n",
        "2026-07-26,109.8\n2026-07-25,109.7\n",
    ],
)
def test_validate_csv_rejects_duplicate_or_unsorted_dates(tmp_path: Path, rows: str):
    path = write_csv(tmp_path, f"date,weight_kg\n{rows}")
    with pytest.raises(ValueError, match="unique and increasing"):
        validate_csv(path)


def test_validate_csv_rejects_bad_header(tmp_path: Path):
    path = write_csv(tmp_path, "day,weight\n2026-07-25,109.8\n")
    with pytest.raises(ValueError, match="header"):
        validate_csv(path)


def test_validate_csv_allows_explicit_plan_gaps(tmp_path: Path):
    path = write_csv(tmp_path, "date,weight_kg\n2026-07-25,100.0\n2026-07-26,NaN\n")

    assert validate_csv(path, allow_gaps=True) == 2
    with pytest.raises(ValueError, match="between 0 and 700"):
        validate_csv(path)


def test_store_series_writes_valid_private_plan_with_gaps(tmp_path: Path):
    path = tmp_path / "plan.csv"

    row_count = store_series(
        path,
        [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)],
        [100.0, math.nan, 95.0],
        allow_gaps=True,
    )

    assert row_count == 3
    assert path.read_text(encoding="utf-8") == (
        "date,weight_kg\n2026-08-01,100\n2026-08-02,NaN\n2026-08-03,95\n"
    )
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_store_series_rejects_mismatched_dates_and_weights(tmp_path: Path):
    with pytest.raises(ValueError):  # noqa: PT011 - only rejection is part of this contract
        store_series(tmp_path / "plan.csv", [date(2026, 8, 1)], [])
