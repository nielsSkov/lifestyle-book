import math
from datetime import date, time, timedelta

from plotly import graph_objects as go

from sleep_data import SleepRecord


def build_sleep_figure(records: list[SleepRecord]) -> go.Figure:
    figure = go.Figure()
    if records:
        records_by_date = {record.date: record for record in records}
        dates = _daily_dates(records[0].date, records[-1].date)
        for name, colour, attribute in (
            ("Wake time", "#a78bfa", "wake_time"),
            ("Sleep time", "#6d4cc4", "sleep_time"),
        ):
            values = [getattr(records_by_date.get(day), attribute, None) for day in dates]
            figure.add_trace(
                go.Scatter(
                    x=dates,
                    y=[_clock_hour(value) for value in values],
                    customdata=[_format_time(value) for value in values],
                    mode="lines+markers",
                    name=name,
                    connectgaps=False,
                    line={"color": colour, "width": 2.2},
                    marker={"color": colour, "size": 7},
                    hovertemplate="%{x|%d %b %Y}<br>%{customdata}<extra>%{fullData.name}</extra>",
                )
            )

    ticks = list(range(0, 25, 3))
    figure.update_layout(
        template="none",
        autosize=True,
        title={"text": "Sleep and Wake Times", "x": 0.5},
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
        uirevision="sleep-times",
        margin={"l": 64, "r": 24, "t": 84, "b": 64},
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
            "title": "Time",
            "range": [0, 24],
            "tickvals": ticks,
            "ticktext": [f"{tick:02d}:00" for tick in ticks],
            "gridcolor": "#383047",
            "linecolor": "#524762",
            "fixedrange": False,
        },
    )
    return figure


def _daily_dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _clock_hour(value: time | None) -> float:
    if value is None:
        return math.nan
    return value.hour + value.minute / 60


def _format_time(value: time | None) -> str:
    return "" if value is None else value.strftime("%H:%M")
