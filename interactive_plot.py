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
            xshift=12,
            yshift=12,
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
            "rangeslider": {
                "visible": True,
                "bgcolor": "#0f0c16",
                "bordercolor": "#30283e",
                "borderwidth": 1,
            },
        },
        yaxis={
            "title": "Weight (kg)",
            "gridcolor": "#383047",
            "linecolor": "#524762",
            "zeroline": False,
        },
    )
    return figure
