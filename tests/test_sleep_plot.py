import json
from datetime import date, datetime
from typing import cast

import pytest

from sleep_data import SleepRecord
from sleep_plot import build_sleep_duration_figure, build_sleep_figure


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
    assert second_fill["width"] == pytest.approx(60_480_000)
    assert second_fill["base"] == [22.0]
    assert second_fill["y"] == [8.0]
    assert sleep_trace["x"] == [
        "2026-08-01",
        "2026-08-02",
        "2026-08-03",
        "2026-08-04",
    ]
    assert sleep_trace["customdata"][0] == ["1–2 Aug<br>2026", "23:00"]
    assert sleep_trace["hovertemplate"] == "%{customdata[1]}<extra>%{fullData.name}</extra>"
    assert sleep_trace["y"] == [23.0, 22.5, None, 22.0]
    assert wake_trace["y"] == [31.0, 32.0, 31.0, 30.0]
    assert sleep_trace["connectgaps"] is False
    assert wake_trace["connectgaps"] is False
    assert [sleep_trace["name"], wake_trace["name"]] == ["Sleep time", "Wake time"]
    assert serialized["layout"]["yaxis"]["tickvals"] == list(range(18, 37))
    assert serialized["layout"]["xaxis"]["range"] == [
        "2026-07-31T12:00:00",
        "2026-08-04T12:00:00",
    ]
    assert serialized["layout"]["xaxis"]["unifiedhovertitle"]["text"] == "%{customdata[0]}"


def test_sleep_figure_supports_empty_data():
    assert not build_sleep_figure([]).data


def test_sleep_duration_figure_uses_same_night_buckets_and_complete_records():
    figure = build_sleep_duration_figure(
        [
            SleepRecord(date(2026, 8, 1), datetime(2026, 8, 1, 23), datetime(2026, 8, 2, 7)),
            SleepRecord(date(2026, 8, 3), wake_at=datetime(2026, 8, 4, 7)),
            SleepRecord(
                date(2026, 8, 4),
                datetime(2026, 8, 4, 22, 30),
                datetime(2026, 8, 5, 6, 45),
            ),
        ]
    )

    serialized = json.loads(cast(str, figure.to_json()))
    trace = serialized["data"][0]
    assert trace["type"] == "bar"
    assert trace["x"] == ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"]
    assert trace["y"] == [8.0, None, None, 8.25]
    assert trace["customdata"] == [
        ["1–2 Aug<br>2026", "8 h 00 min"],
        ["2–3 Aug<br>2026", ""],
        ["3–4 Aug<br>2026", ""],
        ["4–5 Aug<br>2026", "8 h 15 min"],
    ]
    assert trace["marker"]["color"] == "#8354e8"
    assert trace["hovertemplate"] == "%{customdata[1]}<extra>Sleep duration</extra>"
    assert serialized["layout"]["xaxis"]["type"] == "date"
    assert "tickformat" not in serialized["layout"]["xaxis"]
    assert serialized["layout"]["xaxis"]["range"] == [
        "2026-07-31T12:00:00",
        "2026-08-04T12:00:00",
    ]
    assert serialized["layout"]["xaxis"]["unifiedhovertitle"]["text"] == "%{customdata[0]}"
    assert serialized["layout"]["yaxis"]["title"]["text"] == "Hours"
    assert serialized["layout"]["yaxis"]["dtick"] == 1


def test_sleep_duration_figure_supports_empty_data():
    assert not build_sleep_duration_figure([]).data
