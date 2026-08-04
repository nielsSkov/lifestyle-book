from datetime import date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, redirect, render_template, request, url_for

from interactive_plot import (
    PLOTLY_CONFIG,
    build_difference_figure,
    build_interactive_figure,
    build_rate_figure,
    plotly_javascript,
)
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
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
PLOTLY_VERSION = version("plotly")

app = Flask(__name__)


def current_date() -> date:
    return datetime.now(COPENHAGEN).date()


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
    return render_template(
        "section.html",
        active_section="sleep",
        section_title="Sleep",
        description="Sleep and wake times will live here",
    )


@app.get("/movement-food")
def movement_food():
    return render_template(
        "section.html",
        active_section="movement_food",
        section_title="Movement & Food",
        description="Everyday movement and food achievements will live here",
    )


@app.get("/plotly.min.js")
def plotly_runtime():
    return Response(
        plotly_javascript(),
        mimetype="text/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
