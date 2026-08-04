import stat
from datetime import date, time
from pathlib import Path

import pytest

from sleep_data import (
    SleepRecord,
    delete_sleep,
    parse_sleep_times,
    parse_wake_date,
    read_sleep_records,
    sleep_duration_minutes,
    store_sleep,
)


def test_sleep_duration_supports_overnight_and_after_midnight_bedtimes():
    assert sleep_duration_minutes(time(23, 30), time(7, 15)) == 465
    assert sleep_duration_minutes(time(1), time(8)) == 420


@pytest.mark.parametrize(
    ("sleep_value", "wake_value", "error_category"),
    [
        (None, "07:00", "both"),
        ("23:00", None, "both"),
        ("invalid", "07:00", "valid"),
        ("07:00", "07:00", "different"),
    ],
)
def test_parse_sleep_times_rejects_incomplete_or_invalid_records(
    sleep_value,
    wake_value,
    error_category,
):
    with pytest.raises(ValueError, match=error_category):
        parse_sleep_times(sleep_value, wake_value)


def test_parse_wake_date_rejects_future_dates():
    with pytest.raises(ValueError, match="future"):
        parse_wake_date("2026-08-04", date(2026, 8, 3))


def test_store_sleep_sorts_replaces_and_protects_file(tmp_path: Path):
    path = tmp_path / "data" / "sleep.csv"
    store_sleep(path, SleepRecord(date(2026, 8, 3), time(23, 30), time(7, 15)))
    store_sleep(path, SleepRecord(date(2026, 8, 1), time(0, 15), time(8)))
    store_sleep(path, SleepRecord(date(2026, 8, 3), time(23), time(7)))

    assert read_sleep_records(path) == [
        SleepRecord(date(2026, 8, 1), time(0, 15), time(8)),
        SleepRecord(date(2026, 8, 3), time(23), time(7)),
    ]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_delete_sleep_removes_only_the_selected_date(tmp_path: Path):
    path = tmp_path / "sleep.csv"
    first = SleepRecord(date(2026, 8, 1), time(23), time(7))
    second = SleepRecord(date(2026, 8, 2), time(0), time(8))
    store_sleep(path, first)
    store_sleep(path, second)

    assert delete_sleep(path, first.wake_date) is True
    assert delete_sleep(path, date(2026, 7, 31)) is False
    assert read_sleep_records(path) == [second]


def test_read_sleep_records_rejects_an_incompatible_schema(tmp_path: Path):
    path = tmp_path / "sleep.csv"
    path.write_text("date,bedtime,wakeup\n2026-08-01,23:00,07:00\n", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        read_sleep_records(path)
