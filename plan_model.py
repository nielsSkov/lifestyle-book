import math
from datetime import date, timedelta

from weight_data import MAX_WEIGHT_KG, MIN_WEIGHT_KG

MAX_PLAN_DURATION_DAYS = 3650
MAX_TAPER = 10.0


def build_plan_interval(
    start_date: date,
    start_weight: float,
    target_weight: float,
    duration_days: int,
    taper: float,
) -> tuple[list[date], list[float]]:
    if not math.isfinite(start_weight) or not MIN_WEIGHT_KG <= start_weight <= MAX_WEIGHT_KG:
        raise ValueError(f"Starting weight must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG} kg")
    if not math.isfinite(target_weight) or not MIN_WEIGHT_KG <= target_weight <= MAX_WEIGHT_KG:
        raise ValueError(f"Target weight must be between {MIN_WEIGHT_KG} and {MAX_WEIGHT_KG} kg")
    if (
        isinstance(duration_days, bool)
        or not isinstance(duration_days, int)
        or not 1 <= duration_days <= MAX_PLAN_DURATION_DAYS
    ):
        raise ValueError(f"Duration must be between 1 and {MAX_PLAN_DURATION_DAYS} days")
    if not math.isfinite(taper) or not 0 <= taper <= MAX_TAPER:
        raise ValueError(f"Taper must be between 0 and {MAX_TAPER:g}")

    try:
        dates = [start_date + timedelta(days=offset) for offset in range(duration_days + 1)]
    except OverflowError:
        raise ValueError("Interval end date is outside the supported date range") from None
    weights = []
    for offset in range(duration_days + 1):
        elapsed = offset / duration_days
        progress = elapsed
        if taper >= 1e-8:
            progress = math.expm1(-taper * elapsed) / math.expm1(-taper)
        weights.append(start_weight + (target_weight - start_weight) * progress)
    return dates, weights
