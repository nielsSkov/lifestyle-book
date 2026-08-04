import json
from datetime import date, time
from typing import cast

from sleep_data import SleepRecord
from sleep_plot import build_sleep_figure


def test_sleep_figure_wraps_wake_times_and_fills_only_complete_nights():
    figure = build_sleep_figure(
        [
            SleepRecord(date(2026, 8, 1), wake_time=time(7), sleep_time=time(23)),
            SleepRecord(date(2026, 8, 2), wake_time=time(8)),
            SleepRecord(date(2026, 8, 3), sleep_time=time(22)),
            SleepRecord(date(2026, 8, 4), wake_time=time(6)),
        ]
    )

    first_fill, second_fill, sleep_trace, wake_trace = json.loads(cast(str, figure.to_json()))[
        "data"
    ]
    assert first_fill["fill"] == "toself"
    assert second_fill["fill"] == "toself"
    assert first_fill["showlegend"] is False
    assert second_fill["showlegend"] is False
    assert sleep_trace["x"] == [
        "2026-07-31",
        "2026-08-01",
        "2026-08-02",
        "2026-08-03",
        "2026-08-04",
    ]
    assert sleep_trace["y"] == [None, 23.0, None, 22.0, None]
    assert wake_trace["y"] == [31.0, 32.0, None, 30.0, None]
    assert sleep_trace["connectgaps"] is False
    assert wake_trace["connectgaps"] is False
    assert [sleep_trace["name"], wake_trace["name"]] == ["Sleep time", "Wake time"]


def test_sleep_figure_supports_empty_data():
    assert not build_sleep_figure([]).data
