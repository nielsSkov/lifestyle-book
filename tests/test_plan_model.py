import math
from datetime import date

import pytest

from plan_model import build_plan_interval, interpolate_plan


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


def test_interpolate_plan_includes_each_day_and_endpoint():
    dates, weights = interpolate_plan(
        [
            (date(2026, 7, 25), 100.0),
            (date(2026, 7, 27), 98.0),
        ]
    )

    assert dates == [date(2026, 7, 25), date(2026, 7, 26), date(2026, 7, 27)]
    assert weights == [100.0, 99.0, 98.0]


def test_interpolate_plan_supports_plateaus():
    dates, weights = interpolate_plan(
        [
            (date(2026, 7, 25), 100.0),
            (date(2026, 7, 26), 99.0),
            (date(2026, 7, 28), 99.0),
        ]
    )

    assert dates[-3:] == [date(2026, 7, 26), date(2026, 7, 27), date(2026, 7, 28)]
    assert weights == [100.0, 99.0, 99.0, 99.0]


def test_interpolate_plan_supports_function_intervals_and_numeric_plateaus():
    dates, weights = interpolate_plan(
        [
            (date(2026, 8, 1), lambda days: 100.0 - days),
            (date(2026, 8, 3), 94.0),
            (date(2026, 8, 5), 94.0),
        ]
    )

    assert dates == [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
    ]
    assert weights == [100.0, 99.0, 94.0, 94.0, 94.0]


def test_interpolate_plan_can_transition_into_function_interval():
    dates, weights = interpolate_plan(
        [
            (date(2026, 8, 1), 100.0),
            (date(2026, 8, 3), lambda days: 98.0 - days),
            (date(2026, 8, 5), 96.0),
        ]
    )

    assert dates == [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
    ]
    assert weights == [100.0, 99.0, 98.0, 97.0, 96.0]


def test_interpolate_plan_supports_explicit_gaps():
    dates, weights = interpolate_plan(
        [
            (date(2026, 8, 1), lambda days: 100.0 - days),
            (date(2026, 8, 3), None),
            (date(2026, 8, 4), 95.0),
            (date(2026, 8, 5), 95.0),
        ]
    )

    assert dates == [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
    ]
    assert weights[:2] == [100.0, 99.0]
    assert math.isnan(weights[2])
    assert weights[3:] == [95.0, 95.0]


def test_interpolate_plan_rejects_final_function_without_calling_it():
    def invalid_final(_days):
        raise AssertionError("Final function should not be called")

    with pytest.raises(ValueError, match="final control point"):
        interpolate_plan(
            [
                (date(2026, 8, 1), 100.0),
                (date(2026, 8, 2), invalid_final),
            ]
        )


def test_interpolate_plan_rejects_invalid_generated_function_values():
    def invalid_curve(_days):
        return 701.0

    with pytest.raises(ValueError, match="between 0 and 700"):
        interpolate_plan(
            [
                (date(2026, 8, 1), invalid_curve),
                (date(2026, 8, 3), 100.0),
            ]
        )


@pytest.mark.parametrize(
    ("control_points", "error_category"),
    [
        ([], "at least one"),
        ([(date(2026, 7, 25), -0.1)], "between 0 and 700"),
        (
            [(date(2026, 7, 25), 100.0), (date(2026, 7, 25), 99.0)],
            "unique and increasing",
        ),
    ],
)
def test_interpolate_plan_rejects_invalid_control_points(control_points, error_category):
    with pytest.raises(ValueError, match=error_category):
        interpolate_plan(control_points)
