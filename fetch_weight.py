#!/usr/bin/env python3
import argparse
import os
import subprocess
from pathlib import Path

from server_sync import file_checksum, load_server_config, remote_checksum
from weight_data import validate_csv

PROJECT_DIR = Path(__file__).parent


def install_download(download: Path, destination: Path, expected_checksum: str) -> int:
    row_count = validate_csv(download)
    actual_checksum = file_checksum(download)
    if actual_checksum != expected_checksum:
        raise RuntimeError("Downloaded weight data does not match the server checksum")

    destination.parent.mkdir(parents=True, exist_ok=True)
    download.chmod(0o600)
    os.replace(download, destination)
    return row_count


def fetch_weight(destination: Path, config_path: Path) -> tuple[int, str]:
    target, directory = load_server_config(config_path)
    remote_weight = f"{directory}/weight.csv"
    temporary = destination.with_name(f".{destination.name}.download")

    try:
        subprocess.run(["scp", f"{target}:{remote_weight}", str(temporary)], check=True)
        checksum = remote_checksum(target, remote_weight)
        row_count = install_download(temporary, destination, checksum)
    finally:
        temporary.unlink(missing_ok=True)

    return row_count, checksum


def main():
    parser = argparse.ArgumentParser(description="Safely retrieve weight.csv from the server")
    parser.add_argument("destination", nargs="?", type=Path, default=PROJECT_DIR / "weight.csv")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_DIR / "server.local.json",
        help="private server configuration (default: server.local.json)",
    )
    args = parser.parse_args()

    try:
        row_count, checksum = fetch_weight(args.destination, args.config)
    except (ValueError, OSError, subprocess.CalledProcessError, RuntimeError) as error:
        raise SystemExit(f"Fetch failed: {error}") from None

    print(f"Retrieved {row_count} weight rows into {args.destination}")
    print(f"SHA-256: {checksum}")


if __name__ == "__main__":
    main()
