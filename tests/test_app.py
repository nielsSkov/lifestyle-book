from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

import app as app_module
from weight_data import read_series


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


def redirect_parameters(response) -> dict[str, list[str]]:
    assert response.status_code == 302
    location = urlparse(response.headers["Location"])
    assert location.path == "/"
    return parse_qs(location.query)


def test_weight_page_exposes_entry_controls_and_chart_regions(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b'id="previous-date"' in response.data
    assert b'id="next-date"' in response.data
    assert b'aria-live="polite"' in response.data
    assert b'name="date"' in response.data
    assert b'value="2026-08-03"' in response.data
    assert b'max="2026-08-03"' in response.data
    assert b'id="weight-plot"' in response.data
    assert b'id="difference-plot"' in response.data
    assert b'id="rate-plot"' in response.data


def test_save_weight_inserts_historical_date_and_advances(client):
    response = client.post(
        "/weights",
        data={"date": "2026-07-31", "weight": "100.5"},
    )

    parameters = redirect_parameters(response)
    assert parameters["date"] == ["2026-08-01"]
    assert "saved" in parameters
    assert read_series(app_module.WEIGHT_CSV) == (
        [date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 2)],
        [100.5, 100.0, 99.5],
    )


def test_save_weight_rejects_future_date(client):
    original = app_module.WEIGHT_CSV.read_bytes()
    response = client.post(
        "/weights",
        data={"date": "2026-08-04", "weight": "99.0"},
    )

    assert "error" in redirect_parameters(response)
    assert app_module.WEIGHT_CSV.read_bytes() == original


def test_save_weight_accepts_comma_decimal_separator(client):
    response = client.post(
        "/weights",
        data={"date": "2026-08-03", "weight": "99,4"},
    )

    assert "saved" in redirect_parameters(response)
    dates, weights = read_series(app_module.WEIGHT_CSV)
    assert dates[-1] == date(2026, 8, 3)
    assert weights[-1] == 99.4


def test_invalid_weight_preserves_existing_data(client):
    original = app_module.WEIGHT_CSV.read_bytes()
    response = client.post(
        "/weights",
        data={"date": "2026-08-03", "weight": "29"},
    )

    assert "error" in redirect_parameters(response)
    assert app_module.WEIGHT_CSV.read_bytes() == original


def test_blank_weight_deletes_existing_date_and_advances(client):
    response = client.post(
        "/weights",
        data={"date": "2026-08-01", "weight": ""},
    )

    parameters = redirect_parameters(response)
    assert parameters["date"] == ["2026-08-02"]
    assert "deleted" in parameters
    assert read_series(app_module.WEIGHT_CSV) == ([date(2026, 8, 2)], [99.5])


def test_blank_weight_rejects_date_without_measurement(client):
    original = app_module.WEIGHT_CSV.read_bytes()
    response = client.post(
        "/weights",
        data={"date": "2026-07-31", "weight": ""},
    )

    assert "error" in redirect_parameters(response)
    assert app_module.WEIGHT_CSV.read_bytes() == original


def test_plotly_runtime_is_served_locally_and_cached(client):
    response = client.get("/plotly.min.js")

    assert response.status_code == 200
    assert response.mimetype == "text/javascript"
    assert response.cache_control.max_age == 31_536_000
    assert response.cache_control.immutable
    assert response.data
