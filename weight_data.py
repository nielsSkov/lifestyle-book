import csv
import io
import math
import os
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

CSV_HEADER = ["date", "weight_kg"]
MIN_WEIGHT_KG = 0
MAX_WEIGHT_KG = 700


def parse_weight(raw_value: str | None) -> Decimal:
    if raw_value is None:
        raise ValueError("Enter a valid weight")
    try:
        weight = Decimal(raw_value.replace(",", "."))
    except InvalidOperation:
        raise ValueError("Enter a valid weight") from None

    if not weight.is_finite() or not Decimal(MIN_WEIGHT_KG) <= weight <= Decimal(MAX_WEIGHT_KG):
        raise ValueError(f"Weight must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG} kg")
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
    return read_series_bytes(path.read_bytes())


def read_series_bytes(contents: bytes) -> tuple[list[date], list[float]]:
    dates = []
    weights = []
    with io.TextIOWrapper(io.BytesIO(contents), encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, strict=True)
        if reader.fieldnames != CSV_HEADER:
            raise ValueError("Expected header: date,weight_kg")
        for row in reader:
            dates.append(date.fromisoformat(row["date"]))
            weights.append(float(row["weight_kg"]))
    return dates, weights


def validate_csv(path: Path, allow_gaps: bool = False) -> int:
    return validate_csv_bytes(path.read_bytes(), allow_gaps=allow_gaps)


def validate_csv_bytes(contents: bytes, allow_gaps: bool = False) -> int:
    previous_date = None
    row_count = 0

    try:
        csv_file = io.TextIOWrapper(io.BytesIO(contents), encoding="utf-8-sig", newline="")
        csv_file.read(0)
    except UnicodeError:
        raise ValueError("CSV must use UTF-8 encoding") from None
    with csv_file:
        reader = csv.reader(csv_file, strict=True)
        try:
            if next(reader, None) != CSV_HEADER:
                raise ValueError("Expected header: date,weight_kg")

            for line_number, row in enumerate(reader, 2):
                day = _validate_csv_row(row, line_number, allow_gaps)
                if previous_date is not None and day <= previous_date:
                    raise ValueError(f"Line {line_number}: dates must be unique and increasing")
                previous_date = day
                row_count += 1
        except UnicodeError:
            raise ValueError("CSV must use UTF-8 encoding") from None
        except csv.Error as error:
            raise ValueError(f"Invalid CSV: {error}") from None

    if row_count == 0:
        raise ValueError("CSV contains no data rows")
    return row_count


def _validate_csv_row(row: list[str], line_number: int, allow_gaps: bool) -> date:
    if len(row) != 2:
        raise ValueError(f"Line {line_number}: expected two columns")
    try:
        day = date.fromisoformat(row[0])
    except ValueError:
        raise ValueError(f"Line {line_number}: invalid date {row[0]!r}") from None
    if day.isoformat() != row[0]:
        raise ValueError(f"Line {line_number}: invalid date {row[0]!r}")
    try:
        weight = Decimal(row[1])
    except InvalidOperation:
        raise ValueError(f"Line {line_number}: invalid weight {row[1]!r}") from None
    if row[1] != "NaN" and not _decimal_syntax(row[1]):
        raise ValueError(f"Line {line_number}: invalid weight {row[1]!r}")
    if row[1] != "NaN" or not allow_gaps:
        if not weight.is_finite() or not Decimal(MIN_WEIGHT_KG) <= weight <= Decimal(MAX_WEIGHT_KG):
            raise ValueError(
                f"Line {line_number}: weight must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG} kg"
            )
    return day


def _decimal_syntax(value: str) -> bool:
    if not value or value.strip() != value:
        return False
    unsigned = value.removeprefix("+").removeprefix("-")
    whole, separator, fraction = unsigned.partition(".")
    return whole.isdigit() and (not separator or fraction.isdigit())


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
