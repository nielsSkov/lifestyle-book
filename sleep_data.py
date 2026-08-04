import csv
import os
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

CSV_HEADER = ["date", "wake_time", "sleep_time"]
LEGACY_CSV_HEADER = ["wake_date", "sleep_time", "wake_time"]


@dataclass(frozen=True)
class SleepRecord:
    date: date
    wake_time: time | None = None
    sleep_time: time | None = None


def parse_sleep_date(raw_value: str | None, today: date) -> date:
    if not raw_value:
        raise ValueError("Choose a valid date")
    try:
        record_date = date.fromisoformat(raw_value)
    except ValueError:
        raise ValueError("Choose a valid date") from None
    if record_date > today:
        raise ValueError("Date cannot be in the future")
    return record_date


def parse_sleep_times(
    raw_wake_time: str | None,
    raw_sleep_time: str | None,
) -> tuple[time | None, time | None]:
    wake_time = _parse_optional_time(raw_wake_time)
    sleep_time = _parse_optional_time(raw_sleep_time)
    if wake_time is None and sleep_time is None:
        raise ValueError("Enter a wake time or sleep time")
    return wake_time, sleep_time


def read_sleep_records(path: Path) -> list[SleepRecord]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames == CSV_HEADER:
            return _read_current_records(reader)
        if reader.fieldnames == LEGACY_CSV_HEADER:
            return _read_legacy_records(reader)
        raise ValueError("Expected header: date,wake_time,sleep_time")


def store_sleep(path: Path, record: SleepRecord) -> None:
    records_by_date = {existing.date: existing for existing in read_sleep_records(path)}
    records_by_date[record.date] = record
    _replace_sleep_records(path, [records_by_date[day] for day in sorted(records_by_date)])


def delete_sleep(path: Path, record_date: date) -> bool:
    records = read_sleep_records(path)
    remaining = [record for record in records if record.date != record_date]
    if len(remaining) == len(records):
        return False
    _replace_sleep_records(path, remaining)
    return True


def _read_current_records(reader: csv.DictReader) -> list[SleepRecord]:
    records = []
    previous_date = None
    for row in reader:
        record_date = date.fromisoformat(row["date"])
        if previous_date is not None and record_date <= previous_date:
            raise ValueError("Sleep record dates must be unique and increasing")
        wake_time, sleep_time = parse_sleep_times(row["wake_time"], row["sleep_time"])
        records.append(SleepRecord(record_date, wake_time, sleep_time))
        previous_date = record_date
    return records


def _read_legacy_records(reader: csv.DictReader) -> list[SleepRecord]:
    records = []
    for row in reader:
        records.append(
            SleepRecord(
                date.fromisoformat(row["wake_date"]),
                _parse_required_time(row["wake_time"]),
                _parse_required_time(row["sleep_time"]),
            )
        )
    return records


def _parse_optional_time(raw_value: str | None) -> time | None:
    if raw_value is None or not raw_value.strip():
        return None
    return _parse_required_time(raw_value)


def _parse_required_time(raw_value: str) -> time:
    try:
        return datetime.strptime(raw_value, "%H:%M").time()
    except ValueError:
        raise ValueError("Enter valid wake and sleep times") from None


def _replace_sleep_records(path: Path, records: list[SleepRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(
                (
                    record.date.isoformat(),
                    _format_time(record.wake_time),
                    _format_time(record.sleep_time),
                )
                for record in records
            )
            csv_file.flush()
            os.fsync(csv_file.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _format_time(value: time | None) -> str:
    return "" if value is None else value.strftime("%H:%M")
