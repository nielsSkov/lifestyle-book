import stat
from datetime import date, time
from pathlib import Path

import pytest

from sleep_data import (
    SleepRecord,
    delete_sleep,
    parse_sleep_date,
    parse_sleep_times,
    read_sleep_records,
    store_sleep,
)


@pytest.mark.parametrize(
    ("wake_value", "sleep_value", "expected"),
    [
        ("07:15", "", (time(7, 15), None)),
        ("", "23:30", (None, time(23, 30))),
        ("07:15", "23:30", (time(7, 15), time(23, 30))),
    ],
)
def test_parse_sleep_times_supports_independent_entries(wake_value, sleep_value, expected):
    assert parse_sleep_times(wake_value, sleep_value) == expected


@pytest.mark.parametrize(
    ("wake_value", "sleep_value", "error_category"),
    [
        ("", "", "wake time or sleep time"),
        ("invalid", "23:00", "valid"),
        ("07:00", "invalid", "valid"),
    ],
)
def test_parse_sleep_times_rejects_empty_or_invalid_records(
    wake_value,
    sleep_value,
    error_category,
):
    with pytest.raises(ValueError, match=error_category):
        parse_sleep_times(wake_value, sleep_value)


def test_parse_sleep_date_rejects_future_dates():
    with pytest.raises(ValueError, match="future"):
        parse_sleep_date("2026-08-04", date(2026, 8, 3))


def test_store_sleep_sorts_replaces_and_protects_partial_records(tmp_path: Path):
    path = tmp_path / "data" / "sleep.csv"
    store_sleep(path, SleepRecord(date(2026, 8, 3), wake_time=time(7, 15)))
    store_sleep(path, SleepRecord(date(2026, 8, 1), sleep_time=time(23, 30)))
    store_sleep(
        path,
        SleepRecord(date(2026, 8, 3), wake_time=time(7), sleep_time=time(23)),
    )

    assert read_sleep_records(path) == [
        SleepRecord(date(2026, 8, 1), sleep_time=time(23, 30)),
        SleepRecord(date(2026, 8, 3), wake_time=time(7), sleep_time=time(23)),
    ]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_delete_sleep_removes_only_the_selected_date(tmp_path: Path):
    path = tmp_path / "sleep.csv"
    first = SleepRecord(date(2026, 8, 1), wake_time=time(7))
    second = SleepRecord(date(2026, 8, 2), sleep_time=time(23))
    store_sleep(path, first)
    store_sleep(path, second)

    assert delete_sleep(path, first.date) is True
    assert delete_sleep(path, date(2026, 7, 31)) is False
    assert read_sleep_records(path) == [second]


def test_read_sleep_records_migrates_legacy_nights_into_daily_events(tmp_path: Path):
    path = tmp_path / "sleep.csv"
    path.write_text(
        "wake_date,sleep_time,wake_time\n2026-08-02,23:30,07:15\n",
        encoding="utf-8",
    )

    assert read_sleep_records(path) == [
        SleepRecord(date(2026, 8, 1), sleep_time=time(23, 30)),
        SleepRecord(date(2026, 8, 2), wake_time=time(7, 15)),
    ]


def test_read_sleep_records_rejects_an_incompatible_schema(tmp_path: Path):
    path = tmp_path / "sleep.csv"
    path.write_text("date,bedtime,wakeup\n2026-08-01,23:00,07:00\n", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        read_sleep_records(path)
