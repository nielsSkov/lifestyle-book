import hashlib
import json
import math
from datetime import date, datetime, timedelta
from importlib.metadata import version
from io import BytesIO
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

from achievement_catalog import ACHIEVEMENTS, configured_achievements
from daily_data import (
    parse_daily_date,
    read_daily_records,
    store_daily_achievement,
)
from daily_plot import build_active_days_figure, build_daily_figure
from lifestyle_config import LifestyleSettings, load_lifestyle_settings, store_lifestyle_settings
from plan_apply import ParsedInterval, merge_plan_intervals, store_active_plan, store_uploaded_plan
from plan_backup import (
    consolidate_plan_backups,
    list_plan_backups,
    protect_plan_update,
    read_plan_backup,
    restore_plan_backup,
)
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
    read_series_bytes,
    store_weight,
    validate_csv_bytes,
)
from weight_plotly import build_difference_figure, build_rate_figure, build_weight_figure

BASE_DIR = Path(__file__).parent
WEIGHT_CSV = BASE_DIR / "weight.csv"
PLAN_CSV = BASE_DIR / "plan.csv"
PLAN_BACKUP_DIRECTORY = BASE_DIR / "backups"
SLEEP_CSV = BASE_DIR / "data" / "sleep.csv"
DAILY_CSV = BASE_DIR / "data" / "daily.csv"
LIFESTYLE_CONFIG = BASE_DIR / "lifestyle.local.json"
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
PLOTLY_VERSION = version("plotly")
DEFAULT_PLAN_DURATION_DAYS = 182
MAX_PLAN_UPLOAD_BYTES = 2 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_PLAN_UPLOAD_BYTES + 64 * 1024
app.config["LIFESTYLE_SETTINGS"] = load_lifestyle_settings(LIFESTYLE_CONFIG)


def lifestyle_settings() -> LifestyleSettings:
    settings = app.config["LIFESTYLE_SETTINGS"]
    if not isinstance(settings, LifestyleSettings):
        raise TypeError("Expected LifestyleSettings in application configuration")
    return settings


@app.context_processor
def site_identity() -> dict[str, str]:
    return {"record_subtitle": lifestyle_settings().record_subtitle}


@app.errorhandler(RequestEntityTooLarge)
def upload_too_large(_error):
    if request.path.startswith("/weight/plan/upload-"):
        return jsonify(error="Plan CSV must be 2 MB or smaller"), 413
    return Response("Request too large", status=413)


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
    try:
        plan_contents = PLAN_CSV.read_bytes()
    except FileNotFoundError:
        plan_contents = b""
    active_plan_revision = hashlib.sha256(plan_contents).hexdigest()
    active_plan_error = None
    try:
        plan_dates, plan = read_series_bytes(plan_contents) if plan_contents else ([], [])
    except (KeyError, UnicodeError, ValueError):
        plan_dates, plan = [], []
        active_plan_error = "The active plan cannot be read. Restore a backup below."
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
        15,
        1,
        MAX_PLAN_DURATION_DAYS,
    )
    figure = build_weight_figure(
        weight_dates,
        weights,
        plan_dates,
        plan,
    )
    consolidate_plan_backups(PLAN_BACKUP_DIRECTORY, active_plan_path=PLAN_CSV)
    backups = [
        {
            "name": backup.name,
            "created_label": backup.created_at.astimezone(COPENHAGEN).strftime(
                "%d %b %Y, %H:%M:%S %Z"
            ),
            "size_label": f"{backup.size / 1024:.1f} KB",
            "revision": backup.revision,
        }
        for backup in list_plan_backups(PLAN_BACKUP_DIRECTORY)
    ]
    return render_template(
        "weight_plan.html",
        active_section="weight-plan",
        today=current_date(),
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
        plan_backups=backups,
        active_plan_revision=active_plan_revision,
        active_plan_error=active_plan_error,
    )


