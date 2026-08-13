import json
import math
from datetime import date, timedelta
from typing import cast

import pytest

from weight_plotly import build_difference_figure, build_rate_figure, build_weight_figure


def test_build_weight_figure_preserves_data_gaps_and_interactions():
    figure = build_weight_figure(
        [date(2026, 8, 1), date(2026, 8, 2)],
        [100.0, 99.5],
        [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)],
        [100.0, math.nan, 95.0],
    )

    serialized = json.loads(cast(str, figure.to_json()))
    plan_trace, weight_trace, latest_trace = serialized["data"]
    assert plan_trace["connectgaps"] is False
    assert plan_trace["y"] == [100.0, None, 95.0]
    assert plan_trace["x"] == ["2026-08-01", "2026-08-02", "2026-08-03"]
    assert weight_trace["x"] == ["2026-08-01", "2026-08-02"]
    assert weight_trace["y"] == [100.0, 99.5]
    assert latest_trace["x"] == ["2026-08-02"]
    assert latest_trace["y"] == [99.5]
    assert "rangeslider" not in serialized["layout"]["xaxis"]
    assert serialized["layout"]["margin"]["r"] == 24
    assert serialized["layout"]["yaxis"]["fixedrange"] is False


def test_build_weight_figure_supports_empty_data():
    figure = build_weight_figure([], [], [], [])

    serialized = json.loads(cast(str, figure.to_json()))
    assert not serialized["data"]
    assert "annotations" not in serialized["layout"]


def test_build_weight_figure_adds_blue_candidate_plan():
    figure = build_weight_figure(
        [],
        [],
        [date(2026, 8, 1)],
        [100.0],
        [date(2026, 8, 1), date(2026, 8, 2)],
        [100.0, 99.0],
    )

    serialized = json.loads(cast(str, figure.to_json()))
    active_trace, candidate_trace = serialized["data"]
    assert active_trace["name"] == "Plan"
    assert candidate_trace["name"] == "Candidate plan"
    assert candidate_trace["line"]["color"] == "#2563eb"
    assert candidate_trace["connectgaps"] is False
    assert candidate_trace["y"] == [100.0, 99.0]


def test_build_weight_figure_marks_inclusive_erase_interval():
    figure = build_weight_figure(
        [],
        [],
        [date(2026, 8, 1)],
        [100.0],
        erase_intervals=[(date(2026, 8, 10), date(2026, 8, 12))],
    )

    serialized = json.loads(cast(str, figure.to_json()))
    shape = serialized["layout"]["shapes"][0]
    assert shape["x0"] == "2026-08-10"
    assert shape["x1"] == "2026-08-13"
    assert shape["fillcolor"] == "rgba(180, 83, 60, 0.2)"
    assert shape["line"]["width"] == 0
    assert serialized["layout"]["annotations"][0]["text"] == "Erase active plan"


def test_build_difference_figure_shows_plan_difference():
    dates = [date(2026, 1, day) for day in range(1, 4)]
    weights = [101.0, 99.0, 100.0]
    plan = [100.0, 100.0, 100.0]

    serialized = json.loads(
        cast(str, build_difference_figure(dates, weights, dates, plan).to_json())
    )
    above_plan_trace, below_plan_trace = serialized["data"]

    assert above_plan_trace["x"] == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert above_plan_trace["y"] == [1.0, None, None]
    assert below_plan_trace["y"] == [None, -1.0, 0.0]


def test_build_difference_figure_interpolates_between_measurements_only():
    plan_dates = [date(2026, 1, day) for day in range(1, 8)]

    serialized = json.loads(
        cast(
            str,
            build_difference_figure(
                [date(2026, 1, 2), date(2026, 1, 6)],
                [102.0, 98.0],
                plan_dates,
                [100.0] * len(plan_dates),
            ).to_json(),
        )
    )
    above_plan_trace, below_plan_trace = serialized["data"]

    assert above_plan_trace["x"] == [
        "2026-01-02",
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
        "2026-01-06",
    ]
    assert above_plan_trace["y"] == [2.0, 1.0, None, None, None]
    assert below_plan_trace["y"] == [None, None, 0.0, -1.0, -2.0]


def test_build_difference_figure_keeps_single_exact_measurement():
    measurement_date = date(2026, 1, 2)

    serialized = json.loads(
        cast(
            str,
            build_difference_figure(
                [measurement_date],
                [101.0],
                [date(2026, 1, 1), measurement_date, date(2026, 1, 3)],
                [100.0, 100.0, 100.0],
            ).to_json(),
        )
    )

    assert serialized["data"][0]["x"] == ["2026-01-02"]
    assert serialized["data"][0]["y"] == [1.0]


def test_build_rate_figure_shows_28_day_rates():
    start = date(2026, 1, 1)
    dates = [start + timedelta(days=offset) for offset in range(35)]
    weights = [100 - offset / 7 for offset in range(35)]
    plan = [100 - 2 * offset / 7 for offset in range(35)]

    serialized = json.loads(cast(str, build_rate_figure(dates, weights, dates, plan).to_json()))
    recorded_rate_trace, planned_rate_trace = serialized["data"]

    assert recorded_rate_trace["y"][:27] == [None] * 27
    assert recorded_rate_trace["y"][-1] == pytest.approx(-1)
    assert planned_rate_trace["y"][-1] == pytest.approx(-2)


def test_build_rate_figure_preserves_plan_rate_gaps():
    start = date(2026, 1, 1)
    dates = [start + timedelta(days=offset) for offset in range(60)]
    weights = [100 - offset / 14 for offset in range(60)]
    plan = list(weights)
    plan[30] = math.nan

    serialized = json.loads(cast(str, build_rate_figure(dates, weights, dates, plan).to_json()))
    planned_rate_trace = serialized["data"][-1]

    assert planned_rate_trace["connectgaps"] is False
    assert planned_rate_trace["y"][30:58] == [None] * 28
    assert planned_rate_trace["y"][58] == pytest.approx(-0.5)


def test_insight_figures_support_empty_data():
    for figure in (build_difference_figure([], [], [], []), build_rate_figure([], [], [], [])):
        serialized = json.loads(cast(str, figure.to_json()))
        assert not serialized["data"]
