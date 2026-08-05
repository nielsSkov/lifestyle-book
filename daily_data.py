import csv
import os
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class DailyRecord:
    day: date
    activities: frozenset[str]


@dataclass(frozen=True)
class _DailyFile:
    columns: tuple[str, ...]
    records: tuple[DailyRecord, ...]


def parse_daily_date(raw_value: str | None, today: date) -> date:
    if not raw_value:
        raise ValueError("Choose a valid date")
    try:
        selected_date = date.fromisoformat(raw_value)
    except ValueError:
        raise ValueError("Choose a valid date") from None
    if selected_date > today:
        raise ValueError("Date cannot be in the future")
    return selected_date


def read_daily_records(path: Path) -> list[DailyRecord]:
    return list(_read_daily_file(path).records)


def store_daily_record(
    path: Path,
    day: date,
    selected_keys: Collection[str],
    active_keys: Sequence[str],
) -> None:
    if len(active_keys) != len(set(active_keys)):
        raise ValueError("Daily category keys must be unique")

    selected = set(selected_keys)
    active = set(active_keys)
    if not selected <= active:
        raise ValueError("Unknown daily activity")

    daily_file = _read_daily_file(path)
    columns = [*daily_file.columns]
    columns.extend(key for key in active_keys if key not in columns)

    records_by_date = {record.day: record for record in daily_file.records}
    previous = records_by_date.get(day, DailyRecord(day, frozenset()))
    activities = (set(previous.activities) - active) | selected
    if activities:
        records_by_date[day] = DailyRecord(day, frozenset(activities))
    else:
        records_by_date.pop(day, None)

    _replace_daily_records(
        path,
        columns,
        [records_by_date[record_date] for record_date in sorted(records_by_date)],
    )


def store_daily_activity(path: Path, day: date, key: str, selected: bool) -> None:
    daily_file = _read_daily_file(path)
    columns = [*daily_file.columns]
    if key not in columns:
        columns.append(key)

    records_by_date = {record.day: record for record in daily_file.records}
    previous = records_by_date.get(day, DailyRecord(day, frozenset()))
    activities = set(previous.activities)
    if selected:
        activities.add(key)
    else:
        activities.discard(key)

    if activities:
        records_by_date[day] = DailyRecord(day, frozenset(activities))
    else:
        records_by_date.pop(day, None)

    _replace_daily_records(
        path,
        columns,
        [records_by_date[record_date] for record_date in sorted(records_by_date)],
    )


def _read_daily_file(path: Path) -> _DailyFile:
    if not path.exists():
        return _DailyFile((), ())

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames
        if not fieldnames or fieldnames[0] != "date":
            raise ValueError("Expected daily CSV to begin with a date column")
        columns = fieldnames[1:]
        if any(not column for column in columns) or len(columns) != len(set(columns)):
            raise ValueError("Daily CSV category columns must be named and unique")

        records = _read_daily_rows(reader, columns)

    return _DailyFile(tuple(columns), tuple(records))


def _read_daily_rows(reader: csv.DictReader, columns: Sequence[str]) -> list[DailyRecord]:
    records = []
    previous_date = None
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Daily CSV row does not match its header")
        try:
            day = date.fromisoformat(row["date"])
        except ValueError:
            raise ValueError("Daily CSV contains an invalid date") from None
        if previous_date is not None and day <= previous_date:
            raise ValueError("Daily record dates must be unique and increasing")

        activities = set()
        for column in columns:
            value = row[column].strip()
            if value not in {"", "1"}:
                raise ValueError("Daily CSV values must be 1 or blank")
            if value == "1":
                activities.add(column)
        if not activities:
            raise ValueError("Daily CSV cannot contain an empty record")
        records.append(DailyRecord(day, frozenset(activities)))
        previous_date = day
    return records


def _replace_daily_records(path: Path, columns: list[str], records: list[DailyRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(["date", *columns])
            writer.writerows(
                [
                    record.day.isoformat(),
                    *("1" if key in record.activities else "" for key in columns),
                ]
                for record in records
            )
            csv_file.flush()
            os.fsync(csv_file.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
