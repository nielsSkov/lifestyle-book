import json
from datetime import date, time
from typing import cast

from sleep_data import SleepRecord
from sleep_plot import build_sleep_figure


def test_sleep_figure_plots_independent_lines_with_clean_gaps():
    figure = build_sleep_figure(
        [
            SleepRecord(date(2026, 8, 1), wake_time=time(7)),
            SleepRecord(date(2026, 8, 2), wake_time=time(8), sleep_time=time(23, 30)),
            SleepRecord(date(2026, 8, 4), sleep_time=time(0, 30)),
        ]
    )

    wake_trace, sleep_trace = json.loads(cast(str, figure.to_json()))["data"]
    assert wake_trace["x"] == ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"]
    assert wake_trace["y"] == [7.0, 8.0, None, None]
    assert sleep_trace["y"] == [None, 23.5, None, 0.5]
    assert wake_trace["connectgaps"] is False
    assert sleep_trace["connectgaps"] is False
    assert [wake_trace["name"], sleep_trace["name"]] == ["Wake time", "Sleep time"]


def test_sleep_figure_supports_empty_data():
    assert not build_sleep_figure([]).data