@app.get("/weight/plan/download")
def download_weight_plan():
    try:
        contents = PLAN_CSV.read_bytes()
    except FileNotFoundError:
        abort(404, "No active weight plan is available")
    return send_file(
        BytesIO(contents),
        mimetype="text/csv",
        as_attachment=True,
        download_name="plan.csv",
        max_age=0,
    )


@app.post("/weight/plan/preview")
def preview_weight_plan():
    try:
        parsed_intervals = _parse_candidate_request(request.get_json(silent=True))
        weight_dates, weights = read_series(WEIGHT_CSV)
        try:
            plan_contents = PLAN_CSV.read_bytes()
        except FileNotFoundError:
            plan_contents = b""
        plan_dates, plan = read_series_bytes(plan_contents) if plan_contents else ([], [])
        candidate_dates, candidate_plan, erase_intervals, summaries = _build_candidate_intervals(
            parsed_intervals
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
        erase_intervals,
    )
    return jsonify(
        figure=json.loads(cast(str, figure.to_json())),
        intervals=summaries,
        revision=hashlib.sha256(plan_contents).hexdigest(),
    )


@app.post("/weight/plan/apply")
def apply_weight_plan():
    try:
        payload = request.get_json(silent=True)
        parsed_intervals = _parse_candidate_request(payload)
        revision = payload.get("revision") if isinstance(payload, dict) else None
        if not isinstance(revision, str):
            raise ValueError("Preview the candidate before applying it")
        with protect_plan_update(
            PLAN_CSV, PLAN_BACKUP_DIRECTORY, expected_revision=revision
        ) as backup:
            plan_dates, plan = read_series(PLAN_CSV)
            merged_dates, merged_plan = merge_plan_intervals(plan_dates, plan, parsed_intervals)
            store_active_plan(PLAN_CSV, merged_dates, merged_plan)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        app.logger.exception("Could not apply weight plan")
        return jsonify(error="Could not safely apply the plan"), 500
    return jsonify(
        message="Candidate changes applied",
        backup=backup.name if backup else None,
    )


@app.post("/weight/plan/restore")
def restore_weight_plan():
    payload = request.get_json(silent=True)
    backup_name = payload.get("backup") if isinstance(payload, dict) else None
    revision = payload.get("revision") if isinstance(payload, dict) else None
    backup_revision = payload.get("backup_revision") if isinstance(payload, dict) else None
    if (
        not isinstance(backup_name, str)
        or not isinstance(revision, str)
        or not isinstance(backup_revision, str)
    ):
        return jsonify(error="Choose a valid plan backup"), 400
    try:
        current_backup = restore_plan_backup(
            PLAN_CSV,
            PLAN_BACKUP_DIRECTORY,
            backup_name,
            expected_revision=revision,
            expected_backup_revision=backup_revision,
        )
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        app.logger.exception("Could not restore weight plan backup")
        return jsonify(error="Could not safely restore the plan backup"), 500
    return jsonify(
        message="Plan backup restored",
        current_backup=current_backup.name if current_backup else None,
    )


@app.post("/weight/plan/backup-preview")
def preview_weight_plan_backup():
    payload = request.get_json(silent=True)
    backup_name = payload.get("backup") if isinstance(payload, dict) else None
    backup_revision = payload.get("backup_revision") if isinstance(payload, dict) else None
    if not isinstance(backup_name, str) or not isinstance(backup_revision, str):
        return jsonify(error="Choose a valid plan backup"), 400
    try:
        contents = read_plan_backup(
            PLAN_BACKUP_DIRECTORY,
            backup_name,
            expected_revision=backup_revision,
        )
        backup_dates, backup_plan = read_series_bytes(contents)
        weight_dates, weights = read_series(WEIGHT_CSV)
        try:
            plan_dates, plan = read_series(PLAN_CSV)
        except (KeyError, UnicodeError, ValueError):
            plan_dates, plan = [], []
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        app.logger.exception("Could not preview weight plan backup")
        return jsonify(error="Could not preview the plan backup"), 500
    figure = build_weight_figure(
        weight_dates,
        weights,
        plan_dates,
        plan,
        backup_dates,
        backup_plan,
    )
    return jsonify(figure=json.loads(cast(str, figure.to_json())))


