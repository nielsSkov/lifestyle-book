import json
from datetime import date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from daily_categories import DAILY_CATEGORIES, active_categories
from daily_data import (
    parse_daily_date,
    read_daily_records,
    store_daily_activity,
    store_daily_record,
)
from daily_plot import build_active_days_figure, build_daily_figure
from interactive_plot import (
    PLOTLY_CONFIG,
    build_difference_figure,
    build_interactive_figure,
    build_rate_figure,
    plotly_javascript,
)
from lifestyle_config import LifestyleSettings, load_lifestyle_settings, store_lifestyle_settings
from sleep_data import (
    build_sleep_record,
    delete_sleep,
    parse_night_start_date,
    parse_sleep_times,
    read_sleep_records,
    store_sleep,
)
from sleep_plot import build_sleep_figure
from weight_data import (
    delete_weight,
    parse_measurement_date,
    parse_weight,
    read_series,
    store_weight,
)

BASE_DIR = Path(__file__).parent
WEIGHT_CSV = BASE_DIR / "weight.csv"
PLAN_CSV = BASE_DIR / "plan.csv"
SLEEP_CSV = BASE_DIR / "data" / "sleep.csv"
DAILY_CSV = BASE_DIR / "data" / "daily.csv"
LIFESTYLE_CONFIG = BASE_DIR / "lifestyle.local.json"
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
PLOTLY_VERSION = version("plotly")

app = Flask(__name__)
app.config["LIFESTYLE_SETTINGS"] = load_lifestyle_settings(LIFESTYLE_CONFIG)


def lifestyle_settings() -> LifestyleSettings:
    settings = app.config["LIFESTYLE_SETTINGS"]
    if not isinstance(settings, LifestyleSettings):
        raise TypeError("Expected LifestyleSettings in application configuration")
    return settings


@app.context_processor
def site_identity() -> dict[str, str]:
    return {"record_subtitle": lifestyle_settings().record_subtitle}


def current_date() -> date:
    return datetime.now(COPENHAGEN).date()


def current_night_start() -> date:
    now = datetime.now(COPENHAGEN)
    return now.date() - timedelta(days=1) if now.hour < 12 else now.date()


@app.get("/")
def home():
    return redirect(url_for("weight"))


@app.get("/weight")
def weight():
    dates, weights = read_series(WEIGHT_CSV)
    plan_dates, plan = read_series(PLAN_CSV)
    today = current_date()
    try:
        selected_date = parse_measurement_date(request.args.get("date", today.isoformat()), today)
    except ValueError:
        selected_date = today
    latest = None
    if dates:
        latest = {"date": dates[-1], "weight": weights[-1]}

    figure = build_interactive_figure(dates, weights, plan_dates, plan)
    difference_figure = build_difference_figure(dates, weights, plan_dates, plan)
    rate_figure = build_rate_figure(dates, weights, plan_dates, plan)
    return render_template(
        "index.html",
        active_section="weight",
        latest=latest,
        today=today,
        selected_date=selected_date,
        weight_entries={
            day.isoformat(): weight for day, weight in zip(dates, weights, strict=True)
        },
        saved=request.args.get("saved"),
        deleted=request.args.get("deleted"),
        error=request.args.get("error"),
        graph_json=figure.to_json(),
        difference_json=difference_figure.to_json(),
        rate_json=rate_figure.to_json(),
        plotly_config=PLOTLY_CONFIG,
        plotly_version=PLOTLY_VERSION,
    )


@app.post("/weights")
def save_weight():
    raw_date = request.form.get("date")
    raw_weight = request.form.get("weight")
    try:
        today = current_date()
        measurement_date = parse_measurement_date(raw_date, today)
        if raw_weight is None or not raw_weight.strip():
            if not delete_weight(WEIGHT_CSV, measurement_date):
                raise ValueError("No measurement exists for this date")
            next_date = min(measurement_date + timedelta(days=1), today)
            return redirect(
                url_for(
                    "weight",
                    date=next_date.isoformat(),
                    deleted=measurement_date.strftime("%d %b %Y"),
                )
            )
        weight = parse_weight(raw_weight)
        store_weight(WEIGHT_CSV, measurement_date, weight)
    except ValueError as error:
        return redirect(url_for("weight", date=raw_date, error=str(error)))
    next_date = min(measurement_date + timedelta(days=1), today)
    return redirect(url_for("weight", date=next_date.isoformat(), saved=format(weight, "f")))


