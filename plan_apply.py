import math
import os
from datetime import date, timedelta
from pathlib import Path

from weight_data import store_series

ParsedInterval = tuple[date, date, list[date] | None, list[float] | None, bool]


def merge_plan_intervals(
    plan_dates: list[date],
    plan_weights: list[float],
    intervals: list[ParsedInterval],
) -> tuple[list[date], list[float]]:
    merged = dict(zip(plan_dates, plan_weights, strict=True))
    for start_date, end_date, interval_dates, interval_weights, erase in intervals:
        if erase:
            day = start_date
            while day <= end_date:
                merged[day] = math.nan
                day += timedelta(days=1)
            continue
        assert interval_dates is not None
        assert interval_weights is not None
        merged.update(zip(interval_dates, interval_weights, strict=True))
    dates = sorted(merged)
    return dates, [merged[day] for day in dates]


def store_active_plan(path: Path, dates: list[date], weights: list[float]) -> None:
    if dates:
        store_series(path, dates, weights, allow_gaps=True)
        _sync_directory(path.parent)
        return
    path.unlink(missing_ok=True)
    _sync_directory(path.parent)


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
