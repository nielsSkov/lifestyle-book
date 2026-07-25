from datetime import date
from pathlib import Path

import pytest

import app as app_module


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    weight_csv = tmp_path / "weight.csv"
    weight_csv.write_text(
        "date,weight_kg\n2026-08-01,100.0\n2026-08-02,99.5\n",
        encoding="utf-8",
    )
    plan_csv = tmp_path / "plan.csv"
    plan_csv.write_text(
        "date,weight_kg\n2026-08-01,100.0\n2026-08-02,NaN\n2026-08-03,95.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(app_module, "WEIGHT_CSV", weight_csv)
    monkeypatch.setattr(app_module, "PLAN_CSV", plan_csv)
    monkeypatch.setattr(app_module, "current_date", lambda: date(2026, 8, 3))
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def test_index_renders_interactive_plotly_chart(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b'id="previous-date"' in response.data
    assert b'id="next-date"' in response.data
    assert b'name="date"' in response.data
    assert b'value="2026-08-03"' in response.data
    assert b'max="2026-08-03"' in response.data
    assert b'"2026-08-01": 100.0' in response.data
    assert b'id="weight-plot"' in response.data
    assert b'id="insights-plot"' in response.data
    assert b"Plotly.newPlot" in response.data
    assert b'Plotly.newPlot("insights-plot"' in response.data
    assert b"plotly_relayout" in response.data
    assert b"Plotly.relayout(target, linkedUpdate)" in response.data
    assert b'"modeBarButtons": [["zoom2d", "pan2d", "resetScale2d"]]' in response.data
    assert b'"name":"Recorded weight"' in response.data
    assert b'"name":"Above plan"' in response.data
    assert b'"name":"Below plan"' in response.data
    assert b"28-Day Rate of Change" in response.data
    assert b"7-Day Rate of Change" not in response.data
    assert b"14-Day Rate of Change" not in response.data
    assert b'"y":[100.0,null,95.0]' in response.data
    assert b"range-picker" not in response.data
    assert b"graph-toolbar" not in response.data
    assert b"plot.png" not in response.data


def test_save_weight_inserts_historical_date_and_advances(client):
    response = client.post(
        "/weights",
        data={"date": "2026-07-31", "weight": "100.5"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Saved 100.5 kg." in response.data
    assert b'value="2026-08-01"' in response.data
    assert app_module.WEIGHT_CSV.read_text(encoding="utf-8") == (
        "date,weight_kg\n2026-07-31,100.5\n2026-08-01,100.0\n2026-08-02,99.5\n"
    )


def test_save_weight_rejects_future_date(client):
    response = client.post(
        "/weights",
        data={"date": "2026-08-04", "weight": "99.0"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Measurement date cannot be in the future." in response.data
    assert b"2026-08-04,99.0" not in app_module.WEIGHT_CSV.read_bytes()


def test_plotly_runtime_is_served_locally_and_cached(client):
    response = client.get("/plotly.min.js")

    assert response.status_code == 200
    assert response.mimetype == "text/javascript"
    assert response.cache_control.max_age == 31_536_000
    assert response.cache_control.immutable
    assert len(response.data) > 1_000_000


def test_png_plot_endpoint_is_removed(client):
    assert client.get("/plot.png").status_code == 404
