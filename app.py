from datetime import date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, redirect, render_template, request, url_for

from daily_categories import active_categories
from daily_data import parse_daily_date, read_daily_records, store_daily_record
from daily_plot import build_daily_figure
from interactive_plot import (
    PLOTLY_CONFIG,
    build_difference_figure,
    build_interactive_figure,
    build_rate_figure,
    plotly_javascript,
)
from lifestyle_config import load_record_subtitle
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
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
PLOTLY_VERSION = version("plotly")

app = Flask(__name__)
app.config["RECORD_SUBTITLE"] = load_record_subtitle(BASE_DIR / "lifestyle.local.json")


@app.context_processor
def site_identity() -> dict[str, str]:
    return {"record_subtitle": app.config["RECORD_SUBTITLE"]}


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
    today = current_date()
    try:
        selected_date = parse_night_start_date(
            request.args.get("date", current_night_start().isoformat()),
            today,
        )
    except ValueError:
        selected_date = today
    figure = build_sleep_figure(records)
    return render_template(
        "sleep.html",
        active_section="sleep",
        today=today,
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
        today = current_date()
        night_start_date = parse_night_start_date(raw_date, today)
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
    categories = active_categories()
    records = read_daily_records(DAILY_CSV)
    today = current_date()
    try:
        selected_date = parse_daily_date(request.args.get("date", today.isoformat()), today)
    except ValueError:
        selected_date = today
    figure = build_daily_figure(records, categories)
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
        plotly_config=PLOTLY_CONFIG,
        plotly_version=PLOTLY_VERSION,
    )


@app.post("/daily")
def save_daily():
    raw_date = request.form.get("date")
    try:
        selected_date = parse_daily_date(raw_date, current_date())
        categories = active_categories()
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


@app.get("/movement-food")
def movement_food():
    return redirect(url_for("daily"))


@app.get("/plotly.min.js")
def plotly_runtime():
    return Response(
        plotly_javascript(),
        mimetype="text/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
