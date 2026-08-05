from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

import app as app_module
from daily_data import DailyRecord, read_daily_records
from lifestyle_config import LifestyleSettings, load_lifestyle_settings
from sleep_data import SleepRecord, read_sleep_records, store_sleep
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
    monkeypatch.setattr(app_module, "SLEEP_CSV", tmp_path / "data" / "sleep.csv")
    monkeypatch.setattr(app_module, "DAILY_CSV", tmp_path / "data" / "daily.csv")
    monkeypatch.setattr(app_module, "LIFESTYLE_CONFIG", tmp_path / "lifestyle.local.json")
    monkeypatch.setattr(app_module, "current_date", lambda: date(2026, 8, 3))
    monkeypatch.setattr(app_module, "current_night_start", lambda: date(2026, 8, 2))
    app_module.app.config.update(TESTING=True)
    app_module.app.config["LIFESTYLE_SETTINGS"] = LifestyleSettings()
    return app_module.app.test_client()


def redirect_parameters(response, expected_path: str = "/weight") -> dict[str, list[str]]:
    assert response.status_code == 302
    location = urlparse(response.headers["Location"])
    assert location.path == expected_path
    return parse_qs(location.query)


def test_weight_page_exposes_entry_controls_and_chart_regions(client):
    response = client.get("/weight")

    assert response.status_code == 200
    assert b'<html lang="en-US">' in response.data
    assert b"<small data-record-subtitle>Everyday log</small>" in response.data
    assert b'href="/options" aria-label="Options"' in response.data
    assert b'<nav class="section-tabs" aria-label=' in response.data
    assert b'href="/weight" aria-current="page"' in response.data
    assert b'href="/sleep"' in response.data
    assert b'href="/daily"' in response.data
    assert response.data.count(b'aria-current="page"') == 1
    assert b'id="previous-date"' in response.data
    assert b'id="next-date"' in response.data
    assert b'aria-live="polite"' in response.data
    assert b'name="date"' in response.data
    assert b'value="2026-08-03"' in response.data
    assert b'max="2026-08-03"' in response.data
    assert b'id="weight-plot"' in response.data
    assert b'id="difference-plot"' in response.data
    assert b'id="rate-plot"' in response.data
    assert b"data-weight-form" in response.data


