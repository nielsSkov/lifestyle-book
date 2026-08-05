from pathlib import Path

import pytest

from lifestyle_config import DEFAULT_RECORD_SUBTITLE, load_record_subtitle


def test_missing_configuration_uses_public_default(tmp_path: Path):
    assert load_record_subtitle(tmp_path / "lifestyle.local.json") == DEFAULT_RECORD_SUBTITLE


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Niels", "Niels' Record"), ("Alex", "Alex's Record")],
)
def test_name_builds_personal_record_subtitle(tmp_path: Path, name: str, expected: str):
    path = tmp_path / "lifestyle.local.json"
    path.write_text(f'{{"name": "{name}"}}', encoding="utf-8")

    assert load_record_subtitle(path) == expected


@pytest.mark.parametrize(
    "content",
    ["[]", "not json", '{"name": ""}', '{"subtitle": "Personal"}'],
)
def test_invalid_configuration_is_rejected(tmp_path: Path, content: str):
    path = tmp_path / "lifestyle.local.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):  # noqa: PT011 - every invalid configuration is rejected
        load_record_subtitle(path)
