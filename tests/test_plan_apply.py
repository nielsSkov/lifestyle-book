import math
from datetime import date
from pathlib import Path

from plan_apply import merge_plan_intervals, store_active_plan
from weight_data import read_series


def test_merge_plan_intervals_changes_only_covered_dates():
    dates, weights = merge_plan_intervals(
        [date(2026, 8, day) for day in range(1, 8)],
        [101.0, 100.0, 99.0, 98.0, 97.0, 96.0, 95.0],
        [
            (
                date(2026, 8, 2),
                date(2026, 8, 3),
                [date(2026, 8, 2), date(2026, 8, 3)],
                [100.5, 100.0],
                False,
            ),
            (date(2026, 8, 5), date(2026, 8, 6), None, None, True),
        ],
    )

    assert dates == [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
        date(2026, 8, 6),
        date(2026, 8, 7),
    ]
    assert weights[:4] == [101.0, 100.5, 100.0, 98.0]
    assert math.isnan(weights[4])
    assert math.isnan(weights[5])
    assert weights[6] == 95.0


def test_merge_plan_intervals_preserves_unrelated_gap():
    dates, weights = merge_plan_intervals(
        [date(2026, 8, 1), date(2026, 8, 2)],
        [100.0, math.nan],
        [
            (
                date(2026, 8, 3),
                date(2026, 8, 4),
                [date(2026, 8, 3), date(2026, 8, 4)],
                [99.0, 98.0],
                False,
            )
        ],
    )

    assert dates == [date(2026, 8, day) for day in range(1, 5)]
    assert math.isnan(weights[1])
    assert weights[2:] == [99.0, 98.0]


def test_store_active_plan_replaces_csv_privately(tmp_path: Path):
    path = tmp_path / "plan.csv"

    store_active_plan(path, [date(2026, 8, 1)], [100.0])

    assert read_series(path) == ([date(2026, 8, 1)], [100.0])
    assert path.stat().st_mode & 0o777 == 0o600


def test_store_active_plan_removes_file_for_empty_plan(tmp_path: Path):
    path = tmp_path / "plan.csv"
    path.write_text("date,weight_kg\n2026-08-01,100\n", encoding="utf-8")

    store_active_plan(path, [], [])

    assert not path.exists()
