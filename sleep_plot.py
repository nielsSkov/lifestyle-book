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
        night_labels = [_night_label(day) for day in night_dates]
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
                        x=[night_dates[index]],
                        y=[upper_values[index] - lower_values[index]],
                        base=[lower_values[index]],
                        width=0.7 * 86_400_000,
                        marker={"color": "rgba(139, 92, 246, 0.18)"},
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
            else:
                fill_dates = [night_dates[index] for index in run]
                fill_lower = [lower_values[index] for index in run]
                fill_upper = [upper_values[index] for index in run]
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

        for name, colour, values, events in (
            ("Sleep time", "#6d4cc4", lower_values, sleep_events),
            ("Wake time", "#a78bfa", upper_values, wake_events),
        ):
            figure.add_trace(
                go.Scatter(
                    x=night_dates,
                    y=values,
                    customdata=[
                        [night_label, _format_time(value)]
                        for night_label, value in zip(night_labels, events, strict=True)
                    ],
                    mode="lines+markers",
                    name=name,
                    connectgaps=False,
                    line={"color": colour, "width": 2.2},
                    marker={"color": colour, "size": 7},
                    hovertemplate="%{customdata[1]}<extra>%{fullData.name}</extra>",
                )
            )

    finite_values = [value for value in [*lower_values, *upper_values] if math.isfinite(value)]
    lower = min([18, *finite_values])
    upper = max([36, *finite_values])
    ticks = list(range(math.floor(lower), math.ceil(upper) + 1))
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
            "type": "date",
            "unifiedhovertitle": {"text": "%{customdata[0]}"},
            "tickangle": 0,
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
    _set_sleep_x_range(figure, night_dates)
    return figure


def build_sleep_duration_figure(records: list[SleepRecord]) -> go.Figure:
    figure = go.Figure()
    night_dates: list[date] = []

    if records:
        records_by_date = {record.night_start_date: record for record in records}
        night_dates = _daily_dates(
            records[0].night_start_date,
            records[-1].night_start_date,
        )
        night_labels = [_night_label(day) for day in night_dates]
        durations = []
        duration_labels = []
        for day in night_dates:
            record = records_by_date.get(day)
            duration = _sleep_duration(record)
            durations.append(duration)
            duration_labels.append(_format_duration(duration))

        figure.add_trace(
            go.Bar(
                x=night_dates,
                y=durations,
                customdata=[
                    [night_label, duration_label]
                    for night_label, duration_label in zip(
                        night_labels, duration_labels, strict=True
                    )
                ],
                marker={"color": "#8354e8"},
                hovertemplate="%{customdata[1]}<extra>Sleep duration</extra>",
                showlegend=False,
            )
        )

    figure.update_layout(
        template="none",
        autosize=True,
        title={"text": "Sleep Duration", "x": 0.5},
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
        uirevision="sleep-duration",
        margin={"l": 64, "r": 24, "t": 84, "b": 64},
        xaxis={
            "title": "Night",
            "type": "date",
            "unifiedhovertitle": {"text": "%{customdata[0]}"},
            "tickangle": 0,
            "automargin": True,
            "gridcolor": "#383047",
            "linecolor": "#524762",
        },
        yaxis={
            "title": "Hours",
            "rangemode": "tozero",
            "dtick": 1,
            "gridcolor": "#383047",
            "linecolor": "#524762",
            "fixedrange": False,
        },
    )
    _set_sleep_x_range(figure, night_dates)
    return figure


def _daily_dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _set_sleep_x_range(figure: go.Figure, night_dates: list[date]) -> None:
    if night_dates:
        figure.update_xaxes(
            range=[
                datetime.combine(night_dates[0], time()) - timedelta(hours=12),
                datetime.combine(night_dates[-1], time()) + timedelta(hours=12),
            ]
        )


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


def _sleep_duration(record: SleepRecord | None) -> float:
    if record is None or record.sleep_at is None or record.wake_at is None:
        return math.nan
    return (record.wake_at - record.sleep_at).total_seconds() / 3600


def _format_duration(duration: float) -> str:
    if not math.isfinite(duration):
        return ""
    total_minutes = round(duration * 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours} h {minutes:02d} min"
