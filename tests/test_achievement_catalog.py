import pytest

from achievement_catalog import active_categories


def test_default_categories_do_not_include_roller_skate():
    keys = {category.key for category in active_categories()}

    assert "roller_skate" not in keys
    assert "other_activity" in keys


def test_configured_categories_follow_catalog_order():
    categories = active_categories(["cooked", "roller_skate", "walk"])

    assert [category.key for category in categories] == ["walk", "roller_skate", "cooked"]


def test_configured_categories_reject_unknown_keys():
    with pytest.raises(ValueError, match="Unknown"):
        active_categories(["walk", "unknown"])
