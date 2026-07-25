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
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp examples/weight.example.csv weight.csv
cp examples/plan.example.csv plan.csv
.venv/bin/python -m unittest -v
.venv/bin/flask --app app run --port 8000
```

Open <http://127.0.0.1:8000>.

## Server deployment

The supported production model is a Git checkout containing ignored, server-local CSV files. The application has no authentication and should only be reachable through a trusted private network or VPN.

On Debian:

```sh
sudo apt update
sudo apt install git python3-venv
git clone https://github.com/nielsSkov/weight-tracker.git /home/YOUR_USER/weight-tracker
cd /home/YOUR_USER/weight-tracker
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest -v
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
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest -v
sudo systemctl restart weight-tracker.service
git rev-parse HEAD
```

Never use `git clean` in the deployment checkout: `weight.csv` and `plan.csv` are intentionally untracked live data.

## Plan workflow

`generate_plan.py` is a safe skeleton. Implement `build_plan()` so it returns chronological `(date, weight_kg)` rows, then run:

```sh
./generate_plan.py
```

An empty generator exits without changing the existing plan. Generated rows are validated before replacing local `plan.csv`.

To deploy a plan without logging into the server, create the ignored local configuration:

```sh
cp deploy.local.example.json deploy.local.json
```

Set the SSH target and deployment directory:

```json
{
  "target": "user@server",
  "directory": "/home/user/weight-tracker"
}
```

Then deploy:

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
