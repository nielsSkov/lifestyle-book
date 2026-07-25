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
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def test_index_renders_interactive_plotly_chart(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b'id="weight-plot"' in response.data
    assert b"Plotly.newPlot" in response.data
    assert b'"name":"Recorded weight"' in response.data
    assert b'"y":[100.0,null,95.0]' in response.data
    assert b"range-picker" not in response.data
    assert b"graph-toolbar" not in response.data
    assert b"plot.png" not in response.data


def test_plotly_runtime_is_served_locally_and_cached(client):
    response = client.get("/plotly.min.js")

    assert response.status_code == 200
    assert response.mimetype == "text/javascript"
    assert response.cache_control.max_age == 31_536_000
    assert response.cache_control.immutable
    assert len(response.data) > 1_000_000


def test_png_plot_endpoint_is_removed(client):
    assert client.get("/plot.png").status_code == 404
