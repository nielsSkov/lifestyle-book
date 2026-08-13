import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from plan_backup import create_plan_backup, protect_plan_update

VALID_PLAN = b"date,weight_kg\n2026-08-01,100\n2026-08-02,NaN\n"


def test_create_plan_backup_preserves_exact_bytes_and_private_permissions(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(VALID_PLAN)
    backup_directory = tmp_path / "backups"

    backup = create_plan_backup(
        plan,
        backup_directory,
        created_at=datetime(2026, 8, 13, 10, 15, 30, 123456, tzinfo=UTC),
    )

    assert backup is not None
    assert backup == backup_directory / "plan-auto-20260813T101530123456Z.csv"
    assert backup.read_bytes() == VALID_PLAN
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup_directory.stat().st_mode) == 0o700
    assert plan.read_bytes() == VALID_PLAN


def test_create_plan_backup_uses_collision_safe_names(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(VALID_PLAN)
    backup_directory = tmp_path / "backups"
    created_at = datetime(2026, 8, 13, tzinfo=UTC)

    first = create_plan_backup(plan, backup_directory, created_at=created_at)
    second = create_plan_backup(plan, backup_directory, created_at=created_at)

    assert first is not None
    assert second is not None
    assert first.name == "plan-auto-20260813T000000000000Z.csv"
    assert second.name == "plan-auto-20260813T000000000000Z-2.csv"


def test_collision_retention_keeps_latest_sequence(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(VALID_PLAN)
    backup_directory = tmp_path / "backups"
    created_at = datetime(2026, 8, 13, tzinfo=UTC)

    create_plan_backup(plan, backup_directory, created_at=created_at, retention=1)
    latest = create_plan_backup(plan, backup_directory, created_at=created_at, retention=1)

    assert latest is not None
    assert latest.exists()
    assert [path.name for path in backup_directory.glob("plan-auto-*.csv")] == [
        "plan-auto-20260813T000000000000Z-2.csv"
    ]


def test_create_plan_backup_retains_only_newest_managed_backups(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(VALID_PLAN)
    backup_directory = tmp_path / "backups"
    backup_directory.mkdir()
    unrelated = backup_directory / "sleep-before-import.csv"
    unrelated.write_text("keep me", encoding="utf-8")
    similar = backup_directory / "plan-auto-notes.csv"
    similar.write_text("keep me too", encoding="utf-8")
    start = datetime(2026, 8, 1, tzinfo=UTC)

    for offset in range(4):
        create_plan_backup(
            plan,
            backup_directory,
            created_at=start + timedelta(days=offset),
            retention=3,
        )

    backups = sorted(
        path
        for path in backup_directory.glob("plan-auto-*.csv")
        if path.name != "plan-auto-notes.csv"
    )
    assert [backup.name for backup in backups] == [
        "plan-auto-20260802T000000000000Z.csv",
        "plan-auto-20260803T000000000000Z.csv",
        "plan-auto-20260804T000000000000Z.csv",
    ]
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert similar.read_text(encoding="utf-8") == "keep me too"


def test_create_plan_backup_returns_none_without_active_plan(tmp_path: Path):
    backup = create_plan_backup(tmp_path / "plan.csv", tmp_path / "backups")

    assert backup is None
    assert not (tmp_path / "backups").exists()


def test_create_plan_backup_rejects_invalid_source_without_leaving_files(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_text("invalid,data\n", encoding="utf-8")
    backup_directory = tmp_path / "backups"

    with pytest.raises(ValueError, match="Expected header"):
        create_plan_backup(plan, backup_directory)

    assert [path.name for path in backup_directory.iterdir()] == [".plan-backup.lock"]


def test_create_plan_backup_rejects_invalid_retention(tmp_path: Path):
    with pytest.raises(ValueError, match="at least 1"):
        create_plan_backup(tmp_path / "plan.csv", tmp_path / "backups", retention=0)


def test_create_plan_backup_rejects_naive_timestamp(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(VALID_PLAN)

    with pytest.raises(ValueError, match="include a timezone"):
        create_plan_backup(
            plan,
            tmp_path / "backups",
            created_at=datetime(2026, 8, 13),
        )


def test_protect_plan_update_keeps_verified_backup_available_during_replacement(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(VALID_PLAN)
    replacement = b"date,weight_kg\n2026-08-01,99\n"

    with protect_plan_update(plan, tmp_path / "backups") as backup:
        assert backup is not None
        assert backup.read_bytes() == VALID_PLAN
        plan.write_bytes(replacement)

    assert backup.read_bytes() == VALID_PLAN
    assert plan.read_bytes() == replacement


def test_retention_preserves_new_backup_with_older_timestamp(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(VALID_PLAN)
    backup_directory = tmp_path / "backups"
    create_plan_backup(
        plan,
        backup_directory,
        created_at=datetime(2026, 8, 13, tzinfo=UTC),
        retention=1,
    )

    latest = create_plan_backup(
        plan,
        backup_directory,
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
        retention=1,
    )

    assert latest is not None
    assert latest.exists()
    assert [path.name for path in backup_directory.glob("plan-auto-*.csv")] == [latest.name]
