import stat
from datetime import date, datetime, time
from pathlib import Path

import pytest

from sleep_data import (
    SleepRecord,
    build_sleep_record,
    delete_sleep,
    parse_night_start_date,
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
    ("wake_value", "sleep_value"),
    [("", ""), ("invalid", "23:00"), ("07:00", "invalid")],
)
def test_parse_sleep_times_rejects_empty_or_invalid_records(wake_value, sleep_value):
    with pytest.raises(ValueError):  # noqa: PT011 - each input must simply be rejected
        parse_sleep_times(wake_value, sleep_value)


def test_parse_night_start_date_rejects_future_dates():
    with pytest.raises(ValueError, match="future"):
        parse_night_start_date("2026-08-04", date(2026, 8, 3))


def test_build_sleep_record_resolves_dates_within_the_selected_night():
    assert build_sleep_record(date(2026, 8, 4), time(6), time(1)) == SleepRecord(
        date(2026, 8, 4),
        sleep_at=datetime(2026, 8, 5, 1),
        wake_at=datetime(2026, 8, 5, 6),
    )
    assert build_sleep_record(date(2026, 8, 5), time(6), time(22)) == SleepRecord(
        date(2026, 8, 5),
        sleep_at=datetime(2026, 8, 5, 22),
        wake_at=datetime(2026, 8, 6, 6),
    )


def test_build_sleep_record_rejects_waking_before_sleeping():
    with pytest.raises(ValueError, match="later"):
        build_sleep_record(date(2026, 8, 4), time(6), time(11))


def test_store_sleep_sorts_replaces_and_protects_partial_records(tmp_path: Path):
    path = tmp_path / "data" / "sleep.csv"
    store_sleep(
        path,
        SleepRecord(date(2026, 8, 3), wake_at=datetime(2026, 8, 4, 7, 15)),
    )
    store_sleep(
        path,
        SleepRecord(date(2026, 8, 1), sleep_at=datetime(2026, 8, 1, 23, 30)),
    )
    replacement = SleepRecord(
        date(2026, 8, 3),
        sleep_at=datetime(2026, 8, 3, 23),
        wake_at=datetime(2026, 8, 4, 7),
    )
    store_sleep(path, replacement)

    assert read_sleep_records(path) == [
        SleepRecord(date(2026, 8, 1), sleep_at=datetime(2026, 8, 1, 23, 30)),
        replacement,
    ]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_delete_sleep_removes_only_the_selected_night(tmp_path: Path):
    path = tmp_path / "sleep.csv"
    first = SleepRecord(date(2026, 8, 1), wake_at=datetime(2026, 8, 2, 7))
    second = SleepRecord(date(2026, 8, 2), sleep_at=datetime(2026, 8, 2, 23))
    store_sleep(path, first)
    store_sleep(path, second)

    assert delete_sleep(path, first.night_start_date) is True
    assert delete_sleep(path, date(2026, 7, 31)) is False
    assert read_sleep_records(path) == [second]


def test_read_sleep_records_rejects_an_incompatible_schema(tmp_path: Path):
    path = tmp_path / "sleep.csv"
    path.write_text("date,bedtime,wakeup\n2026-08-01,23:00,07:00\n", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        read_sleep_records(path)
