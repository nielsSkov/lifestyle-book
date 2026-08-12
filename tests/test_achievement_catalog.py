import pytest

from achievement_catalog import configured_achievements


def test_default_achievements_do_not_include_roller_skate():
    keys = {achievement.key for achievement in configured_achievements()}

    assert "roller_skate" not in keys
    assert "other_activity" in keys
    assert "yoga" in keys


def test_configured_achievements_follow_catalog_order():
    achievements = configured_achievements(["cooked", "roller_skate", "yoga", "walk"])

    assert [achievement.key for achievement in achievements] == [
        "walk",
        "yoga",
        "roller_skate",
        "cooked",
    ]


def test_configured_achievements_reject_unknown_keys():
    with pytest.raises(ValueError, match="Unknown"):
        configured_achievements(["walk", "unknown"])
