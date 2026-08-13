#!/usr/bin/env python3
import argparse
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from server_sync import file_checksum, load_server_config, remote_checksum
from weight_data import validate_csv

PROJECT_DIR = Path(__file__).parent


def deploy(plan_path, config_path):
    row_count = validate_csv(plan_path, allow_gaps=True)
    target, directory = load_server_config(config_path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    operation_id = uuid4().hex
    remote_plan = f"{directory}/plan.csv"
    remote_upload = f"{directory}/.plan-{operation_id}.csv.upload"
    remote_backup = f"{directory}/backups/plan-{timestamp}-{operation_id}.csv"
    remote_lock = f"{directory}/backups/.plan-backup.lock"

    subprocess.run(["scp", str(plan_path), f"{target}:{remote_upload}"], check=True)

    quoted = {
        name: shlex.quote(value)
        for name, value in {
            "directory": directory,
            "plan": remote_plan,
            "upload": remote_upload,
            "backup": remote_backup,
            "lock": remote_lock,
        }.items()
    }
    locked_command = (
        f"if [ -f {quoted['plan']} ]; then cp -p {quoted['plan']} {quoted['backup']}; fi && "
        f"chmod 600 {quoted['upload']} && mv {quoted['upload']} {quoted['plan']}"
    )
    remote_command = (
        f"mkdir -p {quoted['directory']}/backups && "
        f"flock {quoted['lock']} sh -c {shlex.quote(locked_command)}"
    )
    subprocess.run(["ssh", target, remote_command], check=True)

    local_checksum = file_checksum(plan_path)
    deployed_checksum = remote_checksum(target, remote_plan)
    if local_checksum != deployed_checksum:
        raise RuntimeError("Deployment finished, but checksums do not match")

    print(f"Deployed {row_count} plan rows to {target}:{remote_plan}")
    print(f"Previous plan backed up as {remote_backup}")
    print(f"SHA-256: {local_checksum}")


def main():
    parser = argparse.ArgumentParser(
        description="Safely deploy plan.csv to the Lifestyle Book server"
    )
    parser.add_argument("plan", nargs="?", type=Path, default=PROJECT_DIR / "plan.csv")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_DIR / "server.local.json",
        help="private server configuration (default: server.local.json)",
    )
    args = parser.parse_args()

    try:
        deploy(args.plan, args.config)
    except (ValueError, OSError, subprocess.CalledProcessError, RuntimeError) as error:
        raise SystemExit(f"Deployment failed: {error}") from None


if __name__ == "__main__":
    main()
