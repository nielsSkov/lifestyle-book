import io
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, redirect, render_template, request, send_file, url_for
from matplotlib.backends.backend_agg import FigureCanvasAgg

from weight_data import parse_weight, read_series, store_weight
from weight_plot import build_figure, period_bounds

BASE_DIR = Path(__file__).parent
WEIGHT_CSV = BASE_DIR / "weight.csv"
PLAN_CSV = BASE_DIR / "plan.csv"
COPENHAGEN = ZoneInfo("Europe/Copenhagen")

app = Flask(__name__)


def get_period():
    try:
        return max(0, min(int(request.args.get("period", 0)), 100))
    except ValueError:
        return 0


def get_window():
    window = request.args.get("window", "1y")
    return window if window in ("7d", "4w", "1y", "all") else "1y"


@app.get("/")
def index():
    dates, weights = read_series(WEIGHT_CSV)
    plan_dates, _ = read_series(PLAN_CSV)
    all_dates = dates + plan_dates
    period = get_period()
    window = get_window()
    today = datetime.now(COPENHAGEN).date()
    period_start, period_end = period_bounds(window, period, all_dates, today)
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
    today = datetime.now(COPENHAGEN).date()
    period_start, period_end = period_bounds(window, get_period(), weight_dates + plan_dates, today)
    figure = build_figure(
        weight_dates,
        weights,
        plan_dates,
        plan,
        period_start,
        period_end,
        mobile,
    )

    image = io.BytesIO()
    FigureCanvasAgg(figure).print_png(image)
    image.seek(0)
    return send_file(image, mimetype="image/png", max_age=0)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
