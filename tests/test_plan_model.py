from datetime import date

import pytest

from plan_model import build_plan_interval


def test_build_plan_interval_is_linear_at_zero_taper():
    dates, weights = build_plan_interval(date(2026, 8, 1), 100.0, 98.0, 2, 0)

    assert dates == [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)]
    assert weights == [100.0, 99.0, 98.0]


def test_build_plan_interval_tapers_while_preserving_endpoints():
    _dates, weights = build_plan_interval(date(2026, 8, 1), 100.0, 90.0, 10, 1)

    assert weights[0] == 100.0
    assert weights[5] < 95.0
    assert weights[-1] == 90.0


def test_build_plan_interval_treats_negligible_taper_as_linear():
    _dates, weights = build_plan_interval(date(2026, 8, 1), 100.0, 90.0, 10, 5e-324)

    assert weights == [float(weight) for weight in range(100, 89, -1)]


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ((-0.1, 90.0, 10, 0), "Starting weight"),
        ((100.0, 701.0, 10, 0), "Target weight"),
        ((100.0, 90.0, 0, 0), "Duration"),
        ((100.0, 90.0, 1.5, 0), "Duration"),
        ((100.0, 90.0, 10, 10.1), "Taper"),
        ((100.0, 90.0, 10, 0), "outside the supported date range"),
    ],
)
def test_build_plan_interval_rejects_invalid_values(values, message):
    start_date = date.max if message == "outside the supported date range" else date(2026, 8, 1)
    with pytest.raises(ValueError, match=message):
        build_plan_interval(start_date, *values)
