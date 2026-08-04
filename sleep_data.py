import csv
import os
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

CSV_HEADER = ["wake_date", "sleep_time", "wake_time"]


@dataclass(frozen=True)
class SleepRecord:
    wake_date: date
    sleep_time: time
    wake_time: time

    @property
    def duration_minutes(self) -> int:
        return sleep_duration_minutes(self.sleep_time, self.wake_time)


def parse_wake_date(raw_value: str | None, today: date) -> date:
    if not raw_value:
        raise ValueError("Choose a valid wake date")
    try:
        wake_date = date.fromisoformat(raw_value)
    except ValueError:
        raise ValueError("Choose a valid wake date") from None
    if wake_date > today:
        raise ValueError("Wake date cannot be in the future")
    return wake_date


def parse_sleep_times(
    raw_sleep_time: str | None,
    raw_wake_time: str | None,
) -> tuple[time, time]:
    if not raw_sleep_time or not raw_wake_time:
        raise ValueError("Enter both sleep and wake times")
    try:
        sleep_time = datetime.strptime(raw_sleep_time, "%H:%M").time()
        wake_time = datetime.strptime(raw_wake_time, "%H:%M").time()
    except ValueError:
        raise ValueError("Enter valid sleep and wake times") from None
    if sleep_duration_minutes(sleep_time, wake_time) == 0:
        raise ValueError("Sleep and wake times must be different")
    return sleep_time, wake_time


def sleep_duration_minutes(sleep_time: time, wake_time: time) -> int:
    sleep_minutes = sleep_time.hour * 60 + sleep_time.minute
    wake_minutes = wake_time.hour * 60 + wake_time.minute
    return (wake_minutes - sleep_minutes) % (24 * 60)


def read_sleep_records(path: Path) -> list[SleepRecord]:
    if not path.exists():
        return []

    records = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != CSV_HEADER:
            raise ValueError("Expected header: wake_date,sleep_time,wake_time")
        for row in reader:
            sleep_time, wake_time = parse_sleep_times(row["sleep_time"], row["wake_time"])
            records.append(
                SleepRecord(
                    wake_date=date.fromisoformat(row["wake_date"]),
                    sleep_time=sleep_time,
                    wake_time=wake_time,
                )
            )
    return records


def store_sleep(path: Path, record: SleepRecord) -> None:
    records_by_date = {existing.wake_date: existing for existing in read_sleep_records(path)}
    records_by_date[record.wake_date] = record
    _replace_sleep_records(path, [records_by_date[day] for day in sorted(records_by_date)])


def delete_sleep(path: Path, wake_date: date) -> bool:
    records = read_sleep_records(path)
    remaining = [record for record in records if record.wake_date != wake_date]
    if len(remaining) == len(records):
        return False
    _replace_sleep_records(path, remaining)
    return True


def _replace_sleep_records(path: Path, records: list[SleepRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(
                (
                    record.wake_date.isoformat(),
                    record.sleep_time.strftime("%H:%M"),
                    record.wake_time.strftime("%H:%M"),
                )
                for record in records
            )
            csv_file.flush()
            os.fsync(csv_file.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
