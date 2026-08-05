import json
from datetime import date, datetime
from typing import cast

from sleep_data import SleepRecord
from sleep_plot import build_sleep_figure


def test_sleep_figure_uses_night_buckets_and_fills_only_complete_nights():
    figure = build_sleep_figure(
        [
            SleepRecord(date(2026, 8, 1), datetime(2026, 8, 1, 23), datetime(2026, 8, 2, 7)),
            SleepRecord(
                date(2026, 8, 2),
                datetime(2026, 8, 2, 22, 30),
                datetime(2026, 8, 3, 8),
            ),
            SleepRecord(date(2026, 8, 3), wake_at=datetime(2026, 8, 4, 7)),
            SleepRecord(
                date(2026, 8, 4),
                datetime(2026, 8, 4, 22),
                datetime(2026, 8, 5, 6),
            ),
        ]
    )

    serialized = json.loads(cast(str, figure.to_json()))
    first_fill, second_fill, sleep_trace, wake_trace = serialized["data"]
    assert first_fill["fill"] == "toself"
    assert second_fill["type"] == "bar"
    assert second_fill["base"] == [22.0]
    assert second_fill["y"] == [8.0]
    assert sleep_trace["x"] == [
        "1–2 Aug<br>2026",
        "2–3 Aug<br>2026",
        "3–4 Aug<br>2026",
        "4–5 Aug<br>2026",
    ]
    assert sleep_trace["y"] == [23.0, 22.5, None, 22.0]
    assert wake_trace["y"] == [31.0, 32.0, 31.0, 30.0]
    assert sleep_trace["connectgaps"] is False
    assert wake_trace["connectgaps"] is False
    assert [sleep_trace["name"], wake_trace["name"]] == ["Sleep time", "Wake time"]


def test_sleep_figure_supports_empty_data():
    assert not build_sleep_figure([]).data
