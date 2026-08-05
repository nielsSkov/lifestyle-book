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
    DailyCategory("walk", "Walk", "movement", "#78b68b", "#3b5745", "#5a8768", "walk"),
    DailyCategory("run", "Run", "movement", "#dc786f", "#68413f", "#a25d57", "run"),
    DailyCategory("swim", "Swim", "movement", "#61a9c4", "#34505d", "#4b7d91", "swim"),
    DailyCategory("dance", "Dance", "movement", "#b77bc9", "#563d60", "#875c95", "dance"),
    DailyCategory("cycling", "Bike", "movement", "#d0a64f", "#62522d", "#997c3e", "cycling"),
    DailyCategory(
        "low_sugar",
        "Low Sugar",
        "food",
        "#8fb76f",
        "#465a35",
        "#6b8952",
        "low-sugar",
    ),
    DailyCategory("cooked", "Cooked", "food", "#cf865f", "#604137", "#98644b", "cooked"),
)


def active_categories() -> tuple[DailyCategory, ...]:
    return tuple(category for category in DAILY_CATEGORIES if category.active)
