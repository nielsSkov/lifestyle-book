from collections.abc import Sequence
from datetime import date, time
from typing import cast

from plotly import graph_objects as go

from sleep_data import SleepRecord
from sleep_plot import build_sleep_figure


def test_sleep_figure_plots_each_overnight_interval():
    figure = build_sleep_figure(
        [
            SleepRecord(date(2026, 8, 1), time(23, 30), time(7, 15)),
            SleepRecord(date(2026, 8, 2), time(1), time(8)),
        ]
    )

    trace = cast(go.Bar, figure.data[0])
    assert list(cast(Sequence[date], trace.x)) == [date(2026, 8, 1), date(2026, 8, 2)]
    assert list(cast(Sequence[float], trace.base)) == [23.5, 25.0]
    assert list(cast(Sequence[float], trace.y)) == [7.75, 7.0]


def test_sleep_figure_supports_empty_data():
    assert not build_sleep_figure([]).data
