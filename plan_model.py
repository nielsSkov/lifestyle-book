import math
from collections.abc import Callable, Sequence
from datetime import date, timedelta

from weight_data import MAX_WEIGHT_KG, MIN_WEIGHT_KG

PlanFunction = Callable[[int], float]
ControlValue = float | PlanFunction | None
MAX_PLAN_DURATION_DAYS = 3650
MAX_TAPER = 10.0


def validate_weight(weight: float, control_point: int) -> None:
    if not math.isfinite(weight) or not MIN_WEIGHT_KG <= weight <= MAX_WEIGHT_KG:
        raise ValueError(
            f"Control point {control_point}: weight must be between "
            f"{MIN_WEIGHT_KG} and {MAX_WEIGHT_KG} kg"
        )


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


def interpolate_segment_weight(
    start_value: ControlValue,
    end_value: ControlValue,
    offset: int,
    duration: int,
) -> float:
    if start_value is None:
        return math.nan
    if callable(start_value):
        return start_value(offset)
    if end_value is None:
        end_weight = start_value
    elif callable(end_value):
        end_weight = end_value(0)
    else:
        end_weight = end_value
    return start_value + (end_weight - start_value) * offset / duration


def interpolate_plan(
    control_points: Sequence[tuple[date, ControlValue]],
) -> tuple[list[date], list[float]]:
    if not control_points:
        raise ValueError("Add at least one control point")

    for index, (day, value) in enumerate(control_points):
        if value is not None and not callable(value):
            validate_weight(value, index + 1)
        if index and day <= control_points[index - 1][0]:
            raise ValueError("Control point dates must be unique and increasing")

    final_date, final_value = control_points[-1]
    if callable(final_value):
        raise ValueError("The final control point must be a weight")

    plan_dates = []
    plan_weights = []
    for index, ((start_date, start_value), (end_date, end_value)) in enumerate(
        zip(control_points, control_points[1:], strict=False),
        1,
    ):
        duration = (end_date - start_date).days
        for offset in range(duration):
            weight = interpolate_segment_weight(start_value, end_value, offset, duration)
            if start_value is not None:
                validate_weight(weight, index)
            plan_dates.append(start_date + timedelta(days=offset))
            plan_weights.append(weight)

    plan_dates.append(final_date)
    plan_weights.append(math.nan if final_value is None else final_value)

    return plan_dates, plan_weights
