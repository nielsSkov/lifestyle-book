from dataclasses import dataclass


@dataclass(frozen=True)
class DailyCategory:
    key: str
    label: str
    group: str
    colour: str
    selected_colour: str
    icon: str
    active: bool = True


DAILY_CATEGORIES = (
    DailyCategory("walk", "Walk", "movement", "#78b68b", "#3b5745", "walk"),
    DailyCategory("run", "Run", "movement", "#dc786f", "#68413f", "run"),
    DailyCategory("swim", "Swim", "movement", "#61a9c4", "#34505d", "swim"),
    DailyCategory("dance", "Dance", "movement", "#b77bc9", "#563d60", "dance"),
    DailyCategory("cycling", "Bike", "movement", "#d0a64f", "#62522d", "cycling"),
    DailyCategory("low_sugar", "Low Sugar", "food", "#8fb76f", "#465a35", "low-sugar"),
    DailyCategory("cooked", "Cooked", "food", "#cf865f", "#604137", "cooked"),
)


def active_categories() -> tuple[DailyCategory, ...]:
    return tuple(category for category in DAILY_CATEGORIES if category.active)
