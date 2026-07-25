# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
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

# %%
import sys
from datetime import timedelta
from pathlib import Path

PROJECT_DIR = Path.cwd()
if not (PROJECT_DIR / "weight_data.py").exists():
    PROJECT_DIR = PROJECT_DIR.parent
if not (PROJECT_DIR / "weight_data.py").exists():
    raise RuntimeError("Run this notebook from the project root or planning directory")
sys.path.insert(0, str(PROJECT_DIR))

from plan_model import interpolate_plan  # noqa: E402
from weight_data import read_series  # noqa: E402
from weight_plot import build_figure  # noqa: E402

# %%
weight_dates, weights = read_series(PROJECT_DIR / "weight.csv")
existing_plan_dates, existing_plan = read_series(PROJECT_DIR / "plan.csv")
if not weight_dates:
    raise RuntimeError("weight.csv has no measurements; run uv run fetch_weight.py first")

# %% [markdown]
# Edit these points to shape the candidate plan. The model interpolates one value per day;
# consecutive points with the same weight create a plateau.

# %%
control_points = [
    (weight_dates[-1], weights[-1]),
    (weight_dates[-1] + timedelta(weeks=12), weights[-1] - 6),
    (weight_dates[-1] + timedelta(weeks=14), weights[-1] - 6),
]

candidate_dates, candidate_weights = interpolate_plan(control_points)

# %% [markdown]
# ## Existing plan

# %%
all_dates = [*weight_dates, *existing_plan_dates, *candidate_dates]
period_start, period_end = min(all_dates), max(all_dates)

build_figure(
    weight_dates,
    weights,
    existing_plan_dates,
    existing_plan,
    period_start,
    period_end,
)

# %% [markdown]
# ## Candidate plan

# %%
build_figure(
    weight_dates,
    weights,
    candidate_dates,
    candidate_weights,
    period_start,
    period_end,
)
