# Weight tracker

A small self-hosted Flask application for recording daily weight and comparing it with a planned trajectory. Data stays in two CSV files, and Matplotlib renders responsive desktop and mobile graphs.

## Features

- Fast mobile weight entry
- Same-day entries replace the previous value
- 7-day, 4-week, 1-year, and complete-history views
- Recorded and planned weight lines
- No database, frontend build system, or external analytics

## Data

The application reads two local files:

```text
weight.csv  Recorded measurements
plan.csv    Planned trajectory
```

Both use this format:

```csv
date,weight_kg
2026-01-01,82.4
```

Real CSV files are ignored by Git. Fictional examples are available under `examples/`.

## Local development

```sh
uv sync
cp examples/weight.example.csv weight.csv
cp examples/plan.example.csv plan.csv
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run flask --app app run --port 8000
```

Open <http://127.0.0.1:8000>.

## Server deployment

The supported production model is a Git checkout containing ignored, server-local CSV files. The application has no authentication and should only be reachable through a trusted private network or VPN.

On Debian:

```sh
sudo apt update
sudo apt install curl git
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
git clone https://github.com/nielsSkov/weight-tracker.git /home/YOUR_USER/weight-tracker
cd /home/YOUR_USER/weight-tracker
uv sync --no-dev
uv run --no-dev gunicorn --check-config app:app
```

Create or copy `weight.csv` and `plan.csv` into the checkout, then restrict their permissions:

```sh
chmod 600 weight.csv plan.csv
```

Prepare and install the service:

```sh
cp deploy/weight-tracker.service.example weight-tracker.service
# Replace YOUR_USER and SERVER_IP in weight-tracker.service.
sudo install -m 644 weight-tracker.service /etc/systemd/system/weight-tracker.service
sudo systemctl daemon-reload
sudo systemctl enable --now weight-tracker.service
```

Use a router DHCP reservation to keep `SERVER_IP` stable. Linux can continue using DHCP.

### Updating

Deploy only commits that have passed CI:

```sh
cd /home/YOUR_USER/weight-tracker
git pull --ff-only origin main
uv sync --no-dev
uv run --no-dev gunicorn --check-config app:app
sudo systemctl restart weight-tracker.service
git rev-parse HEAD
```

Never use `git clean` in the deployment checkout: `weight.csv` and `plan.csv` are intentionally untracked live data.

## Plan workflow

Create the ignored local server configuration:

```sh
cp server.local.example.json server.local.json
```

Set the SSH target and deployment directory:

```json
{
  "target": "user@server",
  "directory": "/home/user/weight-tracker"
}
```

Retrieve the latest measurements before planning:

```sh
uv run fetch_weight.py
```

The fetch command downloads to a temporary file, validates the CSV, compares its checksum with the server, and only then atomically replaces local `weight.csv`.

Create the paired notebook from the tracked Jupytext source:

```sh
uv run jupytext --sync planning/plan.py
```

Open `planning/plan.ipynb` and edit the control points to build a daily candidate; equal-weight points create plateaus. The notebook uses the same plotting code as the application and shows one continuous plan made from historical plan data followed by the new candidate.

Control-point values can also be functions of elapsed days. Each function runs from its control-point date until the next entry; numeric entries continue to use linear interpolation, and equal numeric entries create plateaus. `planning/planning_helpers.py` also provides the notebook's loading, merging, and plotting helpers.

Use `None` as a control-point value to place an explicit gap in the plan. Saved plans represent gaps as `NaN`; plan deployment and the online graph support them, while recorded measurements still require finite weights.

When the candidate is ready, save it explicitly from a separate notebook cell:

```python
planning.save_plan(plan_dates, plan_weights)
```

This validates and atomically replaces the ignored local `plan.csv`; normal notebook execution does not save automatically.

The generated notebook is ignored, while `planning/plan.py` is the tracked source. Saving requires running the separate save cell, and deployment remains a separate command.

After separately saving a validated candidate as `plan.csv`, deploy it with:

```sh
./deploy_plan.py
```

The utility validates the plan, uploads it under a temporary name, backs up the current server plan, atomically replaces it, and verifies its SHA-256 checksum. No service restart is needed.

## Operations

```sh
sudo systemctl status weight-tracker.service
sudo systemctl restart weight-tracker.service
sudo journalctl -u weight-tracker.service -f
```

Back up the ignored CSV files separately from the Git repository. For example:

```sh
scp user@server:/home/user/weight-tracker/weight.csv .
```
