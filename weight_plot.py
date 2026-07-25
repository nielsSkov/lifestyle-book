from collections.abc import Sequence
from datetime import date, timedelta

import matplotlib.dates as mdates
from matplotlib.figure import Figure


def shift_year(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def period_bounds(
    window: str,
    period: int,
    all_dates: Sequence[date] | None,
    today: date,
) -> tuple[date, date]:
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


def within_period(
    dates: Sequence[date],
    weights: Sequence[float],
    start: date,
    end: date,
) -> tuple[list[date], list[float]]:
    points = [
        (day, weight) for day, weight in zip(dates, weights, strict=True) if start <= day <= end
    ]
    return [point[0] for point in points], [point[1] for point in points]


def build_figure(
    weight_dates: Sequence[date],
    weights: Sequence[float],
    plan_dates: Sequence[date],
    plan: Sequence[float],
    period_start: date,
    period_end: date,
    mobile: bool = False,
) -> Figure:
    visible_weight_dates, visible_weights = within_period(
        weight_dates, weights, period_start, period_end
    )
    visible_plan_dates, visible_plan = within_period(plan_dates, plan, period_start, period_end)
    visible_weight_x = mdates.date2num(visible_weight_dates)
    visible_plan_x = mdates.date2num(visible_plan_dates)

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

    if visible_plan_dates:
        axis.plot(visible_plan_x, visible_plan, color="#087044", linewidth=2.8, label="Plan")
    if visible_weight_dates:
        axis.plot(
            visible_weight_x,
            visible_weights,
            color="#8b5cf6",
            linewidth=1.8,
            label="Recorded weight",
        )
        axis.scatter(visible_weight_x[-1], visible_weights[-1], color="#8b5cf6", s=35, zorder=3)
        axis.annotate(
            f"{visible_weights[-1]:.1f} kg",
            (visible_weight_x[-1], visible_weights[-1]),
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
    axis.set_xlim(float(mdates.date2num(period_start)), float(mdates.date2num(period_end)))
    if visible_weight_dates or visible_plan_dates:
        axis.legend(frameon=False, labelcolor="#ded8e8")
        axis.margins(x=0.015, y=0.08)

    return figure
