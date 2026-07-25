import csv
import io
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
from flask import Flask, redirect, render_template, request, send_file, url_for
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

BASE_DIR = Path(__file__).parent
WEIGHT_CSV = BASE_DIR / "weight.csv"
PLAN_CSV = BASE_DIR / "plan.csv"
COPENHAGEN = ZoneInfo("Europe/Copenhagen")

app = Flask(__name__)


def parse_weight(raw_value):
    try:
        weight = Decimal(raw_value)
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid weight.") from None

    if not weight.is_finite() or not Decimal("30") <= weight <= Decimal("300"):
        raise ValueError("Weight must be between 30 and 300 kg.")
    return weight


def read_series(path):
    if not path.exists():
        return [], []

    dates = []
    weights = []
    with path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            dates.append(date.fromisoformat(row["date"]))
            weights.append(float(row["weight_kg"]))
    return dates, weights


def shift_year(day, years):
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def get_period():
    try:
        return max(0, min(int(request.args.get("period", 0)), 100))
    except ValueError:
        return 0


def get_window():
    window = request.args.get("window", "1y")
    return window if window in ("7d", "4w", "1y", "all") else "1y"


def period_bounds(window, period, all_dates=None, today=None):
    today = today or datetime.now(COPENHAGEN).date()
    if window == "all":
        return (min(all_dates), max(all_dates)) if all_dates else (today - timedelta(days=1), today)
    if window == "7d":
        end = today - timedelta(days=7 * period)
        return end - timedelta(days=6), end
    if window == "4w":
        end = today - timedelta(days=28 * period)
        return end - timedelta(days=27), end

    end = shift_year(today, -period)
    return shift_year(end, -1), end


def within_period(dates, weights, start, end):
    points = [
        (day, weight) for day, weight in zip(dates, weights, strict=True) if start <= day <= end
    ]
    return [point[0] for point in points], [point[1] for point in points]


def store_weight(path, measurement_date, weight):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as csv_file:
            rows = [(row["date"], row["weight_kg"]) for row in csv.DictReader(csv_file)]

    day = measurement_date.isoformat()
    replacement = (day, format(weight, "f"))
    for index, row in enumerate(rows):
        if row[0] == day:
            rows[index] = replacement
            break
    else:
        rows.append(replacement)

    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(("date", "weight_kg"))
            writer.writerows(rows)
            csv_file.flush()
            os.fsync(csv_file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@app.get("/")
def index():
    dates, weights = read_series(WEIGHT_CSV)
    plan_dates, _ = read_series(PLAN_CSV)
    all_dates = dates + plan_dates
    period = get_period()
    window = get_window()
    period_start, period_end = period_bounds(window, period, all_dates)
    latest = None
    if dates:
        latest = {"date": dates[-1], "weight": weights[-1]}

    versions = [path.stat().st_mtime_ns for path in (WEIGHT_CSV, PLAN_CSV) if path.exists()]
    return render_template(
        "index.html",
        latest=latest,
        saved=request.args.get("saved"),
        error=request.args.get("error"),
        graph_version=max(versions, default=0),
        period=period,
        window=window,
        period_start=period_start,
        period_end=period_end,
        can_go_back=window != "all" and bool(all_dates and min(all_dates) < period_start),
    )


@app.post("/weights")
def save_weight():
    try:
        weight = parse_weight(request.form.get("weight"))
        store_weight(WEIGHT_CSV, datetime.now(COPENHAGEN).date(), weight)
    except ValueError as error:
        return redirect(url_for("index", error=str(error)))
    return redirect(url_for("index", saved=format(weight, "f")))


@app.get("/plot.png")
def plot():
    weight_dates, weights = read_series(WEIGHT_CSV)
    plan_dates, plan = read_series(PLAN_CSV)
    window = get_window()
    mobile = request.args.get("mobile") == "1"
    period_start, period_end = period_bounds(window, get_period(), weight_dates + plan_dates)
    weight_dates, weights = within_period(weight_dates, weights, period_start, period_end)
    plan_dates, plan = within_period(plan_dates, plan, period_start, period_end)

    figure = Figure(
        figsize=(7, 7) if mobile else (12, 6),
        layout="constrained",
        facecolor="#15111f",
    )
    axis = figure.subplots()
    axis.set_facecolor("#15111f")
    axis.grid(color="#383047", linewidth=0.8)
    axis.tick_params(colors="#bbb3c9")
    for spine in axis.spines.values():
        spine.set_color("#524762")

    if plan_dates:
        axis.plot(plan_dates, plan, color="#087044", linewidth=2.8, label="Plan")
    if weight_dates:
        axis.plot(weight_dates, weights, color="#8b5cf6", linewidth=1.8, label="Recorded weight")
        axis.scatter(weight_dates[-1], weights[-1], color="#8b5cf6", s=35, zorder=3)
        axis.annotate(
            f"{weights[-1]:.1f} kg",
            (weight_dates[-1], weights[-1]),
            xytext=(8, 8),
            textcoords="offset points",
            color="#a78bfa",
            fontweight="bold",
        )

    axis.set_title("Recorded Weight and Plan", color="#f4f0fa")
    axis.set_xlabel("Date", color="#bbb3c9")
    axis.set_ylabel("Weight (kg)", color="#bbb3c9")
    axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=6 if mobile else 10))
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(axis.xaxis.get_major_locator()))
    axis.set_xlim(mdates.date2num(period_start), mdates.date2num(period_end))
    if weight_dates or plan_dates:
        axis.legend(frameon=False, labelcolor="#ded8e8")
        axis.margins(x=0.015, y=0.08)

    image = io.BytesIO()
    FigureCanvasAgg(figure).print_png(image)
    image.seek(0)
    return send_file(image, mimetype="image/png", max_age=0)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