@app.get("/sleep")
def sleep():
    records = read_sleep_records(SLEEP_CSV)
    latest_night_start = current_night_start()
    try:
        selected_date = parse_night_start_date(
            request.args.get("date", latest_night_start.isoformat()),
            latest_night_start,
        )
    except ValueError:
        selected_date = latest_night_start
    figure = build_sleep_figure(records)
    return render_template(
        "sleep.html",
        active_section="sleep",
        latest_night_start=latest_night_start,
        selected_date=selected_date,
        sleep_entries={
            record.night_start_date.isoformat(): {
                "wake_time": (record.wake_at.strftime("%H:%M") if record.wake_at else None),
                "sleep_time": (record.sleep_at.strftime("%H:%M") if record.sleep_at else None),
            }
            for record in records
        },
        saved=request.args.get("saved"),
        deleted=request.args.get("deleted"),
        error=request.args.get("error"),
        graph_json=figure.to_json(),
        plotly_config=PLOTLY_CONFIG,
        plotly_version=PLOTLY_VERSION,
    )


@app.post("/sleep")
def save_sleep():
    raw_date = request.form.get("date")
    raw_sleep_time = request.form.get("sleep_time")
    raw_wake_time = request.form.get("wake_time")
    try:
        night_start_date = parse_night_start_date(raw_date, current_night_start())
        if not (raw_sleep_time or "").strip() and not (raw_wake_time or "").strip():
            if not delete_sleep(SLEEP_CSV, night_start_date):
                raise ValueError("No sleep record exists for this night")
            return redirect(
                url_for(
                    "sleep",
                    date=night_start_date.isoformat(),
                    deleted=night_start_date.isoformat(),
                )
            )
        wake_time, sleep_time = parse_sleep_times(raw_wake_time, raw_sleep_time)
        store_sleep(
            SLEEP_CSV,
            build_sleep_record(night_start_date, wake_time, sleep_time),
        )
    except ValueError as error:
        return redirect(url_for("sleep", date=raw_date, error=str(error)))
    return redirect(
        url_for(
            "sleep",
            date=night_start_date.isoformat(),
            saved=night_start_date.isoformat(),
        )
    )


@app.get("/daily")
def daily():
    categories = active_categories(lifestyle_settings().active_achievements)
    records = read_daily_records(DAILY_CSV)
    today = current_date()
    try:
        selected_date = parse_daily_date(request.args.get("date", today.isoformat()), today)
    except ValueError:
        selected_date = today
    figure = build_daily_figure(records, categories)
    active_days_figure = build_active_days_figure(records, DAILY_CATEGORIES)
    return render_template(
        "daily.html",
        active_section="daily",
        today=today,
        selected_date=selected_date,
        movement_categories=[category for category in categories if category.group == "movement"],
        food_categories=[category for category in categories if category.group == "food"],
        daily_entries={
            record.day.isoformat(): sorted(record.activities & {item.key for item in categories})
            for record in records
        },
        selected_activities=next(
            (record.activities for record in records if record.day == selected_date),
            frozenset(),
        ),
        saved=request.args.get("saved"),
        error=request.args.get("error"),
        graph_json=figure.to_json(),
        active_days_graph_json=active_days_figure.to_json(),
        plotly_config=PLOTLY_CONFIG,
        plotly_version=PLOTLY_VERSION,
    )


@app.post("/daily")
def save_daily():
    raw_date = request.form.get("date")
    try:
        selected_date = parse_daily_date(raw_date, current_date())
        categories = active_categories(lifestyle_settings().active_achievements)
        store_daily_record(
            DAILY_CSV,
            selected_date,
            request.form.getlist("activity"),
            [category.key for category in categories],
        )
    except ValueError as error:
        return redirect(url_for("daily", date=raw_date, error=str(error)))
    return redirect(
        url_for("daily", date=selected_date.isoformat(), saved=selected_date.isoformat())
    )


