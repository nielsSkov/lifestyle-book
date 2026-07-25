from datetime import date

from matplotlib import pyplot

from planning.planning_helpers import build_full_plan, plot_plan


def test_build_full_plan_replaces_existing_plan_from_candidate_start():
    dates, weights = build_full_plan(
        [date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 2)],
        [101.0, 100.0, 99.0],
        [(date(2026, 8, 1), 100.5), (date(2026, 8, 2), 100.0)],
    )

    assert dates == [date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 2)]
    assert weights == [101.0, 100.5, 100.0]


def test_plot_plan_returns_axis():
    axis = plot_plan(
        [date(2026, 8, 1)],
        [100.0],
        [date(2026, 8, 1), date(2026, 8, 2)],
        [100.0, 99.0],
    )

    assert axis.get_title() == "Recorded Weight and Plan"
    pyplot.close()
