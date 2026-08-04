import math
from datetime import time

from plotly import graph_objects as go

from sleep_data import SleepRecord


def build_sleep_figure(records: list[SleepRecord]) -> go.Figure:
    figure = go.Figure()
    if records:
        starts = [_clock_axis_hour(record.sleep_time) for record in records]
        durations = [record.duration_minutes / 60 for record in records]
        ends = [start + duration for start, duration in zip(starts, durations, strict=True)]
        figure.add_trace(
            go.Bar(
                x=[record.wake_date for record in records],
                y=durations,
                base=starts,
                customdata=[
                    [
                        record.sleep_time.strftime("%H:%M"),
                        record.wake_time.strftime("%H:%M"),
                        _format_duration(record.duration_minutes),
                    ]
                    for record in records
                ],
                marker={"color": "#7c5cc4", "line": {"color": "#a78bfa", "width": 1}},
                hovertemplate=(
                    "%{x|%d %b %Y}<br>Sleep %{customdata[0]}"
                    "<br>Wake %{customdata[1]}<br>%{customdata[2]}<extra></extra>"
                ),
            )
        )
        lower = min(18, math.floor(min(starts)))
        upper = max(36, math.ceil(max(ends)))
    else:
        lower, upper = 18, 36

    first_tick = math.floor(lower / 3) * 3
    ticks = list(range(first_tick, math.ceil(upper / 3) * 3 + 1, 3))
    figure.update_layout(
        template="none",
        autosize=True,
        title={"text": "Sleep Timing", "x": 0.5},
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
        uirevision="sleep-timing",
        margin={"l": 64, "r": 24, "t": 70, "b": 64},
        bargap=0.35,
        showlegend=False,
        xaxis={
            "title": "Wake Date",
            "gridcolor": "#383047",
            "linecolor": "#524762",
        },
        yaxis={
            "title": "Time",
            "range": [lower, upper],
            "tickvals": ticks,
            "ticktext": [f"{tick % 24:02d}:00" for tick in ticks],
            "gridcolor": "#383047",
            "linecolor": "#524762",
            "fixedrange": False,
        },
    )
    return figure


def _clock_axis_hour(value: time) -> float:
    hour = value.hour + value.minute / 60
    return hour + 24 if hour < 18 else hour


def _format_duration(minutes: int) -> str:
    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes:02d}m"
