from collections.abc import Sequence
from datetime import date, timedelta

from plotly import graph_objects as go

from achievement_catalog import Achievement
from daily_data import DailyRecord


def build_daily_figure(
    records: Sequence[DailyRecord],
    achievements: Sequence[Achievement],
) -> go.Figure:
    figure = go.Figure()
    used_keys = {key for record in records for key in record.achievements}
    displayed = [achievement for achievement in achievements if achievement.key in used_keys]
    movement = [achievement for achievement in displayed if achievement.group == "movement"]
    food = [achievement for achievement in displayed if achievement.group == "food"]
    group_gap = 1 if movement and food else 0
    y_positions = {achievement.key: len(food) - index for index, achievement in enumerate(food)} | {
        achievement.key: len(food) + group_gap + len(movement) - index
        for index, achievement in enumerate(movement)
    }

    dates = _daily_dates(records[0].day, records[-1].day) if displayed and records else []
    achievements_by_date = {record.day: record.achievements for record in records}

    for achievement in displayed:
        figure.add_trace(
            go.Heatmap(
                z=[
                    [
                        1 if achievement.key in achievements_by_date.get(day, frozenset()) else None
                        for day in dates
                    ]
                ],
                x0=dates[0] if dates else None,
                dx=86_400_000,
                y0=y_positions[achievement.key],
                dy=1,
                name=achievement.label,
                colorscale=[[0, achievement.tile_colour], [1, achievement.tile_colour]],
                zmin=0,
                zmax=1,
                xgap=10,
                ygap=10,
                showscale=False,
                showlegend=False,
                hoverongaps=False,
                hovertemplate=f"%{{x|%d %b %Y}}<extra>{achievement.label}</extra>",
            )
        )

    if movement:
        movement_values = [y_positions[achievement.key] for achievement in movement]
        figure.add_hrect(
            y0=min(movement_values) - 0.5,
            y1=max(movement_values) + 0.5,
            fillcolor="rgba(97, 169, 196, 0.045)",
            line_width=0,
            layer="below",
        )
        figure.add_annotation(
            text="MOVEMENT",
            x=0,
            y=max(movement_values) + 0.55,
            xref="paper",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font={"color": "#849dac", "size": 10},
        )
    if food:
        food_values = [y_positions[achievement.key] for achievement in food]
        figure.add_hrect(
            y0=min(food_values) - 0.5,
            y1=max(food_values) + 0.5,
            fillcolor="rgba(207, 134, 95, 0.055)",
            line_width=0,
            layer="below",
        )
        figure.add_annotation(
            text="FOOD",
            x=0,
            y=max(food_values) + 0.55,
            xref="paper",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font={"color": "#a88c7c", "size": 10},
        )
    if movement and food:
        divider = (
            min(y_positions[achievement.key] for achievement in movement)
            + max(y_positions[achievement.key] for achievement in food)
        ) / 2
        figure.add_hline(y=divider, line={"color": "#524762", "width": 1})

    if not displayed:
        figure.add_annotation(
            text="Recorded achievements will appear here",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"color": "#8f859d", "size": 14},
        )

    figure.update_layout(
        template="none",
        autosize=True,
        title={"text": "Daily Achievements", "x": 0.5},
        paper_bgcolor="#15111f",
        plot_bgcolor="#15111f",
        font={
            "color": "#bbb3c9",
            "family": 'Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif',
        },
        hoverlabel={
            "bgcolor": "#2c2340",
            "bordercolor": "#524762",
            "font": {"color": "#f4f0fa"},
        },
        uirevision="daily-achievements",
        margin={"l": 92, "r": 28, "t": 76, "b": 58},
        xaxis={
            "title": "Date",
            "type": "date",
            "tickformat": "%d %b",
            "gridcolor": "#383047",
            "linecolor": "#524762",
        },
        yaxis={
            "range": [0.5, max(y_positions.values()) + 1] if displayed else [0, 1],
            "tickvals": [y_positions[achievement.key] for achievement in displayed],
            "ticktext": [achievement.label for achievement in displayed],
            "gridcolor": "rgba(56, 48, 71, 0.5)",
            "linecolor": "#524762",
            "fixedrange": True,
            "automargin": True,
        },
    )
    return figure


def build_active_days_figure(
    records: Sequence[DailyRecord],
    achievements: Sequence[Achievement],
) -> go.Figure:
    figure = go.Figure()
    movement_keys = {
        achievement.key for achievement in achievements if achievement.group == "movement"
    }
    dates = _daily_dates(records[0].day, records[-1].day) if records else []
    achievements_by_date = {record.day: record.achievements for record in records}
    values = [
        1 if achievements_by_date.get(day, frozenset()) & movement_keys else None for day in dates
    ]

    if dates:
        figure.add_trace(
            go.Heatmap(
                z=[values],
                x0=dates[0],
                dx=86_400_000,
                y0=1,
                dy=0.5,
                name="Active Day",
                colorscale=[[0, "#6930d1"], [1, "#6930d1"]],
                zmin=0,
                zmax=1,
                xgap=10,
                ygap=10,
                showscale=False,
                showlegend=False,
                hoverongaps=False,
                hovertemplate="%{x|%d %b %Y}<extra>Active Day</extra>",
            )
        )
    if not any(value == 1 for value in values):
        figure.add_annotation(
            text="Movement achievements will appear here",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"color": "#8f859d", "size": 13},
        )

    figure.update_layout(
        template="none",
        autosize=True,
        title={"text": "Active Days", "x": 0.5, "font": {"size": 15}},
        paper_bgcolor="#15111f",
        plot_bgcolor="#15111f",
        font={
            "color": "#bbb3c9",
            "family": 'Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif',
        },
        hoverlabel={
            "bgcolor": "#2c2340",
            "bordercolor": "#524762",
            "font": {"color": "#f4f0fa"},
        },
        uirevision="active-days",
        margin={"l": 92, "r": 28, "t": 52, "b": 42},
        xaxis={
            "type": "date",
            "tickformat": "%d %b",
            "showticklabels": True,
            "gridcolor": "#383047",
            "linecolor": "#524762",
            "fixedrange": False,
        },
        yaxis={
            "title": "Active",
            "range": [0.5, 1.5],
            "showticklabels": False,
            "showgrid": False,
            "linecolor": "#524762",
            "fixedrange": True,
        },
    )
    return figure


def _daily_dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
