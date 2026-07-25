import math
from collections.abc import Sequence
from datetime import date
from typing import cast

from matplotlib.figure import Figure

from weight_plot import build_figure, period_bounds, shift_year, within_period


def test_period_bounds():
    assert shift_year(date(2024, 2, 29), -1) == date(2023, 2, 28)
    today = date(2026, 7, 25)
    assert period_bounds("7d", 0, None, today) == (date(2026, 7, 19), today)
    assert period_bounds("4w", 0, None, today) == (date(2026, 6, 28), today)
    assert period_bounds("1y", 0, None, today) == (date(2025, 7, 25), today)
    assert period_bounds("all", 0, [date(2024, 5, 7), date(2026, 12, 31)], today) == (
        date(2024, 5, 7),
        date(2026, 12, 31),
    )


def test_within_period():
    dates, weights = within_period(
        [date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1)],
        [100.0, 101.0, 102.0],
        date(2025, 1, 1),
        date(2026, 1, 1),
    )
    assert dates == [date(2025, 1, 1), date(2026, 1, 1)]
    assert weights == [101.0, 102.0]


def test_build_figure():
    supplied_figure = Figure(figsize=(7, 7))
    figure = build_figure(
        [date(2026, 7, 24), date(2026, 7, 25)],
        [109.8, 109.4],
        [date(2026, 7, 24), date(2026, 7, 25)],
        [109.7, 109.6],
        date(2026, 7, 19),
        date(2026, 7, 25),
        mobile=True,
        figure=supplied_figure,
    )

    axis = figure.axes[0]
    assert figure is supplied_figure
    assert tuple(figure.get_size_inches()) == (7.0, 7.0)
    assert axis.get_title() == "Recorded Weight and Plan"
    assert [line.get_label() for line in axis.lines] == ["Plan", "Recorded weight"]


def test_build_figure_preserves_plan_gaps():
    figure = build_figure(
        [],
        [],
        [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)],
        [100.0, math.nan, 95.0],
        date(2026, 8, 1),
        date(2026, 8, 3),
    )

    plotted_weights = cast(Sequence[float], figure.axes[0].lines[0].get_ydata())
    assert math.isnan(plotted_weights[1])
