import math
from collections.abc import Sequence
from datetime import date, timedelta
from itertools import pairwise


def interpolate_plan(
    control_points: Sequence[tuple[date, float]],
) -> tuple[list[date], list[float]]:
    if not control_points:
        raise ValueError("Add at least one control point")

    for index, (day, weight) in enumerate(control_points):
        if not math.isfinite(weight) or not 30 <= weight <= 300:
            raise ValueError(f"Control point {index + 1}: weight must be between 30 and 300 kg")
        if index and day <= control_points[index - 1][0]:
            raise ValueError("Control point dates must be unique and increasing")

    plan_dates = [control_points[0][0]]
    plan_weights = [control_points[0][1]]
    for (start_date, start_weight), (end_date, end_weight) in pairwise(control_points):
        duration = (end_date - start_date).days
        for offset in range(1, duration + 1):
            fraction = offset / duration
            plan_dates.append(start_date + timedelta(days=offset))
            plan_weights.append(start_weight + (end_weight - start_weight) * fraction)

    return plan_dates, plan_weights
