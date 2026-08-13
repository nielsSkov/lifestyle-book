import hashlib
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path

from weight_data import validate_csv

DEFAULT_PLAN_BACKUP_RETENTION = 30
BACKUP_PREFIX = "plan-auto-"
BACKUP_PATTERN = re.compile(r"^plan-auto-(\d{8}T\d{12}Z)(?:-(\d+))?\.csv$")


@dataclass(frozen=True)
class PlanBackup:
    name: str
    created_at: datetime
    size: int
    revision: str


def list_plan_backups(backup_directory: Path) -> list[PlanBackup]:
    if not backup_directory.exists():
        return []
    backups_by_revision = {}
    for path in backup_directory.iterdir():
        match = BACKUP_PATTERN.fullmatch(path.name)
        if not match or path.is_symlink() or not path.is_file():
            continue
        try:
            contents = path.read_bytes()
            backup = PlanBackup(
                name=path.name,
                created_at=datetime.strptime(match.group(1), "%Y%m%dT%H%M%S%fZ").replace(
                    tzinfo=UTC
                ),
                size=len(contents),
                revision=_plan_revision(contents),
            )
            previous = backups_by_revision.get(backup.revision)
            if previous is None or (backup.created_at, backup.name) > (
                previous.created_at,
                previous.name,
            ):
                backups_by_revision[backup.revision] = backup
        except (FileNotFoundError, ValueError):
            continue
    return sorted(
        backups_by_revision.values(),
        key=lambda backup: (backup.created_at, backup.name),
        reverse=True,
    )


def consolidate_plan_backups(
    backup_directory: Path, *, active_plan_path: Path | None = None
) -> None:
    if not backup_directory.exists():
        return
    _prepare_backup_directory(backup_directory)
    with plan_backup_lock(backup_directory):
        try:
            active_revision = (
                _plan_revision(active_plan_path.read_bytes())
                if active_plan_path is not None
                else None
            )
        except FileNotFoundError:
            active_revision = _plan_revision(b"")
        newest_by_revision = {}
        for path in backup_directory.iterdir():
            if not BACKUP_PATTERN.fullmatch(path.name) or path.is_symlink() or not path.is_file():
                continue
            try:
                revision = _plan_revision(path.read_bytes())
            except FileNotFoundError:
                continue
            if revision == active_revision:
                path.unlink(missing_ok=True)
                continue
            previous = newest_by_revision.get(revision)
            if previous is None or path.name > previous.name:
                if previous is not None:
                    previous.unlink(missing_ok=True)
                newest_by_revision[revision] = path
            else:
                path.unlink(missing_ok=True)
        _sync_directory(backup_directory)


def read_plan_backup(
    backup_directory: Path,
    backup_name: str,
    *,
    expected_revision: str | None = None,
) -> bytes:
    if not BACKUP_PATTERN.fullmatch(backup_name):
        raise ValueError("Choose a valid plan backup")
    source = backup_directory / backup_name
    if source.is_symlink():
        raise ValueError("Choose a valid plan backup")
    try:
        contents = source.read_bytes()
    except FileNotFoundError:
        raise ValueError("That plan backup is no longer available") from None
    validate_csv(source, allow_gaps=True)
    if expected_revision is not None and _plan_revision(contents) != expected_revision:
        raise ValueError("That plan backup changed. Reload the backup history and try again.")
    return contents


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

        destination = _write_backup_bytes(backup_directory, contents, timestamp, validate=True)
        _prune_plan_backups(backup_directory, retention, preserve={destination})
        yield destination


def restore_plan_backup(
    plan_path: Path,
    backup_directory: Path,
    backup_name: str,
    *,
    retention: int = DEFAULT_PLAN_BACKUP_RETENTION,
    expected_revision: str | None = None,
    expected_backup_revision: str | None = None,
) -> Path | None:
    if not BACKUP_PATTERN.fullmatch(backup_name):
        raise ValueError("Choose a valid plan backup")
    _prepare_backup_directory(backup_directory)
    with plan_backup_lock(backup_directory):
        restored_contents = read_plan_backup(
            backup_directory,
            backup_name,
            expected_revision=expected_backup_revision,
        )
        try:
            current_contents = plan_path.read_bytes()
        except FileNotFoundError:
            current_contents = None
        current_revision = _plan_revision(current_contents or b"")
        if expected_revision is not None and current_revision != expected_revision:
            raise ValueError("The active plan changed. Reload the backup history and try again.")
        current_backup = (
            _write_backup_bytes(
                backup_directory, current_contents, datetime.now(UTC), validate=False
            )
            if current_contents is not None
            else None
        )
        _replace_plan_bytes(plan_path, restored_contents)
        try:
            _remove_backups_with_revision(backup_directory, _plan_revision(restored_contents))
            preserved = set()
            if current_backup is not None:
                preserved.add(current_backup)
            _prune_plan_backups(backup_directory, retention, preserve=preserved)
        except OSError:
            # The active plan is already durably restored; consolidation can retry on page load.
            pass
        return current_backup


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


def _write_backup_bytes(
    backup_directory: Path,
    contents: bytes,
    timestamp: datetime,
    *,
    validate: bool,
) -> Path:
    stem = f"{BACKUP_PREFIX}{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}"
    destination = _unused_backup_path(backup_directory, stem)
    temporary = destination.with_suffix(".tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as backup_file:
            backup_file.write(contents)
            backup_file.flush()
            os.fsync(backup_file.fileno())
        if validate:
            validate_csv(temporary, allow_gaps=True)
        os.replace(temporary, destination)
        _sync_directory(backup_directory)
    finally:
        temporary.unlink(missing_ok=True)
    revision = _plan_revision(contents)
    for duplicate in _backup_paths_with_revision(backup_directory, revision):
        if duplicate != destination:
            duplicate.unlink()
    _sync_directory(backup_directory)
    return destination


def _replace_plan_bytes(plan_path: Path, contents: bytes) -> None:
    temporary = plan_path.with_suffix(".restore.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as plan_file:
            plan_file.write(contents)
            plan_file.flush()
            os.fsync(plan_file.fileno())
        validate_csv(temporary, allow_gaps=True)
        os.replace(temporary, plan_path)
        _sync_directory(plan_path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _prune_plan_backups(directory: Path, retention: int, *, preserve: set[Path]) -> None:
    backups = []
    for path in directory.iterdir():
        match = BACKUP_PATTERN.fullmatch(path.name)
        if match and not path.is_symlink() and path.is_file():
            backups.append((match.group(1), int(match.group(2) or 1), path))
    backups.sort(key=lambda backup: (backup[2].stat().st_mtime_ns, backup[0], backup[1]))
    removable = [backup for backup in backups if backup[2] not in preserve]
    excess = max(0, len(backups) - retention)
    for _timestamp, _sequence, obsolete in removable[:excess]:
        obsolete.unlink()
    _sync_directory(directory)


def _backup_paths_with_revision(directory: Path, revision: str) -> list[Path]:
    matches = []
    for path in directory.iterdir():
        if not BACKUP_PATTERN.fullmatch(path.name) or path.is_symlink() or not path.is_file():
            continue
        try:
            if _plan_revision(path.read_bytes()) == revision:
                matches.append(path)
        except FileNotFoundError:
            continue
    return matches


def _remove_backups_with_revision(directory: Path, revision: str) -> None:
    for path in _backup_paths_with_revision(directory, revision):
        path.unlink()
    _sync_directory(directory)


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _plan_revision(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()
