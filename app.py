import json
import math
from datetime import date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from achievement_catalog import ACHIEVEMENTS, configured_achievements
from daily_data import (
    parse_daily_date,
    read_daily_records,
    store_daily_achievement,
)
from daily_plot import build_active_days_figure, build_daily_figure
from lifestyle_config import LifestyleSettings, load_lifestyle_settings, store_lifestyle_settings
from plan_model import MAX_PLAN_DURATION_DAYS, MAX_TAPER, build_plan_interval
from plotly_support import PLOTLY_CONFIG, plotly_javascript
from sleep_data import (
    build_sleep_record,
    delete_sleep,
    parse_night_start_date,
    parse_sleep_times,
    read_sleep_records,
    store_sleep,
)
from sleep_plot import build_sleep_duration_figure, build_sleep_figure
from weight_data import (
    MAX_WEIGHT_KG,
    MIN_WEIGHT_KG,
    delete_weight,
    parse_measurement_date,
    parse_weight,
    read_series,
    store_weight,
)
from weight_plotly import build_difference_figure, build_rate_figure, build_weight_figure

BASE_DIR = Path(__file__).parent
WEIGHT_CSV = BASE_DIR / "weight.csv"
PLAN_CSV = BASE_DIR / "plan.csv"
SLEEP_CSV = BASE_DIR / "data" / "sleep.csv"
DAILY_CSV = BASE_DIR / "data" / "daily.csv"
LIFESTYLE_CONFIG = BASE_DIR / "lifestyle.local.json"
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
PLOTLY_VERSION = version("plotly")
DEFAULT_PLAN_DURATION_DAYS = 182

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

    figure, difference_figure, rate_figure, full_x_range = _build_weight_page_figures(
        dates,
        weights,
        plan_dates,
        plan,
    )
    return render_template(
        "weight.html",
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
        full_x_range=full_x_range,
        plotly_config=PLOTLY_CONFIG,
        plotly_version=PLOTLY_VERSION,
    )


@app.get("/weight/plan")
def weight_plan():
    weight_dates, weights = read_series(WEIGHT_CSV)
    plan_dates, plan = read_series(PLAN_CSV)
    start_weight = 100.0
    duration_days = DEFAULT_PLAN_DURATION_DAYS
    taper = 0.0
    weight_range_min, weight_range_max = _planning_slider_window(
        start_weight,
        10,
        MIN_WEIGHT_KG,
        MAX_WEIGHT_KG,
    )
    duration_range_min, duration_range_max = _planning_slider_window(
        duration_days,
        90,
        1,
        MAX_PLAN_DURATION_DAYS,
    )
    figure = build_weight_figure(
        weight_dates,
        weights,
        plan_dates,
        plan,
    )
    return render_template(
        "weight_plan.html",
        active_section="weight",
        start_weight=start_weight,
        duration_days=duration_days,
        taper=taper,
        graph_json=figure.to_json(),
        plotly_config=PLOTLY_CONFIG,
        plotly_version=PLOTLY_VERSION,
        max_duration_days=MAX_PLAN_DURATION_DAYS,
        max_taper=MAX_TAPER,
        min_weight=MIN_WEIGHT_KG,
        max_weight=MAX_WEIGHT_KG,
        weight_range_min=weight_range_min,
        weight_range_max=weight_range_max,
        duration_range_min=duration_range_min,
        duration_range_max=duration_range_max,
    )


@app.post("/weight/plan/preview")
def preview_weight_plan():
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ValueError("Enter valid planning values")
        weight_dates, weights = read_series(WEIGHT_CSV)
        plan_dates, plan = read_series(PLAN_CSV)
        if payload.get("initialize") is True:
            start_date = _parse_planning_start_date(payload.get("start_date"))
            start_weight = _default_planning_weight(
                start_date,
                weight_dates,
                weights,
                plan_dates,
                plan,
            )
            target_weight = start_weight
            duration_days = DEFAULT_PLAN_DURATION_DAYS
            taper = 0.0
        else:
            start_date, start_weight, target_weight, duration_days, taper = _parse_planning_preview(
                payload
            )
        candidate_dates, candidate_plan = build_plan_interval(
            start_date,
            start_weight,
            target_weight,
            duration_days,
            taper,
        )
    except ValueError as error:
        return jsonify(error=str(error)), 400

    figure = build_weight_figure(
        weight_dates,
        weights,
        plan_dates,
        plan,
        candidate_dates,
        candidate_plan,
    )
    return jsonify(
        figure=json.loads(cast(str, figure.to_json())),
        end_date=candidate_dates[-1].isoformat(),
        end_date_label=candidate_dates[-1].strftime("%d %b %Y"),
        weekly_change=(target_weight - start_weight) * 7 / duration_days,
        start_weight=start_weight,
        target_weight=target_weight,
        duration_days=duration_days,
        taper=taper,
    )


