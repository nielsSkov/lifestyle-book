import hashlib
import json
import shlex
import subprocess
from pathlib import Path


def load_server_config(path: Path) -> tuple[str, str]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        target = config["target"]
        directory = config["directory"]
    except (OSError, json.JSONDecodeError, KeyError) as error:
        raise ValueError(f"Could not read server config {path}: {error}") from None
    if not isinstance(target, str) or not isinstance(directory, str) or not target or not directory:
        raise ValueError("Server config requires non-empty target and directory strings")
    return target, directory.rstrip("/")


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_checksum(target: str, remote_path: str) -> str:
    result = subprocess.run(
        ["ssh", target, f"sha256sum {shlex.quote(remote_path)}"],
        check=True,
        capture_output=True,
        text=True,
    )
    fields = result.stdout.split()
    if not fields:
        raise RuntimeError(f"Server returned no checksum for {remote_path}")
    return fields[0]