def test_home_redirects_to_weight(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/weight"


def test_daily_route_sets_active_navigation_and_exposes_categories(client):
    response = client.get("/daily")

    assert response.status_code == 200
    assert b'href="/daily" aria-current="page"' in response.data
    assert response.data.count(b'aria-current="page"') == 1
    assert b'<p class="eyebrow">Daily</p>' in response.data
    assert b"<h1>Achievements</h1>" in response.data
    assert b'value="cycling"' in response.data
    assert b"<span>Bike</span>" in response.data
    assert b'value="other_activity"' in response.data
    assert b'value="roller_skate"' not in response.data
    assert b'id="active-days-plot"' in response.data
    assert b'id="daily-plot"' in response.data
    assert b"Save Day" not in response.data


def test_options_page_shows_catalog_with_roller_skate_inactive(client):
    response = client.get("/options")

    assert response.status_code == 200
    assert b'href="/options" aria-label="Options" aria-current="page"' in response.data
    assert b'value="walk" data-option-achievement checked' in response.data
    assert b'value="other_activity" data-option-achievement checked' in response.data
    assert b'value="roller_skate" data-option-achievement>' in response.data
    assert b"Roller Skate" in response.data
    assert b"Save Name" in response.data
    assert b"Save Options" not in response.data


def test_save_options_personalizes_log_and_changes_daily_categories(client):
    response = client.post(
        "/options",
        data={
            "name": "Niels",
            "active_achievement": ["walk", "roller_skate", "cooked"],
        },
    )

    parameters = redirect_parameters(response, "/options")
    assert "saved" in parameters
    assert load_lifestyle_settings(app_module.LIFESTYLE_CONFIG) == LifestyleSettings(
        "Niels", ("walk", "roller_skate", "cooked")
    )
    page = client.get("/daily")
    assert b"<small data-record-subtitle>Niels&#39; log</small>" in page.data
    assert b'value="roller_skate"' in page.data
    assert b'value="run"' not in page.data


def test_save_options_rejects_unknown_achievement(client):
    response = client.post(
        "/options",
        data={"name": "Niels", "active_achievement": ["walk", "unknown"]},
    )

    assert "error" in redirect_parameters(response, "/options")
    assert not app_module.LIFESTYLE_CONFIG.exists()


def test_save_options_name_preserves_active_achievements_without_redirect(client):
    app_module.app.config["LIFESTYLE_SETTINGS"] = LifestyleSettings("Old Name", ("walk", "cooked"))

    response = client.post("/options/name", data={"name": "Niels"})

    assert response.status_code == 200
    assert response.json == {"record_subtitle": "Niels' log"}
    assert load_lifestyle_settings(app_module.LIFESTYLE_CONFIG) == LifestyleSettings(
        "Niels", ("walk", "cooked")
    )


def test_options_achievement_autosave_preserves_name_and_materializes_defaults(client):
    app_module.app.config["LIFESTYLE_SETTINGS"] = LifestyleSettings("Niels")

    response = client.post(
        "/options/achievement",
        data={"key": "roller_skate", "selected": "true"},
    )

    assert response.status_code == 200
    settings = load_lifestyle_settings(app_module.LIFESTYLE_CONFIG)
    assert settings.name == "Niels"
    assert settings.active_achievements is not None
    assert "roller_skate" in settings.active_achievements
    assert "walk" in settings.active_achievements


def test_options_achievement_autosave_rejects_unknown_key(client):
    response = client.post(
        "/options/achievement",
        data={"key": "unknown", "selected": "true"},
    )

    assert response.status_code == 400
    assert "error" in response.json
    assert not app_module.LIFESTYLE_CONFIG.exists()


def test_old_movement_food_route_redirects_to_daily(client):
    response = client.get("/movement-food")

    assert response.status_code == 302
    assert response.headers["Location"] == "/daily"


def test_save_daily_stays_on_date_and_records_selected_categories(client):
    response = client.post(
        "/daily",
        data={"date": "2026-08-02", "activity": ["walk", "cycling", "cooked"]},
    )

    parameters = redirect_parameters(response, "/daily")
    assert parameters["date"] == ["2026-08-02"]
    assert "saved" in parameters
    assert read_daily_records(app_module.DAILY_CSV) == [
        DailyRecord(date(2026, 8, 2), frozenset({"walk", "cycling", "cooked"}))
    ]


def test_save_daily_rejects_unknown_categories_without_changing_data(client):
    client.post("/daily", data={"date": "2026-08-02", "activity": "walk"})
    original = app_module.DAILY_CSV.read_bytes()

    response = client.post(
        "/daily",
        data={"date": "2026-08-02", "activity": ["walk", "unknown"]},
    )

    assert "error" in redirect_parameters(response, "/daily")
    assert app_module.DAILY_CSV.read_bytes() == original


def test_daily_activity_autosave_updates_one_achievement_without_redirect(client):
    response = client.post(
        "/daily/activity",
        data={"date": "2026-08-02", "key": "run", "selected": "true"},
    )

    assert response.status_code == 200
    assert response.json["activities"] == ["run"]
    assert response.json["active_days_figure"]["data"][0]["z"] == [[1]]
    assert read_daily_records(app_module.DAILY_CSV) == [
        DailyRecord(date(2026, 8, 2), frozenset({"run"}))
    ]


def test_daily_activity_autosave_rejects_untracked_achievement(client):
    response = client.post(
        "/daily/activity",
        data={"date": "2026-08-02", "key": "roller_skate", "selected": "true"},
    )

    assert response.status_code == 400
    assert "error" in response.json
    assert not app_module.DAILY_CSV.exists()


def test_daily_page_uses_nightly_record_sleep_heading(client):
    response = client.get("/sleep")

    assert b'<p class="eyebrow">Nightly record</p>' in response.data


def test_sleep_page_exposes_entry_controls_and_chart_region(client):
    response = client.get("/sleep")

    assert response.status_code == 200
    assert b'href="/sleep" aria-current="page"' in response.data
    assert b'name="sleep_time"' in response.data
    assert b'name="wake_time"' in response.data
    assert b'name="wake_time" type="time" lang="en-GB"' in response.data
    assert b"data-date-navigation" in response.data
    assert b"data-night-label" in response.data
    assert b'value="2026-08-02"' in response.data
    assert b'max="2026-08-02"' in response.data
    assert b'id="sleep-plot"' in response.data
    assert b"data-sleep-form" in response.data


def test_sleep_page_rejects_explicit_night_that_has_not_started(client):
    response = client.get("/sleep?date=2026-08-03")

    assert response.status_code == 200
    assert b'value="2026-08-02"' in response.data


def test_save_sleep_rejects_night_that_has_not_started(client):
    response = client.post(
        "/sleep",
        data={"date": "2026-08-03", "wake_time": "07:15", "sleep_time": "23:30"},
    )

    parameters = redirect_parameters(response, "/sleep")
    assert "error" in parameters
    assert not app_module.SLEEP_CSV.exists()


def test_save_sleep_accepts_wake_time_without_sleep_time(client):
    response = client.post(
        "/sleep",
        data={"date": "2026-08-01", "wake_time": "07:15", "sleep_time": ""},
    )

    parameters = redirect_parameters(response, "/sleep")
    assert parameters["date"] == ["2026-08-01"]
    assert "saved" in parameters
    assert read_sleep_records(app_module.SLEEP_CSV) == [
        SleepRecord(date(2026, 8, 1), wake_at=datetime(2026, 8, 2, 7, 15))
    ]


def test_save_sleep_json_updates_entries_and_figure_without_redirect(client):
    response = client.post(
        "/sleep",
        data={"date": "2026-08-01", "wake_time": "07:15", "sleep_time": "23:30"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json["message"] == "Saved sleep record"
    assert response.json["selected_date"] == "2026-08-01"
    assert response.json["entries"]["2026-08-01"] == {
        "sleep_time": "23:30",
        "wake_time": "07:15",
    }
    assert response.json["figure"]["data"]


def test_invalid_sleep_json_returns_error_without_redirect(client):
    response = client.post(
        "/sleep",
        data={"date": "2026-08-01", "wake_time": "invalid", "sleep_time": "23:30"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    assert "error" in response.json


def test_save_sleep_accepts_sleep_time_without_wake_time(client):
    response = client.post(
        "/sleep",
        data={"date": "2026-08-01", "wake_time": "", "sleep_time": "23:30"},
    )

    assert "saved" in redirect_parameters(response, "/sleep")
    assert read_sleep_records(app_module.SLEEP_CSV) == [
        SleepRecord(date(2026, 8, 1), sleep_at=datetime(2026, 8, 1, 23, 30))
    ]


def test_blank_sleep_times_delete_existing_night(client):
    store_sleep(
        app_module.SLEEP_CSV,
        SleepRecord(
            date(2026, 8, 1),
            sleep_at=datetime(2026, 8, 1, 23),
            wake_at=datetime(2026, 8, 2, 7),
        ),
    )

    response = client.post(
        "/sleep",
        data={"date": "2026-08-01", "sleep_time": "", "wake_time": ""},
    )

    parameters = redirect_parameters(response, "/sleep")
    assert parameters["date"] == ["2026-08-01"]
    assert "deleted" in parameters
    assert read_sleep_records(app_module.SLEEP_CSV) == []


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


def test_save_weight_json_updates_summary_and_figures_without_redirect(client):
    response = client.post(
        "/weights",
        data={"date": "2026-08-03", "weight": "99.4"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json["message"] == "Saved 99.4 kg"
    assert response.json["selected_date"] == "2026-08-03"
    assert response.json["entries"]["2026-08-03"] == 99.4
    assert response.json["latest"] == {
        "date": "2026-08-03",
        "date_label": "03 Aug 2026",
        "weight": 99.4,
    }
    assert response.json["figure"]["data"]
    assert "difference_figure" in response.json
    assert "rate_figure" in response.json


def test_invalid_weight_json_returns_error_without_redirect(client):
    response = client.post(
        "/weights",
        data={"date": "2026-08-03", "weight": "invalid"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    assert "error" in response.json


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