@app.post("/weight")
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
            if _wants_json():
                return _weight_json_response(
                    next_date,
                    f"Deleted entry for {measurement_date:%d %b %Y}",
                )
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
        if _wants_json():
            return jsonify(error=str(error)), 400
        return redirect(url_for("weight", date=raw_date, error=str(error)))
    next_date = min(measurement_date + timedelta(days=1), today)
    if _wants_json():
        return _weight_json_response(next_date, f"Saved {weight} kg")
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
    duration_figure = build_sleep_duration_figure(records)
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
        duration_graph_json=duration_figure.to_json(),
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
            if _wants_json():
                return _sleep_json_response(
                    night_start_date,
                    f"Deleted sleep record for {night_start_date.isoformat()}",
                )
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
        if _wants_json():
            return jsonify(error=str(error)), 400
        return redirect(url_for("sleep", date=raw_date, error=str(error)))
    if _wants_json():
        return _sleep_json_response(night_start_date, "Saved sleep record")
    return redirect(
        url_for(
            "sleep",
            date=night_start_date.isoformat(),
            saved=night_start_date.isoformat(),
        )
    )


def _wants_json() -> bool:
    return request.accept_mimetypes.best == "application/json"


def _default_planning_weight(
    start_date: date,
    weight_dates: list[date],
    weights: list[float],
    plan_dates: list[date],
    plan: list[float],
) -> float:
    for day, weight in reversed(list(zip(weight_dates, weights, strict=True))):
        age = (start_date - day).days
        if 0 <= age <= 7:
            return round(weight, 1)
        if age > 7:
            break

    planned_weight = dict(zip(plan_dates, plan, strict=True)).get(start_date)
    if planned_weight is not None and math.isfinite(planned_weight):
        return round(planned_weight, 1)
    return 100.0


def _planning_slider_window(
    value: float,
    radius: float,
    hard_minimum: float,
    hard_maximum: float,
) -> tuple[float, float]:
    minimum = max(hard_minimum, value - radius)
    maximum = min(hard_maximum, value + radius)
    if minimum == hard_minimum:
        maximum = min(hard_maximum, minimum + 2 * radius)
    if maximum == hard_maximum:
        minimum = max(hard_minimum, maximum - 2 * radius)
    return minimum, maximum


def _parse_planning_preview(payload: dict) -> tuple[date, float, float, int, float]:
    start_date = _parse_planning_start_date(payload.get("start_date"))
    start_weight = _planning_number(payload.get("start_weight"), "Starting weight")
    target_weight = _planning_number(payload.get("target_weight"), "Target weight")
    duration_days = payload.get("duration_days")
    if isinstance(duration_days, bool) or not isinstance(duration_days, int):
        raise ValueError("Duration must be a whole number of days")
    taper = _planning_number(payload.get("taper"), "Taper")
    return start_date, start_weight, target_weight, duration_days, taper


def _parse_planning_start_date(raw_start_date: object) -> date:
    try:
        if not isinstance(raw_start_date, str):
            raise ValueError
        return date.fromisoformat(raw_start_date)
    except ValueError:
        raise ValueError("Choose a valid start date") from None


def _planning_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a number")
    try:
        return float(value)
    except OverflowError:
        raise ValueError(f"{label} must be a number") from None


def _build_weight_page_figures(
    dates: list[date],
    weights: list[float],
    plan_dates: list[date],
    plan: list[float],
):
    figures = (
        build_weight_figure(dates, weights, plan_dates, plan),
        build_difference_figure(dates, weights, plan_dates, plan),
        build_rate_figure(dates, weights, plan_dates, plan),
    )
    all_dates = [*dates, *plan_dates]
    if not all_dates:
        return (*figures, [])

    first_date = min(all_dates)
    final_date = max(all_dates)
    padding_days = max(1, round((final_date - first_date).days * 0.02))
    full_range = [
        date.fromordinal(
            max(date.min.toordinal(), first_date.toordinal() - padding_days)
        ).isoformat(),
        date.fromordinal(
            min(date.max.toordinal(), final_date.toordinal() + padding_days)
        ).isoformat(),
    ]
    for figure in figures:
        figure.update_xaxes(range=full_range)
    return (*figures, full_range)


