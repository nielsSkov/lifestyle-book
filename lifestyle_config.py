import json
from pathlib import Path

DEFAULT_RECORD_SUBTITLE = "Everyday Record"


def load_record_subtitle(path: Path) -> str:
    if not path.exists():
        return DEFAULT_RECORD_SUBTITLE

    try:
        configuration = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Lifestyle configuration contains invalid JSON") from error
    if not isinstance(configuration, dict):
        raise ValueError("Lifestyle configuration must be a JSON object")
    if set(configuration) - {"name"}:
        raise ValueError("Lifestyle configuration contains an unknown setting")

    name = configuration.get("name")
    if name is None:
        return DEFAULT_RECORD_SUBTITLE
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Lifestyle name must be a non-empty string")

    name = name.strip()
    possessive = f"{name}'" if name.lower().endswith("s") else f"{name}'s"
    return f"{possessive} Record"