@app.post("/weight/plan/upload-preview")
def preview_uploaded_weight_plan():
    try:
        contents, filename = _uploaded_plan()
        row_count = validate_csv_bytes(contents, allow_gaps=True)
        upload_dates, upload_plan = read_series_bytes(contents)
        weight_dates, weights = read_series(WEIGHT_CSV)
        plan_dates, plan, active_contents = _read_active_plan_for_preview()
    except ValueError as error:
        return jsonify(error=str(error)), 400
    figure = build_weight_figure(
        weight_dates,
        weights,
        plan_dates,
        plan,
        upload_dates,
        upload_plan,
    )
    return jsonify(
        figure=json.loads(cast(str, figure.to_json())),
        filename=filename,
        row_count=row_count,
        start_date=upload_dates[0].strftime("%d %b %Y"),
        end_date=upload_dates[-1].strftime("%d %b %Y"),
        gap_count=sum(math.isnan(weight) for weight in upload_plan),
        upload_revision=hashlib.sha256(contents).hexdigest(),
        active_revision=hashlib.sha256(active_contents).hexdigest(),
    )


@app.post("/weight/plan/upload-apply")
def apply_uploaded_weight_plan():
    try:
        contents, _filename = _uploaded_plan()
        upload_revision = request.form.get("upload_revision")
        active_revision = request.form.get("active_revision")
        if not upload_revision or hashlib.sha256(contents).hexdigest() != upload_revision:
            raise ValueError("The selected file changed. Preview it again before importing.")
        if not active_revision:
            raise ValueError("Preview the uploaded plan before importing it")
        validate_csv_bytes(contents, allow_gaps=True)
        with protect_plan_update(
            PLAN_CSV,
            PLAN_BACKUP_DIRECTORY,
            expected_revision=active_revision,
            validate_backup=False,
        ) as backup:
            store_uploaded_plan(PLAN_CSV, contents)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        app.logger.exception("Could not import uploaded weight plan")
        return jsonify(error="Could not safely import the uploaded plan"), 500
    return jsonify(
        message="Uploaded plan imported",
        backup=backup.name if backup else None,
    )


@app.post("/weight/plan/defaults")
def weight_plan_defaults():
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ValueError("Choose a valid start date")
        start_date = _parse_planning_start_date(payload.get("start_date"))
        plan_dates, plan = read_series(PLAN_CSV)
        start_weight = _default_planning_weight(
            start_date,
            plan_dates,
            plan,
        )
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(
        start_weight=start_weight,
        target_weight=start_weight,
        duration_days=DEFAULT_PLAN_DURATION_DAYS,
        taper=0.0,
    )


def _uploaded_plan() -> tuple[bytes, str]:
    upload = request.files.get("plan")
    if upload is None or not upload.filename:
        raise ValueError("Choose a plan CSV file")
    if not upload.filename.lower().endswith(".csv"):
        raise ValueError("Choose a CSV file")
    contents = upload.stream.read(MAX_PLAN_UPLOAD_BYTES + 1)
    if len(contents) > MAX_PLAN_UPLOAD_BYTES:
        raise ValueError("Plan CSV must be 2 MB or smaller")
    return contents, Path(upload.filename).name


def _read_active_plan_for_preview() -> tuple[list[date], list[float], bytes]:
    try:
        contents = PLAN_CSV.read_bytes()
    except FileNotFoundError:
        return [], [], b""
    try:
        dates, plan = read_series_bytes(contents)
    except (KeyError, UnicodeError, ValueError):
        return [], [], contents
    return dates, plan, contents


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
            if _wants_json():
                return _weight_json_response(
                    measurement_date,
                    f"Deleted entry for {measurement_date:%d %b %Y}",
                )
            return redirect(
                url_for(
                    "weight",
                    date=measurement_date.isoformat(),
                    deleted=measurement_date.strftime("%d %b %Y"),
                )
            )
        weight = parse_weight(raw_weight)
        store_weight(WEIGHT_CSV, measurement_date, weight)
    except ValueError as error:
        if _wants_json():
            return jsonify(error=str(error)), 400
        return redirect(url_for("weight", date=raw_date, error=str(error)))
    if _wants_json():
        return _weight_json_response(measurement_date, f"Saved {weight} kg")
    return redirect(url_for("weight", date=measurement_date.isoformat(), saved=format(weight, "f")))


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
    plan_dates: list[date],
    plan: list[float],
) -> float:
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


