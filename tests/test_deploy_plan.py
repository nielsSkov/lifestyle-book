from pathlib import Path

import pytest

from deploy_plan import validate_plan


def write_plan(tmp_path: Path, content: str):
    path = tmp_path / "plan.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_valid_plan(tmp_path: Path):
    path = write_plan(
        tmp_path,
        "date,weight_kg\n2026-07-25,109.8\n2026-07-26,109.7\n",
    )
    assert validate_plan(path) == 2


def test_rejects_duplicate_or_unsorted_dates(tmp_path: Path):
    path = write_plan(
        tmp_path,
        "date,weight_kg\n2026-07-25,109.8\n2026-07-25,109.7\n",
    )
    with pytest.raises(ValueError, match="unique and increasing"):
        validate_plan(path)


def test_rejects_bad_header(tmp_path: Path):
    path = write_plan(tmp_path, "day,weight\n2026-07-25,109.8\n")
    with pytest.raises(ValueError, match="Expected header"):
        validate_plan(path)
