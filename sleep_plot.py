import math
from datetime import date, datetime, time, timedelta

from plotly import graph_objects as go

from sleep_data import SleepRecord


def build_sleep_figure(records: list[SleepRecord]) -> go.Figure:
    figure = go.Figure()
    lower_values: list[float] = []
    upper_values: list[float] = []
    night_dates: list[date] = []
    sleep_times: list[time | None] = []
    wake_times: list[time | None] = []

    if records:
        records_by_date = {record.date: record for record in records}
        night_dates = _daily_dates(records[0].date - timedelta(days=1), records[-1].date)
        for day in night_dates:
            record = records_by_date.get(day)
            next_record = records_by_date.get(day + timedelta(days=1))
            sleep_times.append(record.sleep_time if record else None)
            wake_times.append(next_record.wake_time if next_record else None)
        lower_values = [_sleep_hour(value) for value in sleep_times]
        upper_values = [_wake_hour(value) for value in wake_times]

        for run in _complete_runs(lower_values, upper_values):
            fill_dates, fill_lower, fill_upper = _fill_coordinates(
                night_dates,
                lower_values,
                upper_values,
                run,
            )
            figure.add_trace(
                go.Scatter(
                    x=[*fill_dates, *reversed(fill_dates)],
                    y=[*fill_lower, *reversed(fill_upper)],
                    fill="toself",
                    fillcolor="rgba(139, 92, 246, 0.18)",
                    line={"width": 0},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        for name, colour, values, times in (
            ("Sleep time", "#6d4cc4", lower_values, sleep_times),
            ("Wake time", "#a78bfa", upper_values, wake_times),
        ):
            figure.add_trace(
                go.Scatter(
                    x=night_dates,
                    y=values,
                    customdata=[_format_time(value) for value in times],
                    mode="lines+markers",
                    name=name,
                    connectgaps=False,
                    line={"color": colour, "width": 2.2},
                    marker={"color": colour, "size": 7},
                    hovertemplate=("%{x|%d %b %Y}<br>%{customdata}<extra>%{fullData.name}</extra>"),
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
            "title": "Night Starting",
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


def _sleep_hour(value: time | None) -> float:
    if value is None:
        return math.nan
    hour = value.hour + value.minute / 60
    return hour + 24 if hour < 12 else hour


def _wake_hour(value: time | None) -> float:
    if value is None:
        return math.nan
    return 24 + value.hour + value.minute / 60


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


def _fill_coordinates(
    dates: list[date],
    lower_values: list[float],
    upper_values: list[float],
    run: list[int],
) -> tuple[list[date | datetime], list[float], list[float]]:
    if len(run) > 1:
        return (
            [dates[index] for index in run],
            [lower_values[index] for index in run],
            [upper_values[index] for index in run],
        )

    index = run[0]
    centre = datetime.combine(dates[index], time())
    return (
        [centre - timedelta(hours=9), centre + timedelta(hours=9)],
        [lower_values[index], lower_values[index]],
        [upper_values[index], upper_values[index]],
    )


def _format_time(value: time | None) -> str:
    return "" if value is None else value.strftime("%H:%M")
