import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from IPython.display import HTML, display
from matplotlib import pyplot
from matplotlib.axes import Axes

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from plan_model import interpolate_plan
from weight_data import read_series
from weight_plot import build_figure

ControlValue = float | Callable[[int], float]


def apply_notebook_style() -> None:
    css = (Path(__file__).parent / "notebook.css").read_text(encoding="utf-8")
    display(HTML(f"<style>{css}</style>"))


def load_planning_data() -> tuple[list[date], list[float], list[date], list[float]]:
    weight_dates, weights = read_series(PROJECT_DIR / "weight.csv")
    if not weight_dates:
        raise ValueError("weight.csv has no measurements; run uv run fetch_weight.py first")
    plan_dates, plan_weights = read_series(PROJECT_DIR / "plan.csv")
    return weight_dates, weights, plan_dates, plan_weights


def build_full_plan(
    existing_dates: Sequence[date],
    existing_weights: Sequence[float],
    control_points: Sequence[tuple[date, ControlValue]],
) -> tuple[list[date], list[float]]:
    candidate_dates, candidate_weights = interpolate_plan(control_points)
    historical_plan = [
        (day, weight)
        for day, weight in zip(existing_dates, existing_weights, strict=True)
        if day < candidate_dates[0]
    ]
    return (
        [day for day, _weight in historical_plan] + candidate_dates,
        [weight for _day, weight in historical_plan] + candidate_weights,
    )


def plot_plan(
    weight_dates: Sequence[date],
    weights: Sequence[float],
    plan_dates: Sequence[date],
    plan_weights: Sequence[float],
) -> Axes:
    all_dates = [*weight_dates, *plan_dates]
    if not all_dates:
        raise ValueError("Add recorded weights or plan points before plotting")
    figure = pyplot.figure(figsize=(12, 6), layout="constrained", facecolor="#15111f")
    for setting, value in {
        "header_visible": False,
        "footer_visible": False,
        "resizable": False,
        "toolbar_position": "bottom",
        "toolbar_visible": True,
    }.items():
        if hasattr(figure.canvas, setting):
            setattr(figure.canvas, setting, value)
    figure = build_figure(
        weight_dates,
        weights,
        plan_dates,
        plan_weights,
        min(all_dates),
        max(all_dates),
        figure=figure,
    )
    return figure.axes[0]