@app.post("/daily/activity")
def save_daily_activity():
    try:
        selected_date = parse_daily_date(request.form.get("date"), current_date())
        key = request.form.get("key", "")
        raw_selected = request.form.get("selected")
        if raw_selected not in {"true", "false"}:
            raise ValueError("Choose whether the achievement is selected")

        categories = active_categories(lifestyle_settings().active_achievements)
        active_keys = {category.key for category in categories}
        if key not in active_keys:
            raise ValueError("Achievement is not currently tracked")
        store_daily_activity(DAILY_CSV, selected_date, key, raw_selected == "true")

        records = read_daily_records(DAILY_CSV)
        record = next((item for item in records if item.day == selected_date), None)
        daily_figure = build_daily_figure(records, categories)
        active_days_figure = build_active_days_figure(records, DAILY_CATEGORIES)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error="Could not save achievement"), 500

    return jsonify(
        activities=sorted(record.activities & active_keys) if record else [],
        daily_figure=json.loads(cast(str, daily_figure.to_json())),
        active_days_figure=json.loads(cast(str, active_days_figure.to_json())),
    )


@app.get("/movement-food")
def movement_food():
    return redirect(url_for("daily"))


@app.get("/options")
def options():
    settings = lifestyle_settings()
    categories = active_categories(settings.active_achievements)
    active_keys = {category.key for category in categories}
    return render_template(
        "options.html",
        active_section="options",
        settings=settings,
        movement_categories=[
            category for category in DAILY_CATEGORIES if category.group == "movement"
        ],
        food_categories=[category for category in DAILY_CATEGORIES if category.group == "food"],
        active_keys=active_keys,
        saved=request.args.get("saved"),
        error=request.args.get("error"),
    )


@app.post("/options")
def save_options():
    raw_name = request.form.get("name", "").strip()
    selected_keys = request.form.getlist("active_achievement")
    try:
        if len(raw_name) > 80:
            raise ValueError("Name must be 80 characters or fewer")
        if len(selected_keys) != len(set(selected_keys)):
            raise ValueError("Each achievement can only be selected once")
        active_categories(selected_keys)
        ordered_keys = tuple(
            category.key for category in DAILY_CATEGORIES if category.key in selected_keys
        )
        settings = LifestyleSettings(raw_name or None, ordered_keys)
        store_lifestyle_settings(LIFESTYLE_CONFIG, settings)
        app.config["LIFESTYLE_SETTINGS"] = settings
    except ValueError as error:
        return redirect(url_for("options", error=str(error)))
    return redirect(url_for("options", saved="1"))


@app.post("/options/name")
def save_options_name():
    raw_name = request.form.get("name", "").strip()
    try:
        if len(raw_name) > 80:
            raise ValueError("Name must be 80 characters or fewer")
        current = lifestyle_settings()
        settings = LifestyleSettings(raw_name or None, current.active_achievements)
        store_lifestyle_settings(LIFESTYLE_CONFIG, settings)
        app.config["LIFESTYLE_SETTINGS"] = settings
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error="Could not save name"), 500
    return jsonify(record_subtitle=settings.record_subtitle)


@app.post("/options/achievement")
def save_options_achievement():
    key = request.form.get("key", "")
    raw_selected = request.form.get("selected")
    try:
        if raw_selected not in {"true", "false"}:
            raise ValueError("Choose whether the achievement is tracked")
        known_keys = {category.key for category in DAILY_CATEGORIES}
        if key not in known_keys:
            raise ValueError("Unknown achievement selected")

        current = lifestyle_settings()
        selected_keys = {
            category.key for category in active_categories(current.active_achievements)
        }
        if raw_selected == "true":
            selected_keys.add(key)
        else:
            selected_keys.discard(key)
        ordered_keys = tuple(
            category.key for category in DAILY_CATEGORIES if category.key in selected_keys
        )
        settings = LifestyleSettings(current.name, ordered_keys)
        store_lifestyle_settings(LIFESTYLE_CONFIG, settings)
        app.config["LIFESTYLE_SETTINGS"] = settings
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error="Could not save tracked achievement"), 500
    return jsonify(active_achievements=list(settings.active_achievements or ()))


@app.get("/plotly.min.js")
def plotly_runtime():
    return Response(
        plotly_javascript(),
        mimetype="text/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
