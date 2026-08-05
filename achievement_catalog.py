from collections.abc import Collection
from dataclasses import dataclass


@dataclass(frozen=True)
class DailyCategory:
    key: str
    label: str
    group: str
    colour: str
    selected_colour: str
    tile_colour: str
    icon: str
    active: bool = True


DAILY_CATEGORIES = (
    DailyCategory("walk", "Walk", "movement", "#78b68b", "#3b5745", "#3f8659", "walk"),
    DailyCategory("run", "Run", "movement", "#dc786f", "#68413f", "#a94f4a", "run"),
    DailyCategory("swim", "Swim", "movement", "#61a9c4", "#34505d", "#377992", "swim"),
    DailyCategory("dance", "Dance", "movement", "#b77bc9", "#563d60", "#7e4695", "dance"),
    DailyCategory("cycling", "Bike", "movement", "#d0a64f", "#62522d", "#927126", "cycling"),
    DailyCategory(
        "roller_skate",
        "Roller Skate",
        "movement",
        "#67b4a5",
        "#345a52",
        "#3b8176",
        "roller-skate",
        active=False,
    ),
    DailyCategory(
        "other_activity",
        "Other Activity",
        "movement",
        "#9b86cb",
        "#4c4064",
        "#7054a3",
        "other-activity",
    ),
    DailyCategory(
        "low_sugar",
        "Low Sugar",
        "food",
        "#8fb76f",
        "#465a35",
        "#5d8339",
        "low-sugar",
    ),
    DailyCategory("cooked", "Cooked", "food", "#cf865f", "#604137", "#98513a", "cooked"),
)


def active_categories(selected_keys: Collection[str] | None = None) -> tuple[DailyCategory, ...]:
    if selected_keys is None:
        return tuple(category for category in DAILY_CATEGORIES if category.active)

    selected = set(selected_keys)
    known = {category.key for category in DAILY_CATEGORIES}
    if selected - known:
        raise ValueError("Unknown achievement selected")
    return tuple(category for category in DAILY_CATEGORIES if category.key in selected)
