import csv
import math
import os
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

CSV_HEADER = ["date", "weight_kg"]


def parse_weight(raw_value: str | None) -> Decimal:
    if raw_value is None:
        raise ValueError("Enter a valid weight")
    try:
        weight = Decimal(raw_value.replace(",", "."))
    except InvalidOperation:
        raise ValueError("Enter a valid weight") from None

    if not weight.is_finite() or not Decimal("30") <= weight <= Decimal("300"):
        raise ValueError("Weight must be between 30 and 300 kg")
    return weight


def parse_measurement_date(raw_value: str | None, today: date) -> date:
    if not raw_value:
        raise ValueError("Choose a valid measurement date")
    try:
        measurement_date = date.fromisoformat(raw_value)
    except ValueError:
        raise ValueError("Choose a valid measurement date") from None
    if measurement_date > today:
        raise ValueError("Measurement date cannot be in the future")
    return measurement_date


def read_series(path: Path) -> tuple[list[date], list[float]]:
    if not path.exists():
        return [], []

    dates = []
    weights = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            dates.append(date.fromisoformat(row["date"]))
            weights.append(float(row["weight_kg"]))
    return dates, weights


def validate_csv(path: Path, allow_gaps: bool = False) -> int:
    previous_date = None
    row_count = 0

    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file)
        if next(reader, None) != CSV_HEADER:
            raise ValueError("Expected header: date,weight_kg")

        for line_number, row in enumerate(reader, 2):
            if len(row) != 2:
                raise ValueError(f"Line {line_number}: expected two columns")
            try:
                day = date.fromisoformat(row[0])
            except ValueError:
                raise ValueError(f"Line {line_number}: invalid date {row[0]!r}") from None
            try:
                weight = Decimal(row[1])
            except InvalidOperation:
                raise ValueError(f"Line {line_number}: invalid weight {row[1]!r}") from None
            if row[1] == "NaN" and allow_gaps:
                pass
            elif not weight.is_finite() or not Decimal("30") <= weight <= Decimal("300"):
                raise ValueError(f"Line {line_number}: weight must be between 30 and 300 kg")
            if previous_date is not None and day <= previous_date:
                raise ValueError(f"Line {line_number}: dates must be unique and increasing")
            previous_date = day
            row_count += 1

    if row_count == 0:
        raise ValueError("CSV contains no data rows")
    return row_count


def store_series(
    path: Path,
    dates: Sequence[date],
    weights: Sequence[float],
    allow_gaps: bool = False,
) -> int:
    rows = list(zip(dates, weights, strict=True))
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(
                (day.isoformat(), "NaN" if math.isnan(weight) else format(weight, "g"))
                for day, weight in rows
            )
            csv_file.flush()
            os.fsync(csv_file.fileno())
        row_count = validate_csv(temporary, allow_gaps=allow_gaps)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        return row_count
    finally:
        temporary.unlink(missing_ok=True)


def store_weight(path: Path, measurement_date: date, weight: Decimal) -> None:
    rows = _read_weight_rows(path)

    day = measurement_date.isoformat()
    replacement = (day, format(weight, "f"))
    for index, row in enumerate(rows):
        if row[0] == day:
            rows[index] = replacement
            break
    else:
        rows.append(replacement)
    rows.sort(key=lambda row: row[0])
    _replace_weight_rows(path, rows)


def delete_weight(path: Path, measurement_date: date) -> bool:
    rows = _read_weight_rows(path)
    day = measurement_date.isoformat()
    remaining_rows = [row for row in rows if row[0] != day]
    if len(remaining_rows) == len(rows):
        return False
    _replace_weight_rows(path, remaining_rows)
    return True


def _read_weight_rows(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as csv_file:
        return [(row["date"], row["weight_kg"]) for row in csv.DictReader(csv_file)]


def _replace_weight_rows(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(rows)
            csv_file.flush()
            os.fsync(csv_file.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
