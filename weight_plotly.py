import math
from collections.abc import Sequence
from datetime import date
from functools import cache

from plotly import graph_objects as go
from plotly.offline import get_plotlyjs

PLOTLY_CONFIG: dict[str, object] = {
    "displaylogo": False,
    "displayModeBar": True,
    "modeBarButtons": [["zoom2d", "pan2d", "resetScale2d"]],
    "responsive": True,
    "scrollZoom": True,
    "showTips": False,
}


@cache
def plotly_javascript() -> str:
    return get_plotlyjs()


def build_interactive_figure(
    weight_dates: Sequence[date],
    weights: Sequence[float],
    plan_dates: Sequence[date],
    plan: Sequence[float],
) -> go.Figure:
    weight_points = list(zip(weight_dates, weights, strict=True))
    plan_points = list(zip(plan_dates, plan, strict=True))
    figure = go.Figure()

    if plan_points:
        figure.add_trace(
            go.Scatter(
                x=[day for day, _weight in plan_points],
                y=[weight for _day, weight in plan_points],
                mode="lines",
                name="Plan",
                connectgaps=False,
                line={"color": "#087044", "width": 2.8},
                hovertemplate="%{x|%d %b %Y}<br>%{y:.1f} kg<extra>Plan</extra>",
            )
        )

    if weight_points:
        figure.add_trace(
            go.Scatter(
                x=[day for day, _weight in weight_points],
                y=[weight for _day, weight in weight_points],
                mode="lines",
                name="Recorded weight",
                line={"color": "#8b5cf6", "width": 1.8},
                hovertemplate=("%{x|%d %b %Y}<br>%{y:.1f} kg<extra>Recorded weight</extra>"),
            )
        )
        latest_date, latest_weight = weight_points[-1]
        figure.add_trace(
            go.Scatter(
                x=[latest_date],
                y=[latest_weight],
                mode="markers",
                marker={"color": "#8b5cf6", "size": 9},
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_annotation(
            x=latest_date,
            y=latest_weight,
            text=f"{latest_weight:.1f} kg",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            xshift=8,
            yshift=8,
            font={"color": "#a78bfa", "size": 13},
        )

    figure.update_layout(
        template="none",
        autosize=True,
        title={"text": "Recorded Weight and Plan", "x": 0.5},
        paper_bgcolor="#15111f",
        plot_bgcolor="#15111f",
        font={
            "color": "#bbb3c9",
            "family": 'Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif',
        },
        hovermode="x unified",
        hoverlabel={
            "bgcolor": "#2c2340",
            "bordercolor": "#524762",
            "font": {"color": "#f4f0fa"},
        },
        uirevision="weight-tracker",
        margin={"l": 64, "r": 24, "t": 70, "b": 48},
        legend={
            "orientation": "h",
            "x": 0,
            "y": 1.02,
            "xanchor": "left",
            "yanchor": "bottom",
        },
        xaxis={
            "title": "Date",
            "gridcolor": "#383047",
            "linecolor": "#524762",
        },
        yaxis={
            "title": "Weight (kg)",
            "gridcolor": "#383047",
            "linecolor": "#524762",
            "fixedrange": False,
            "zeroline": False,
        },
    )
    return figure


def build_difference_figure(
    weight_dates: Sequence[date],
    weights: Sequence[float],
    plan_dates: Sequence[date],
    plan: Sequence[float],
) -> go.Figure:
    weight_points = list(zip(weight_dates, weights, strict=True))
    plan_points = list(zip(plan_dates, plan, strict=True))
    plan_by_date = {day: weight for day, weight in plan_points if math.isfinite(weight)}
    differences = [
        (day, weight, plan_by_date[day]) for day, weight in weight_points if day in plan_by_date
    ]

    figure = go.Figure()

    if differences:
        difference_values = [weight - planned for _day, weight, planned in differences]
        difference_dates = [day for day, _weight, _planned in differences]
        difference_details = [[weight, planned] for _day, weight, planned in differences]
        for name, color, values in (
            (
                "Above plan",
                "#b4533c",
                [difference if difference > 0 else math.nan for difference in difference_values],
            ),
            (
                "Below plan",
                "#087044",
                [difference if difference <= 0 else math.nan for difference in difference_values],
            ),
        ):
            figure.add_trace(
                go.Bar(
                    x=difference_dates,
                    y=values,
                    customdata=difference_details,
                    marker={"color": color},
                    name=name,
                    hovertemplate=(
                        "%{x|%d %b %Y}<br>%{y:+.1f} kg vs plan"
                        "<br>Recorded %{customdata[0]:.1f} kg"
                        "<br>Plan %{customdata[1]:.1f} kg<extra></extra>"
                    ),
                )
            )

    _style_insight_figure(figure, "Difference from Plan", "weight-difference", "kg")
    figure.update_layout(bargap=0, barmode="overlay")
    return figure


def build_rate_figure(
    weight_dates: Sequence[date],
    weights: Sequence[float],
    plan_dates: Sequence[date],
    plan: Sequence[float],
) -> go.Figure:
    weight_points = list(zip(weight_dates, weights, strict=True))
    plan_points = list(zip(plan_dates, plan, strict=True))
    figure = go.Figure()
    recorded_rates = _rolling_weekly_rates(weight_dates, weights, 28)
    planned_rates = _rolling_weekly_rates(plan_dates, plan, 28)
    if weight_points:
        figure.add_trace(
            go.Scatter(
                x=list(weight_dates),
                y=recorded_rates,
                mode="lines",
                name="Recorded rate",
                connectgaps=False,
                line={"color": "#8b5cf6", "width": 2.2},
                hovertemplate=("%{x|%d %b %Y}<br>%{y:+.2f} kg/week<extra>Recorded rate</extra>"),
            )
        )
    if plan_points:
        figure.add_trace(
            go.Scatter(
                x=list(plan_dates),
                y=planned_rates,
                mode="lines",
                name="Planned rate",
                connectgaps=False,
                line={"color": "#087044", "width": 2.2},
                hovertemplate=("%{x|%d %b %Y}<br>%{y:+.2f} kg/week<extra>Planned rate</extra>"),
            )
        )

    _style_insight_figure(
        figure,
        "4-Week Average Weight Change",
        "weight-rate",
        "kg/week",
    )
    return figure


def _style_insight_figure(figure: go.Figure, title: str, uirevision: str, yaxis_title: str) -> None:
    figure.update_layout(
        template="none",
        autosize=True,
        title={"text": title, "x": 0.5, "font": {"size": 13}},
        paper_bgcolor="#15111f",
        plot_bgcolor="#15111f",
        font={
            "color": "#bbb3c9",
            "family": 'Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif',
        },
        hovermode="x unified",
        hoverlabel={
            "bgcolor": "#2c2340",
            "bordercolor": "#524762",
            "font": {"color": "#f4f0fa"},
        },
        uirevision=uirevision,
        margin={"l": 64, "r": 24, "t": 84, "b": 80},
        legend={
            "orientation": "h",
            "x": 0,
            "y": 1.02,
            "xanchor": "left",
            "yanchor": "bottom",
        },
    )
    figure.update_xaxes(
        title={"text": "Date", "standoff": 28},
        gridcolor="#383047",
        linecolor="#524762",
        fixedrange=False,
    )
    figure.update_yaxes(
        title=yaxis_title,
        gridcolor="#383047",
        linecolor="#524762",
        fixedrange=False,
        zeroline=True,
        zerolinecolor="#706580",
    )


def _rolling_weekly_rates(
    dates: Sequence[date], values: Sequence[float], window_days: int
) -> list[float]:
    points = list(zip(dates, values, strict=True))
    rates: list[float] = []
    segment_start = 0
    window_start = 0

    for end, (current_date, current_value) in enumerate(points):
        if not math.isfinite(current_value):
            rates.append(math.nan)
            segment_start = end + 1
            window_start = segment_start
            continue

        threshold = current_date.toordinal() - (window_days - 1)
        while window_start < end and points[window_start][0].toordinal() < threshold:
            window_start += 1
        window_start = max(window_start, segment_start)
        window = points[window_start : end + 1]
        span = (current_date - window[0][0]).days
        if len(window) < 7 or span < window_days - 1:
            rates.append(math.nan)
            continue

        elapsed_days = [(day - window[0][0]).days for day, _weight in window]
        mean_day = sum(elapsed_days) / len(elapsed_days)
        mean_weight = sum(weight for _day, weight in window) / len(window)
        denominator = sum((day - mean_day) ** 2 for day in elapsed_days)
        slope = (
            sum(
                (day - mean_day) * (weight - mean_weight)
                for day, (_date, weight) in zip(elapsed_days, window, strict=True)
            )
            / denominator
        )
        rates.append(slope * 7)

    return rates
