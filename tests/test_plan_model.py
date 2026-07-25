import math
from datetime import date

import pytest

from plan_model import interpolate_plan


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

    with pytest.raises(ValueError, match="final.*weight"):
        interpolate_plan(
            [
                (date(2026, 8, 1), 100.0),
                (date(2026, 8, 2), invalid_final),
            ]
        )


def test_interpolate_plan_validates_function_values_as_they_are_generated():
    def invalid_curve(days):
        if days:
            raise AssertionError("Later values should not be generated")
        return 301.0

    with pytest.raises(ValueError, match="between 30 and 300"):
        interpolate_plan(
            [
                (date(2026, 8, 1), invalid_curve),
                (date(2026, 8, 3), 100.0),
            ]
        )


@pytest.mark.parametrize(
    ("control_points", "message"),
    [
        ([], "at least one"),
        ([(date(2026, 7, 25), 29.0)], "between 30 and 300"),
        (
            [(date(2026, 7, 25), 100.0), (date(2026, 7, 25), 99.0)],
            "unique and increasing",
        ),
        ([(date(2026, 7, 25), lambda days: 100.0 - days)], "final.*weight"),
    ],
)
def test_interpolate_plan_rejects_invalid_control_points(control_points, message):
    with pytest.raises(ValueError, match=message):
        interpolate_plan(control_points)
