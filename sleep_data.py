import csv
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

CSV_HEADER = ["night_start_date", "sleep_at", "wake_at"]
DAILY_CSV_HEADER = ["date", "wake_time", "sleep_time"]
LEGACY_CSV_HEADER = ["wake_date", "sleep_time", "wake_time"]
NEXT_DAY_SLEEP_CUTOFF = 12


@dataclass(frozen=True)
class SleepRecord:
    night_start_date: date
    sleep_at: datetime | None = None
    wake_at: datetime | None = None


def parse_night_start_date(raw_value: str | None, latest_night_start: date) -> date:
    if not raw_value:
        raise ValueError("Choose a valid night")
    try:
        night_start_date = date.fromisoformat(raw_value)
    except ValueError:
        raise ValueError("Choose a valid night") from None
    if night_start_date > latest_night_start:
        raise ValueError("Night cannot start in the future")
    return night_start_date


def parse_sleep_times(
    raw_wake_time: str | None,
    raw_sleep_time: str | None,
) -> tuple[time | None, time | None]:
    wake_time = _parse_optional_time(raw_wake_time)
    sleep_time = _parse_optional_time(raw_sleep_time)
    if wake_time is None and sleep_time is None:
        raise ValueError("Enter a wake time or sleep time")
    return wake_time, sleep_time


def build_sleep_record(
    night_start_date: date,
    wake_time: time | None,
    sleep_time: time | None,
) -> SleepRecord:
    sleep_at = None
    if sleep_time is not None:
        sleep_date = night_start_date
        if sleep_time.hour < NEXT_DAY_SLEEP_CUTOFF:
            sleep_date += timedelta(days=1)
        sleep_at = datetime.combine(sleep_date, sleep_time)

    wake_at = None
    if wake_time is not None:
        wake_at = datetime.combine(night_start_date + timedelta(days=1), wake_time)

    record = SleepRecord(night_start_date, sleep_at, wake_at)
    _validate_record(record)
    return record


def read_sleep_records(path: Path) -> list[SleepRecord]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames == CSV_HEADER:
            return _read_night_records(reader)
        if reader.fieldnames == DAILY_CSV_HEADER:
            return _migrate_daily_records(reader, "date")
        if reader.fieldnames == LEGACY_CSV_HEADER:
            return _migrate_daily_records(reader, "wake_date")
        raise ValueError("Expected header: night_start_date,sleep_at,wake_at")


def migrate_sleep_file(path: Path) -> int:
    records = read_sleep_records(path)
    if path.exists():
        _replace_sleep_records(path, records)
    return len(records)


def store_sleep(path: Path, record: SleepRecord) -> None:
    _validate_record(record)
    records_by_date = {existing.night_start_date: existing for existing in read_sleep_records(path)}
    records_by_date[record.night_start_date] = record
    _replace_sleep_records(path, [records_by_date[day] for day in sorted(records_by_date)])


def delete_sleep(path: Path, night_start_date: date) -> bool:
    records = read_sleep_records(path)
    remaining = [record for record in records if record.night_start_date != night_start_date]
    if len(remaining) == len(records):
        return False
    _replace_sleep_records(path, remaining)
    return True


def _read_night_records(reader: csv.DictReader) -> list[SleepRecord]:
    records = []
    previous_date = None
    for row in reader:
        night_start_date = date.fromisoformat(row["night_start_date"])
        if previous_date is not None and night_start_date <= previous_date:
            raise ValueError("Sleep record dates must be unique and increasing")
        record = SleepRecord(
            night_start_date,
            _parse_optional_datetime(row["sleep_at"]),
            _parse_optional_datetime(row["wake_at"]),
        )
        _validate_record(record)
        records.append(record)
        previous_date = night_start_date
    return records


def _migrate_daily_records(reader: csv.DictReader, date_column: str) -> list[SleepRecord]:
    records_by_date: dict[date, SleepRecord] = {}
    for row in reader:
        event_date = date.fromisoformat(row[date_column])
        wake_time = _parse_optional_time(row["wake_time"])
        sleep_time = _parse_optional_time(row["sleep_time"])
        if wake_time is not None:
            night_start = event_date - timedelta(days=1)
            existing = records_by_date.get(night_start, SleepRecord(night_start))
            records_by_date[night_start] = SleepRecord(
                night_start,
                existing.sleep_at,
                datetime.combine(event_date, wake_time),
            )
        if sleep_time is not None:
            night_start = event_date
            if sleep_time.hour < NEXT_DAY_SLEEP_CUTOFF:
                night_start -= timedelta(days=1)
            existing = records_by_date.get(night_start, SleepRecord(night_start))
            records_by_date[night_start] = SleepRecord(
                night_start,
                datetime.combine(event_date, sleep_time),
                existing.wake_at,
            )

    records = [records_by_date[day] for day in sorted(records_by_date)]
    for record in records:
        _validate_record(record)
    return records


def _validate_record(record: SleepRecord) -> None:
    if record.sleep_at is None and record.wake_at is None:
        raise ValueError("A sleep record needs a sleep time or wake time")
    if record.sleep_at is not None and record.wake_at is not None:
        if record.wake_at <= record.sleep_at:
            raise ValueError("Wake time must be later than sleep time")


def _parse_optional_time(raw_value: str | None) -> time | None:
    if raw_value is None or not raw_value.strip():
        return None
    try:
        return datetime.strptime(raw_value, "%H:%M").time()
    except ValueError:
        raise ValueError("Enter valid wake and sleep times") from None


def _parse_optional_datetime(raw_value: str | None) -> datetime | None:
    if raw_value is None or not raw_value.strip():
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        raise ValueError("Sleep records contain an invalid datetime") from None


def _replace_sleep_records(path: Path, records: list[SleepRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(
                (
                    record.night_start_date.isoformat(),
                    _format_datetime(record.sleep_at),
                    _format_datetime(record.wake_at),
                )
                for record in records
            )
            csv_file.flush()
            os.fsync(csv_file.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _format_datetime(value: datetime | None) -> str:
    return "" if value is None else value.isoformat(timespec="minutes")