def _parse_candidate_interval(
    raw_interval: object,
) -> tuple[date, date, list[date] | None, list[float] | None, bool]:
    if not isinstance(raw_interval, dict):
        raise ValueError("Enter valid interval values")
    erase = raw_interval.get("erase", False)
    if not isinstance(erase, bool):
        raise ValueError("Erase must be true or false")
    if not erase:
        start_date, start_weight, target_weight, duration_days, taper = _parse_planning_preview(
            raw_interval
        )
        interval_dates, interval_weights = build_plan_interval(
            start_date, start_weight, target_weight, duration_days, taper
        )
        return start_date, interval_dates[-1], interval_dates, interval_weights, False

    start_date = _parse_planning_start_date(raw_interval.get("start_date"))
    duration_days = raw_interval.get("duration_days")
    if (
        isinstance(duration_days, bool)
        or not isinstance(duration_days, int)
        or not 1 <= duration_days <= MAX_PLAN_DURATION_DAYS
    ):
        raise ValueError(f"Duration must be between 1 and {MAX_PLAN_DURATION_DAYS} days")
    try:
        end_date = start_date + timedelta(days=duration_days)
    except OverflowError:
        raise ValueError("Interval end date is outside the supported date range") from None
    return start_date, end_date, None, None, True


def _parse_candidate_request(payload: object) -> list[ParsedInterval]:
    if not isinstance(payload, dict):
        raise ValueError("Enter valid planning values")
    raw_intervals = payload.get("intervals")
    if not isinstance(raw_intervals, list) or not raw_intervals:
        raise ValueError("Add at least one complete interval")
    if len(raw_intervals) > 20:
        raise ValueError("Add no more than 20 intervals")
    parsed = sorted(
        (_parse_candidate_interval(interval) for interval in raw_intervals),
        key=lambda interval: interval[0],
    )
    previous_end = None
    for start_date, end_date, *_rest in parsed:
        if previous_end is not None and start_date <= previous_end:
            raise ValueError("Planning intervals cannot overlap")
        previous_end = end_date
    return parsed


def _build_candidate_intervals(
    parsed_intervals: list[ParsedInterval],
) -> tuple[list[date], list[float], list[tuple[date, date]], list[dict[str, object]]]:
    candidate_dates: list[date] = []
    candidate_weights: list[float] = []
    erase_intervals: list[tuple[date, date]] = []
    summaries: list[dict[str, object]] = []
    previous_weight_end: date | None = None
    for start_date, end_date, interval_dates, interval_weights, erase in parsed_intervals:
        weekly_change = None
        if erase:
            if previous_weight_end is not None:
                candidate_dates.append(start_date)
                candidate_weights.append(math.nan)
            erase_intervals.append((start_date, end_date))
            previous_weight_end = None
        else:
            assert interval_dates is not None
            assert interval_weights is not None
            if previous_weight_end is not None and start_date > previous_weight_end + timedelta(
                days=1
            ):
                candidate_dates.append(previous_weight_end + timedelta(days=1))
                candidate_weights.append(math.nan)
            candidate_dates.extend(interval_dates)
            candidate_weights.extend(interval_weights)
            previous_weight_end = end_date
            weekly_change = (
                (interval_weights[-1] - interval_weights[0]) * 7 / (len(interval_dates) - 1)
            )
        summaries.append(
            {
                "start_date_label": start_date.strftime("%d %b %Y"),
                "end_date": end_date.isoformat(),
                "end_date_label": end_date.strftime("%d %b %Y"),
                "weekly_change": weekly_change,
                "erase": erase,
            }
        )
    return candidate_dates, candidate_weights, erase_intervals, summaries


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
