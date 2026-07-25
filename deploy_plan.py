#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import shlex
import subprocess
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


PROJECT_DIR = Path(__file__).parent


def validate_plan(path):
    previous_date = None
    row_count = 0

    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file)
        if next(reader, None) != ["date", "weight_kg"]:
            raise ValueError("Expected header: date,weight_kg")

        for line_number, row in enumerate(reader, 2):
            if len(row) != 2:
                raise ValueError(f"Line {line_number}: expected two columns")
            try:
                day = date.fromisoformat(row[0])
            except ValueError:
                raise ValueError(f"Line {line_number}: invalid date {row[0]!r}") from None
            try:
                weight = Decimal(row[1])
            except InvalidOperation:
                raise ValueError(f"Line {line_number}: invalid weight {row[1]!r}") from None
            if not weight.is_finite() or not Decimal("30") <= weight <= Decimal("300"):
                raise ValueError(f"Line {line_number}: weight must be between 30 and 300 kg")
            if previous_date is not None and day <= previous_date:
                raise ValueError(f"Line {line_number}: dates must be unique and increasing")
            previous_date = day
            row_count += 1

    if row_count == 0:
        raise ValueError("Plan contains no data rows")
    return row_count


def load_config(path):
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        target = config["target"]
        directory = config["directory"]
    except (OSError, json.JSONDecodeError, KeyError) as error:
        raise ValueError(f"Could not read deployment config {path}: {error}") from None
    if not isinstance(target, str) or not isinstance(directory, str) or not target or not directory:
        raise ValueError("Deployment config requires non-empty target and directory strings")
    return target, directory.rstrip("/")


def file_checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deploy(plan_path, config_path):
    row_count = validate_plan(plan_path)
    target, directory = load_config(config_path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    remote_plan = f"{directory}/plan.csv"
    remote_upload = f"{directory}/.plan.csv.upload"
    remote_backup = f"{directory}/backups/plan-{timestamp}.csv"

    subprocess.run(["scp", str(plan_path), f"{target}:{remote_upload}"], check=True)

    quoted = {name: shlex.quote(value) for name, value in {
        "directory": directory,
        "plan": remote_plan,
        "upload": remote_upload,
        "backup": remote_backup,
    }.items()}
    remote_command = (
        f"mkdir -p {quoted['directory']}/backups && "
        f"if [ -f {quoted['plan']} ]; then cp -p {quoted['plan']} {quoted['backup']}; fi && "
        f"chmod 600 {quoted['upload']} && mv {quoted['upload']} {quoted['plan']}"
    )
    subprocess.run(["ssh", target, remote_command], check=True)

    result = subprocess.run(
        ["ssh", target, f"sha256sum {shlex.quote(remote_plan)}"],
        check=True,
        capture_output=True,
        text=True,
    )
    local_checksum = file_checksum(plan_path)
    remote_checksum = result.stdout.split()[0]
    if local_checksum != remote_checksum:
        raise RuntimeError("Deployment finished, but checksums do not match")

    print(f"Deployed {row_count} plan rows to {target}:{remote_plan}")
    print(f"Previous plan backed up as {remote_backup}")
    print(f"SHA-256: {local_checksum}")


def main():
    parser = argparse.ArgumentParser(description="Safely deploy plan.csv to the weight tracker")
    parser.add_argument("plan", nargs="?", type=Path, default=PROJECT_DIR / "plan.csv")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_DIR / "deploy.local.json",
        help="private deployment configuration (default: deploy.local.json)",
    )
    args = parser.parse_args()

    try:
        deploy(args.plan, args.config)
    except (ValueError, OSError, subprocess.CalledProcessError, RuntimeError) as error:
        raise SystemExit(f"Deployment failed: {error}") from None


if __name__ == "__main__":
    main()
