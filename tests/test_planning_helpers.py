import math
import stat
from datetime import date

import pytest

from planning.planning_helpers import build_full_plan, plot_plan, save_plan
from weight_data import read_series


def test_build_full_plan_replaces_existing_plan_from_candidate_start():
    dates, weights = build_full_plan(
        [date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 2)],
        [101.0, 100.0, 99.0],
        [(date(2026, 8, 1), 100.5), (date(2026, 8, 2), 100.0)],
    )

    assert dates == [date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 2)]
    assert weights == [101.0, 100.5, 100.0]


def test_build_full_plan_preserves_explicit_gaps():
    dates, weights = build_full_plan(
        [],
        [],
        [
            (date(2026, 8, 1), lambda days: 100.0 - days),
            (date(2026, 8, 3), None),
            (date(2026, 8, 4), 95.0),
        ],
    )

    assert dates == [
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 4),
    ]
    assert weights[:2] == [100.0, 99.0]
    assert math.isnan(weights[2])
    assert weights[3:] == [95.0]


def test_plot_plan_rejects_empty_data():
    with pytest.raises(ValueError, match="recorded weights or plan"):
        plot_plan([], [], [], [])


def test_save_plan_uses_private_project_plan_path(monkeypatch, tmp_path):
    plan_path = tmp_path / "plan.csv"
    monkeypatch.setattr("planning.planning_helpers.PROJECT_DIR", tmp_path)

    row_count = save_plan(
        [date(2026, 8, 1), date(2026, 8, 2)],
        [100.0, math.nan],
    )

    assert row_count == 2
    dates, weights = read_series(plan_path)
    assert dates == [date(2026, 8, 1), date(2026, 8, 2)]
    assert weights[0] == 100.0
    assert math.isnan(weights[1])
    assert stat.S_IMODE(plan_path.stat().st_mode) == 0o600
