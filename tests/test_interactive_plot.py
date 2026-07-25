import json
import math
from datetime import date, timedelta

import pytest

from interactive_plot import (
    PLOTLY_CONFIG,
    build_insights_figure,
    build_interactive_figure,
    plotly_javascript,
)


def test_build_interactive_figure_preserves_style_and_gaps():
    figure = build_interactive_figure(
        [date(2026, 8, 1), date(2026, 8, 2)],
        [100.0, 99.5],
        [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)],
        [100.0, math.nan, 95.0],
    )

    serialized_json = figure.to_json()
    assert isinstance(serialized_json, str)
    serialized = json.loads(serialized_json)
    plan_trace, weight_trace, latest_trace = serialized["data"]
    assert plan_trace["name"] == "Plan"
    assert plan_trace["connectgaps"] is False
    assert plan_trace["line"]["color"] == "#087044"
    assert weight_trace["name"] == "Recorded weight"
    assert weight_trace["line"]["color"] == "#8b5cf6"
    assert latest_trace["showlegend"] is False
    assert serialized["data"][0]["y"] == [100.0, None, 95.0]
    assert serialized["data"][0]["x"] == ["2026-08-01", "2026-08-02", "2026-08-03"]
    assert serialized["layout"]["paper_bgcolor"] == "#15111f"
    assert serialized["layout"]["plot_bgcolor"] == "#15111f"
    assert serialized["layout"]["hoverlabel"]["bgcolor"] == "#2c2340"
    assert serialized["layout"]["xaxis"]["rangeslider"]["visible"] is True
    assert serialized["layout"]["yaxis"]["fixedrange"] is False
    assert serialized["layout"]["annotations"][0]["text"] == "99.5 kg"
    assert serialized["layout"]["annotations"][0]["xanchor"] == "left"
    assert serialized["layout"]["annotations"][0]["yanchor"] == "bottom"
    assert serialized["layout"]["margin"]["r"] == 72


def test_build_interactive_figure_supports_empty_data():
    figure = build_interactive_figure([], [], [], [])

    serialized_json = figure.to_json()
    assert isinstance(serialized_json, str)
    serialized = json.loads(serialized_json)
    assert not serialized["data"]
    assert "annotations" not in serialized["layout"]


def test_build_insights_figure_compares_difference_and_rate_windows():
    start = date(2026, 1, 1)
    dates = [start + timedelta(days=offset) for offset in range(35)]
    weights = [100 - offset / 7 for offset in range(35)]
    plan = [100 - 2 * offset / 7 for offset in range(35)]

    serialized_json = build_insights_figure(dates, weights, dates, plan).to_json()
    assert isinstance(serialized_json, str)
    serialized = json.loads(serialized_json)
    above_plan_trace, below_plan_trace, *rate_traces = serialized["data"]

    assert above_plan_trace["name"] == "Above plan"
    assert above_plan_trace["y"][0] is None
    assert above_plan_trace["y"][-1] == pytest.approx(34 / 7)
    assert above_plan_trace["marker"]["color"] == "#ef6f6c"
    assert below_plan_trace["name"] == "Below plan"
    assert below_plan_trace["y"][0] == 0
    assert below_plan_trace["marker"]["color"] == "#34a875"
    for index, window_days in enumerate((7, 14, 28)):
        recorded_rate_trace = rate_traces[index * 2]
        planned_rate_trace = rate_traces[index * 2 + 1]
        assert recorded_rate_trace["name"] == "Recorded rate"
        assert recorded_rate_trace["y"][: window_days - 1] == [None] * (window_days - 1)
        assert recorded_rate_trace["y"][-1] == pytest.approx(-1)
        assert planned_rate_trace["name"] == "Planned rate"
        assert planned_rate_trace["y"][-1] == pytest.approx(-2)
    assert serialized["layout"]["yaxis"]["title"]["text"] == "kg"
    assert serialized["layout"]["legend"]["entrywidth"] == 100
    for axis_number in range(2, 5):
        assert serialized["layout"][f"xaxis{axis_number}"]["matches"] == "x"
        assert serialized["layout"][f"yaxis{axis_number}"]["title"]["text"] == "kg/week"


def test_build_insights_figure_preserves_plan_rate_gaps():
    start = date(2026, 1, 1)
    dates = [start + timedelta(days=offset) for offset in range(60)]
    weights = [100 - offset / 14 for offset in range(60)]
    plan = list(weights)
    plan[30] = math.nan

    serialized_json = build_insights_figure(dates, weights, dates, plan).to_json()
    assert isinstance(serialized_json, str)
    serialized = json.loads(serialized_json)
    planned_rate_trace = serialized["data"][-1]

    assert planned_rate_trace["connectgaps"] is False
    assert planned_rate_trace["y"][30:58] == [None] * 28
    assert planned_rate_trace["y"][58] == pytest.approx(-0.5)


def test_build_insights_figure_supports_empty_data():
    serialized_json = build_insights_figure([], [], [], []).to_json()
    assert isinstance(serialized_json, str)
    serialized = json.loads(serialized_json)

    assert not serialized["data"]


def test_plotly_runtime_is_local_and_interactive():
    javascript = plotly_javascript()

    assert "Plotly" in javascript
    assert len(javascript) > 1_000_000
    assert PLOTLY_CONFIG == {
        "displaylogo": False,
        "displayModeBar": True,
        "modeBarButtons": [["zoom2d", "pan2d", "resetScale2d"]],
        "responsive": True,
        "scrollZoom": True,
        "showTips": False,
    }
