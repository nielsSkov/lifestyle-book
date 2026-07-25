import math
from collections.abc import Callable, Sequence
from datetime import date, timedelta

PlanFunction = Callable[[int], float]
ControlValue = float | PlanFunction


def validate_weight(weight: float, control_point: int) -> None:
    if not math.isfinite(weight) or not 30 <= weight <= 300:
        raise ValueError(f"Control point {control_point}: weight must be between 30 and 300 kg")


def interpolate_plan(
    control_points: Sequence[tuple[date, ControlValue]],
) -> tuple[list[date], list[float]]:
    if not control_points:
        raise ValueError("Add at least one control point")

    for index, (day, value) in enumerate(control_points):
        if not callable(value):
            validate_weight(value, index + 1)
        if index and day <= control_points[index - 1][0]:
            raise ValueError("Control point dates must be unique and increasing")
    if callable(control_points[-1][1]):
        raise ValueError("The final control point must be a weight")

    plan_dates = []
    plan_weights = []
    for index, ((start_date, start_value), (end_date, end_value)) in enumerate(
        zip(control_points, control_points[1:], strict=False),
        1,
    ):
        duration = (end_date - start_date).days
        end_weight = end_value(0) if callable(end_value) else end_value
        for offset in range(duration):
            weight = (
                start_value(offset)
                if callable(start_value)
                else start_value + (end_weight - start_value) * offset / duration
            )
            validate_weight(weight, index)
            plan_dates.append(start_date + timedelta(days=offset))
            plan_weights.append(weight)

    final_date, final_value = control_points[-1]
    plan_dates.append(final_date)
    plan_weights.append(final_value)

    return plan_dates, plan_weights
