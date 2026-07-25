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


@pytest.mark.parametrize(
    ("control_points", "message"),
    [
        ([], "at least one"),
        ([(date(2026, 7, 25), 29.0)], "between 30 and 300"),
        (
            [(date(2026, 7, 25), 100.0), (date(2026, 7, 25), 99.0)],
            "unique and increasing",
        ),
    ],
)
def test_interpolate_plan_rejects_invalid_control_points(control_points, message):
    with pytest.raises(ValueError, match=message):
        interpolate_plan(control_points)
