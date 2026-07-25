from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, redirect, render_template, request, url_for

from interactive_plot import (
    PLOTLY_CONFIG,
    build_insights_figure,
    build_interactive_figure,
    plotly_javascript,
)
from weight_data import parse_weight, read_series, store_weight

BASE_DIR = Path(__file__).parent
WEIGHT_CSV = BASE_DIR / "weight.csv"
PLAN_CSV = BASE_DIR / "plan.csv"
COPENHAGEN = ZoneInfo("Europe/Copenhagen")
PLOTLY_VERSION = version("plotly")

app = Flask(__name__)


@app.get("/")
def index():
    dates, weights = read_series(WEIGHT_CSV)
    plan_dates, plan = read_series(PLAN_CSV)
    latest = None
    if dates:
        latest = {"date": dates[-1], "weight": weights[-1]}

    figure = build_interactive_figure(dates, weights, plan_dates, plan)
    insights_figure = build_insights_figure(dates, weights, plan_dates, plan)
    return render_template(
        "index.html",
        latest=latest,
        saved=request.args.get("saved"),
        error=request.args.get("error"),
        graph_json=figure.to_json(),
        insights_json=insights_figure.to_json(),
        plotly_config=PLOTLY_CONFIG,
        plotly_version=PLOTLY_VERSION,
    )


@app.post("/weights")
def save_weight():
    try:
        weight = parse_weight(request.form.get("weight"))
        store_weight(WEIGHT_CSV, datetime.now(COPENHAGEN).date(), weight)
    except ValueError as error:
        return redirect(url_for("index", error=str(error)))
    return redirect(url_for("index", saved=format(weight, "f")))


@app.get("/plotly.min.js")
def plotly_runtime():
    return Response(
        plotly_javascript(),
        mimetype="text/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
