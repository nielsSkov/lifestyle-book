import json
from datetime import date
from typing import cast

from daily_categories import DailyCategory
from daily_data import DailyRecord
from daily_plot import build_active_days_figure, build_daily_figure


def test_daily_figure_shows_used_active_categories_in_two_bands():
    categories = [
        DailyCategory("walk", "Walk", "movement", "#111111", "#444444", "#777777", "walk"),
        DailyCategory("run", "Run", "movement", "#222222", "#555555", "#888888", "run"),
        DailyCategory("cooked", "Cooked", "food", "#333333", "#666666", "#999999", "cooked"),
    ]
    records = [
        DailyRecord(date(2026, 8, 1), frozenset({"archived"})),
        DailyRecord(date(2026, 8, 3), frozenset({"walk", "cooked"})),
    ]

    serialized = json.loads(cast(str, build_daily_figure(records, categories).to_json()))

    assert [trace["name"] for trace in serialized["data"]] == ["Walk", "Cooked"]
    assert serialized["data"][0]["type"] == "heatmap"
    assert serialized["data"][0]["x0"] == "2026-08-01"
    assert serialized["data"][0]["dx"] == 86_400_000
    assert serialized["data"][0]["y0"] == 3
    assert serialized["data"][0]["dy"] == 1
    assert serialized["data"][0]["z"] == [[None, None, 1]]
    assert serialized["data"][1]["z"] == [[None, None, 1]]
    assert serialized["data"][0]["xgap"] == 10
    assert serialized["data"][0]["ygap"] == 10
    assert serialized["data"][0]["colorscale"] == [[0, "#777777"], [1, "#777777"]]
    assert serialized["layout"]["yaxis"]["ticktext"] == ["Walk", "Cooked"]
    assert len(serialized["layout"]["shapes"]) == 3
    assert [item["text"] for item in serialized["layout"]["annotations"]] == [
        "MOVEMENT",
        "FOOD",
    ]


def test_daily_figure_supports_empty_data_without_empty_category_rows():
    category = DailyCategory("walk", "Walk", "movement", "#111111", "#444444", "#777777", "walk")
    figure = build_daily_figure([], [category])

    assert not figure.data
    assert figure.layout.yaxis.ticktext == ()
    assert figure.layout.annotations[0].text == "Recorded achievements will appear here"


def test_active_days_figure_counts_inactive_movement_but_not_food():
    categories = [
        DailyCategory("walk", "Walk", "movement", "#111111", "#444444", "#777777", "walk"),
        DailyCategory(
            "roller_skate",
            "Roller Skate",
            "movement",
            "#222222",
            "#555555",
            "#888888",
            "roller-skate",
            active=False,
        ),
        DailyCategory("cooked", "Cooked", "food", "#333333", "#666666", "#999999", "cooked"),
    ]
    records = [
        DailyRecord(date(2026, 8, 1), frozenset({"roller_skate"})),
        DailyRecord(date(2026, 8, 2), frozenset({"cooked"})),
        DailyRecord(date(2026, 8, 3), frozenset({"walk"})),
    ]

    serialized = json.loads(cast(str, build_active_days_figure(records, categories).to_json()))

    assert serialized["data"][0]["name"] == "Active Day"
    assert serialized["data"][0]["dy"] == 0.5
    assert serialized["data"][0]["z"] == [[1, None, 1]]
    assert serialized["data"][0]["colorscale"] == [[0, "#6930d1"], [1, "#6930d1"]]
    assert serialized["layout"]["title"]["text"] == "Active Days"
    assert serialized["layout"]["xaxis"]["showticklabels"] is True
    assert serialized["layout"]["yaxis"]["title"]["text"] == "Active"


def test_active_days_figure_supports_no_movement_data():
    cooked = DailyCategory("cooked", "Cooked", "food", "#333333", "#666666", "#999999", "cooked")
    figure = build_active_days_figure(
        [DailyRecord(date(2026, 8, 1), frozenset({"cooked"}))],
        [cooked],
    )
    serialized = json.loads(cast(str, figure.to_json()))

    assert serialized["data"][0]["z"] == [[None]]
    assert serialized["layout"]["annotations"][0]["text"] == (
        "Movement achievements will appear here"
    )
