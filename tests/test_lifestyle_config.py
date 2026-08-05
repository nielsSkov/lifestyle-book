import stat
from pathlib import Path

import pytest

from lifestyle_config import (
    DEFAULT_RECORD_SUBTITLE,
    LifestyleSettings,
    load_lifestyle_settings,
    store_lifestyle_settings,
)


def test_missing_configuration_uses_public_defaults(tmp_path: Path):
    settings = load_lifestyle_settings(tmp_path / "lifestyle.local.json")

    assert settings == LifestyleSettings()
    assert settings.record_subtitle == DEFAULT_RECORD_SUBTITLE


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Niels", "Niels' log"), ("Alex", "Alex's log")],
)
def test_name_builds_personal_log_subtitle(tmp_path: Path, name: str, expected: str):
    path = tmp_path / "lifestyle.local.json"
    path.write_text(f'{{"name": "{name}"}}', encoding="utf-8")

    assert load_lifestyle_settings(path).record_subtitle == expected


def test_active_achievements_are_loaded_in_configured_order(tmp_path: Path):
    path = tmp_path / "lifestyle.local.json"
    path.write_text(
        '{"name": "Alex", "active_achievements": ["walk", "roller_skate"]}',
        encoding="utf-8",
    )

    assert load_lifestyle_settings(path) == LifestyleSettings("Alex", ("walk", "roller_skate"))


def test_store_lifestyle_settings_atomically_writes_private_file(tmp_path: Path):
    path = tmp_path / "lifestyle.local.json"
    settings = LifestyleSettings("Niels", ("walk", "cooked"))

    store_lifestyle_settings(path, settings)

    assert load_lifestyle_settings(path) == settings
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.read_text(encoding="utf-8") == (
        '{\n  "name": "Niels",\n  "active_achievements": [\n    "walk",\n    "cooked"\n  ]\n}\n'
    )


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        "not json",
        '{"name": ""}',
        '{"subtitle": "Personal"}',
        '{"active_achievements": "walk"}',
        '{"active_achievements": ["walk", "walk"]}',
    ],
)
def test_invalid_configuration_is_rejected(tmp_path: Path, content: str):
    path = tmp_path / "lifestyle.local.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):  # noqa: PT011 - every invalid configuration is rejected
        load_lifestyle_settings(path)