def _weight_json_response(selected_date: date, message: str):
    dates, weights = read_series(WEIGHT_CSV)
    plan_dates, plan = read_series(PLAN_CSV)
    latest = None
    if dates:
        latest = {
            "date": dates[-1].isoformat(),
            "date_label": dates[-1].strftime("%d %b %Y"),
            "weight": weights[-1],
        }
    figure, difference_figure, rate_figure, full_x_range = _build_weight_page_figures(
        dates,
        weights,
        plan_dates,
        plan,
    )
    return jsonify(
        message=message,
        selected_date=selected_date.isoformat(),
        entries={day.isoformat(): value for day, value in zip(dates, weights, strict=True)},
        latest=latest,
        figure=json.loads(cast(str, figure.to_json())),
        difference_figure=json.loads(cast(str, difference_figure.to_json())),
        rate_figure=json.loads(cast(str, rate_figure.to_json())),
        full_x_range=full_x_range,
    )


def _sleep_json_response(selected_date: date, message: str):
    records = read_sleep_records(SLEEP_CSV)
    return jsonify(
        message=message,
        selected_date=selected_date.isoformat(),
        entries={
            record.night_start_date.isoformat(): {
                "wake_time": (record.wake_at.strftime("%H:%M") if record.wake_at else None),
                "sleep_time": (record.sleep_at.strftime("%H:%M") if record.sleep_at else None),
            }
            for record in records
        },
        figure=json.loads(cast(str, build_sleep_figure(records).to_json())),
        duration_figure=json.loads(cast(str, build_sleep_duration_figure(records).to_json())),
    )


@app.get("/daily")
def daily():
    achievements = configured_achievements(lifestyle_settings().active_achievements)
    records = read_daily_records(DAILY_CSV)
    today = current_date()
    try:
        selected_date = parse_daily_date(request.args.get("date", today.isoformat()), today)
    except ValueError:
        selected_date = today
    figure = build_daily_figure(records, achievements)
    active_days_figure = build_active_days_figure(records, ACHIEVEMENTS)
    return render_template(
        "daily.html",
        active_section="daily",
        today=today,
        selected_date=selected_date,
        movement_achievements=[
            achievement for achievement in achievements if achievement.group == "movement"
        ],
        food_achievements=[
            achievement for achievement in achievements if achievement.group == "food"
        ],
        achievement_entries={
            record.day.isoformat(): sorted(
                record.achievements & {item.key for item in achievements}
            )
            for record in records
        },
        selected_achievements=next(
            (record.achievements for record in records if record.day == selected_date),
            frozenset(),
        ),
        graph_json=figure.to_json(),
        active_days_graph_json=active_days_figure.to_json(),
        plotly_config=PLOTLY_CONFIG,
        plotly_version=PLOTLY_VERSION,
    )


@app.post("/daily/achievement")
def save_daily_achievement():
    try:
        selected_date = parse_daily_date(request.form.get("date"), current_date())
        key = request.form.get("key", "")
        raw_selected = request.form.get("selected")
        if raw_selected not in {"true", "false"}:
            raise ValueError("Choose whether the achievement is selected")

        achievements = configured_achievements(lifestyle_settings().active_achievements)
        active_keys = {achievement.key for achievement in achievements}
        if key not in active_keys:
            raise ValueError("Achievement is not currently tracked")
        store_daily_achievement(DAILY_CSV, selected_date, key, raw_selected == "true")

        records = read_daily_records(DAILY_CSV)
        record = next((item for item in records if item.day == selected_date), None)
        daily_figure = build_daily_figure(records, achievements)
        active_days_figure = build_active_days_figure(records, ACHIEVEMENTS)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error="Could not save achievement"), 500

    return jsonify(
        achievements=sorted(record.achievements & active_keys) if record else [],
        daily_figure=json.loads(cast(str, daily_figure.to_json())),
        active_days_figure=json.loads(cast(str, active_days_figure.to_json())),
    )


@app.get("/options")
def options():
    settings = lifestyle_settings()
    achievements = configured_achievements(settings.active_achievements)
    active_keys = {achievement.key for achievement in achievements}
    return render_template(
        "options.html",
        active_section="options",
        settings=settings,
        movement_achievements=[
            achievement for achievement in ACHIEVEMENTS if achievement.group == "movement"
        ],
        food_achievements=[
            achievement for achievement in ACHIEVEMENTS if achievement.group == "food"
        ],
        active_keys=active_keys,
    )


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
        known_keys = {achievement.key for achievement in ACHIEVEMENTS}
        if key not in known_keys:
            raise ValueError("Unknown achievement selected")

        current = lifestyle_settings()
        selected_keys = {
            achievement.key for achievement in configured_achievements(current.active_achievements)
        }
        if raw_selected == "true":
            selected_keys.add(key)
        else:
            selected_keys.discard(key)
        ordered_keys = tuple(
            achievement.key for achievement in ACHIEVEMENTS if achievement.key in selected_keys
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
