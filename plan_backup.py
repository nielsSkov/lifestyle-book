import hashlib
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path

from weight_data import validate_csv

DEFAULT_PLAN_BACKUP_RETENTION = 30
BACKUP_PREFIX = "plan-auto-"
BACKUP_PATTERN = re.compile(r"^plan-auto-(\d{8}T\d{12}Z)(?:-(\d+))?\.csv$")


def create_plan_backup(
    plan_path: Path,
    backup_directory: Path,
    *,
    created_at: datetime | None = None,
    retention: int = DEFAULT_PLAN_BACKUP_RETENTION,
) -> Path | None:
    with protect_plan_update(
        plan_path,
        backup_directory,
        created_at=created_at,
        retention=retention,
    ) as backup:
        return backup


@contextmanager
def protect_plan_update(
    plan_path: Path,
    backup_directory: Path,
    *,
    created_at: datetime | None = None,
    retention: int = DEFAULT_PLAN_BACKUP_RETENTION,
    expected_revision: str | None = None,
) -> Iterator[Path | None]:
    if retention < 1:
        raise ValueError("Plan backup retention must be at least 1")
    _prepare_backup_directory(backup_directory)
    with plan_backup_lock(backup_directory):
        timestamp = created_at or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise ValueError("Plan backup timestamp must include a timezone")
        try:
            contents = plan_path.read_bytes()
        except FileNotFoundError:
            if expected_revision not in (None, _plan_revision(b"")):
                raise ValueError(
                    "The active plan changed after this preview. Review it again."
                ) from None
            yield None
            return
        if expected_revision is not None and _plan_revision(contents) != expected_revision:
            raise ValueError("The active plan changed after this preview. Review it again.")

        stem = f"{BACKUP_PREFIX}{timestamp.astimezone(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
        destination = _unused_backup_path(backup_directory, stem)
        temporary = destination.with_suffix(".tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as backup_file:
                backup_file.write(contents)
                backup_file.flush()
                os.fsync(backup_file.fileno())
            validate_csv(temporary, allow_gaps=True)
            os.replace(temporary, destination)
            _sync_directory(backup_directory)
        finally:
            temporary.unlink(missing_ok=True)

        _prune_plan_backups(backup_directory, retention, preserve=destination)
        yield destination


@contextmanager
def plan_backup_lock(directory: Path) -> Iterator[None]:
    lock_path = directory / ".plan-backup.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.chmod(lock_path, 0o600)
        flock(descriptor, LOCK_EX)
        yield
    finally:
        flock(descriptor, LOCK_UN)
        os.close(descriptor)


def _prepare_backup_directory(directory: Path) -> None:
    missing = not directory.exists()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    _sync_directory(directory)
    if missing:
        _sync_directory(directory.parent)


def _unused_backup_path(directory: Path, stem: str) -> Path:
    destination = directory / f"{stem}.csv"
    suffix = 2
    while destination.exists() or destination.with_suffix(".tmp").exists():
        destination = directory / f"{stem}-{suffix}.csv"
        suffix += 1
    return destination


def _prune_plan_backups(directory: Path, retention: int, *, preserve: Path) -> None:
    backups = []
    for path in directory.iterdir():
        match = BACKUP_PATTERN.fullmatch(path.name)
        if match and path.is_file():
            backups.append((match.group(1), int(match.group(2) or 1), path))
    backups.sort(key=lambda backup: (backup[2].stat().st_mtime_ns, backup[0], backup[1]))
    removable = [backup for backup in backups if backup[2] != preserve]
    excess = max(0, len(backups) - retention)
    for _timestamp, _sequence, obsolete in removable[:excess]:
        obsolete.unlink()
    _sync_directory(directory)


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _plan_revision(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()
