# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
#       comment_magics: true
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Weight plan
#
# Fetch the latest measurements with `uv run fetch_weight.py` before editing the control
# points. This notebook only builds an in-memory candidate; it does not change `plan.csv`.
# The graph preserves historical plan data and replaces the plan from the first new control
# point onward.

# %%
# %matplotlib widget

from datetime import date, timedelta
from importlib import reload

import planning_helpers as planning
from matplotlib import pyplot

planning = reload(planning)
planning.apply_notebook_style()

weight_dates, weights, existing_plan_dates, existing_plan = planning.load_planning_data()


# Numbers interpolate linearly, functions control their interval, and equal numbers stay flat.
# Fictional example:
# def curved_loss(days):
#     return 98.0 - 4.0 * (days / 61) ** 1.5
#
# control_points = [
#     (date(2026, 8, 1), 100.0),      # Linear to 98 kg
#     (date(2026, 9, 1), curved_loss), # Nonlinear to 94 kg
#     (date(2026, 11, 1), None),      # Explicit gap
#     (date(2026, 11, 2), 94.0),      # Flat at 94 kg
#     (date(2026, 11, 15), 94.0),
# ]
control_points = [
    (weight_dates[-1], weights[-1]),
    (weight_dates[-1] + timedelta(weeks=12), weights[-1] - 6),
    (weight_dates[-1] + timedelta(weeks=14), weights[-1] - 6),
]

plan_dates, plan_weights = planning.build_full_plan(
    existing_plan_dates,
    existing_plan,
    control_points,
)
axis = planning.plot_plan(weight_dates, weights, plan_dates, plan_weights)
pyplot.show()

# %%
# Run this cell only after reviewing the candidate plot.
planning.save_plan(plan_dates, plan_weights)
