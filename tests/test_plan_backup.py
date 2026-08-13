import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from plan_backup import (
    consolidate_plan_backups,
    create_plan_backup,
    list_plan_backups,
    protect_plan_update,
    restore_plan_backup,
)

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
    assert [backup.name for backup in backups] == ["plan-auto-20260804T000000000000Z.csv"]
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert similar.read_text(encoding="utf-8") == "keep me too"


def test_create_plan_backup_returns_none_without_active_plan(tmp_path: Path):
    backup = create_plan_backup(tmp_path / "plan.csv", tmp_path / "backups")

    assert backup is None
    assert not list((tmp_path / "backups").glob("plan-auto-*.csv"))


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


def test_list_plan_backups_returns_newest_managed_files_only(tmp_path: Path):
    directory = tmp_path / "backups"
    directory.mkdir()
    older = directory / "plan-auto-20260812T100000000000Z.csv"
    newer = directory / "plan-auto-20260813T100000000000Z.csv"
    older.write_bytes(VALID_PLAN)
    newer.write_bytes(VALID_PLAN + b"2026-08-03,99\n")
    (directory / "plan-manual.csv").write_bytes(VALID_PLAN)

    backups = list_plan_backups(directory)

    assert [backup.name for backup in backups] == [newer.name, older.name]
    assert backups[0].created_at == datetime(2026, 8, 13, 10, tzinfo=UTC)
    assert backups[0].size == newer.stat().st_size


def test_list_plan_backups_collapses_duplicate_content_to_latest_file(tmp_path: Path):
    directory = tmp_path / "backups"
    directory.mkdir()
    older = directory / "plan-auto-20260812T100000000000Z.csv"
    newer = directory / "plan-auto-20260813T100000000000Z.csv"
    older.write_bytes(VALID_PLAN)
    newer.write_bytes(VALID_PLAN)

    backups = list_plan_backups(directory)

    assert [backup.name for backup in backups] == [newer.name]


def test_consolidate_plan_backups_removes_older_duplicate_files(tmp_path: Path):
    directory = tmp_path / "backups"
    directory.mkdir()
    older = directory / "plan-auto-20260812T100000000000Z.csv"
    newer = directory / "plan-auto-20260813T100000000000Z.csv"
    distinct = directory / "plan-auto-20260814T100000000000Z.csv"
    older.write_bytes(VALID_PLAN)
    newer.write_bytes(VALID_PLAN)
    distinct.write_bytes(b"date,weight_kg\n2026-08-01,90\n")

    consolidate_plan_backups(directory)

    assert not older.exists()
    assert newer.exists()
    assert distinct.exists()


def test_consolidate_plan_backups_removes_active_plan_copy(tmp_path: Path):
    directory = tmp_path / "backups"
    directory.mkdir()
    active_copy = directory / "plan-auto-20260813T100000000000Z.csv"
    alternative = directory / "plan-auto-20260814T100000000000Z.csv"
    active_copy.write_bytes(VALID_PLAN)
    alternative.write_bytes(b"date,weight_kg\n2026-08-01,90\n")
    active_plan = tmp_path / "plan.csv"
    active_plan.write_bytes(VALID_PLAN)

    consolidate_plan_backups(
        directory,
        active_plan_path=active_plan,
    )

    assert not active_copy.exists()
    assert alternative.exists()


def test_restore_plan_backup_saves_current_plan_and_restores_exact_bytes(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    current = b"date,weight_kg\n2026-08-01,90\n"
    plan.write_bytes(current)
    directory = tmp_path / "backups"
    directory.mkdir()
    source = directory / "plan-auto-20260812T100000000000Z.csv"
    source.write_bytes(VALID_PLAN)

    current_backup = restore_plan_backup(plan, directory, source.name)

    assert plan.read_bytes() == VALID_PLAN
    assert current_backup is not None
    assert current_backup.read_bytes() == current
    assert stat.S_IMODE(plan.stat().st_mode) == 0o600
    assert not source.exists()


def test_restore_plan_backup_rejects_unmanaged_or_missing_name(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(VALID_PLAN)
    directory = tmp_path / "backups"

    with pytest.raises(ValueError, match="valid plan backup"):
        restore_plan_backup(plan, directory, "../plan.csv")
    with pytest.raises(ValueError, match="no longer available"):
        restore_plan_backup(plan, directory, "plan-auto-20260812T100000000000Z.csv")


def test_restore_plan_backup_allows_recovery_from_invalid_current_plan(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    damaged = b"damaged current plan\n"
    plan.write_bytes(damaged)
    directory = tmp_path / "backups"
    directory.mkdir()
    source = directory / "plan-auto-20260812T100000000000Z.csv"
    source.write_bytes(VALID_PLAN)

    damaged_backup = restore_plan_backup(plan, directory, source.name)

    assert plan.read_bytes() == VALID_PLAN
    assert damaged_backup is not None
    assert damaged_backup.read_bytes() == damaged


def test_restore_at_retention_limit_preserves_selected_source(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(b"date,weight_kg\n2026-08-01,90\n")
    directory = tmp_path / "backups"
    directory.mkdir()
    sources = []
    for day in range(1, 4):
        source = directory / f"plan-auto-2026080{day}T100000000000Z.csv"
        source.write_bytes(VALID_PLAN)
        sources.append(source)

    restore_plan_backup(plan, directory, sources[0].name, retention=3)

    assert not sources[0].exists()
    assert plan.read_bytes() == VALID_PLAN
    remaining = list(directory.glob("plan-auto-*.csv"))
    assert len(remaining) == 1
    assert remaining[0].read_bytes() == b"date,weight_kg\n2026-08-01,90\n"


def test_restore_rejects_changed_active_plan_before_creating_backup(tmp_path: Path):
    plan = tmp_path / "plan.csv"
    plan.write_bytes(b"date,weight_kg\n2026-08-01,90\n")
    directory = tmp_path / "backups"
    directory.mkdir()
    source = directory / "plan-auto-20260812T100000000000Z.csv"
    source.write_bytes(VALID_PLAN)

    with pytest.raises(ValueError, match="active plan changed"):
        restore_plan_backup(plan, directory, source.name, expected_revision="stale")

    assert list(directory.glob("plan-auto-*.csv")) == [source]
