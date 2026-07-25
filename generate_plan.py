#!/usr/bin/env python3
import csv
import os
from pathlib import Path

from deploy_plan import validate_plan

PLAN_FILE = Path(__file__).parent / "plan.csv"


def build_plan():
    """Return (date, weight_kg) rows. Add planning logic here."""
    return []


def main():
    rows = build_plan()
    if not rows:
        raise SystemExit(
            "No plan generated. Implement build_plan() first; plan.csv was not changed."
        )

    temporary = PLAN_FILE.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, lineterminator="\n")
            writer.writerow(("date", "weight_kg"))
            writer.writerows(rows)
        validate_plan(temporary)
        os.replace(temporary, PLAN_FILE)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"Generated {len(rows)} rows in {PLAN_FILE}")


if __name__ == "__main__":
    main()
