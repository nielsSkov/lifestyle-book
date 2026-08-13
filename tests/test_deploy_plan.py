import subprocess
from pathlib import Path

from deploy_plan import deploy


def test_deploy_plan_uses_shared_backup_lock(tmp_path: Path, monkeypatch):
    plan = tmp_path / "plan.csv"
    plan.write_text("date,weight_kg\n2026-08-01,100\n", encoding="utf-8")
    commands = []

    monkeypatch.setattr("deploy_plan.load_server_config", lambda _path: ("host", "/app"))
    monkeypatch.setattr("deploy_plan.file_checksum", lambda _path: "checksum")
    monkeypatch.setattr("deploy_plan.remote_checksum", lambda _target, _path: "checksum")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, check: commands.append(command),
    )

    deploy(plan, tmp_path / "server.local.json")

    remote_command = commands[1][2]
    assert "flock /app/backups/.plan-backup.lock sh -c" in remote_command
    assert "mv /app/.plan-" in remote_command
    assert ".csv.upload /app/plan.csv" in remote_command
    assert commands[0][0] == "scp"
    assert commands[0][2].startswith("host:/app/.plan-")
