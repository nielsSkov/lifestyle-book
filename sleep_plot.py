import math
from datetime import date, datetime, time, timedelta

from plotly import graph_objects as go

from sleep_data import SleepRecord


def build_sleep_figure(records: list[SleepRecord]) -> go.Figure:
    figure = go.Figure()
    lower_values: list[float] = []
    upper_values: list[float] = []
    night_dates: list[date] = []
    sleep_events: list[datetime | None] = []
    wake_events: list[datetime | None] = []

    if records:
        records_by_date = {record.night_start_date: record for record in records}
        night_dates = _daily_dates(
            records[0].night_start_date,
            records[-1].night_start_date,
        )
        night_keys = [_night_label(day) for day in night_dates]
        for day in night_dates:
            record = records_by_date.get(day)
            sleep_events.append(record.sleep_at if record else None)
            wake_events.append(record.wake_at if record else None)
        lower_values = [
            _event_hour(value, day) for value, day in zip(sleep_events, night_dates, strict=True)
        ]
        upper_values = [
            _event_hour(value, day) for value, day in zip(wake_events, night_dates, strict=True)
        ]

        for run in _complete_runs(lower_values, upper_values):
            if len(run) == 1:
                index = run[0]
                figure.add_trace(
                    go.Bar(
                        x=[night_keys[index]],
                        y=[upper_values[index] - lower_values[index]],
                        base=[lower_values[index]],
                        width=0.7,
                        marker={"color": "rgba(139, 92, 246, 0.18)"},
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
            else:
                fill_keys = [night_keys[index] for index in run]
                fill_lower = [lower_values[index] for index in run]
                fill_upper = [upper_values[index] for index in run]
                figure.add_trace(
                    go.Scatter(
                        x=[*fill_keys, *reversed(fill_keys)],
                        y=[*fill_lower, *reversed(fill_upper)],
                        fill="toself",
                        fillcolor="rgba(139, 92, 246, 0.18)",
                        line={"width": 0},
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

        for name, colour, values, events in (
            ("Sleep time", "#6d4cc4", lower_values, sleep_events),
            ("Wake time", "#a78bfa", upper_values, wake_events),
        ):
            figure.add_trace(
                go.Scatter(
                    x=night_keys,
                    y=values,
                    customdata=[_format_time(value) for value in events],
                    mode="lines+markers",
                    name=name,
                    connectgaps=False,
                    line={"color": colour, "width": 2.2},
                    marker={"color": colour, "size": 7},
                    hovertemplate=("%{x}<br>%{customdata}<extra>%{fullData.name}</extra>"),
                )
            )

    finite_values = [value for value in [*lower_values, *upper_values] if math.isfinite(value)]
    lower = min([18, *finite_values])
    upper = max([36, *finite_values])
    first_tick = math.floor(lower / 3) * 3
    ticks = list(range(first_tick, math.ceil(upper / 3) * 3 + 1, 3))
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
            "title": "Night",
            "type": "category",
            "categoryorder": "array",
            "categoryarray": [_night_label(day) for day in night_dates],
            "tickangle": -35,
            "automargin": True,
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


def _daily_dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _event_hour(value: datetime | None, night_start_date: date) -> float:
    if value is None:
        return math.nan
    night_start = datetime.combine(night_start_date, time())
    return (value - night_start).total_seconds() / 3600


def _complete_runs(lower_values: list[float], upper_values: list[float]) -> list[list[int]]:
    runs: list[list[int]] = []
    current: list[int] = []
    for index, (lower, upper) in enumerate(zip(lower_values, upper_values, strict=True)):
        if math.isfinite(lower) and math.isfinite(upper):
            current.append(index)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def _night_label(day: date) -> str:
    next_day = day + timedelta(days=1)
    if day.year != next_day.year:
        return f"{day:%-d %b %Y}–{next_day:%-d %b %Y}"
    if day.month != next_day.month:
        return f"{day:%-d %b}–{next_day:%-d %b}<br>{day.year}"
    return f"{day.day}–{next_day.day} {day:%b}<br>{day.year}"


def _format_time(value: datetime | None) -> str:
    return "" if value is None else value.strftime("%H:%M")
