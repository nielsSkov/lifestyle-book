import json
from datetime import date, time
from typing import cast

from sleep_data import SleepRecord
from sleep_plot import build_sleep_figure


def test_sleep_figure_wraps_wake_times_and_fills_only_complete_nights():
    figure = build_sleep_figure(
        [
            SleepRecord(date(2026, 8, 1), wake_time=time(7), sleep_time=time(23)),
            SleepRecord(date(2026, 8, 2), wake_time=time(8), sleep_time=time(22, 30)),
            SleepRecord(date(2026, 8, 3), wake_time=time(7)),
            SleepRecord(date(2026, 8, 4), sleep_time=time(22)),
            SleepRecord(date(2026, 8, 5), wake_time=time(6)),
        ]
    )

    serialized = json.loads(cast(str, figure.to_json()))
    first_fill, second_fill, sleep_trace, wake_trace = serialized["data"]
    assert first_fill["fill"] == "toself"
    assert second_fill["type"] == "bar"
    assert second_fill["base"] == [22.0]
    assert second_fill["y"] == [8.0]
    assert first_fill["showlegend"] is False
    assert second_fill["showlegend"] is False
    assert sleep_trace["x"] == [
        "31 Jul–1 Aug<br>2026",
        "1–2 Aug<br>2026",
        "2–3 Aug<br>2026",
        "3–4 Aug<br>2026",
        "4–5 Aug<br>2026",
        "5–6 Aug<br>2026",
    ]
    assert sleep_trace["y"] == [None, 23.0, 22.5, None, 22.0, None]
    assert wake_trace["y"] == [31.0, 32.0, 31.0, None, 30.0, None]
    assert sleep_trace["connectgaps"] is False
    assert wake_trace["connectgaps"] is False
    assert [sleep_trace["name"], wake_trace["name"]] == ["Sleep time", "Wake time"]
    assert serialized["layout"]["xaxis"]["type"] == "category"
    assert serialized["layout"]["xaxis"]["title"]["text"] == "Night"
    assert serialized["layout"]["xaxis"]["categoryarray"][:2] == [
        "31 Jul–1 Aug<br>2026",
        "1–2 Aug<br>2026",
    ]


def test_sleep_figure_supports_empty_data():
    assert not build_sleep_figure([]).data
