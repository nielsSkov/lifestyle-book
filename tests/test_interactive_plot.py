import json
import math
from datetime import date

from interactive_plot import PLOTLY_CONFIG, build_interactive_figure, plotly_javascript


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
    assert serialized["layout"]["modebar"]["color"] == "#a99db9"
    assert serialized["layout"]["hoverlabel"]["bgcolor"] == "#2c2340"
    assert serialized["layout"]["xaxis"]["modebardisable"] == "zoominout"
    assert serialized["layout"]["xaxis"]["rangeslider"]["visible"] is True
    assert serialized["layout"]["annotations"][0]["text"] == "99.5 kg"


def test_build_interactive_figure_supports_empty_data():
    figure = build_interactive_figure([], [], [], [])

    serialized_json = figure.to_json()
    assert isinstance(serialized_json, str)
    serialized = json.loads(serialized_json)
    assert not serialized["data"]
    assert "annotations" not in serialized["layout"]


def test_plotly_runtime_is_local_and_interactive():
    javascript = plotly_javascript()

    assert "Plotly" in javascript
    assert len(javascript) > 1_000_000
    assert PLOTLY_CONFIG == {
        "displaylogo": False,
        "displayModeBar": True,
        "modeBarButtonsToRemove": [
            "toImage",
            "select2d",
            "lasso2d",
            "hoverClosestCartesian",
            "hoverCompareCartesian",
            "toggleSpikelines",
        ],
        "responsive": True,
        "scrollZoom": True,
        "showTips": False,
    }
