import stat
from datetime import date
from pathlib import Path

import pytest

from daily_data import DailyRecord, parse_daily_date, read_daily_records, store_daily_record


def test_parse_daily_date_rejects_future_dates():
    with pytest.raises(ValueError, match="future"):
        parse_daily_date("2026-08-04", date(2026, 8, 3))


def test_store_daily_record_creates_sorted_private_wide_csv(tmp_path: Path):
    path = tmp_path / "data" / "daily.csv"
    keys = ["walk", "run", "cycling"]
    store_daily_record(path, date(2026, 8, 3), {"cycling"}, keys)
    store_daily_record(path, date(2026, 8, 1), {"walk", "run"}, keys)

    assert path.read_text(encoding="utf-8") == (
        "date,walk,run,cycling\n2026-08-01,1,1,\n2026-08-03,,,1\n"
    )
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert read_daily_records(path) == [
        DailyRecord(date(2026, 8, 1), frozenset({"walk", "run"})),
        DailyRecord(date(2026, 8, 3), frozenset({"cycling"})),
    ]


def test_archiving_category_preserves_its_column_and_historical_value(tmp_path: Path):
    path = tmp_path / "daily.csv"
    day = date(2026, 8, 1)
    store_daily_record(path, day, {"walk", "cycling"}, ["walk", "cycling"])

    store_daily_record(path, day, set(), ["walk"])

    assert read_daily_records(path) == [DailyRecord(day, frozenset({"cycling"}))]
    assert path.read_text(encoding="utf-8") == "date,walk,cycling\n2026-08-01,,1\n"


def test_new_category_appends_column_without_changing_old_records(tmp_path: Path):
    path = tmp_path / "daily.csv"
    store_daily_record(path, date(2026, 8, 1), {"walk"}, ["walk"])

    store_daily_record(path, date(2026, 8, 2), {"run"}, ["walk", "run"])

    assert path.read_text(encoding="utf-8") == ("date,walk,run\n2026-08-01,1,\n2026-08-02,,1\n")


def test_clearing_all_active_values_removes_empty_record(tmp_path: Path):
    path = tmp_path / "daily.csv"
    day = date(2026, 8, 1)
    store_daily_record(path, day, {"walk"}, ["walk", "run"])

    store_daily_record(path, day, set(), ["walk", "run"])

    assert read_daily_records(path) == []
    assert path.read_text(encoding="utf-8") == "date,walk,run\n"


@pytest.mark.parametrize(
    "content",
    [
        "activity,walk\n2026-08-01,1\n",
        "date,walk\n2026-08-01,yes\n",
        "date,walk\n2026-08-01,\n",
        "date,walk\n2026-08-02,1\n2026-08-01,1\n",
    ],
)
def test_read_daily_records_rejects_invalid_files(tmp_path: Path, content: str):
    path = tmp_path / "daily.csv"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):  # noqa: PT011 - each malformed file must be rejected
        read_daily_records(path)
