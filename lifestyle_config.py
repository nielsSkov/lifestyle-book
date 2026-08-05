import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RECORD_SUBTITLE = "Everyday log"


@dataclass(frozen=True)
class LifestyleSettings:
    name: str | None = None
    active_achievements: tuple[str, ...] | None = None

    @property
    def record_subtitle(self) -> str:
        if self.name is None:
            return DEFAULT_RECORD_SUBTITLE
        possessive = f"{self.name}'" if self.name.lower().endswith("s") else f"{self.name}'s"
        return f"{possessive} log"


def load_lifestyle_settings(path: Path) -> LifestyleSettings:
    if not path.exists():
        return LifestyleSettings()

    try:
        configuration = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Lifestyle configuration contains invalid JSON") from error
    if not isinstance(configuration, dict):
        raise ValueError("Lifestyle configuration must be a JSON object")
    if set(configuration) - {"name", "active_achievements"}:
        raise ValueError("Lifestyle configuration contains an unknown setting")

    name = _parse_name(configuration.get("name"))
    active = _parse_active_achievements(configuration.get("active_achievements"))
    return LifestyleSettings(name, active)


def _parse_name(value: object) -> str | None:
    name = value
    if name is not None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Lifestyle name must be a non-empty string")
        name = name.strip()
        if len(name) > 80:
            raise ValueError("Lifestyle name must be 80 characters or fewer")

    return name


def _parse_active_achievements(value: object) -> tuple[str, ...] | None:
    active = value
    if active is not None:
        if not isinstance(active, list) or any(not isinstance(key, str) for key in active):
            raise ValueError("Active achievements must be a list of names")
        if len(active) != len(set(active)):
            raise ValueError("Active achievements must be unique")
    return tuple(active) if active is not None else None


def store_lifestyle_settings(path: Path, settings: LifestyleSettings) -> None:
    configuration: dict[str, object] = {}
    if settings.name is not None:
        configuration["name"] = settings.name
    if settings.active_achievements is not None:
        configuration["active_achievements"] = list(settings.active_achievements)

    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as config_file:
            json.dump(configuration, config_file, indent=2)
            config_file.write("\n")
            config_file.flush()
            os.fsync(config_file.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
